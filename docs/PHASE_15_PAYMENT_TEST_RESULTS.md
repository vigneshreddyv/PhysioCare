# Phase 15 Razorpay Test Mode readiness

Assessment: 2026-11-01. **Provider result: NOT RUN / BLOCKED.** Staging startup currently requires payments and reconciliation disabled. No Test Mode key, webhook, payment, refund or provider endpoint was contacted.

## Source review

`backend/app/services/payment_service.py` requires a test-mode key prefix, secret, webhook secret and INR configuration before provider operations. Checkout signature and webhook body signature are verified; payment order/amount/currency/status are checked against provider state before capture is persisted. The payment attempt and webhook event models support idempotent state, and captured/cancelled conflicts enter clinic review/reconciliation. `backend/app/services/payment_reconciliation_worker.py` has a Mongo lease for a bounded background worker. The S15-6 source fix now hashes the verified raw webhook body and uses a unique partial digest index to deduplicate replays even when the unsigned event-ID header changes. Four local regressions pass; the actual provider event-ID contract and index behavior remain unverified. These are source and mocked-test observations, not provider evidence. Refunds and live payment flow are not implemented or authorized.

## Approval-gated Test Mode matrix

After the owner approves exact empty staging, test-only keys, a public HTTPS staging webhook, fictional appointments, amount/currency policy and cleanup, first verify the `unique_razorpay_webhook_body_digest` index and any legacy ledger data. Then execute: order creation; successful and failed test payments; cancelled/abandoned checkout; invalid checkout and webhook signatures; duplicate/reordered/retried webhooks (including a changed event-ID header on one signed body); persistence failure; worker restart/lease contention; capture after cancellation; reconciliation visibility. Confirm one provider order/attempt per appointment, no unverified paid state, bounded retry, no lost captured funds and no duplicate side effects. Record redacted provider IDs and before/after application state. Do not use live keys or real cards; do not issue a real refund. Refund authorization remains a separate design and implementation gate.

Current Test Mode status: **not validated**. Payment release checkbox must stay open.
