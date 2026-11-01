import asyncio
import hashlib
import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import razorpay
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.payment_attempt import PaymentAttempt, RazorpayWebhookEvent
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.profile_repository import ProfileRepository


logger = logging.getLogger(__name__)


class PaymentService:
    CURRENCY = "INR"

    @staticmethod
    def is_test_configuration_ready() -> bool:
        return bool(
            settings.RAZORPAY_MODE.strip().lower() == "test"
            and settings.RAZORPAY_KEY_ID.startswith("rzp_test_")
            and settings.RAZORPAY_KEY_SECRET
            and settings.RAZORPAY_WEBHOOK_SECRET
            and settings.APPOINTMENT_BILLING_CURRENCY.strip().upper() == PaymentService.CURRENCY
        )

    @staticmethod
    def readiness() -> dict:
        return {
            "available": PaymentService.is_test_configuration_ready(),
            "mode": "test",
            "currency": PaymentService.CURRENCY if settings.APPOINTMENT_BILLING_CURRENCY.strip().upper() == PaymentService.CURRENCY else None,
        }

    @staticmethod
    def amount_to_paise(amount) -> int:
        try:
            rupees = Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="Appointment amount is invalid") from exc
        if not rupees.is_finite() or rupees <= 0 or rupees.as_tuple().exponent < -2:
            raise HTTPException(status_code=422, detail="Appointment amount must be positive and use at most two decimal places")
        return int(rupees * 100)

    @staticmethod
    def _require_test_configuration() -> None:
        if not PaymentService.is_test_configuration_ready():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Razorpay Test Mode is not fully configured",
            )

    @staticmethod
    def _client():
        return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    @staticmethod
    async def _get_owned_appointment(appointment_id: str, user_id: str) -> Appointment:
        appointment = await AppointmentRepository.get_by_id(appointment_id)
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not appointment or not patient or str(appointment.patient_id) != str(patient.id):
            # Avoid revealing whether another patient's appointment exists.
            raise HTTPException(status_code=404, detail="Appointment not found")
        if appointment.service_mode != "clinic":
            raise HTTPException(status_code=409, detail="Online payment is currently available for clinic appointments only")
        return appointment

    @staticmethod
    async def _update_appointment(appointment_id, fields: dict, only_if_unpaid: bool = False):
        query = {"_id": appointment_id}
        if only_if_unpaid:
            query["billing_status"] = {"$ne": "paid"}
        return await Appointment.get_pymongo_collection().update_one(query, {"$set": fields})

    @staticmethod
    async def _attach_order_to_scheduled_appointment(appointment: Appointment, order_id: str) -> bool:
        result = await Appointment.get_pymongo_collection().update_one(
            {
                "_id": appointment.id,
                "status": "scheduled",
                "billing_status": {"$ne": "paid"},
                "$or": [
                    {"payment_order_id": order_id},
                    {"payment_order_id": None},
                ],
            },
            {
                "$set": {
                    "billing_currency": PaymentService.CURRENCY,
                    "payment_status": "pending",
                    "payment_order_id": order_id,
                }
            },
        )
        return bool(result.matched_count)

    @staticmethod
    async def _persist_attempt_status(attempt, next_status: str, payment_id: str | None = None, event_id: str | None = None) -> str:
        query = {"_id": attempt.id}
        if next_status != "success":
            query["status"] = {"$ne": "success"}
        fields = {"status": next_status, "updated_at": datetime.now(timezone.utc)}
        if payment_id:
            fields["provider_payment_id"] = payment_id
        update = {"$set": fields}
        if event_id:
            update["$addToSet"] = {"processed_event_ids": event_id}
        result = await PaymentAttempt.get_pymongo_collection().update_one(query, update)
        if result.matched_count == 0:
            existing = await PaymentAttempt.find_one({"_id": attempt.id})
            persisted_status = existing.status if existing else attempt.status
            attempt.status = persisted_status
            return persisted_status
        attempt.status = next_status
        attempt.updated_at = fields["updated_at"]
        if payment_id:
            attempt.provider_payment_id = payment_id
        if event_id and event_id not in attempt.processed_event_ids:
            attempt.processed_event_ids.append(event_id)
        return next_status

    @staticmethod
    async def create_order(appointment_id: str, user_id: str) -> dict:
        PaymentService._require_test_configuration()
        appointment = await PaymentService._get_owned_appointment(appointment_id, user_id)
        if appointment.status != "scheduled":
            raise HTTPException(status_code=409, detail="Only scheduled appointments can be paid")
        if appointment.billing_status == "paid":
            raise HTTPException(status_code=409, detail="This appointment is already paid")

        amount_paise = PaymentService.amount_to_paise(appointment.billing_amount)
        if appointment.billing_currency not in {None, PaymentService.CURRENCY}:
            raise HTTPException(status_code=409, detail="Appointment currency is not supported for checkout")

        attempt = await PaymentAttempt.find_one({"appointment_id": appointment.id})
        if attempt and attempt.provider_order_id:
            if attempt.status == "success":
                payment_state = await PaymentService._record_captured_payment(
                    attempt, attempt.provider_payment_id
                )
                if payment_state == "success":
                    raise HTTPException(status_code=409, detail="This appointment is already paid")
                raise HTTPException(
                    status_code=409,
                    detail="A captured payment needs clinic reconciliation; another checkout cannot be started.",
                )
            else:
                persisted_status = await PaymentService._persist_attempt_status(attempt, "pending")
                if persisted_status == "success":
                    payment_state = await PaymentService._record_captured_payment(
                        attempt, attempt.provider_payment_id
                    )
                    if payment_state == "success":
                        raise HTTPException(status_code=409, detail="This appointment is already paid")
                    raise HTTPException(
                        status_code=409,
                        detail="A captured payment needs clinic reconciliation; another checkout cannot be started.",
                    )
                if not await PaymentService._attach_order_to_scheduled_appointment(
                    appointment, attempt.provider_order_id
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="The appointment changed before checkout could start. The existing provider order was not returned.",
                    )
            return PaymentService._order_response(attempt)
        if attempt:
            if attempt.status != "failed" or attempt.provider_payment_id:
                # A previous process may have created a provider order and stopped before
                # saving its ID. Refuse another order rather than risk a duplicate charge.
                raise HTTPException(status_code=409, detail="Payment setup is still being reconciled. Please retry shortly or contact the clinic.")
            # Provider order creation failed before an order ID existed. Reuse the
            # appointment's single attempt record for a safe retry.
            attempt.status = "creating"
            attempt.amount_paise = amount_paise
            attempt.currency = PaymentService.CURRENCY
            attempt.updated_at = datetime.now(timezone.utc)
            await attempt.save()

        else:
            attempt = PaymentAttempt(
                appointment_id=appointment.id,
                patient_id=appointment.patient_id,
                amount_paise=amount_paise,
                currency=PaymentService.CURRENCY,
                status="creating",
            )
            try:
                await attempt.insert()
            except DuplicateKeyError:
                existing = await PaymentAttempt.find_one({"appointment_id": appointment.id})
                if existing and existing.provider_order_id and existing.status != "success":
                    if not await PaymentService._attach_order_to_scheduled_appointment(
                        appointment, existing.provider_order_id
                    ):
                        raise HTTPException(
                            status_code=409,
                            detail="The appointment changed before checkout could start. The existing provider order was not returned.",
                        )
                    return PaymentService._order_response(existing)
                raise HTTPException(status_code=409, detail="Payment setup is already in progress")

        try:
            provider_order = await asyncio.to_thread(
                PaymentService._client().order.create,
                {
                    "amount": amount_paise,
                    "currency": PaymentService.CURRENCY,
                    "receipt": f"pc-{str(appointment.id)}"[:40],
                    "notes": {"appointment_id": str(appointment.id)},
                },
            )
            if (
                provider_order.get("amount") != amount_paise
                or provider_order.get("currency") != PaymentService.CURRENCY
                or not provider_order.get("id")
            ):
                raise ValueError("Provider order did not match the server amount")
        except Exception as exc:
            attempt.status = "failed"
            attempt.updated_at = datetime.now(timezone.utc)
            await attempt.save()
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=502, detail="Payment provider could not create an order") from exc

        attempt.provider_order_id = provider_order["id"]
        attempt.status = "pending"
        attempt.updated_at = datetime.now(timezone.utc)
        await attempt.save()
        if not await PaymentService._attach_order_to_scheduled_appointment(
            appointment, provider_order["id"]
        ):
            raise HTTPException(
                status_code=409,
                detail="The appointment changed while payment setup was in progress. The provider order was recorded, but no checkout was issued.",
            )
        return PaymentService._order_response(attempt)

    @staticmethod
    def _order_response(attempt: PaymentAttempt) -> dict:
        return {
            "appointment_id": str(attempt.appointment_id),
            "order_id": attempt.provider_order_id,
            "amount": attempt.amount_paise,
            "currency": attempt.currency,
            "key_id": settings.RAZORPAY_KEY_ID,
            "status": attempt.status,
        }

    @staticmethod
    async def _verify_provider_payment(order_id: str, payment_id: str) -> dict:
        try:
            payment = await asyncio.to_thread(PaymentService._client().payment.fetch, payment_id)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Payment status could not be verified with the provider") from exc
        if payment.get("order_id") != order_id:
            raise HTTPException(status_code=400, detail="Payment does not belong to this order")
        return payment

    @staticmethod
    async def _record_captured_payment(attempt: PaymentAttempt, payment_id: str | None) -> str:
        """Finalize a provider capture only if cancellation has not won the race.

        PaymentAttempt records the trusted provider capture. The appointment is
        the authoritative booking/payment state and is transitioned atomically.
        """
        if not payment_id:
            raise HTTPException(status_code=400, detail="Captured payment is missing its provider payment ID")
        collection = Appointment.get_pymongo_collection()
        appointment_id = attempt.appointment_id
        payment_fields = {
            "billing_status": "paid",
            "billing_currency": attempt.currency,
            "payment_status": "success",
            "payment_order_id": attempt.provider_order_id,
            "payment_id": payment_id,
        }
        result = await collection.update_one(
            {
                "_id": appointment_id,
                "patient_id": attempt.patient_id,
                "status": {"$ne": "cancelled"},
                "$or": [
                    {"payment_order_id": attempt.provider_order_id},
                    {"payment_order_id": None},
                ],
                "$and": [
                    {
                        "$or": [
                            {"billing_status": {"$ne": "paid"}},
                            {
                                "billing_status": "paid",
                                "payment_id": payment_id,
                                "payment_order_id": attempt.provider_order_id,
                            },
                        ]
                    },
                    {
                        "$or": [
                            {"payment_id": None},
                            {"payment_id": payment_id},
                        ]
                    },
                ],
            },
            {"$set": payment_fields},
        )
        if result.matched_count:
            return "success"

        # Cancellation or a conflicting payment state won. Keep the cancelled
        # status and make the captured money visible for manual reconciliation.
        await collection.update_one(
            {
                "_id": appointment_id,
                "patient_id": attempt.patient_id,
                "status": "cancelled",
                "$or": [
                    {"payment_order_id": attempt.provider_order_id},
                    {"payment_order_id": None},
                ],
                "$and": [
                    {
                        "$or": [
                            {"payment_id": None},
                            {"payment_id": payment_id},
                        ]
                    }
                ],
            },
            {
                "$set": {
                    "payment_status": "reconciliation_required",
                    "payment_order_id": attempt.provider_order_id,
                    "payment_id": payment_id,
                    "billing_currency": attempt.currency,
                }
            },
        )
        appointment = await AppointmentRepository.get_by_id(str(appointment_id))
        if appointment and appointment.status == "cancelled":
            if (
                appointment.payment_status == "reconciliation_required"
                and appointment.payment_order_id == attempt.provider_order_id
                and appointment.payment_id == payment_id
            ):
                return "reconciliation_required"
            raise HTTPException(status_code=409, detail="Captured payment conflicts with the cancelled appointment state")
        if (
            appointment
            and appointment.billing_status == "paid"
            and appointment.payment_order_id == attempt.provider_order_id
            and appointment.payment_id == payment_id
        ):
            return "success"
        raise HTTPException(status_code=409, detail="Captured payment requires appointment reconciliation")

    @staticmethod
    def _capture_is_reflected(attempt: PaymentAttempt, appointment) -> bool:
        if not appointment or not attempt.provider_payment_id or not attempt.provider_order_id:
            return False
        if appointment.status == "cancelled":
            return (
                appointment.payment_status == "reconciliation_required"
                and appointment.payment_order_id == attempt.provider_order_id
                and appointment.payment_id == attempt.provider_payment_id
            )
        return (
            appointment.billing_status == "paid"
            and appointment.payment_status == "success"
            and appointment.payment_order_id == attempt.provider_order_id
            and appointment.payment_id == attempt.provider_payment_id
        )

    @staticmethod
    async def _set_reconciliation_status(attempt: PaymentAttempt, next_status: str) -> bool:
        now = datetime.now(timezone.utc)
        eligible_states = [
            {"reconciliation_status": "pending"},
            {"reconciliation_status": {"$exists": False}},
            {"reconciliation_status": "clinic_review"},
        ]
        result = await PaymentAttempt.get_pymongo_collection().update_one(
            {
                "_id": attempt.id,
                "status": "success",
                "provider_order_id": attempt.provider_order_id,
                "provider_payment_id": attempt.provider_payment_id,
                "$or": eligible_states,
            },
            {"$set": {"reconciliation_status": next_status, "reconciliation_checked_at": now}},
        )
        if result.matched_count:
            attempt.reconciliation_status = next_status
            attempt.reconciliation_checked_at = now
        return bool(result.matched_count)

    @staticmethod
    def _reconciliation_issue(attempt: PaymentAttempt, appointment, reason: str) -> dict:
        return {
            "appointment_id": str(attempt.appointment_id),
            "amount_paise": attempt.amount_paise,
            "currency": attempt.currency,
            "appointment_status": getattr(appointment, "status", None),
            "payment_status": getattr(appointment, "payment_status", None),
            "reason": reason,
        }

    @staticmethod
    async def list_captured_payment_reviews(batch_size: int | None = None) -> dict:
        batch_size = batch_size or settings.PAYMENT_RECONCILIATION_BATCH_SIZE
        attempts = await (
            PaymentAttempt.find({"status": "success", "reconciliation_status": "clinic_review"})
            .sort("updated_at")
            .limit(batch_size)
            .to_list()
        )
        clinic_review = []
        for attempt in attempts:
            appointment = await AppointmentRepository.get_by_id(str(attempt.appointment_id))
            if not attempt.provider_payment_id or not attempt.provider_order_id:
                reason = "Captured attempt is missing its provider identifiers."
            elif not appointment:
                reason = "The appointment linked to this capture could not be found."
            elif appointment.patient_id != attempt.patient_id:
                reason = "The captured attempt does not match the appointment owner."
            elif appointment.status == "cancelled":
                reason = "Captured funds for this cancelled appointment require clinic reconciliation."
            else:
                reason = "The appointment has a newer or conflicting payment state."
            clinic_review.append(PaymentService._reconciliation_issue(attempt, appointment, reason))
        return {"clinic_review": clinic_review}

    @staticmethod
    async def reconcile_captured_payments(
        batch_size: int | None = None,
        include_clinic_review: bool = True,
        should_continue: Callable[[], bool] | None = None,
    ) -> dict:
        """Idempotently reflect trusted provider captures on their appointments.

        A capture is trusted here only because the attempt was marked successful
        after provider-side capture verification. This administrative operation
        never accepts client-supplied payment status or identifiers.
        """
        batch_size = batch_size or settings.PAYMENT_RECONCILIATION_BATCH_SIZE
        states = [
            {"reconciliation_status": "pending"},
            {"reconciliation_status": {"$exists": False}},
        ]
        if include_clinic_review:
            states.append({"reconciliation_status": "clinic_review"})
        attempts = await (
            PaymentAttempt.find({"status": "success", "$or": states})
            .sort("updated_at")
            .limit(batch_size)
            .to_list()
        )
        recovered = 0
        clinic_review = []
        failed = []
        examined = 0

        for attempt in attempts:
            if should_continue is not None and not should_continue():
                break
            examined += 1
            appointment = None
            try:
                appointment = await AppointmentRepository.get_by_id(str(attempt.appointment_id))
                if not attempt.provider_payment_id or not attempt.provider_order_id:
                    reason = "Captured attempt is missing its provider identifiers."
                elif not appointment:
                    reason = "The appointment linked to this capture could not be found."
                elif appointment.patient_id != attempt.patient_id:
                    reason = "The captured attempt does not match the appointment owner."
                elif appointment.status == "cancelled" and PaymentService._capture_is_reflected(attempt, appointment):
                    reason = "Captured funds for this cancelled appointment require clinic reconciliation."
                elif PaymentService._capture_is_reflected(attempt, appointment):
                    await PaymentService._set_reconciliation_status(attempt, "reconciled")
                    continue
                else:
                    try:
                        await PaymentService._record_captured_payment(attempt, attempt.provider_payment_id)
                    except HTTPException:
                        # The capture remains persisted; inspect the resulting
                        # appointment state to distinguish conflicts from recovery.
                        pass
                    appointment = await AppointmentRepository.get_by_id(str(attempt.appointment_id))
                    if appointment and appointment.patient_id == attempt.patient_id:
                        if appointment.status == "cancelled" and PaymentService._capture_is_reflected(attempt, appointment):
                            reason = "Captured funds for this cancelled appointment require clinic reconciliation."
                        elif PaymentService._capture_is_reflected(attempt, appointment):
                            if await PaymentService._set_reconciliation_status(attempt, "reconciled"):
                                recovered += 1
                            continue
                        else:
                            reason = "The appointment has a newer or conflicting payment state."
                    elif not appointment:
                        reason = "The appointment linked to this capture could not be found."
                    else:
                        reason = "The captured attempt does not match the appointment owner."

                await PaymentService._set_reconciliation_status(attempt, "clinic_review")
                clinic_review.append(PaymentService._reconciliation_issue(attempt, appointment, reason))
            except Exception as exc:
                logger.warning(
                    "Captured payment reconciliation attempt failed",
                    extra={"attempt_id": str(attempt.id), "error_type": type(exc).__name__},
                )
                try:
                    await PaymentAttempt.get_pymongo_collection().update_one(
                        {"_id": attempt.id, "status": "success"},
                        {"$set": {"updated_at": datetime.now(timezone.utc)}},
                    )
                except Exception:
                    pass
                failed.append(PaymentService._reconciliation_issue(
                    attempt, appointment, "Temporary reconciliation failure; the worker will retry."
                ))

        return {
            "examined": examined,
            "recovered": recovered,
            "clinic_review": clinic_review,
            "failed": failed,
        }

    @staticmethod
    async def _apply_provider_payment(attempt: PaymentAttempt, payment: dict, event_id: str | None = None) -> str:
        if payment.get("amount") != attempt.amount_paise or payment.get("currency") != attempt.currency:
            raise HTTPException(status_code=400, detail="Provider payment amount does not match the appointment")

        provider_status = payment.get("status")
        if provider_status == "captured":
            await PaymentService._persist_attempt_status(attempt, "success", payment.get("id"), event_id)
            return await PaymentService._record_captured_payment(attempt, payment.get("id"))

        next_status = "failed" if provider_status == "failed" else "pending"
        if attempt.status != "success":
            persisted_status = await PaymentService._persist_attempt_status(attempt, next_status, payment.get("id"), event_id)
            if persisted_status == "success":
                return await PaymentService._record_captured_payment(attempt, attempt.provider_payment_id)
            await PaymentService._update_appointment(
                attempt.appointment_id,
                {"payment_status": next_status},
                only_if_unpaid=True,
            )
        return "success" if attempt.status == "success" else next_status

    @staticmethod
    async def verify_checkout(appointment_id: str, user_id: str, payload: dict) -> dict:
        PaymentService._require_test_configuration()
        appointment = await PaymentService._get_owned_appointment(appointment_id, user_id)
        attempt = await PaymentAttempt.find_one({"appointment_id": appointment.id})
        if not attempt or attempt.provider_order_id != payload.get("razorpay_order_id"):
            raise HTTPException(status_code=404, detail="Payment order not found")
        try:
            await asyncio.to_thread(
                PaymentService._client().utility.verify_payment_signature,
                {
                    "razorpay_order_id": payload.get("razorpay_order_id"),
                    "razorpay_payment_id": payload.get("razorpay_payment_id"),
                    "razorpay_signature": payload.get("razorpay_signature"),
                },
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Payment signature is invalid") from exc
        payment = await PaymentService._verify_provider_payment(
            attempt.provider_order_id,
            payload.get("razorpay_payment_id"),
        )
        payment_status = await PaymentService._apply_provider_payment(attempt, payment)
        current_appointment = await AppointmentRepository.get_by_id(appointment_id)
        return {
            "appointment_id": str(appointment.id),
            "status": payment_status,
            "billing_status": current_appointment.billing_status if current_appointment else "pending",
        }

    @staticmethod
    async def get_status(appointment_id: str, user_id: str) -> dict:
        appointment = await PaymentService._get_owned_appointment(appointment_id, user_id)
        return {
            "appointment_id": str(appointment.id),
            "status": getattr(appointment, "payment_status", "not_started"),
            "billing_status": appointment.billing_status,
            "amount": appointment.billing_amount,
            "currency": getattr(appointment, "billing_currency", None),
        }

    @staticmethod
    async def get_patient_payment_history(user_id: str) -> list[dict]:
        patient = await ProfileRepository.get_patient_by_user_id(user_id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found")

        attempts = await PaymentAttempt.find(
            {"patient_id": patient.id}
        ).sort("-created_at").to_list()
        history = []
        for attempt in attempts:
            appointment = await Appointment.get(attempt.appointment_id)
            history.append({
                "id": str(attempt.id),
                "appointment_id": str(attempt.appointment_id),
                "amount": attempt.amount_paise / 100,
                "currency": attempt.currency,
                "status": attempt.status,
                "reconciliation_status": attempt.reconciliation_status,
                "billing_status": appointment.billing_status if appointment else "unknown",
                "payment_status": appointment.payment_status if appointment else "unknown",
                "appointment_date": appointment.appointment_date if appointment else None,
                "time_slot": appointment.time_slot if appointment else None,
                "service_mode": appointment.service_mode if appointment else None,
            })
        return history

    @staticmethod
    async def abandon_checkout(appointment_id: str, user_id: str) -> dict:
        appointment = await PaymentService._get_owned_appointment(appointment_id, user_id)
        attempt = await PaymentAttempt.find_one({"appointment_id": appointment.id})
        if attempt and attempt.status != "success":
            persisted_status = await PaymentService._persist_attempt_status(attempt, "abandoned")
            if persisted_status != "success":
                await PaymentService._update_appointment(
                    appointment.id,
                    {"payment_status": "abandoned"},
                    only_if_unpaid=True,
                )
        return await PaymentService.get_status(appointment_id, user_id)

    @staticmethod
    async def cancel_checkout(appointment_id: str, user_id: str) -> dict:
        appointment = await PaymentService._get_owned_appointment(appointment_id, user_id)
        attempt = await PaymentAttempt.find_one({"appointment_id": appointment.id})
        if attempt and attempt.status != "success":
            persisted_status = await PaymentService._persist_attempt_status(attempt, "cancelled")
            if persisted_status != "success":
                await PaymentService._update_appointment(
                    appointment.id,
                    {"payment_status": "cancelled"},
                    only_if_unpaid=True,
                )
        return await PaymentService.get_status(appointment_id, user_id)

    @staticmethod
    async def handle_webhook(raw_body: bytes, signature: str | None, event_id: str | None) -> dict:
        PaymentService._require_test_configuration()
        if not signature or not event_id:
            raise HTTPException(status_code=400, detail="Webhook signature and event ID are required")
        try:
            raw_body_text = raw_body.decode("utf-8")
            await asyncio.to_thread(
                PaymentService._client().utility.verify_webhook_signature,
                raw_body_text,
                signature,
                settings.RAZORPAY_WEBHOOK_SECRET,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Webhook signature is invalid") from exc
        try:
            event = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Webhook body is invalid") from exc
        if not isinstance(event, dict):
            raise HTTPException(status_code=400, detail="Webhook body is invalid")

        body_digest = hashlib.sha256(raw_body).hexdigest()
        payload = event.get("payload")
        payment_envelope = payload.get("payment") if isinstance(payload, dict) else None
        entity = payment_envelope.get("entity") if isinstance(payment_envelope, dict) else None
        entity = entity if isinstance(entity, dict) else {}
        order_id = entity.get("order_id")
        payment_id = entity.get("id")
        try:
            webhook_event = await RazorpayWebhookEvent.find_one(
                {"body_digest": body_digest}
            )
        except Exception as exc:
            raise PaymentService._webhook_retryable_error() from exc
        if webhook_event and webhook_event.status == "processed":
            return {"status": "duplicate"}
        if not webhook_event:
            webhook_event = RazorpayWebhookEvent(
                event_id=event_id,
                body_digest=body_digest,
                provider_order_id=order_id,
            )
            try:
                await webhook_event.insert()
            except DuplicateKeyError:
                try:
                    webhook_event = await RazorpayWebhookEvent.find_one(
                        {"body_digest": body_digest}
                    )
                    if not webhook_event:
                        conflicting_header = await RazorpayWebhookEvent.find_one(
                            {"event_id": event_id}
                        )
                        if conflicting_header:
                            raise HTTPException(
                                status_code=409,
                                detail="Webhook event identity conflicts with an earlier payload",
                            )
                except Exception as exc:
                    if isinstance(exc, HTTPException):
                        raise
                    raise PaymentService._webhook_retryable_error() from exc
                if webhook_event and webhook_event.status == "processed":
                    return {"status": "duplicate"}
                if not webhook_event:
                    raise PaymentService._webhook_retryable_error()
            except Exception as exc:
                raise PaymentService._webhook_retryable_error() from exc

        if event.get("event") not in {"payment.captured", "payment.failed"}:
            webhook_event.status = "processed"
            webhook_event.processed_at = datetime.now(timezone.utc)
            try:
                await webhook_event.save()
            except Exception as exc:
                raise PaymentService._webhook_retryable_error() from exc
            return {"status": "ignored"}
        if not order_id or not payment_id:
            raise HTTPException(status_code=400, detail="Payment event is missing provider identifiers")

        try:
            attempt = await PaymentAttempt.find_one(
                {"provider_order_id": order_id}
            )
        except Exception as exc:
            raise PaymentService._webhook_retryable_error() from exc
        if not attempt:
            # The provider can deliver immediately after order creation while
            # the local order write is still completing. A retryable response
            # prevents a valid event from being acknowledged and lost.
            raise PaymentService._webhook_retryable_error()
        payment = await PaymentService._verify_provider_payment(order_id, payment_id)
        result = await PaymentService._apply_provider_payment(attempt, payment, event_id=event_id)
        webhook_event.status = "processed"
        webhook_event.processed_at = datetime.now(timezone.utc)
        try:
            await webhook_event.save()
        except Exception as exc:
            raise PaymentService._webhook_retryable_error() from exc
        return {"status": result}

    @staticmethod
    def _webhook_retryable_error() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook processing is temporarily unavailable",
        )
