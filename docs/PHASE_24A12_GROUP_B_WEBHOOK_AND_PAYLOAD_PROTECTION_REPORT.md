# Phase 24A.12 Group B — Webhook and Persistent-Payload Protection Report

Assessment and implementation date: 2026-11-02  
Branch: `codex/physiocare-integration-2026-10-31`  
HEAD: `5eaced696a156ca74233fd04252fea52345d8af8`  
Scope: offline Group B only; no Group C, Group D, or Phase 24B work

## 1. Executive summary

**Group B status: PASS WITH CONDITIONS.** The application now enforces a 256 KiB streamed fail-safe on its only registered webhook, rejects missing/invalid/oversized headers before reading the body, counts actual streamed bytes even when `Content-Length` is absent or false, and passes the original bytes unchanged to the existing signature-verification path. Oversized input cannot reach JSON parsing, the webhook ledger, payment state, appointment state, or entitlement behavior. No raw webhook payload is persisted or logged.

Non-upload API mutations now have a separate 1 MiB transport ceiling before framework JSON parsing. Confirmed persistent structures have string, item-count, nested-object, identifier, and numeric ceilings before service/repository calls. Mutation and response schemas are deliberately separate where legacy clinical data may exceed the new write limits, so this work neither rewrites old data nor invalidates read paths.

The conditions are external to the verified offline control: 256 KiB is a conservative application fail-safe, not a claimed Razorpay contract maximum; an approved connected test must confirm provider/proxy agreement. The 8,000/16,000-character clinical ceilings are generous technical storage safeguards, not clinic-approved semantic policy. Clinic owners may approve lower or different product limits later. These conditions keep client demonstration, staging, production, and Phase 24B unauthorized.

## 2. Initial Git state

Before Group B changes, the recalculated state matched the Group A handoff:

