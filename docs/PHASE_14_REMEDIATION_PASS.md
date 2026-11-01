# Phase 14 Remediation Pass

Assessment date: 2026-11-01

Status: **Local locked backend verification PASS; connected staging blocked**

This pass responds to the independent Phase 14 review. It did not connect to a
database, create indexes, run migrations, contact a payment provider, deploy, or
use normal patient data.

## Finding disposition

| Finding | Disposition | Local outcome |
|---|---|---|
| H1 cross-patient laboratory booking mutation | Fixed locally | Report creation requires explicit actor context, verifies patient and booking ownership/state, and atomically changes only the matching confirmed booking. A stale claim prevents report insertion; an insert failure conditionally restores the booking. |
| H2 staging isolation not enforced | Fixed locally | A strict environment enum and staging identity/database/host/storage/CORS/proxy/throttle/payment checks run during settings validation, immediately before database initialization, and before any worker can start. |
| M1 inconsistent direct-object responses | Fixed locally | Doctor appointment update, patient cancellation, report download and laboratory withdrawal now return the same generic 404 for missing and unauthorized objects. |
| M2 connected Mongo/multi-worker validation | Prepared, blocked | A deterministic opt-in contract test is hard-guarded to an acknowledged loopback database. It is skipped by normal runs and was not executed in this pass. Real proxy and multi-worker staging evidence remains required. |
| M3 operational scanner missing | Blocked, fail-closed | The default remains unavailable. Staging rejects `PDF_SCANNER_MODE=approved` until an approved adapter is implemented and reviewed; uploads return 503 meanwhile. |
| M4 arbitrary scanner audit metadata | Fixed locally | Scanner engine/reason values are normalized to a bounded safe-token grammar with fixed fallbacks. |
| M5 clinician access policy inconsistency | Documented and constrained | Mutation uses the primary-clinician assignment. Read-only history/released-lab access uses a non-pending appointment treatment relationship. No access was broadened. |
| L1 registration timing | Mitigated, residual accepted | New and duplicate paths share validation, hashing and lookup before branching. Inserts/profile creation still make perfect timing equivalence impossible; no such claim is made. |
| L2 implicit admin service defaults | Fixed locally | Care-plan (including stage and goal mutation), exercise-assignment, report and legacy booking mutation services require explicit actor context; missing context is denied. Exercise assignment creation rejects patient actors, and patient status updates check ownership inside the service. |
| L3 dependency version comparison | Fixed locally | Tests compare normalized package names and exact pinned versions between direct and locked requirements. |
| L4 silent cleanup failure | Fixed for visibility | Cleanup failures emit a category and exception type without storage keys, paths or clinical data. Cleanup can still require operational reconciliation after filesystem failure. |

## Clinician access policy

- The primary clinician recorded on the patient profile may create or mutate care
  plans, exercise prescriptions, clinical reports and linked legacy laboratory
  booking state.
- A clinician with a non-pending appointment relationship may read the limited
  assigned-patient directory, appointment history and released laboratory reports.
- A historical appointment does not grant prescription or report-mutation rights.
- Patients remain owner-scoped. Administrators remain explicitly role-scoped.
- Missing, malformed and unauthorized direct objects use nondisclosing responses.

## Concurrency boundary for diagnostic reports

The report service first validates actor, patient, booking ownership and confirmed
state. Immediately before insertion it performs one atomic compare-and-set on the
booking ID, patient ID and `confirmed` status. Only the winner may insert a report.
If insertion raises, a conditional compensation changes that same booking from
`completed` back to `confirmed`; compensation failure is logged without identifiers.
This prevents ordinary stale/concurrent requests from creating a report or changing
an unrelated booking. Connected Mongo testing remains an evidence gate.

## Remaining gates

- Execute the opt-in Mongo contract only against the approved empty isolated test
  database, then run at least two real backend workers.
- Verify the actual proxy overwrites forwarding headers and matches the configured
  trusted CIDRs.
- Implement and approve an operational malware scanner adapter before enabling PDF
  uploads in staging.
- Run the connected IDOR/browser matrix with fictional data.
- Obtain clean CI, dependency audit and secret-scan evidence for the final commit.

This document records local source changes and the limits of their verification.
It does not establish Phase 14 acceptance or production readiness.

## Earlier offline verification attempt — 2026-11-01

- Frontend contracts: **59 passed**. Lint, production build and the 73-asset
  bundle budget passed. Python source/test compilation and `git diff --check`
  passed.
- The focused security, API contract and full backend suites were each attempted
  on the current tree and each stopped before collection: the available Python
  3.13 installation lacks `pytest_asyncio`. A clean Python 3.13 virtual
  environment was created, but `uv pip install --offline -r requirements.lock`
  could not resolve the pinned graph. No registry was contacted because this pass
  excludes external services. The earlier independent review's **45/109/382**
  results predate the latest care-plan and exercise actor/ownership corrections
  and their regression tests; they are historical evidence, not a fresh pass
  for this tree.
- Run all three backend suites from a clean Python 3.13 locked environment in
  approved CI before accepting this remediation.

### Exact offline dependency gap

An offline, no-dependencies resolution probe checked every one of the **48**
exact lock entries against the local uv cache for Python 3.13. **38** entries
were unavailable at their pinned versions (including compatible wheels):

```text
annotated-doc==0.0.5                 anyio==4.15.1
bcrypt==4.0.1                        beanie==2.2.0
certifi==2026.10.23                  cffi==2.1.1
charset-normalizer==3.5.2           cryptography==50.0.2
dnspython==2.9.1                     email-validator==2.3.0
fastapi==0.162.0                     httptools==0.9.0
idna==3.20                          iniconfig==2.3.1
lazy-model==0.4.0                    motor==3.7.1
opentelemetry-api==1.45.2           passlib==1.7.4
pluggy==1.7.0                       pycparser==3.12
pydantic==2.14.2                    pydantic-core==2.50.2
pydantic-settings==2.16.2           PyJWT[crypto]==2.15.0
pymongo==4.19.0                     pytest==9.2.0
pytest-asyncio==1.4.1               python-dotenv==1.2.4
python-multipart==0.0.33            razorpay==2.0.1
requests==2.34.2                    starlette==1.10.0
tzdata==2026.6                      urllib3==2.8.0
uvicorn==0.54.0                     uvloop==0.23.0
watchfiles==1.3.0                   websockets==17.4
```

This was an offline-cache availability result, not a claim that these versions
do not exist in an approved registry. The later clean locked run below
supersedes this earlier local verification status.

## Clean locked backend verification — 2026-11-01

With package-registry access approved for this turn, a new temporary Python
3.13 virtual environment installed `backend/requirements.lock` successfully.
The install changed no repository dependency file. `pip check` found no broken
requirements. Fresh runs on the current uncommitted tree:

| Gate | Result |
|---|---|
| Focused security/remediation set | **89 passed** |
| API contract suite | **109 passed** |
| Full backend suite | **424 passed, 1 skipped** |

The sole skip is the opt-in connected Mongo contract, which requires a separately
acknowledged isolated loopback database. No database, staging, scanner, cloud or
payment service was contacted. This is a **PASS for local backend verification**,
not a connected staging or production approval. Hosted CI remains unrun because
the changes are uncommitted and no push was authorized.
