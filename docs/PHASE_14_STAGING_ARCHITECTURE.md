# Phase 14 Isolated Staging Architecture

Assessment date: 2026-10-31

Status: **Architecture and secret-free templates prepared; infrastructure not created**

Remediation update 2026-11-01: these boundaries are now represented by fail-closed
application validation, not only operator acceptance checks. They are revalidated
before database initialization. Infrastructure identity still requires owner approval.

Templates:

- `backend/staging.env.example`
- `frontend/staging.env.example`

They contain placeholders only. Blank JWT/database/payment secrets intentionally
prevent a copied backend template from being usable as-is.

## Isolation architecture

| Boundary | Required staging control |
|---|---|
| Database | Dedicated database/cluster named for staging, separate credentials and network policy; no production restore, clone, dump or patient record |
| Accounts | Fictional patient, clinician, admin, receptionist and laboratorian identities under a controlled test domain; no real phone/address/clinical data |
| Authentication | Independent high-entropy JWT access/refresh secrets; Mongo-backed throttle collection; exact trusted proxy networks |
| Frontend/API | Separate HTTPS hostnames and exact CORS origins; Secure cookies validated behind the real staging proxy |
| Reports | Separate clinical and laboratory approved/quarantine roots or buckets, scanner service, owner-only service access, staging-only retention; the current filesystem adapter requires each pair on one filesystem for atomic promotion |
| Payments | `disabled` initially; separately authorized Razorpay Test Mode keys/webhook secret only; never live credentials |
| Webhooks | Dedicated public HTTPS staging endpoint, restricted observability, test events only |
| Network | Database/storage/scanner private; API ingress restricted; administrative access through approved identity/VPN controls |
| Secrets | Approved secret manager/environment injection; no `.env` commit, chat paste, image, log, frontend `VITE_*`, or build artifact |
| Observability | Staging-specific logs/metrics; redact credentials, tokens, signatures, report content and patient fields; restricted retention/access |

## Approval gates

1. Owner names the exact environment and confirms it contains no normal data.
2. Infrastructure owner creates network, database, storage and secret resources.
3. Security owner approves ingress/proxy CIDRs, scanner adapter and log policy.
4. Application owner verifies presence/format only—never secret values.
5. Database owner approves initialization of application collections/indexes,
   including auth rate-limit unique/TTL indexes. This is not authorization for a
   normal/protected database.
6. Payment owner separately authorizes Test Mode after non-payment workflows pass.
7. Test owner approves fictional dataset and cleanup/retention procedure.

## Startup sequence

1. Supply the exact staging deployment/database/storage/proxy identity; invalid or
   incomplete settings must terminate before any connection.
2. Keep payments and reconciliation disabled.
3. Verify DNS/TLS, exact origins, Secure/SameSite cookies and proxy overwrite of
   forwarding headers.
4. Initialize only the new empty staging database under explicit approval.
5. Verify throttle and application indexes; do not create production indexes.
6. Verify both clinical and laboratory approved/quarantine storage separation
   and scanner health. Until then, every PDF upload must return 503.
7. Create fictional accounts through approved application/admin paths.
8. Run authentication/authorization smoke tests, then the connected workflow plan.
9. Enable Razorpay Test Mode only after a separately reviewed configuration-policy
   change; the current staging startup policy rejects all payment enablement.

## Data and cleanup rules

- Use obvious fictional names and `example.com` addresses; use reserved test
  phone/address values approved for the environment.
- Never seed by pointing repository scripts at an existing/normal database.
- Do not reuse production IDs, exports, PDFs, payment IDs or webhook payloads.
- Cleanup is an owner-approved environment procedure, not an ad hoc destructive
  command. Preserve only sanitized test evidence and required audit records.

## Infrastructure still required

No cloud, database, scanner, object storage, DNS, certificate, proxy, webhook or
payment resource was created or modified. Those actions require explicit target
authorization and accountable infrastructure owners.