| Item | Initial state |
|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` |
| Upstream | `origin/codex/physiocare-integration-2026-10-31` |
| Ahead / behind | `0 / 0` |
| Tracked modified paths | 94 |
| Untracked paths | 78 |
| Total dirty paths | 172 |

The Group A report and all earlier tracked/untracked work were preserved. No reset, clean, checkout, restore, stash, commit, push, dependency change, or environment-file edit was performed. The Group A paths included its pagination core, three query repositories, backend/frontend Group A tests, affected API/service/repository/UI changes, and `docs/PHASE_24A12_GROUP_A_UNBOUNDED_RETRIEVAL_REMEDIATION_REPORT.md`.

## 3. Exact Phase 24A.11 findings addressed

The source-of-truth register identifies:

- **A11-M05 — Public webhook buffers an uncapped body before authentication.** Original evidence was `await request.body()` at public `POST /api/webhooks/razorpay`, before required-header rejection and signature verification, with no application cap.
- **A11-M06 — Persistent JSON models lack practical payload/list/string ceilings.** Original representative evidence covered public auth, appointment reason, legacy laboratory test IDs, nested care plans, exercise mutations, and the absence of a general JSON body cap.

This report does not edit the historical A11 documents.

## 4. Webhook entry-point inventory

Static router and decorator inspection found exactly one registered webhook:

| Route | Provider | Authentication boundary | Processing path | Persistence |
|---|---|---|---|---|
| `POST /api/webhooks/razorpay` | Razorpay Test Mode integration | Provider signature + event ID; no user cookie role | `api/payments.py:razorpay_webhook` -> bounded reader -> `PaymentService.handle_webhook` -> signature -> JSON -> digest/idempotency -> provider payment verification -> conditional payment/appointment update | Minimal ledger fields only: event ID, SHA-256 body digest, bounded provider order ID, status, timestamps. Raw or parsed payload is not stored. |

No other webhook decorator, route, provider handler, or generic callback route was found. Middleware did not previously read webhook bodies; the route itself performed the full unbounded `request.body()` read.

## 5. Original buffering behavior and root cause

The old route called `await request.body()` before checking required headers. Starlette therefore accumulated the entire unauthenticated body, trusted neither an application maximum nor a streamed counter, and only then entered provider configuration/header/signature logic. Missing length and chunked transfers had no application ceiling. The payment service correctly verified signatures before parsing JSON, but that trust boundary occurred after the memory allocation.

## 6. Bounded request-body strategy

`backend/app/core/request_limits.py:10-68` introduces one shared one-pass ASGI reader:

- `MAX_RAZORPAY_WEBHOOK_BYTES = 256 * 1024`;
- `MAX_JSON_REQUEST_BYTES = 1024 * 1024`;
- required webhook signature, event header, and provider entity identifiers are capped at 256, 128, and 128 characters respectively;
- a declared length greater than the cap is rejected before the receive channel is read;
- malformed, negative, or ambiguous lengths return 400;
- every actual chunk is counted, so absent or falsely small lengths cannot bypass the maximum;
- the first chunk that crosses the maximum causes 413 without appending that chunk to the application buffer;
- exact-limit bodies are accepted;
- the reader is intentionally single-use.

The unavoidable current ASGI chunk already exists outside this function when received; the application does not claim to bound server/proxy buffering before ASGI delivery. A `bytearray` is accumulated and converted once to immutable `bytes`, which Starlette and the signature service can reuse. No list of chunks or second application body buffer is created.

## 7. Limit evidence and limitations

The webhook handler consumes only an event name and payment/order identifiers. Existing synthetic provider events are small, so 256 KiB is a conservative fail-safe with ample margin. The repository contains no approved Razorpay payload-size contract and no approved ingress configuration. Therefore:

- **256 KiB is an application safety ceiling, not a provider-contract claim.**
- **CONTRACT VERIFICATION REQUIRED:** confirm the provider's supported maximum, proxy limit, chunking behavior, and representative signed events in approved isolated staging before enabling webhook traffic.

The 1 MiB ordinary-mutation ceiling is a technical envelope for small structured application records, not a clinical field policy. Specialized report multipart and laboratory PDF routes are excluded because they already use independent metadata/file streaming limits. The report metadata form string is capped at 64 KiB; clinical and laboratory PDFs retain their existing configured byte limits and quarantine/scanner behavior.

## 8. `Content-Length`, streaming, concurrency, and timeout behavior

The header is an early-rejection hint only. The actual stream count is always authoritative. Tests cover no header, false small, false large, negative, nonnumeric, comma-separated, chunked, exact-limit, and +1-byte cases. Falsely large lengths fail without a body read; falsely small lengths still fail on the actual counter.

Each request owns at most its configured application body buffer, so concurrent webhook memory scales by bounded in-flight requests rather than attacker-selected body size. This does not prevent connection-exhaustion, slow-client, ASGI-server-buffer, parser-amplification, or aggregate concurrency attacks. Proxy/server request timeouts, concurrency limits, and a matching ingress byte cap remain **ENVIRONMENT VERIFICATION REQUIRED**.

## 9. Middleware interaction

`backend/app/main.py:122-148` now bounds all `/api/` POST/PUT/PATCH/DELETE bodies before endpoint JSON parsing, regardless of a misleading content type. It excludes only:

1. Razorpay webhook, because its route applies the stricter 256 KiB reader;
2. clinical report multipart upload, which has 64 KiB metadata plus existing specialized file controls;
3. the laboratory raw-PDF route, which already counts the request stream against its configured PDF maximum.

The middleware stores the one bounded immutable body on the request for downstream reuse; tests prove a downstream body parse does not invoke the receive channel again. The existing unsafe-origin middleware remains outside the body-limit middleware, so a rejected browser origin is denied before reading. No middleware weakens signature handling or introduces a webhook pre-buffer.

## 10. Signature, parsing, acknowledgment, and privacy preservation

`backend/app/api/payments.py:115-129` rejects absent/overlong headers before reading and passes the exact returned bytes to `PaymentService.handle_webhook`. `backend/app/services/payment_service.py:675-719` retains the established order:

1. defensive direct-service/header size checks;
2. Test Mode configuration guard;
3. provider signature verification over the unmodified UTF-8 representation of the exact received bytes;
4. JSON parsing only after signature success;
5. body digest and ledger/idempotency work only after valid signed structured input.

Whitespace is not normalized and JSON is not reserialized before verification. Missing/invalid signatures remain 400. Malformed JSON, invalid encoding, non-object JSON, and malformed provider identifiers fail before database access. Application responses contain generic details and never echo a body, signature, secret, clinical text, or provider credential.

Oversize logs contain only route, fixed rejection category, observed byte count, and configured maximum. Signature/event values and payload contents are excluded. The observed count is not used as an attacker-controlled label.

## 11. Idempotency and payment-state behavior

No payment business rule was changed. Existing tests continue to cover exact raw signature input, invalid signatures before database access, digest-based replay detection despite a changed event header, conflicting event identity, duplicate capture finalization, captured/failed transitions, ownership/order/payment/amount/currency verification, cancellation races, reconciliation states, missing local orders, ledger failures, processed-marker failures, and 503 retry semantics.

Oversize rejection occurs before the service call at the route and has a second direct-service guard. Consequently no ledger row, payment attempt, appointment update, or entitlement action can occur for an oversize body. Transient internal failures remain retryable and are not converted into successful acknowledgments.

## 12. Persistent-payload inventory and implemented limits

All values below are backend-enforced before the affected service/repository write. `extra="forbid"` is used on newly bounded mutation structures unless preserving the public registration anti-enumeration/role-assignment contract requires unknown fields to remain ignored.

| Area | New or confirmed authoritative limits | Evidence and rationale |
|---|---|---|
| Global non-upload mutations | 1 MiB actual streamed body | Pre-parser safety envelope for all API mutation content types. Specialized file routes retain their own caps. |
| Webhook transport/ledger | body 256 KiB; signature 256 chars; event/provider entity IDs 128 chars | Existing checkout signature/ID schemas already use 256/128. Raw body/parsed event is not persisted; only bounded IDs + fixed digest/status/timestamps are stored. |
| Public/staff auth | email 254; password max 1,024; name 100; rehearsal tag 128 | Email standard/product convention, existing UI/profile name convention, and a technical hash/input ceiling. Password minimum policy is unchanged. |
| Clinic appointments | patient/doctor IDs 128; time text 20 then strict parser; reason 500 | Patient booking already displayed/enforced a 500-character product limit; admin UI now matches it. No silent truncation. |
| Home visits | patient-controlled address 500, reason 1,000, city 100, enumerated body/symptom lists already existed; doctor IDs 128 and time 20 added | Retains established product limits and adds identifier/parser input bounds. |
| Legacy laboratory bookings | 1-12 test IDs, each 1-128; date exactly 10; time 20; visit literal; address 500; payment metadata 50/128/128 + status literal | Aligns list count with the active lab-request catalogue and existing provider-ID ceilings. |
| Active lab requests | selected catalogue values max 12, address 500, city 100 already existed; rehearsal tag now 128 | Catalogue membership prevents arbitrary item strings; only the free tag needed a ceiling. |
| Clinician schedules | time strings exactly 5; existing block/date list maxima retained | Parser requires `HH:MM`; bounding before split avoids oversized parser input. |
| Care-plan mutation | IDs 128; title 200; free text 8,000; labels 200; focus areas 32; stages 64; goals 128; recommendations 128; unit 100; status/priority 50; current stage 1-64 | Explicit nested limits prevent arbitrary arrays/objects and keep worst-case requests under the independent 1 MiB envelope. Response schemas remain legacy-tolerant. |
| Exercise mutation | IDs 128; title 200; description/notes 8,000; instruction item 2,000 and list 50; label item 200 and lists 50; URL 500; sets 1,000; reps 10,000; duration 86,400; frequency 200 | Bounds every persisted free-form/list/numeric input without changing response parsing. |
| Clinical report metadata | multipart metadata 64 KiB; IDs 128; title 200; category 100; summary 8,000; clinician 200; each symptoms/findings/recommendations field 16,000 | Fits within the 64 KiB metadata envelope with structural overhead. PDF bytes remain separate specialized storage, quarantine, and scanner input. Response schema remains legacy-tolerant. |
| Patient/doctor profiles and payment checkout | Existing 100/24/80 patient fields, doctor biography/qualification/specialty/URL maxima, and 128/256 checkout identifier/signature maxima retained | Existing adequate server validation; no Group B change needed. |
| Notifications | No public generic notification-create body; content is generated by bounded application workflows | Not classified as a direct external persistence gap. Global mutation cap remains defense in depth. |

No generic user-controlled dictionary is persisted by the reviewed registered mutation schemas. Care-plan/report embedded objects now reject unexpected keys. Public registration intentionally does not use `extra="forbid"`: the established security contract ignores a client-supplied `role` and always assigns the server-authoritative patient role without creating an enumeration distinction.

## 13. Clinical policy and existing-data compatibility

The 8,000/16,000-character clinical limits are deliberately generous technical ceilings. They reject new excessive input; they do not truncate it. The repository has no clinic-approved semantic maximum for detailed care plans, exercise notes, or report narratives, so a lower or materially different limit is **POLICY DECISION REQUIRED**.

Write models are separate from response models for care plans, exercises, and reports. Synthetic legacy records above the new mutation limits remain readable in tests. No database was opened, queried, migrated, rewritten, truncated, or deleted.

## 14. Validation-before-persistence and partial-write evidence

FastAPI/Pydantic constructs mutation schemas before invoking route services. An end-to-end appointment test submits a 501-character reason and proves 422 while the mocked persistence service is never awaited. Direct schema boundary tests cover the other structures. Webhook oversize/malformed/provider-ID tests prove the service or ledger lookup is not reached. The global limit returns 413 before endpoint invocation.

These controls prevent partial writes caused by validation rejection. They do not resolve the separate A11-M08 transaction/versioning finding for valid multi-write clinical operations.

## 15. Frontend change

The patient appointment form already had `maxLength={500}` and a character counter. `frontend/src/pages/admin/AppointmentBooking.jsx:257-269` now presents the same usability ceiling for administrator bookings. Backend validation remains authoritative; the frontend neither slices nor silently truncates input. No unrelated redesign was performed.

## 16. Fresh regression results

All backend commands used the existing locked Python 3.13 environment from `/private/tmp`, `env -i`, synthetic distinct secrets, `ENVIRONMENT=test`, an intentionally unreachable loopback MongoDB port, disabled provider/reconciliation/scanner modes, disabled plugin autoload, explicit `pytest_asyncio`, no pytest cache provider, and no connected-test opt-in.

| Check | Fresh result |
|---|---:|
| New Group B adversarial backend file | **29 passed** |
| Group B + complete Razorpay payment file | **76 passed** |
| Webhook/payment/API/auth/care-plan/exercise/report/laboratory affected selection | **306 passed** |
| Complete backend excluding only AF_UNIX scanner file | **1,027 passed, 3 connected-only skipped** |
| Literal complete backend suite | **1,028 passed, 11 AF_UNIX sandbox failures, 3 connected-only skipped** |
| Focused frontend Group B | **2 passed** |
| Complete frontend | **161 passed** |
| Frontend lint | **PASS** |
| Vite production build | **PASS**, Vite 8.3.5, 1,838 modules |
| Asset budget | **74 JS/CSS assets**, zero violations (450 KiB JS / 300 KiB CSS) |
| Python syntax | **168 files parsed**, zero failures |
| Dependency-lock tests | **2 passed** |
| `pip check` | **No broken requirements found** |
| Offline `npm audit --audit-level=low` | **0 locally cached vulnerabilities**; cache freshness unknown |
| Redacted Gitleaks current-tree scan | **6 existing synthetic fixture findings**, zero in Group B paths |
| `git diff --check` | **PASS** |

The recurring warning is the existing already-imported `pytest_asyncio` assertion-rewrite warning. The three skips are the explicitly guarded connected account-registration, distributed-rate-limit, and report-transaction tests. All 11 failures occur before application assertions when this sandbox rejects `asyncio.start_unix_server()` AF_UNIX bind with `PermissionError`. The scanner tests were not edited, skipped, or weakened.

The first focused frontend execution had one test-only regex failure because the assertion expected a single-line admin endpoint call while the existing role-selecting call spans lines. Only that new source assertion was made formatting-tolerant; application code was not changed to obtain the pass.

## 17. Environmental limitations and remaining risk

- No Razorpay endpoint, credential, or real/test provider account was accessed. Provider delivery size and proxy agreement remain unverified.
- No external or protected MongoDB, ClamAV daemon, protected storage, deployment, migration, index, seed, or patient workflow was accessed.
- Static/mocked verification cannot prove deployed proxy buffering, ASGI server limits, timeouts, worker concurrency, actual document-size distribution, representative-scale parser memory, or connected multi-process behavior.
- Body limits reduce per-request memory/storage risk but are not a complete denial-of-service control.
- Starlette parses multipart uploads before the endpoint's specialized file stream is consumed; existing file size/quarantine controls remain unchanged, and ingress multipart behavior remains part of the connected infrastructure gate.
- The eight connected release gates remain blocked.

## 18. Updated finding status

| Finding | Group B assessment |
|---|---|
| A11-M05 | **OFFLINE REMEDIATED / CONTRACT VERIFICATION REQUIRED.** Every registered webhook has an application streamed cap; missing/false lengths, exact bytes, no pre-parser persistence, and safe logs are tested. Provider/proxy agreement is not verified. |
| A11-M06 | **OFFLINE REMEDIATED WITH POLICY CONDITION.** Global technical envelope and confirmed schema-specific ceilings are enforced before writes; legacy reads are retained. Clinic semantic clinical-text policy remains unresolved. |

Group A previously addressed A11-M01, A11-M02, A11-M03, and A11-L01 in its own report. This milestone did not re-review or remediate A11-M04 (bounded N+1), A11-M07 (unsupported admin patient-create contract), A11-M08 (valid multi-write atomicity/versioning), A11-L02/L03, A11-I01/I02 maintenance items, A11-E01 connected evidence, or A11-P01 clinic policy. A11-I03 remains intentional. Historical registers remain unchanged.

## 19. Files modified or created by Group B

Created:

- `backend/app/core/request_limits.py`
- `backend/tests/test_phase24a12_group_b_payload_protection.py`
- `frontend/tests/phase24a12-group-b-payload-limits.test.mjs`
- `docs/PHASE_24A12_GROUP_B_WEBHOOK_AND_PAYLOAD_PROTECTION_REPORT.md`

Modified within already dirty or newly dirty tracked paths:

- `backend/app/main.py`
- `backend/app/api/payments.py`
- `backend/app/api/reports.py`
- `backend/app/services/payment_service.py`
- `backend/app/schemas/auth.py`
- `backend/app/schemas/appointment.py`
- `backend/app/schemas/home_visit.py`
- `backend/app/schemas/laboratory_booking.py`
- `backend/app/schemas/lab_request.py`
- `backend/app/schemas/clinician_schedule.py`
- `backend/app/schemas/care_plan.py`
- `backend/app/schemas/exercise.py`
- `backend/app/schemas/report.py`
- `frontend/src/pages/admin/AppointmentBooking.jsx`

No dependency, lock, `.env`, credential, index, migration, provider configuration, deployment, or storage implementation was changed.

## 20. Completion status and next milestone

The critical offline webhook properties are verified, so Group B is not PARTIAL or BLOCKED. It is **PASS WITH CONDITIONS** because provider/ingress contract evidence and clinic semantic limits require their separately authorized gates.

Group C and Group D remain unstarted in this milestone. Phase 24B remains blocked. The recommended next milestone, only after explicit review and authorization, is Phase 24A.12 Group C. No client demonstration, staging, or production authorization follows from this report.
