# Phase 15 first-deployment architecture options

Assessment: 2026-11-01. **Recommendation only; no resource created, subscription purchased or deployment performed.** Select the final host after staging evidence and clinic-owner approval.

## Current application constraints

- React is a static production build; FastAPI runs on Python 3.13 with exact-pinned dependencies. Configure one HTTPS public frontend/API origin pair, strict CORS and trusted ingress CIDRs. Security headers and TLS/HSTS must be verified at the ingress; the current local build alone does not prove them.
- The new scanner adapter uses a **Unix socket** and therefore expects a co-located `clamd` daemon or a securely shared local socket. It cannot directly use an independent remote scanner service. Its signature freshness, memory and health require monitoring.
- Clinical files use private filesystem quarantine and approved directories with atomic same-filesystem promotion. This design needs encrypted persistent storage, access controls, backup/restore and retention. It is not yet a private object-storage adapter and is not suitable for arbitrary independent backend hosts sharing no volume.
- Mongo requires dedicated credentials, restricted network, unique/TTL indexes, connected race tests and tested backup/restore. Payments remain Test Mode only after separate approval; no live billing or refunds.

## Comparison

| Candidate | Fit and benefit | Cost/operations risk | Recommendation |
|---|---|---|---|
| Static frontend + one controlled Linux VM for FastAPI and co-located `clamd` + managed Mongo | Direct fit for the current Unix socket and filesystem design; can run two API workers on one host and use a private encrypted disk | VM patching, firewall, disk backups, uptime, ClamAV signatures, restore and incident response are owner responsibilities; single-host outage | Lowest-complexity **conditional pilot** if the owner funds operations and proves restore/rollback; no production approval yet |
| Static frontend + managed container app with `clamd` sidecar/shared private volume + managed Mongo | Better managed compute and scaling path | Platform must support sidecar/socket/volume semantics; persistent volume and scanner RAM raise cost; multi-host files still require a reviewed shared/object-storage design | Suitable after platform-specific proof and storage architecture work |
| Static frontend + separate PaaS backend and separate scanner TCP service | Convenient deployment UI | Current adapter is Unix-only; `clamd` TCP is unauthenticated/unencrypted, and local files are not shared; needs a new protected transport/storage design | **Do not deploy current code this way** |

Free tiers are appropriate for learning or disposable staging previews, not this clinical production workload. Render's own free-tier guidance says not to use free services for production; ClamAV's official container guidance calls for substantial memory (minimum 3 GiB, preferred 4 GiB). MongoDB Atlas documents Flex as lower-cost development/low-traffic use and Dedicated as the tier with granular backup features; tier selection must follow load, backup and compliance requirements, not only price. Cloudflare Pages can host the static frontend subject to its plan limits. Current vendor references: [Render free guidance](https://render.com/docs/free), [Render plans](https://render.com/pricing), [MongoDB Atlas tier comparison](https://www.mongodb.com/docs/atlas/billing/atlas-flex-costs/), [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/), [ClamAV memory guidance](https://docs.clamav.net/manual/Installing/Docker.html). Verify prices and terms again when purchasing.

## Required production controls

Use managed HTTPS/TLS, HSTS and sensible CSP/referrer/content-type headers; a locked-down reverse proxy; least-privilege service accounts and private firewall paths; secret management/rotation; Mongo network restriction and backups; private encrypted report storage with retention; scanner updates/alerts; redacted structured logs and error/uptime monitoring; restore and rollback rehearsals; incident response and access review. Keep staging and production credentials, databases, volumes, hostnames and backups separate. Test every index/migration and restore against an isolated target before touching production.

## Clinic configuration template and fail-closed decision

The owner must fill and approve the existing structured template in `docs/PHASE_13_CLINIC_CONFIGURATION.md`: operating hours/working days/holidays, clinician schedules, 30-minute slot policy or requested duration changes, cancellation cutoff, travel buffers and home-visit coverage, authoritative lab catalogue/prices/capacity, refund policy, report retention and operational owners. None of those values is asserted here. The current demo defaults and published clinician blocks are **not** proof of approved clinic policy. Do not expose booking for an unapproved clinic configuration; disable unsupported home visits, priced laboratory booking and rescheduling until implemented and tested. Verify that absent/unpublished schedules yield no bookable slots in connected staging, then add a production configuration gate before launch.

Architecture decision: **pending** clinic policy, hosting/operations owner, security review and isolated staging evidence. Do not deploy based on this comparison alone.
