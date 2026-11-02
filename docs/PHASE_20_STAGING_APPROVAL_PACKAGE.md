# PhysioCare Phase 20 — Staging approval package

Assessment: 2026-11-01. Branch: `codex/physiocare-integration-2026-10-31`; reviewed HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`. **Planning and approval only.** No provider, region, domain, person, budget, database, or data-retention policy is approved by this document. Existing uncommitted Phase 16–19 work remains in place.

**Status: staging BLOCKED; production NOT READY. Decision on this package: READY FOR STAGING APPROVAL.** This means the choices and gates are ready for the owner to review. It does not mean staging is approved, provisioned, tested, or safe for real patient data.

## 1. Executive summary

The application has a React/Vite frontend, FastAPI API, Mongo/Beanie persistence, staging and production configuration guards, private PDF quarantine, a Unix-socket ClamAV adapter, and offline security tests. These controls need an operational environment before authenticated browser, multi-worker/proxy, scanner, TLS, backup, and connected transaction claims can be made. All seven operational roles are **UNASSIGNED**. The initial staging scope should be fictional data only, with payments and reconciliation disabled.

**Conditional recommendation:** use a single 16 GiB API/scanner host, a dedicated Atlas M10-or-higher staging cluster, a private persistent POSIX volume, HTTPS frontend/API ingress, a locked secret store, and separately restorable database and file backups. The concrete provider, region, network route, budget, and owner assignments require approval. A smaller 8 GiB host is a lower-cost conditional option if scanner and two-worker load tests prove adequate. A two-host architecture needs shared POSIX storage and more integration validation. The named products below are comparison candidates, not procurement decisions.

## 2. Current application readiness and evidence

| Area | Verified local fact | Operational state |
| --- | --- | --- |
| API/runtime | Python 3.13 FastAPI; pinned `backend/requirements.lock`; `backend/app/main.py` validates runtime configuration in lifespan before database initialization and checks configured ClamAV readiness. `backend/run_production.py` is a production-only launcher; staging needs a reviewed process-manager/ASGI launch with `ENVIRONMENT=staging` and lifespan enabled. | No staging process, host, worker or restart evidence. `/health` is lightweight and is **not** dependency readiness. |
| Configuration | `backend/staging.env.example` shows `STAGING_INSTANCE_ID=physiocare-isolated-staging`, exact `physiocare_staging` identity, HTTPS CORS, trusted proxy list, private storage paths, TLS-enabled credentialed Mongo URI, and disabled payments. Startup guards reject unsafe staging identity/TLS. | Template values are synthetic; no real host, certificate, credential or network has been approved. |
| Auth/booking/authorization | Phase 18 local changes cover logout/login failure states, account-profile atomic writes, and a non-demo schedule gate. Auth throttling uses Mongo-backed state. | Two-worker proxy identity, role-negative browser journeys, actual published schedules and connected registration rollback are unverified. |
| Reports/scanner | Clinical and laboratory uploads use private quarantine, bounded 5 MiB defaults, scanning abstraction, fail-closed behavior and cleanup audit. The scanner adapter connects to a local Unix socket. | No approved daemon/signature-update service or persistent private staging storage. Cleanup reconciler is an explicit operation, not an automatic startup job. |
| Verification | Latest recorded unchanged backend full-suite run after startup hardening: **651 passed, 3 opt-in connected tests skipped, 1 pytest plugin warning** (see [production readiness report](PRODUCTION_READINESS_FINAL_REPORT.md)). Phase 18 frontend follow-up recorded **95 tests passed**, lint/build/bundle pass. A separately approved Phase 15 report transaction test passed once against a dedicated **local** replica set. | These are recorded results, **not fresh Phase 20 tests** and not staging evidence. Authenticated browser tests remain [NOT RUN](PHASE_15_BROWSER_TEST_RESULTS.md); independent security review remains open. |

This assessment reviewed the [Phase 16 report](PHASE_16_OPERATIONAL_READINESS_REPORT.md), [Phase 17 inventory](PHASE_17_STAGING_INFRASTRUCTURE_PLAN.md), [Phase 18 assessment](PHASE_18_LOCAL_DEVELOPMENT_REPORT.md), [Phase 19 verification](PHASE_19_LOCAL_RELEASE_VERIFICATION.md), [production readiness report](PRODUCTION_READINESS_FINAL_REPORT.md), and the three backend configuration templates. It did not run code, tests, services, or connected checks.

## 3. Proposed staging architecture

**Candidate B, subject to approval and sizing:** React/Vite static build on a managed HTTPS static host → exact staging frontend origin → HTTPS reverse proxy/API hostname → two FastAPI workers on one 16 GiB Linux host. The host runs an approved `clamd` on a private Unix socket and mounts a persistent encrypted POSIX volume containing four separate laboratory/clinical approved/quarantine directories under `STAGING_STORAGE_ROOT`. The API alone reaches a dedicated, empty `physiocare_staging` Atlas M10+ cluster through verified TLS and a restricted source allowlist. A fixed-egress IP is required if public Atlas access is used; the network design must be approved before selection. Secret injection, logs/alerts, daily DB and file backups, and an isolated restore destination are separate controls. The database name and staging instance ID are code requirements, not an invitation to create them now.

Frontend build: locked `npm ci`, production build, exact public `VITE_API_URL` for the approved API origin, no secrets in Vite variables or bundles, HTTPS, direct SPA route handling and rollback to a known build. Provider-assigned domains can work for a fictional proof if stable and approved; custom names, DNS ownership, certificate renewal and rollback must be recorded before sustained staging. The API service must run non-root, with bounded workers and resources, a process manager with restart/rollback, explicit `ENVIRONMENT=staging`, ASGI lifespan enabled, and only the reverse proxy exposed. Do not use the reload-enabled development runner or `run_production.py` for staging. Two workers on one host exercise shared Mongo throttling while keeping the current local-socket/storage design coherent. One host is a failure domain.

## 4. Alternative architecture comparison

| Option | Provider and purpose | Security capabilities | Limitation, complexity and condition |
| --- | --- | --- | --- |
| **A. Lowest-cost viable candidate** | Cloudflare Pages Free for static frontend; DigitalOcean Basic 8 GiB/4 vCPU VM for reverse proxy, two API workers and `clamd`; private 50 GiB DO Volume; Atlas dedicated M10+; private encrypted backup export in DO Spaces. | HTTPS frontend/API; restricted host ingress; dedicated TLS-verified DB and account; POSIX quarantine/approved files; independent DB/file backups. | **Conditional** on a measured two-worker+scanner memory/load pass, approved fixed-egress Atlas allowlist, and an actual restore. Single API host and attach-one-VM volume are failure domains. If it fails sizing, it is not viable; move to B. Medium-high operations. |
| **B. Balanced recommendation** | Same services and controls, with 16 GiB/8 vCPU DO VM, 100 GiB private volume, larger snapshots and explicit monitoring/backup allowance. | More memory headroom for ClamAV (which [recommends 3–4 GiB](https://docs.clamav.net/manual/Installing/Docker.html)), two workers and cleanup; M10 dedicated backup and network options. | Still one API host. DO-to-Atlas is not automatically a private endpoint; fixed source allowlist + verified TLS needs security approval or a same-cloud private redesign. Daily restore and capacity tests remain mandatory. Medium-high operations. |
| **C. More reliable, production-oriented candidate** | AWS-hosted static frontend (S3/CloudFront or equivalent), two 8 GiB EC2 API/scanner hosts behind an ALB, EFS Standard shared private POSIX file storage, Atlas M10+ on AWS with a supported private connectivity design, AWS secret/log/backup services. | Removes a single API host; private DB network path is possible if exact region and endpoint arrangement are approved; shared storage enables both hosts to see the same report paths. | **Architecture change to validate**, not drop-in readiness: EFS permissions, atomic file promotion, latency, scanner socket on each host, two-host concurrency and recovery must pass. ALB, EFS, NAT/egress, log, backup and endpoint charges can be material. High operations. |

Free Atlas M0 or Flex is **not recommended for this full matrix**: [Flex](https://www.mongodb.com/docs/atlas/reference/flex-limitations/) lacks private endpoints, continuous/PITR backup and test-primary-failover support; free tiers add more limits. They can support disposable exploration under a separate narrow scope, not the required connected and recovery gates. A DO Volume [attaches to one Droplet at a time](https://docs.digitalocean.com/products/volumes/details/limits/), so placing API workers on two DO hosts with a single Volume would be unsafe. Object storage is a **backup target only** in A/B; the current report code expects local POSIX paths and atomic rename, so a live-object-store substitution would require application changes and new tests.

## 5. Estimated monthly costs

**Pricing basis, checked 2026-11-01:** DO Basic [8 GiB $48 / 16 GiB $96](https://www.digitalocean.com/pricing/droplets); DO Volume [$0.10/GiB-month](https://docs.digitalocean.com/products/volumes/details/pricing/); DO basic daily VM backup [30% of VM cost](https://docs.digitalocean.com/products/backups/details/pricing/); Volume snapshot [$0.06/GiB-month](https://www.digitalocean.com/pricing/volumes); DO Spaces [$5/month base](https://docs.digitalocean.com/products/spaces/details/pricing/); Atlas dedicated M10+ [starts around $60/month and backup/transfer may add charges](https://www.mongodb.com/docs/atlas/billing/billing-breakdown-optimization/); [Cloudflare Pages Free limits](https://developers.cloudflare.com/pages/platform/limits/). Prices are provider list prices, **not quotes** for an approved region. INR uses a **planning assumption of ₹96/USD**, not a verified billing exchange rate; actual INR, taxes and foreign-exchange charges vary. No provider credit is assumed.

| Option | Arithmetic from published prices | Conditional monthly planning amount | Backup/storage and omissions |
| --- | --- | --- | --- |
| A | $48 VM + $60 M10 floor + $5/50 GiB Volume + $14.40 daily VM backup + $3/50 GiB Volume snapshot + $5 Spaces = **$135.40 floor** (₹12,998). | **$145–190+** (₹13,920–18,240+) after a provisional allowance for DB backup/monitoring; not a quote. | Separate VM and Volume backups are counted. Atlas backup usage, Spaces overage, DNS, egress, monitoring, taxes and restoration capacity remain unpriced. |
| B | $96 VM + $60 M10 floor + $10/100 GiB Volume + $28.80 daily VM backup + $6/100 GiB Volume snapshot + $5 Spaces = **$205.80 floor** (₹19,757). | **$220–270+** (₹21,120–25,920+) after provisional DB backup/monitoring allowance. | Same omitted variable costs. More file capacity and VM memory do not prove throughput or restore time. |
| C | Two AWS t3.large at [about $0.0835/h each](https://aws.amazon.com/ec2/instance-types/t3/) × 730 h = ~$122; [ALB hourly base ~$16.43 plus usage](https://aws.amazon.com/elasticloadbalancing/pricing/); 100 GiB [EFS Standard illustrative ~$30](https://aws.amazon.com/efs/faq/); Atlas M10+ floor $60 = **~$228 floor** (₹21,888), before frontend. | **$300–500+** (₹28,800–48,000+) planning envelope. | EBS, EFS throughput/backup, ALB LCUs, private endpoint/NAT, logs, DNS, frontend/CDN, DB backup and data transfer need a regional quote. Two-host architecture validation also costs engineering time. |

The provisional A/B planning envelopes are **estimates**, not verified provider prices or approved budgets. Before any purchase, obtain an exact region/service quote including Atlas backup policy, dedicated database storage, egress, monitoring, DNS, certificate operation, taxes and retention. Set a spend cap and alerts. No clinic data is budgeted for staging.

## 6. Fourteen-component infrastructure inventory

All entries are **UNAPPROVED / NOT PROVISIONED**. “Accept” describes future evidence, not a completed test.

| # | Component | Required identity/dependency and future acceptance |
| --- | --- | --- |
| 1 | Frontend host | Exact HTTPS origin, locked build, direct SPA routes, secret-free bundle, rollback and approved `VITE_API_URL`. |
| 2 | API host/process | Python 3.13 lock, non-root process, two workers, ASGI lifespan, bounded resources, restart/rollback, approved staging selectors. |
| 3 | MongoDB | Empty dedicated `physiocare_staging`, least-privilege credential, writable replica-set primary, transaction and index evidence; no shared production/development data. |
| 4 | Mongo TLS/hostname | Exact approved hostname/CA, `tls=true`, trusted chain/SAN, rejected plaintext/bypass/invalid CA or hostname. |
| 5 | Private PDF storage | Persistent encrypted private POSIX mount, distinct lab/clinical approved/quarantine paths, same-filesystem promotion and 0700/0600 access. |
| 6 | ClamAV | Approved daemon/signatures, private socket permissions, readiness/freshness monitoring, safe fixture detection, outage fail-closed. |
| 7 | Reverse proxy | Exact trusted CIDRs, forwarded-header overwrite, direct API blocked, two-worker client identity preserved. |
| 8 | HTTPS API ingress | Stable name, matching certificate, renewal/redirect/security-header checks, exact CORS and secure-cookie/CSRF browser behavior. |
| 9 | Payment webhook ingress | **DEFERRED**. Code route exists; no Test Mode or live provider contact under initial payment-disabled staging guard. Separate design/approval required. |
| 10 | Secret delivery | Separate staging JWT/Mongo/CA materials, restricted access, rotation/revocation audit, no secrets in Git, logs or frontend. |
| 11 | Logs/monitoring | Restricted API/proxy/Mongo/scanner logs, actionable alerts and redaction checks with named responder. |
| 12 | Backups/restore | Encrypted DB and file copies, age/integrity monitoring, isolated restore and consistency verification under approved RPO/RTO. |
| 13 | DNS/domain | Owner, exact staging frontend/API names, renewal/rollback and no production hostname reuse. |
| 14 | Network controls | Firewall and egress policy; only approved HTTPS ingress, DB source restriction, no external scanner/socket or admin port. |

## 7. Network and security design

The approval packet must record the exact region, frontend and API origins, DNS/cert owner, proxy address ranges, API bind interface, DB DNS/IP allowlist or private endpoint, administrative access path and egress rules. The reverse proxy must **overwrite** client-IP forwarding headers and the application must trust only its exact CIDRs; untrusted direct forwarded headers must not alter rate-limit identity. Publish only HTTPS. Configure `CORS_ORIGINS` for exact approved origins and verify credentialed cookies/CSRF in a real browser. Limit host administration to named operators with MFA and audit trails; restrict outbound traffic to approved DB, OS/signature update, backup and monitoring destinations. Frontend bundles and public logs must contain no secrets, synthetic clinical values, tokens, or report URLs.

## 8. Database and TLS requirements

The staging guard requires exact `STAGING_INSTANCE_ID=physiocare-isolated-staging`, `DATABASE_NAME=STAGING_DATABASE_NAME=physiocare_staging`, a URI host matching `STAGING_DATABASE_HOST`, credentialed non-loopback Mongo URI and explicit TLS without certificate/hostname bypass. This is structural validation only. Before any connection or mutation, an assigned database operator must independently verify the approved host, replica-set name, server version, PRIMARY, exact empty target, credential grants, CA chain and hostname, and absence of production data. Test invalid CA/name and plaintext failure without logging URIs. Review MongoDB [transaction prerequisites](https://www.mongodb.com/docs/manual/core/transactions-production-consideration/), unique/TTL indexes and backup configuration. Collection/index creation, connected tests and any cleanup need separate exact-target approval; do not reuse the local Phase 15/19 contract databases.

## 9. PDF storage and scanner design

Mount private persistent storage outside web roots. Use the four configured paths below one absolute `STAGING_STORAGE_ROOT`, with quarantine/approved pairs on the **same filesystem** for `os.replace` promotion; deny public bucket/CDN or direct static serving. The app's default PDF cap is 5 MiB per report type, subject to clinic-approved limits. Prove 0700 directories, 0600 files, encryption, backup, no report retrieval before release, and no cross-patient retrieval. Co-locate an approved `clamd` with the API on a Unix socket accessible only to the service identity; operate signature updates and alert on stale definitions. A disabled scanner is acceptable only before enabling PDF upload tests, not a scanner acceptance pass. Use a safe EICAR fixture and synthetic valid/invalid PDFs; clean files promote, malware/timeout/outage reject, quarantine remains private, and failures are audited. Run the explicit cleanup reconciler only under a reviewed schedule, healthy DB and target-specific authorization, with pending-cleanup counts and alerts.

## 10. Backup and recovery plan

**Proposed target, not approved policy:** daily DB and file backups, backup age ≤24 h, an isolated restore completed within 4 h, and a matching record/file inventory after restore. The owner must set actual RPO/RTO, retention, jurisdiction and immutable/offsite expectations before setup. Database backups and private PDF snapshots must be separately restorable; VM backups do not cover an attached DO Volume automatically. Encrypt and restrict backup copies and keys. Restore into a new isolated target, never over staging or production. Compare synthetic identifiers and checksums, record missing/orphan file count, simulate a failed restore, verify rollback and clean up only the test restore after approval. A backup job without a completed restore test is **FAIL** for this gate.

## 11. Monitoring and incident response

Define synthetic alerts for API process/lifespan failure, 5xx and auth anomalies, proxy client-IP mismatch, Mongo primary/TLS/latency, scanner PING and signature age, malware detection, failed uploads, `CleanupPending`, private-disk capacity, certificate expiry, backup age/failure and restore failure. The `/health` endpoint alone does not prove dependency readiness; a private readiness check or operator probe must independently verify dependencies without exposing configuration. Logs must omit credentials, cookies, signatures, PDF bytes, patient fields and full private paths. Set approved retention and access; test that an assigned responder receives a fictional alert and records acknowledgment, escalation and recovery. No on-call person is assigned yet.

## 12. Seven-role operational ownership register

All current owners and acceptances are **UNASSIGNED / NOT ACCEPTED**. One person may hold multiple roles only with explicit coverage and conflict review. “Backup” below means a deputy operator, not data backup.

| Role / current owner | Responsibilities and required knowledge | Minimum access | Deputy / incident duty |
| --- | --- | --- | --- |
| Project owner — **UNASSIGNED** | Approve scope, region, spend, data/clinic policies, RPO/RTO and go/no-go; understand release and privacy risks. | Read approval/evidence and billing summaries; no routine root access. | Deputy **UNASSIGNED**; incident commander and stakeholder decisions. |
| Backend operator — **UNASSIGNED** | Python/FastAPI startup, workers, configuration, auth/booking/report contracts, rollback. | Scoped API deploy/config and sanitized logs. | Deputy **UNASSIGNED**; isolate bad worker, roll back API, coordinate cleanup. |
| Frontend operator — **UNASSIGNED** | Vite build/origins, CORS/browser/cookie journeys, static rollback. | Scoped static-host release and public diagnostics. | Deputy **UNASSIGNED**; revert bundle/cache and triage browser incident. |
| Database operator — **UNASSIGNED** | Mongo identity, least privilege, TLS, indexes, transaction/backup/restore. | Scoped staging DB admin/backup access, never production by default. | Deputy **UNASSIGNED**; restore isolated DB and reconcile consistency. |
| Security/scanner operator — **UNASSIGNED** | ClamAV/signatures, socket, ingress trust, secrets, redacted alert review. | Scanner/proxy/security controls and restricted logs. | Deputy **UNASSIGNED**; stop unsafe uploads, rotate affected staging secrets. |
| Payment integration operator — **UNASSIGNED** | Separately authorize Test Mode, keys/webhook/reconciliation and finance evidence. | Future Test Mode dashboard only; no live funds. | Deputy **UNASSIGNED**; disable test callback and reconcile test events. |
| Deployment operator — **UNASSIGNED** | Host/network/DNS/cert/file-system runbook, change window, rollback. | Scoped staging infrastructure access. | Deputy **UNASSIGNED**; revert deploy/network and coordinate recovery. |

## 13. Strict fictional-data and privacy policy

Only run-scoped fictional patient, therapist, administrator, receptionist and laboratorian identities may be used. Use reserved example-domain emails, non-routable/example contact details, invented names and synthetic appointment, care-plan and laboratory data. Never import a production dump, real patient name/phone/record, real clinical PDF, live payment identifier or contact list. Synthetic PDFs must be generated specifically for testing, clearly marked, and contain no copied case narrative. Payment scenarios are simulated offline initially; provider Test Mode requires separate authorization and fictional payment identities. Verify source datasets and fixtures by provenance review before upload, scan for real-person/contact fields, and have the privacy/project owner sign the run manifest. Restrict staging and backups to named operators; redact test evidence.

**Proposed retention for approval, not current policy:** delete per-run records/files within 24 h after evidence is captured; nightly orphan/expired-fictional-data check; keep sanitized logs for at most 30 days and encrypted backup copies for at most 30 days unless the owner chooses another period. The operator must record identifiers and expected collections/files before a run, confirm cleanup with independent counts after, and obtain explicit target-specific approval for deletion. Audit entries and backup retention must be considered separately; do not promise zero collections if tests create indexes/collections. No real patient data is permitted even if a retention policy is later approved.

## 14. Ordered connected-validation matrix

**Every row is future work. None was executed in Phase 20.** Before any row: approve exact target/origins, owners, fictional dataset and cleanup manifest; verify empty isolated DB and TLS identity; enable only that row's systems. Record sanitized run ID, configuration fingerprint, timestamp, actor/role, request/result status, worker ID where relevant, DB/file counts and rollback evidence. “PASS” means the stated expected result and independent evidence both match; any missing evidence, unexpected access, residual test record or unapproved target is **FAIL/STOP**. Do not run the current opt-in local connected files against staging by changing their hardcoded target guards; prepare separately reviewed staging-specific tests.

| Order / test | Prerequisite and procedure | Expected result and evidence / PASS criterion |
| --- | --- | --- |
| 0. Identity and isolation | Approved inventory; independently read server/DB/proxy/storage identities and empty DB; probe negative URI/TLS settings without mutation. | Exact staging identities, PRIMARY/replica set, empty target, no production path; sanitized identity and collection-count record. Any mismatch STOP. |
| 1. TLS/HTTPS/CORS | Approved CA, DNS, cert and origins; try valid browser/API and invalid CA, hostname, plaintext, foreign origin. | Valid chain/hostname and HTTPS work; invalid cases fail; capture cert metadata, status and redacted connection trace. |
| 2. Registration | Approved synthetic patient account, explicit collection/index scope; register and verify user/profile together; inject profile-write failure and retry. | One consistent pair on success; rollback leaves no orphan; retry succeeds; duplicate response preserves public neutrality. Evidence: scoped counts and statuses. |
| 3. Login, failure, logout | Synthetic role accounts; valid/invalid login, network/profile-fetch failure, logout success and revocation rejection/retry. | No false signed-in/out state; server session revoked on success; failed revocation remains unconfirmed and private UI hidden. Browser/API trace with redacted cookies. |
| 4. Expiry and CSRF | Short-lived synthetic session under approved test settings; expire/refresh; omit or alter CSRF token on mutations. | Expired session loses access; valid refresh policy works; CSRF-negative requests reject without mutation. Evidence: statuses and scoped counts. |
| 5. Role gates | Synthetic patient, therapist, admin, reception and lab accounts; exercise allowed and denied routes. | Only mapped roles act; denied calls have no side effects. Evidence: role/status/action matrix. |
| 6. Object ownership | Two synthetic patients and assigned/unassigned therapists; access appointments, care plans, exercises, lab requests and reports across identities. | Cross-patient/unassigned access rejected with established enumeration-neutral contract and zero mutation; authorized access works. Evidence: redacted IDs/statuses and counts. |
| 7. Booking/schedules | Publish synthetic clinician schedule; book/cancel, absent schedule, forbidden demo slot, conflicting slot and concurrent requests. | Non-demo booking requires published eligibility; one winning claim; no duplicate booking. Evidence: worker/request IDs and final DB counts. |
| 8. Transaction rollback | Replica-set PRIMARY; inject second-write failure for account and report/booking transaction; inspect records after abort and safe retry. | No partial account, report or booking-status state; retry safe. Evidence: before/after scoped counts and audit events. |
| 9. Worker failure | Two workers, synthetic in-flight request; terminate one under an approved reversible fault plan and retry through proxy. | Surviving worker serves; no duplicate/partial booking/report; restart restores capacity. Evidence: worker logs, response IDs and final counts. |
| 10. Proxy/IP/throttle | Exact proxy CIDRs; send trusted/untrusted forwarded headers and bursts distributed over both workers. | Untrusted headers ignored; real client identities stable; Mongo throttle aggregate applies across workers. Evidence: sanitized proxy and rate-limit counters. |
| 11. Clean/invalid PDF | Scanner ready, private volume; upload synthetic valid PDF and malformed/oversize/non-PDF samples in both lab and clinical flows. | Only clean valid file is released after authorization; other samples reject; no public/quarantine retrieval. Evidence: verdict/audit, file permissions and scoped counts. |
| 12. Malware/outage | Approved EICAR fixture, scanner timeout/down and stale-signature simulation in controlled staging. | Detection and outage/timeout fail closed in both upload paths; no approved file; alert fires. Evidence: scanner health/verdict and private storage inventory. |
| 13. Report retrieval/cleanup | Two synthetic patients; authorized release, cross-patient fetch, injected cleanup failure, explicit reconciler after DB-health check. | Owner-only download, audit trail, pending cleanup visible, reconciler removes only proven orphans. Evidence: redacted response, audit and before/after inventories. |
| 14. Backup/restore | Approved RPO/RTO; create DB and file backups of same fictional dataset, verify integrity, restore to *new* isolated destination. | Restored records match private files/checksums and permissions within targets; production/staging untouched. Evidence: backup timestamps, restore duration and count reconciliation. |
| 15. Browser journeys | Only after 0–14 prerequisites; synthetic accounts, approved origins, no live providers. Complete patient, therapist, admin, reception and lab positive/negative/error flows on desktop and mobile; keyboard/focus and screen-reader smoke. | Role journeys work, forbidden routes stay blocked, errors recover, no horizontal overflow/key traps; accessibility findings logged. Capture redacted screenshots/trace and per-case PASS/FAIL. |
| 16. Payment Test Mode — deferred | **Separate approval and compatible payment-enabled environment/design**; fictional provider test transactions only. | If later approved: signature/digest/dedup/retry/refund policy evidence with no live keys; until then **NOT RUN**, not a staging pass. |

## 15. Clinic decision register

All decisions are **UNAPPROVED**. Accountable functions are proposed; no actual person is assigned.

| Decision / proposed role | Current behavior and risk if unresolved | Clinic approval needed |
| --- | --- | --- |
| Clinician schedules / clinical operations | Demo slots are local only; real hours absent, so booking can be unserviceable. | Actual hours, holidays, assignment and publication owner. |
| Appointment duration / clinical operations | Configurable defaults, no approved visit length; capacity may be wrong. | Durations by service and buffer rules. |
| Booking horizon / clinical operations | Template suggests 30 days; this is not clinic policy. | Allowed advance window and exceptions. |
| Rescheduling / clinical operations | No first-class approved flow; manual changes may conflict. | Eligibility, notice, staff override and patient messaging. |
| Cancellation / clinical operations | Cancellation exists; rules/fees unapproved. | Cutoffs, exceptions, no-show handling. |
| Home-visit coverage / clinical operations | Demo geography is not service area; false promises possible. | Service area, eligibility and dispatch owner. |
| Travel buffers / clinical operations | Real routing/capacity rules absent. | Buffer and concurrent visit limits. |
| Laboratory catalogue / lab lead | Demo catalogue can misstate available tests. | Approved test list, specimen and result workflow. |
| Laboratory pricing / lab + finance | Demo prices are not approved charges. | Price list, tax and publication rules. |
| Collection capacity / lab lead | No confirmed live collection allocation. | Slots, staff coverage and escalation. |
| Email ownership / privacy owner | Registration lacks approved identity proof policy. | Verification, change-of-email and dispute procedure. |
| Account recovery / privacy owner | Support/recovery rules not clinic-approved. | Identity check, reset and support escalation. |
| Patient retention / privacy owner | Code cleanup does not define legal/clinical retention. | Consent, record/report/log/backup periods and deletion exceptions. |
| Refund policy / finance owner | Provider code does not decide refund entitlement. | Approval, timeline, ledger and dispute handling. |
| Payment requirements / finance owner | Staging payments disabled; live launch unapproved. | If/when Test Mode and live payments, pricing and reconciliation owner. |
| Notifications / clinic operations | Channels/templates/delivery expectations unapproved. | Consent, content, timing, retry and failure handling. |
| Staff permissions / clinic director | Code roles exist; actual duty boundaries unconfirmed. | Role-to-job mapping, provisioning and review cadence. |

The [production readiness report](PRODUCTION_READINESS_FINAL_REPORT.md) also records public clinic identity, incident coverage and backup targets as open decisions. They remain separate approval items even though the minimum register above names the 17 requested clinic decisions.

## 16. Infrastructure dependency order

1. Assign seven actual owners and deputies; approve fictional scope, clinic/privacy policy, region, cost cap, RPO/RTO and target inventory.
2. Select provider/service tiers, exact network route, DNS names, certificates and fixed ingress/egress identity. Obtain a regional all-in quote.
3. With separate provisioning approval, create isolated empty Mongo target, scoped credential/CA, private file mount, secret store and firewall. Verify identities **before any app or test mutation**.
4. Approve and operate `clamd`/signature updater and private socket; configure reverse proxy and two API workers with startup guards. Validate readiness/alerts.
5. Publish the secret-free staging frontend and complete TLS/CORS/cookie smoke; establish DB/file backup and isolated restore capability.
6. Obtain test-specific approvals and run the ordered fictional connected matrix with independent cleanup. Payment Test Mode remains separate.
7. Commission independent security/privacy review; resolve clinic decisions; repeat release verification and make a later production decision.

No dependency step is authorized simply because it appears in this order.

## 17. Risks and mitigations

| Risk | Proposed mitigation / release effect |
| --- | --- |
| One API/scanner host or one-attached Volume fails | Restore runbook and tested restart; accept only for staging. Production requires an approved resilient design. |
| DO-to-Atlas route is public or source IP changes | Fixed egress allowlist, TLS chain/name validation, restricted credentials and alerts; security owner must approve or choose same-cloud private endpoint. |
| ClamAV is unready/stale or exceeds host resources | Startup readiness, signature-age alert, load sizing, outage fail-closed test; uploads remain blocked until proven. |
| DB and file backups represent different points in time | Coordinated run manifest, DB/file reconciliation on isolated restore and explicit RPO/RTO. |
| Proxy trust is too broad | Exact trusted CIDRs, direct API block and negative spoofed-header/two-worker tests. |
| Synthetic dataset accidentally includes real details | Provenance review, fictional-only manifest, access review and independent cleanup. Any real-data finding is STOP. |
| Clinic policies or operators remain undefined | Do not open staging to clinic workflow acceptance or make production claims until signed. |
| Payment Test Mode conflicts with staging guard | Keep payments disabled; obtain separate design/code review and provider authorization before testing. |
| Costs exceed estimates | Regional quote, budget cap/alerts, retention plan and approval before creating resources. |

## 18. Approval checklist

- [ ] Project owner signs the fictional-only purpose, region/jurisdiction, privacy/retention, RPO/RTO, cost cap and stop conditions.
- [ ] All seven named operators and deputies accept duties, on-call coverage and least-privilege access.
- [ ] Provider/service tier and exact frontend/API/Mongo/backup/storage/scanner inventory are selected and quoted.
- [ ] Security owner approves TLS/CA, proxy CIDRs, fixed egress or private endpoint, firewall, CORS and secret delivery.
- [ ] Database owner approves the **exact empty** staging target, replica-set/backup/index scope and mutation plan.
- [ ] Clinical/privacy owner approves the synthetic dataset, evidence handling, cleanup and proposed retention.
- [ ] Scanner/storage owner approves daemon version/signature source, socket, private volume and restore method.
- [ ] Connected test owner approves each run's endpoints, cases, failure injection, expected writes and cleanup manifest.
- [ ] Payment operator separately approves any future Razorpay Test Mode; initial staging remains disabled.
- [ ] Deployment owner signs the rollback, incident, monitoring, backup-restore and spend-control runbooks.
- [ ] A separate, explicit **provisioning authorization** is recorded after reviewing the completed choices above.

## 19. Recommended architecture and decision

**Recommend Option B for owner review**, because one 16 GiB host provides a more defensible scanner/two-worker sizing starting point than an unbenchmarked 8 GiB host while retaining the current Unix-socket and POSIX storage model. Use M10+ only after confirming region, TLS, fixed-egress allowlist or approved private connectivity, backup cost and restore features. The **$220–270+/month (₹21,120–25,920+)** planning envelope is conditional; the priced component floor is **$205.80/month** before variable charges. If security requires a private DB endpoint rather than allowlisted public TLS, or if single-host recovery is unacceptable, re-quote Option C in one supported cloud and validate the shared-filesystem integration. Option A remains conditional on measured scanner/API capacity. None is selected today.

## 20. Conditions before provisioning and final disposition

No staging resource may be created until the project owner approves exact provider/region, seven owners/deputies, budget cap, network/DB/storage/scanner design, fictional dataset and retention, RPO/RTO, monitoring/restore plan, and a named provisioning operator. Provisioning approval must be a separate explicit action. Before any connected test, additionally approve the exact empty target, run-specific write/index scope, synthetic records, cleanup and independent verification. Before any browser test, approve the exact frontend/API origins and all required operational dependencies. Before production, require connected evidence, clinic policy decisions, independent security review and a separate release decision.

**Decision: READY FOR STAGING APPROVAL** as a reviewable decision package only. **Staging remains BLOCKED. Production remains NOT READY.** No infrastructure was provisioned or contacted; no real patient data, payment provider, database or scanner was used; no application source, actual `.env`, credential or Git commit/push was changed in Phase 20.
