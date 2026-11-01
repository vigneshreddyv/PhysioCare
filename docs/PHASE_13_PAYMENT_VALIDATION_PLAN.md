# Phase 13 Razorpay Test Mode Validation Plan

Assessment date: 2026-10-31

Provider execution status: **NOT EXECUTED — Test Mode authorization not provided**

No Razorpay API, checkout, webhook, payment, refund, or credential endpoint was
contacted. The current evidence is source review plus mocked automated tests.

## Implementation assessment

| Area | Current behavior | Local evidence | Protected/Test Mode status |
|---|---|---|---|
| Readiness | Fails closed unless mode is `test`, key ID starts `rzp_test_`, both secrets exist, and currency is INR | `PaymentService.is_test_configuration_ready`; route response excludes secrets | Not externally verified |
| Order creation | Server reads stored appointment amount, exact-converts rupees to paise, creates at most one attempt/order per appointment, and conditionally attaches it only while scheduled | Mocked order/idempotency/cancellation-race tests | Provider not called |
| Checkout verification | Verifies checkout signature, fetches payment, then checks order, captured status, amount, and currency | Mocked signature/capture tests | Provider not called |
| Webhook authentication | Verifies signature against raw body before DB access and requires event ID | Mocked invalid/raw-body tests | Public delivery not tested |
| Webhook persistence | Unique event ledger; processed events return idempotently; failed ledger operations ask provider to retry | Mocked persistence/idempotency tests | Protected DB not tested |
| Reconciliation | Bounded worker uses a Mongo lease and conditional/idempotent updates; admin has manual retry/review | Worker and overlap tests | Connected multi-instance behavior not tested |
| Cancellation | Checkout can be abandoned/cancelled; appointment cancellation wins over late capture, which becomes clinic review | Mocked race tests | Provider race not tested |
| Refunds | No application refund endpoint or automatic refund implementation exists | Cancellation tests assert the provider refund API is not called | Requires implementation and separate approval if desired |

The full backend suite passes 346 tests, including the payment and worker tests;
frontend tests pass 58. These tests mock the provider and do not demonstrate an
actual Test Mode charge or webhook.

## Frontend state review

| Required distinction | Assessment |
|---|---|
| Test Mode | Clear: booking header, checkout-opening status, retry text, admin Billing scope, and disclaimer say Test Mode |
| Production Mode | Intentionally unsupported; there is no live-mode path or production checkout label. Production payment readiness therefore remains blocked rather than ambiguous |
| Payment unavailable | Shown as an actionable error while appointment remains unpaid |
| Configuration incomplete | Readiness is checked before booking; current message says Test Mode is not configured. It does not reveal which secret is missing |
| Verification pending | Clear pending/verifying messages and status polling |
| Successful | Clear server-verified success state |
| Failed | Clear provider-failed state; appointment remains unpaid and retry is offered |
| Captured after cancellation | Clear clinic-review warning; booking stays cancelled |

The frontend must continue to use only the public key ID returned by the order
response. Secret/webhook values must never enter a `VITE_*` variable, browser
bundle, DOM, analytics event, screenshot, or client log.

## Authorization and environment gate

Before testing, the owner must explicitly authorize a dedicated staging target
and Razorpay **Test Mode** account. The operator then verifies, without printing
values:

1. target backend, frontend, database, and public HTTPS webhook URL are isolated;
2. fictional patient/admin accounts are used;
3. key ID is a Test Mode key, secrets are injected server-side, and live keys are
   absent;
4. `APPOINTMENT_BILLING_CURRENCY=INR` follows an owner confirmation that stored
   appointment amounts are major-unit INR;
5. webhook subscribes only to `payment.captured` and `payment.failed`;
6. database backup/cleanup policy for fictional payment attempts is approved;
7. reconciliation worker and its lease/batch settings are intentionally enabled;
8. logs/observability redact signatures, raw payloads, patient details, and keys.

## End-to-end test matrix

Each test records fictional appointment ID, local attempt/order/event IDs,
before/after application state, HTTP status, redacted server log correlation,
and Razorpay Test Mode dashboard evidence. Never record card/UPI credentials or
full signatures.

| Case | Controlled steps | Expected application result | Evidence / cleanup |
|---|---|---|---|
| Successful test payment | Create fictional clinic appointment, start checkout with an official Test Mode success method, complete verification, allow webhook | One provider order/attempt; captured payment matches amount/order/currency; appointment `paid`/`success`; duplicate verification no-op/conflict-safe | UI success, API status/history, one attempt and processed event; retain sanitized IDs |
| Failed test payment | Use official Test Mode failure path | Appointment remains scheduled/unpaid; attempt failed; retry reuses safe attempt/order behavior | Failure UI, API state, no paid transition |
| Cancelled/abandoned checkout | Close Checkout, call abandon/cancel payment step, retry once | No payment confirmed; appointment remains unpaid; safe retry does not create an uncontrolled duplicate | Status history and single provider-order relationship |
| Invalid checkout signature | In an isolated API test, alter a fictional signature while retaining known test IDs | 400; no appointment/payment mutation; no secret or signature echoed | Before/after DB comparison and redacted response |
| Duplicate webhook delivery | Replay the same signed Test Mode event through Razorpay retry/resend tooling | One ledger event; second delivery acknowledged without reapplying state | Unique event ID, one processed transition |
| Persistence failure/retry | In isolated staging only, inject a narrowly scoped repository failure before processed marker, then remove fault and resend | Retryable response first; later delivery processes once; no lost capture or duplicate charge | Fault window log, event ledger, final appointment state |
| Reconciliation | Interrupt after provider capture but before appointment reflection using an approved fault point; restore service | Worker/manual reconcile marks matching active booking paid, or surfaces cancelled/conflicting booking for clinic review | Worker aggregate, admin Billing review, idempotent second run |
| Unauthorized refund request | Attempt an unimplemented refund route as patient and non-admin; do not call provider directly | 404/405, no provider refund invocation and no state change | Access log plus unchanged attempt/appointment; current outcome is expected because refunds are not implemented |

Additional race cases: cancel while order creation is in flight, cancel just
before/after capture, concurrent duplicate order requests, worker lease loss,
manual reconciliation overlapping the worker, and process restart with pending
captured attempts.

## Failure and stop rules

Stop immediately if any key is live, the target is not isolated, an amount/currency
does not match server state, a secret appears client-side/logged, a second charge
is possible, an invalid signature changes data, a captured payment disappears,
or a cancelled appointment reopens. Do not “repair” protected data manually;
preserve evidence and obtain owner direction.

## Exit criteria

Payment can be classified **Ready with restrictions for Test Mode** only when all
matrix cases pass in an authorized isolated environment, public webhook delivery
is demonstrated, restart/multi-instance reconciliation is observed, and the
clinic approves captured-after-cancellation handling. Live/production payments
and refunds remain separate product, compliance, operational, and authorization
decisions.
