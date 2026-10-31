# Razorpay Test Mode setup

This integration creates and verifies Razorpay orders only in Test Mode. Do not set `RAZORPAY_MODE` to `live`, and do not use live keys.

Add these variable names to the backend `.env` file. Keep the secret values server-side and do not add them to any `VITE_*` variable:

```text
RAZORPAY_MODE
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
APPOINTMENT_BILLING_CURRENCY
PAYMENT_RECONCILIATION_ENABLED
PAYMENT_RECONCILIATION_INTERVAL_SECONDS
PAYMENT_RECONCILIATION_BATCH_SIZE
PAYMENT_RECONCILIATION_LEASE_SECONDS
```

Payment endpoints return `503` until Test Mode is selected, the key ID has Razorpay's `rzp_test_` prefix, the key secret is present, and the billing currency is explicitly set to `INR`. Webhook delivery additionally requires the webhook secret. Only the public Key ID is returned to the browser for Razorpay Checkout; the key secret and webhook secret remain backend-only.

## Captured-payment recovery worker

The FastAPI lifespan starts the bounded reconciliation worker after Beanie/database initialization. It runs only while Test Mode configuration is ready. Defaults are:

```text
PAYMENT_RECONCILIATION_ENABLED=true
PAYMENT_RECONCILIATION_INTERVAL_SECONDS=30
PAYMENT_RECONCILIATION_BATCH_SIZE=50
PAYMENT_RECONCILIATION_LEASE_SECONDS=120
```

The interval accepts 5–3600 seconds, batch size 1–500, and lease 15–3600 seconds; the lease must be at least twice the poll interval. Set `PAYMENT_RECONCILIATION_ENABLED=false` to disable the worker. Captured attempts remain persisted and can still be retried by an authorized administrator from Billing using **Reconcile captured payments**.

The worker discovers pending captured attempts from MongoDB on every cycle, so process restarts do not depend on in-memory task state. A MongoDB lease reduces simultaneous worker cycles across application instances. Appointment updates are conditional and idempotent; processing is at-least-once, not exactly-once. A lease expiration or manual administrator retry can overlap a cycle, but neither can create a second provider charge or attach the capture to a conflicting appointment/payment. Cancelled appointments stay cancelled and are surfaced for clinic review. Temporary failures remain pending and are retried with a bounded backoff capped at five minutes. The worker reports aggregate counts and logs only attempt identifiers and exception types on per-record failures; it does not log patient details, payment payloads, or secrets.

For local verification, start the backend normally and check its logs for the worker start message and subsequent aggregate cycle summaries. Stop the server and confirm the shutdown message. The authorized Billing control remains available as an operational fallback; it processes a bounded batch and returns separate recovered, clinic-review, and temporary-failure results.

## Test Mode webhook

In the Razorpay Dashboard, switch to **Test Mode**, create a webhook, and set its URL to:

```text
https://<public-staging-host>/api/webhooks/razorpay
```

Subscribe to `payment.captured` and `payment.failed`. Copy the webhook secret into the backend `RAZORPAY_WEBHOOK_SECRET` setting. The implementation verifies `X-Razorpay-Signature` against the original UTF-8 request body and deduplicates by `X-Razorpay-Event-Id`.

Razorpay cannot deliver webhooks to localhost. Use a publicly reachable HTTPS staging endpoint or a supported HTTPS tunnel for webhook testing. Checkout signature verification can be exercised locally, but webhook delivery cannot.

## Amount convention

The existing appointment model did not record a currency, and the former billing screen explicitly said currency was not configured. Therefore checkout remains disabled until the owner confirms the stored `appointments.billing_amount` values are major-unit INR and sets `APPOINTMENT_BILLING_CURRENCY=INR` in the backend environment. After that confirmation, amounts are validated to at most two decimal places and converted to paise on the backend. The amount in Checkout is always taken from the stored appointment, never from the browser. Appointment amounts are locked after a provider order exists.

The app records a paid appointment only after validating the checkout signature or webhook signature and fetching the payment from Razorpay to confirm its captured status, order, amount, and currency. One provider order is retained per appointment and reused for retries, preventing duplicate orders/charges for repeated checkout requests.
