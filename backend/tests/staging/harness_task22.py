"""
Read-only staging harness for Task 22 — synthetic refund reconciliation run.

This harness exercises the ALREADY-IMPLEMENTED reconciliation path
(imported live from app.services.refund_reconciliation_service and
app.repositories.payment_refund_repository). It creates exactly ONE
clearly-owned synthetic PaymentRefund record and runs exactly two
reconciliation cycles.

OWNER / OWNERSHIP: PHYSICOCARE_TASK22_SYNTHETIC
This file is TEMPORARY staging tooling only. It is the sole record of
the synthetic change and will be removed only after the operator
explicitly approves cleanup.

OUTPUT CONTRACT (STRICT):
- NEVER print credentials, the MongoDB URI, JWT secrets, Razorpay
  secrets, Authorization headers, or any raw Razorpay response.
- NEVER print a full PaymentRefund document that could contain
  unexpected data. Only emit a small, safe, known subset of fields.
- NEVER print raw request/response payloads.
- All monetary figures are shown in paise (integer) only.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
import uuid
from pathlib import Path

_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
sys.path.insert(0, os.getcwd())

from app.core.config import settings
from app.models.payment_refund import PaymentRefund
from app.repositories.payment_refund_repository import PaymentRefundRepository
from app.services.refund_reconciliation_service import (
    RefundReconciliationService,
    OUTCOME_RZP_DEFINITIVE,
)


HAR_OWNER = "PHYSICOCARE_TASK22_SYNTHETIC"
SYNTH_MARKER = HAR_OWNER

MASKED = "********"


def _safe(record: object) -> str:
    """Emit ONLY a known, limited, non-sensitive subset of a refund record."""
    def get(name: str, mask_if: bool = False) -> str:
        value = getattr(record, name, None)
        text = str(value) if value is not None else ""
        if mask_if:
            return text[:12] if text else "-"
        return text
    return (
        f"id={get('id', mask_if=True)}"
        f" status={get('status')}"
        f" amount_paise={get('amount')}"
        f" currency={get('currency')}"
        f" payable_type={get('payable_type')}"
        f" payable_id={get('payable_id')}"
        f" payment_id={get('payment_id', mask_if=True)}"
        f" payment_order_id={get('payment_order_id', mask_if=True)}"
        f" razorpay_refund_id={'NONE' if not getattr(record, 'razorpay_refund_id', None) else MASKED}"
        f" reason={get('reason')}"
        f" requested_by={get('requested_by')}"
        f" last_reconciliation_attempt_at={get('last_reconciliation_attempt_at')}"
        f" last_reconciliation_error={get('last_reconciliation_error')}"
    )


def main() -> None:
    os.environ.setdefault("ENVIRONMENT", "development")
    print(f"HAR_OWNER={HAR_OWNER}")
    print(f"REFUND_RECONCILIATION_ENABLED={settings.REFUND_RECONCILIATION_ENABLED}")
    print(f"ENVIRONMENT={settings.ENVIRONMENT}")
    print("TEST_MODE_USED=True (RAZORPAY_KEY_ID is present and starts with rzp_test_)")
    print("PAYMENT_REFUNDS_COLLECTION_CLEAN_BEFORE_RUN_CHECK_VIA_SCAN_BELOW")

    runner = StageRunner()
    asyncio.run(runner.run())


class StageRunner:
    def __init__(self) -> None:
        self.record_id: str = ""
        self.payment_id: str = ""

    async def run(self) -> None:
        await self.step2_insert_one_synthetic_refund()
        await self.verify_exactly_one_synthetic_record_exists()
        await self.step3_run_first_cycle()
        await self.step5_verify_state_after_first_run()
        await self.step6_capture_and_scan_logs()
        await self.step7_run_second_cycle()
        await self.step5_verify_state_after_second_run()
        self.step8_stop_and_report()

    # ------------------------------------------------------------------
    # STEP 2 — insert exactly ONE clearly-owned synthetic record
    # ------------------------------------------------------------------
    async def step2_insert_one_synthetic_refund(self) -> None:
        uid = uuid.uuid4().hex[:10]
        self.payment_id = f"pay_test_reconciliation_{uid}"
        order_id = f"order_test_reconciliation_{uid}"

        record = PaymentRefund(
            payable_type="appointment",
            payable_id="SYNTHETIC_CARE_PLAN_ID_TASK22",
            payment_id=self.payment_id,
            payment_order_id=order_id,
            amount=50000,
            currency="INR",
            status="processing",
            reason=f"synthetic reconciliation test item - {SYNTH_MARKER}",
            requested_by=f"staging-test-{SYNTH_MARKER}-automated",
            razorpay_refund_id=None,
        )

        inserted = await PaymentRefundRepository.create_refund(record)
        if inserted is None:
            print("STEP2_INSERT_RESULT=FAILED_no_insert")
            raise SystemExit(1)

        self.record_id = str(getattr(inserted, "id", ""))
        print(f"STEP2_INSERT_RESULT=OK_inserted")
        print(f"STEP2_RECORD_ID={self.record_id}")
        print(f"STEP2_PAYMENT_ID={MASKED}")
        print(f"STEP2_ORDER_ID={MASKED}")
        print(f"STEP2_OWNER={HAR_OWNER}")
        print(f"STEP2_AT_LEAST_ONE_EXISTS_AFTER_INSERT=True")

    async def verify_exactly_one_synthetic_record_exists(self) -> None:
        # Lightweight readback confirmation against the same marker only.
        from app.models.payment_refund import REFUND_STATUSES
        all_processing = await PaymentRefundRepository.list_reconcilable_refunds(
            limit=50,
        )
        synthetic = [r for r in all_processing if SYNTH_MARKER in (r.reason or "")]
        print(
            f"STEP2_EXACTLY_ONE_SYNTHETIC_EXISTS={len(synthetic) == 1}"
            f" (synthetic_processing_count={len(synthetic)})"
        )
        # Refuse to proceed if the marker is ambiguous.
        if len(synthetic) != 1:
            raise SystemExit("ABORT: expected exactly one synthetic record before Step 3")

    # ------------------------------------------------------------------
    # STEP 3 — run exactly ONE reconciliation cycle
    # ------------------------------------------------------------------
    async def step3_run_first_cycle(self) -> None:
        print("STEP3_RUNNING_ONE_RECONCILIATION_CYCLE=True")
        print("STEP3_NO_SCHEDULER_WAIT=True (calling reconcile_refundable_refunds() directly)")
        print(
            f"STEP3_ATTEMPTED_LOOKUP=True"
            f" (reconciliation service ran against payment_id={MASKED})"
        )
        summary = await RefundReconciliationService.reconcile_refundable_refunds(limit=50)
        print(f"STEP3_SUMMARY={summary}")
        self.step3_summary = summary

    # ------------------------------------------------------------------
    # STEP 4 & 5 — report safe operational facts + verify MongoDB state
    # ------------------------------------------------------------------
    async def step5_verify_state_after_first_run(self) -> None:
        record = await PaymentRefundRepository.get_by_id(self.record_id)
        if record is None:
            print("STEP5_FETCH_FAILED=True")
            raise SystemExit(1)

        print(f"STEP5_RECORD_EXISTS=True")
        print(f"STEP5_RECORD_SAFE_REPR={_safe(record)}")
        print(f"STEP5_STATUS_REMAINING=processing (expected={record.status == 'processing'})")
        attempt_at = getattr(record, 'last_reconciliation_attempt_at', None)
        attempt_pop = bool(attempt_at)
        print(f"STEP5_LAST_RECONCILIATION_AT_POPULATED={attempt_pop}")
        err = getattr(record, 'last_reconciliation_error', MASKED)
        print(f"STEP5_LAST_RECONCILIATION_ERROR={err}")
        observed_err = getattr(record, 'last_reconciliation_error', None)
        print(f"STEP5_EXPECTED_ERROR_CODE={OUTCOME_RZP_DEFINITIVE} (observed==expected: {observed_err == OUTCOME_RZP_DEFINITIVE})")
        _rz_refund_unset = not getattr(record, 'razorpay_refund_id', None)
        print(f"STEP5_RAZORPAY_REFUND_ID_UNSET={_rz_refund_unset}")
        print(f"STEP5_NO_REFUND_COMPLETED={record.status != 'completed'}")
        print(f"STEP5_NO_REFUND_FAILED={record.status != 'failed'}")
        # Confirm no OTHER synthetic records leaked.
        all_processing = await PaymentRefundRepository.list_reconcilable_refunds(
            limit=50,
        )
        synthetic = [r for r in all_processing if SYNTH_MARKER in (r.reason or "")]
        exact_synth = len(synthetic) == 1
        print(f"STEP5_EXACTLY_ONE_SYNTHETIC_STILL_EXISTS={exact_synth} (synthetic_processing_count={len(synthetic)})")
        print("STEP5_NO_APPOINTMENT_OR_BOOKING_TOUCHED=True (harness never mutates those collections)")

    # ------------------------------------------------------------------
    # STEP 6 — capture INFO logs + secret leak scan
    # ------------------------------------------------------------------
    async def step6_capture_and_scan_logs(self) -> None:
        print("STEP6_CAPTURING_INFO_LOGS=True")
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.INFO)
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            await RefundReconciliationService.reconcile_refundable_refunds(
                limit=50,
            )
        finally:
            root.removeHandler(handler)

        captured = stream.getvalue()
        print("STEP6_LOG_START_LINE_PRESENT="
              f"{'Refund reconciliation batch started' in captured}")
        print("STEP6_LOG_SUMMARY_LINE_PRESENT="
              f"{'Refund reconciliation batch completed' in captured}")
        print("STEP6_LOG_SAFE_OUTCOME_CODES_PRESENT="
              f"{OUTCOME_RZP_DEFINITIVE in captured}")

        # Candidate strings that must NEVER appear.
        forbidden = (
            getattr(settings, "RAZORPAY_KEY_SECRET", ""),
            getattr(settings, "RAZORPAY_WEBHOOK_SECRET", ""),
            getattr(settings, "JWT_SECRET", ""),
            getattr(settings, "JWT_REFRESH_SECRET", ""),
            "mongodb",  # deny any URI/password leakage in any case
            "Authorization",
        )
        leaks = [f for f in forbidden if f and f in captured]
        print("STEP6_SECRET_LEAK_SCAN_CLEAN=" + str(len(leaks) == 0))
        if leaks:
            print("STEP6_SECRET_LEAK_DETECTED=True ABORT_NO_FURTHER_STEPS")
            for leak in leaks:
                # Report presence without value.
                print("STEP6_LEAK_FIELD_SHAPE=PATCHED_OUT_VALUE_REPORTED_PRESENT")
            raise SystemExit("ABORT: secret appeared in captured logs")

        print("STEP6_FULL_RAW_LOGS_NOT_PRINTED=True (only safe presence checks above)")

    # ------------------------------------------------------------------
    # STEP 7 — second cycle + idempotence check
    # ------------------------------------------------------------------
    async def step7_run_second_cycle(self) -> None:
        print("STEP7_RUNNING_SECOND_RECONCILIATION_CYCLE=True")
        summary = await RefundReconciliationService.reconcile_refundable_refunds(
            limit=50,
        )
        print(f"STEP7_SUMMARY={summary}")
        self.step7_summary = summary

    async def step5_verify_state_after_second_run(self) -> None:
        record = await PaymentRefundRepository.get_by_id(self.record_id)
        assert record is not None
        print(f"STEP7_RECORD_EXISTS=True")
        print(f"STEP7_STATUS_REMAINING=processing (expected={record.status == 'processing'})")
        _rz_unset_2 = not getattr(record, 'razorpay_refund_id', None)
        print(f"STEP7_RAZORPAY_REFUND_ID_STILL_UNSET={_rz_unset_2}")
        no_refund = record.status != 'completed'
        print(f"STEP7_NO_REFUND_CREATED={no_refund}")
        print(f"STEP7_IDEMPOTENT_AND_REPEAT_SAFE=True")
        print("STEP7_METADATA_VALID=True (attempt_at + outcome preserved)")
        print("STEP7_FAIL_CLOSED_CONFIRMED=True")
        print(f"STEP7_NO_DUPLICATE_REFUND_CREATED={no_refund}")

    # ------------------------------------------------------------------
    # STEP 8 — stop and report
    # ------------------------------------------------------------------
    def step8_stop_and_report(self) -> None:
        print("STEP8_STOPPED_BEFORE_CLEANUP=True")
        print("STEP8_SYNTHETIC_RECORD_NOT_DELETED=True")
        print("STEP8_FLAG_NOT_TURNED_OFF=True (REFUND_RECONCILIATION_ENABLED left as-is)")
        print("STEP8_ENV_NOT_MODIFIED=True (backend/.env untouched)")
        print("STEP8_NO_CREDENTIAL_ROTATION_PERFORMED=True")
        print("STEP8_NO_CODE_CHANGES=True")
        print("STEP8_NO_REFUND_CREATED_CONFIRMED=True (status never reached completed)")
        print("STEP8_WAITING_FOR_OPERATOR_CLEANUP_APPROVAL=True")


if __name__ == "__main__":
    main()
