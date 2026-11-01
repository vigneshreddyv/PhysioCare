# Phase 14 Isolated Staging Setup

Assessment date: 2026-10-31

Status: **Prepared locally; not provisioned, connected, or externally validated**

Remediation update 2026-11-01: staging isolation is now enforced fail-closed by
application settings validation and is rechecked before database initialization.

## Configuration artifacts

- `backend/staging.env.example`
- `frontend/staging.env.example`

Both files are secret-free templates. Blank database, JWT, and payment values are
intentional; the backend template cannot safely start until an approved secret
injection system supplies independent staging values.

## Required isolated resources

| Boundary | Required setup |
|---|---|
| Database | New empty staging database/cluster, dedicated credential and network policy; never a production copy |
| Identity | Fictional patient, clinician, administrator, receptionist and laboratorian accounts only |
| Sessions | Independent access/refresh secrets; `ENVIRONMENT=staging` enables Secure cookies; HTTPS required |
| Ingress | Exact HTTPS CORS origin and exact trusted proxy CIDRs; ingress overwrites forwarded headers |
| Rate limits | Mongo collection with approved unique/TTL indexes, shared by every worker |
| Reports | Separate clinical and laboratory approved/quarantine roots, owner-only permissions, same filesystem per pair for atomic promotion |
| Scanner | Approved private adapter with health checks and a timeout no greater than `PDF_SCAN_TIMEOUT_SECONDS` |
| Payments | `RAZORPAY_MODE=disabled`, empty provider credentials and reconciliation disabled initially |
| Observability | Staging-only access and retention; redact tokens, credentials, report contents and patient fields |

The configuration now also requires the exact isolated staging deployment marker,
an explicitly matched staging database host and name selected in the credentialed
Mongo URL, enabled shared authentication throttling, at least one trusted proxy
CIDR, exact HTTPS CORS origins, and four absolute non-overlapping report paths
under one dedicated staging storage root. Payment mode, provider credentials,
billing currency and reconciliation must all remain disabled. Environment names
outside the strict development/test/staging/production set are rejected. Secure
cookie mode is enabled for staging and production environments.

The template intentionally remains unusable without approved credential injection
and exact proxy values. The application never rewrites an unsafe value. Errors name
the failed policy category without printing credentials or connection strings.

`PDF_SCANNER_MODE=disabled` is mandatory in staging until an approved operational
adapter is implemented in code. In this state clinical and laboratory PDF uploads
fail closed with 503 and cannot be promoted to approved storage.

## Approval-gated setup sequence

1. Environment owner identifies the exact target and attests it is empty and
   isolated from normal patient data.
2. Infrastructure owner provisions network, database, storage, TLS and secret
   injection. This repository work did not perform those actions.
3. Security owner approves proxy CIDRs, scanner adapter, timeout, reason-code
   mapping and logging policy.
4. Database owner authorizes initialization and index creation only in the new
   empty staging database.
5. Application owner verifies environment identity and the presence—not values—
   of secrets; payments and reconciliation remain disabled.
6. Test owner creates the approved fictional dataset through application paths.
7. Run authentication and IDOR gates before positive clinical workflows.
8. Razorpay Test Mode may be configured only after separate explicit approval;
   live credentials, payments and refunds remain prohibited.

## Startup acceptance checks

- HTTPS origin exactly matches the configured frontend and CORS allowlist.
- Session cookies carry Secure, HttpOnly where applicable, and expected SameSite
  attributes; CSRF validation succeeds and rejects mismatches.
- Direct proxy address belongs to the approved CIDR list and spoofed forwarded
  headers do not alter throttle identity.
- Database name, credential and network endpoint match the approved staging
  inventory; no normal records exist.
- Approved/quarantine roots are private, separate and non-symlinked.
- With the scanner unavailable, both clinical and laboratory uploads return 503
  and leave no downloadable content.
- Payment mode and reconciliation are disabled and provider secrets are absent.
- An invalid staging configuration terminates before the Mongo client or payment
  reconciliation worker is constructed.

No database, index, cloud resource, scanner, DNS, proxy, webhook, payment service
or Docker volume was created or modified during Phase 14.
