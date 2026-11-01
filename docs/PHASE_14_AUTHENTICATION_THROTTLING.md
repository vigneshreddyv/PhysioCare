# Phase 14 Authentication Throttling

Assessment date: 2026-10-31

Remediation update 2026-11-01: an opt-in connected contract now exists for two
rate-limit store instances sharing one Mongo counter and verifying unique/TTL
indexes. It is hard-guarded to the acknowledged loopback database
`physiocare_phase14_connected_test`, skipped by normal runs, and was not executed
during this pass. Real staging proxy and multi-worker evidence remains required.

## Implemented design

Authentication throttling uses atomic fixed-window counters in MongoDB through
`AuthRateLimitBucket`. It is shared across backend workers and instances that use
the same staging/application database; the in-memory store exists only as a
deterministic test adapter and is not the application default.

No rate-limit record stores a raw email address, IP address, password, refresh
token, or CSRF token. Bucket keys are HMAC-SHA256 digests, domain-separated by
purpose and window, using the configured JWT secret as key material. Bucket
documents contain only the opaque digest, attempt count, and TTL expiration.

## Protected operations

| Operation | Default policy | Identifier | Behavior |
|---|---|---|---|
| Login traffic | 30 requests / 300 seconds | Client address digest | Limits broad abuse without making normal successful use fragile |
| Account login attempts | 5 reserved attempts / 300 seconds | Normalized email digest | Reservation is atomic before password verification so a concurrent burst cannot bypass the limit; successful authentication clears the current account bucket |
| Registration | 5 requests / 3600 seconds | Client address digest | Limits automated account creation while preserving schema validation |
| Refresh and CSRF issue | 120 requests / 60 seconds per client plus 30 / 60 seconds per token | Client-address and refresh-token digests | Unique invalid tokens cannot bypass the client limit; token replay is independently bounded without storing the token |

The safe throttle response is always `429` with `Too many requests. Try again
later.` and a bounded `Retry-After` header. Storage failures return a generic
`503` and fail closed before authentication work. A best-effort failure-counter
clear after a successfully persisted login cannot suppress the valid session.

## Trusted client address handling

The direct socket peer is authoritative by default. `X-Forwarded-For` is ignored
unless that direct peer belongs to a network explicitly listed in
`TRUSTED_PROXY_NETWORKS`. When trusted, the resolver walks the forwarding chain
from the application outward and selects the first address outside the trusted
proxy networks. A malformed chain is ignored in full.

Only known ingress/load-balancer IPs or CIDRs may be configured. Do not add
public client networks or broad private ranges merely to make an observed header
work. The ingress must overwrite, not append to, untrusted client-provided
forwarding headers.

## Configuration

```text
AUTH_RATE_LIMIT_ENABLED=true
AUTH_LOGIN_IP_LIMIT=30
AUTH_LOGIN_FAILURE_LIMIT=5
AUTH_LOGIN_WINDOW_SECONDS=300
AUTH_REGISTRATION_LIMIT=5
AUTH_REGISTRATION_WINDOW_SECONDS=3600
AUTH_REFRESH_IP_LIMIT=120
AUTH_REFRESH_LIMIT=30
AUTH_REFRESH_WINDOW_SECONDS=60
TRUSTED_PROXY_NETWORKS=[]
```

Configuration has bounded validation. Disabling the limiter is acceptable only
for a documented local diagnostic, never as a staging/production workaround.

## Deployment dependency

The shared store requires the `auth_rate_limit_buckets` collection and its
unique bucket-key and TTL indexes. No database or index operation was executed
in Phase 14. First startup against an explicitly approved isolated staging
database must verify those definitions. Production index creation remains a
separate approval gate.

Mongo availability is now part of authentication availability. Monitor 429 and
503 rates without logging bucket inputs, emails, tokens, passwords, or raw
forwarding chains. Alert thresholds and support recovery are owner/operations
decisions.

## Test coverage

Focused tests cover repeated failures, successful-login clearing, window expiry,
registration abuse, refresh-token/client abuse, trusted/untrusted/malformed
forwarding, opaque state, atomic concurrent account reservations, Mongo
first-upsert race recovery, pre-verification account blocking, generic
registration responses, and route-level success/failure hooks. Connected
multi-worker Mongo behavior remains an isolated staging test.
