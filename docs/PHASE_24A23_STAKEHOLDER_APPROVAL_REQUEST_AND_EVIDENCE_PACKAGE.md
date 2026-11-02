# Phase 24A.23 — Stakeholder Approval Request and Evidence Package

Prepared: 2026-11-02

Policy reference: `five-role-read-only-v1`

Repository baseline: `5eaced696a156ca74233fd04252fea52345d8af8`

> **Package status:** REQUEST MATERIALS ONLY. No section records an approval, signature, authorization, stakeholder contact, or implementation permission. All placeholders must be completed and independently verified in a later evidence-intake milestone.

## 1. Executive brief

### Purpose

PhysioCare is intended to demonstrate how five clinic roles could view a small, fictional set of information while the system actively prevents editing, booking, clinical authoring, file handling, payments, and other unapproved activity. The five roles are patient, doctor, receptionist, laboratorian, and administrator.

The proposal is not to expose the normal application and rely on presenters to avoid unsafe buttons. The backend would enforce a closed list of permitted methods and paths, keep normal sign-in/session/role/ownership checks, and deny everything else. The first implementation request is narrower still: it would build only the offline backend policy and denial boundary, then stop for review before role-data endpoints or user interfaces are built.

### Proposed demonstration scope

The reviewed v1 design contains 19 historical candidates: six existing sign-in/session/readiness operations and 13 proposed role-data reads. Notifications are excluded, leaving 18 effective candidates. Notifications are omitted because current notification text and related identifiers may be sensitive and the current user interface includes read-state mutations and background unread-count requests.

The eventual role stories would be limited to:

- patient: minimal identity, owned completed visits, and owned file-free report metadata;
- doctor: assigned fictional patient aliases and same-doctor completed visits;
- receptionist: bounded schedule, schedule-scoped patient aliases, active clinicians, and published availability;
- laboratorian: assigned request/test/status metadata without upload or result files; and
- administrator: minimal staff/clinician status and bounded operational counts without management actions.

Payments, provider/webhook activity, PDFs, uploads/downloads, scanners, external storage, registration, management mutations, real clinical/contact data, and real accounts are excluded. A dedicated fictional-data environment is required so ordinary development, staging, production, real credentials, and real records cannot be confused with the demo.

### Technical review already completed

Phase 24A.19 independently audited the original design. Phase 24A.20 revised it to address seven Medium, three Low, and two Informational findings. Phase 24A.21 independently found the revised design technically ready **with conditions**. Phase 24A.22 then found no qualifying stakeholder approval evidence and kept implementation unauthorized.

No demo policy, new role-data endpoint, role-specific demo view, launcher, account, fixture, or demonstration environment has been implemented by those milestones. Technical readiness is not production readiness and is not clinic or project-owner approval.

### Decision requested

Before the narrow offline backend-policy milestone can be considered, authorized stakeholders must decide approvals 1, 2, 4, 7, 8, and 9 and the project owner must separately authorize the exact code/test scope. Approval of those items would permit only the limited milestone in section 4. It would not authorize database use, accounts/data, frontend views, launcher work, service startup, browser activity, a local demonstration, connected integrations, deployment, or Phase 24B.

Current state: **11 PENDING; 0 qualifying evidence items; 0 verified approvals; implementation NOT AUTHORIZED / NOT STARTED; local and connected demos NO-GO.**

## 2. Exact 11-item approval register

The requirement names and responsible roles preserve Phase 24A.22 and the Phase 24A.16 source order. No person is assigned by this package.

| # | Exact requirement and why necessary | Documented stakeholder role | Required decision and evidence | Dependencies and activity authorized | Does not authorize | Status |
|---:|---|---|---|---|---|---|
| 1 | **Named demo environment and machine.** Prevents ordinary development, production, or an incompatible host from being mistaken for the demo. | Project/environment owner — **UNASSIGNED** | Approve or reject a machine ID/OS, chosen architecture, exact DB identity, ports, interface, and launcher direction; provide dated written acceptance. | Prerequisite for limited environment-bound implementation, launcher, preparation, startup, smoke, and demo. Authorizes only the identity values explicitly stated. | Provisioning, startup, DB access, launcher code, or presentation by itself. | **PENDING** |
| 2 | **Environment owner/operator.** Establishes accountability for configuration, implementation evidence, and operational custody. | Project owner — **UNASSIGNED** | Name operator/reviewer, contact channel, responsibilities, authority limits, and validity window; record acceptance. | Prerequisite for limited implementation and every later preparation/operational activity. Authorizes the named responsibility only. | Any technical action outside separately approved scope. | **PENDING** |
| 3 | **Approved demo viewers.** Limits access even to fictional clinical information. | Clinic/project authority — **UNASSIGNED** | Approve named viewers, purpose, least-privilege viewing rule, and presentation window. | Required before current-spec browser verification and any presentation. | Implementation, preparation, startup, or connected access. | **PENDING** |
| 4 | **Approved workflow list.** Prevents incomplete, sensitive, or mutating workflows from entering the demo. | Clinic/product/security authority — **UNASSIGNED** | Approve or reduce the exact route-level included/excluded scope, including effective 18-entry v1 table and notification exclusion; supply signed/digitally attributable decision. | Prerequisite for limited policy/gate implementation, launcher, preparation, startup, smoke, and presentation. Authorizes enforcement of only the accepted list. | Adding routes/fields/roles or implementing later data/UI work. | **PENDING** |
| 5 | **Fictional dataset approval.** Prevents realistic identifiers and unsupported clinical/payment claims. | Clinic/data owner — **UNASSIGNED** | Approve record specification, labels, provenance, prohibited fields, retention, and relationship rules. | Required before DB/account/fixture preparation, browser use, and presentation. | Policy-only code or any real-data use. | **PENDING** |
| 6 | **Demo account roles and access.** Establishes five least-privilege identities and relationship boundaries. | Security/account owner — **UNASSIGNED** | Approve role matrix, creation method, assignment map, activation/lifetime, credential custodian, and handling procedure. | Required before account/data preparation, authentication browser smoke, and presentation. | Creating accounts or credentials until a separate preparation action is authorized. | **PENDING** |
| 7 | **Network exposure boundary.** Prevents public or LAN exposure and fixes security-policy authority values. | Environment/security owner — **UNASSIGNED** | Approve exact loopback interface, frontend/backend ports, Host/origin rules, proxy posture, firewall/port verification, and public/LAN denial. | Prerequisite for limited Host/CORS policy implementation, launcher, startup, browser, and presentation. | Opening a listener, starting services, changing firewall/network, or public access. | **PENDING** |
| 8 | **Payment-disabled confirmation.** Prevents provider, webhook, billing-success, or reconciliation activity. | Payment/security owner — **UNASSIGNED** | Approve complete payment exclusion and verification requirements: blank provider credentials, disabled mode/reconciliation, and future runtime health evidence before startup/demo acceptance. | Prerequisite for limited excluded-capability guards, launcher, preparation, startup, smoke, and demo. | Any payment integration, Test Mode, charge, refund, webhook, or provider access. | **PENDING** |
| 9 | **Storage and scanner exclusions.** Prevents unverified PDF/file/scanner/storage dependencies. | Security/storage owner — **UNASSIGNED** | Approve metadata-only/no-file scope, every file/PDF route denied, and no scanner/private/external storage use; provide signed/digitally attributable decision. | Prerequisite for limited excluded-capability guards, launcher, preparation, startup, smoke, and demo. | File/PDF work, upload/download, storage, scanner, or daemon access. | **PENDING** |
| 10 | **Start, stop and abort authority.** Ensures safe lifecycle and immediate response. | Operational owner — **UNASSIGNED** | Name start/stop/abort decision-makers, rules, observer, incident handling, and approved window. | Required before launcher/runtime/startup/browser/presentation. | Offline policy-and-test implementation or any runtime action before later authorization. | **PENDING** |
| 11 | **Disposable-data cleanup approval.** Prevents unauthorized deletion and ambiguous retention. | Data/operational owner — **UNASSIGNED** | Approve retain-or-clean policy, targets, validation, responsible owner, evidence disposition, and target-specific final confirmation process. | Required before DB/account/fixture preparation and presentation; deletion still needs final exact-target confirmation. | Automatic cleanup, broad deletion, or database preparation by itself. | **PENDING** |

Status legend:

- **PENDING:** no qualifying decision evidence has been received.
- **EVIDENCE RECEIVED – NOT VERIFIED:** attributable evidence exists but authority, date, scope, applicability, or integrity is not yet verified.
- **APPROVED – VERIFIED:** explicit evidence from the documented authorized role is verified for the exact current scope.
- **REJECTED:** an authorized stakeholder explicitly rejects the item or proposed scope.
- **NOT APPLICABLE – JUSTIFIED:** an authorized, documented scope change removes the dependency and the justification is independently verified.

Partial approvals do not open the overall implementation gate. Conditions apply only to the item and scope recorded.

## 3. Six prerequisite approval requests

Each request is independent. Text under “Proposed decision” is a decision for the named stakeholder to accept, reject, revise, or defer; it is not a recorded approval. Bracketed fields must be completed before submission, and an incomplete response cannot be verified.

### Request A1 — Named demo environment and machine

1. **Approval requirement:** approval 1, Named demo environment and machine.
2. **Context:** immutable environment guards cannot be implemented safely until the intended non-production machine, operating system, architecture, database identity, ports, interface, and launcher direction are fixed.
3. **Proposed decision:** “I approve a dedicated local PhysioCare five-role read-only demo identity on `[machine identifier]`, `[OS/version]`, using the architecture in Phase 24A.20, database identity `physiocare_read_only_demo`, backend port `[exact port]`, frontend port `[exact port]`, IPv4 loopback only, and `[future launcher direction]`. This approval is limited to the Phase 24A.22 section 7 offline implementation request and does not authorize provisioning or startup.”
4. **Scope covered:** configuration constants, validation rules, and offline tests for the named identity.
5. **Risks and safeguards:** wrong-machine/DB/port selection could reach an unintended environment; exact identity, default-off behavior, reserved-name rejection, and no connection/startup in the first milestone limit that risk.
6. **Evidence required:** dated attributable decision from the project/environment owner containing every proposed value, policy version, branch/baseline, conditions, and validity window.
7. **Consequence of approval:** satisfies approval 1 only; the implementation gate remains closed until every other entry criterion passes.
8. **Consequence of rejection/deferral:** environment-bound policy work remains blocked; stakeholder may propose a smaller or different environment for a new review.

### Request A2 — Environment owner/operator

1. **Approval requirement:** approval 2, Environment owner/operator.
2. **Context:** the project needs one accountable person for configuration choices, evidence custody, boundary decisions, and escalation; an automated report or implementer cannot self-approve.
3. **Proposed decision:** “I appoint `[name/role]` as environment owner/operator for `[responsibility scope]` from `[start]` through `[expiry/review date]`, with `[reviewer/escalation role]`. The appointment does not itself authorize implementation or runtime activity.”
4. **Scope covered:** responsibility, evidence ownership, review coordination, and escalation within the stated window.
5. **Risks and safeguards:** unclear ownership can produce conflicting settings or self-approval; named limits, a reviewer, expiry, and separation from technical authorization constrain this.
6. **Evidence required:** dated project-owner decision plus the appointee's explicit acceptance, contact channel, duties, authority limits, reviewer, and validity window.
7. **Consequence of approval:** satisfies approval 2 for its stated scope only.
8. **Consequence of rejection/deferral:** no accountable implementation/environment custodian exists; implementation remains blocked.

### Request A4 — Approved workflow list

1. **Approval requirement:** approval 4, Approved workflow list.
2. **Context:** normal PhysioCare routes include mutations, files, payments, management, and broader data. Phase 24A.20 proposes a closed-world v1 table: six existing lifecycle/readiness candidates plus 12 proposed role reads, with notifications excluded.
3. **Proposed decision:** “I approve policy `five-role-read-only-v1` and the effective 18-entry method/path/role table in Phase 24A.20 §8, including default denial of every unlisted operation and exclusion of notifications, registration, files/PDFs, payments, product mutations, docs, and integrations. For the first milestone, I authorize only policy/gate implementation described in Phase 24A.22 §7; role-data endpoints remain excluded.”
4. **Scope covered:** the immutable allow/deny contract and focused offline tests for the first milestone.
5. **Risks and safeguards:** accidental route expansion or role bypass could expose data/actions; exact method/path templates, route-inventory failure, normal authentication/role/ownership preservation, and independent review are mandatory.
6. **Evidence required:** dated signed or digitally attributable route-level acceptance by clinic/product/security authority, referencing policy version, Phase 24A.20 revision, Phase 24A.22 subset, conditions, and any explicitly removed entry.
7. **Consequence of approval:** freezes approval 4 scope; it does not create routes or authorize code until project-owner authorization is separately verified.
8. **Consequence of rejection/deferral:** policy implementation remains blocked; any revised route table requires technical impact review before resubmission.

### Request A7 — Network exposure boundary

1. **Approval requirement:** approval 7, Network exposure boundary.
2. **Context:** localhost binding alone does not prevent hostile Host/forwarded-authority behavior. The policy needs exact approved authorities and must prohibit public/LAN/proxy access.
3. **Proposed decision:** “I approve IPv4 loopback-only operation: frontend `http://127.0.0.1:[frontend port]`, backend `127.0.0.1:[backend port]`, no `localhost`/IPv6/LAN/public aliases, no trusted proxy, forwarded authority rejected, and no firewall/public exposure. The first milestone may encode and offline-test these values but may not start listeners or alter networks.”
4. **Scope covered:** immutable Host/origin/port/CORS/proxy validation and offline request tests.
5. **Risks and safeguards:** DNS rebinding, Host spoofing, unintended LAN exposure, and permissive CORS; exact authority checks, loopback binding, trusted-proxy empty state, narrow CORS, and startup failure guard them.
6. **Evidence required:** dated environment/security-owner decision with completed ports, Host/origin rules, proxy posture, verification method, conditions, policy version, and applicability to the named machine.
7. **Consequence of approval:** supplies approval 7 values for offline implementation; no network or service action is authorized.
8. **Consequence of rejection/deferral:** Host/CORS/environment guard implementation remains blocked; public or proxied alternatives require a new security specification.

### Request A8 — Payment-disabled confirmation

1. **Approval requirement:** approval 8, Payment-disabled confirmation.
2. **Context:** a controlled read-only demo must never create orders, verify payments, receive provider webhooks, reconcile charges, or imply billing success.
3. **Proposed decision:** “I approve complete payment exclusion for `five-role-read-only-v1`: provider mode disabled; reconciliation disabled; key ID, key secret, webhook secret, and billing currency blank; every payment/webhook/reconciliation route denied; no payment UI or background worker. The first milestone may add offline guards/tests only.”
4. **Scope covered:** excluded-capability policy, configuration validation, route denial, and worker-start prevention tests.
5. **Risks and safeguards:** accidental provider contact, credential reuse, charges, or false payment claims; blank settings, disabled workers, route denial, outbound-start spies, and no service startup constrain them.
6. **Evidence required:** dated payment/security-owner decision accepting the exclusion and required verification; redacted configuration evidence when available; and runtime health evidence before startup/demo acceptance. No credential values should appear in evidence. The stakeholder decision may support offline policy implementation, but it does not substitute for later runtime proof.
7. **Consequence of approval:** satisfies approval 8 for a no-payment demo only; no provider access is authorized.
8. **Consequence of rejection/deferral:** first milestone remains blocked; adding payments requires a separate policy, provider approval, connected controls, and review.

### Request A9 — Storage and scanner exclusions

1. **Approval requirement:** approval 9, Storage and scanner exclusions.
2. **Context:** PDF/file workflows require private storage, quarantine, malware scanning, release rules, and connected evidence that the local demo deliberately does not provide.
3. **Proposed decision:** “I approve a metadata-only/no-file v1 scope: every file/PDF/upload/download route denied; no file records/paths; scanner disabled with no socket; dedicated unused paths only as fail-closed configuration; no private/external storage access; no file UI. The first milestone may add denial/configuration tests only.”
4. **Scope covered:** file/scanner/storage excluded-capability rules and offline route/startup tests.
5. **Risks and safeguards:** file disclosure, malicious uploads, scanner failure, storage misrouting, or misleading viewer controls; universal route denial, absent UI/data, disabled integration, startup validation, and spies constrain them.
6. **Evidence required:** dated signed or digitally attributable security/storage-owner decision accepting the complete exclusion, policy version, conditions, and evidence method.
7. **Consequence of approval:** satisfies approval 9 for exclusion only; no file, scanner, daemon, or storage operation is authorized.
8. **Consequence of rejection/deferral:** first milestone remains blocked; including files requires a new connected storage/scanner specification and approvals.

## 4. Separate project-owner implementation authorization request

This request is separate from approvals 1, 2, 4, 7, 8, and 9. It must not be signed until those approvals are verified for the same baseline and scope.

### Proposed authorization wording

> I, `[project-owner name and role]`, on `[date/time with timezone]`, authorize a documentation-referenced, offline-only implementation milestone on branch `codex/physiocare-integration-2026-10-31` at baseline `[exact HEAD/status reference]`. The authoritative design is `five-role-read-only-v1` in Phase 24A.20, subject to Phase 24A.21 conditions and the verified approval evidence references `[A1, A2, A4, A7, A8, A9]`.
>
> Authorized scope is limited to: one immutable Settings/policy application-construction path; default-off environment and staging/production/conflict guards; exact Host, method/path, CORS-preflight, route-inventory and uniform-denial enforcement; preservation of existing session, CSRF, active-account, role and ownership/assignment controls; and focused offline tests T01–T06 and T16 plus the agreed ordinary-mode regressions.
>
> The milestone must stop for independent review before authentication schema changes, role-data endpoint implementation, frontend work, launcher work, database work, or runtime activity. It must not modify or access production, staging, external, or connected resources.
>
> This authorization expires or requires reapproval if the policy/version/table, approval conditions, branch/baseline, authorized paths, environment values, route inventory, or stop point changes. `[Additional conditions or “none”]`.

### Exact excluded work

- typed demo `/api/auth/me` and all 12 proposed role-data endpoint implementations;
- all new patient, doctor, receptionist, laboratorian, and administrator frontend views;
- account, credential, fictional-data, fixture, seed, or cleanup work;
- database/Beanie initialization changes, connections, indexes, migrations, or preparation;
- launcher or production-style static-server implementation;
- FastAPI, Vite, MongoDB, Docker, browser, or demo startup;
- payment/provider/webhook, PDF/file/scanner/storage, and all connected integrations;
- infrastructure, deployment, presentation, and Phase 24B.

### Repository safeguards

- record branch, HEAD, upstream, staged/tracked/untracked counts, and exact authorized paths before work;
- preserve every pre-existing dirty path and stop on overlap that cannot be safely isolated;
- no commit, push, stash, reset, clean, destructive checkout/restore, or history rewrite without separate authorization;
- use reviewable scoped edits; never put secrets or credentials in repository, logs, tests, or evidence;
- run only the approved offline tests and `git diff --check`; retain exact commands/results;
- provide final path-level diff/status and prove no application/database/service/external access beyond the authorization.

### Required security tests and deliverables

Required tests: T01 policy-object conflict, T02 runtime immutability, T03 CORS/preflight ordering, T04 Host/forwarded-authority denial, T05 framework-documentation denial, T06 synthetic future-route default denial, T16 narrow CORS capability, default-off and staging/production failure, and approved existing configuration/auth/route regressions.

Deliverables: immutable policy/config types, app-factory injection, authority and closed-world gate, route-inventory assertion, narrow CORS configuration, focused tests, source/security notes, exact verification results, dirty-worktree preservation evidence, and an independent-review handoff. No runtime artifact is an approved demo.

### Mandatory stop conditions

Stop without workaround if approval evidence is missing/ambiguous/superseded; policy or route scope changes; a pre-existing path conflict cannot be isolated; a test indicates ordinary-mode/auth/role/ownership regression; configuration cannot fail before external connection; implementation would require DB/service/network access; an excluded integration starts; secrets/real data are encountered; or any requested work exceeds the authorization.

Creating or signing this template alone does not start work. A later intake must verify the signer's authority, wording, scope, date, baseline, dependencies, and absence of contradiction.

## 5. Evidence submission standard

### 5.1 Accepted formats

Acceptable evidence may be:

- a signed PDF or digitally signed document with a verifiable signer and date;
- an authenticated approval-system export or immutable decision record identifying the approver and scope;
- an attributable written response from the authorized stakeholder account that quotes or references the complete approval request and states an unambiguous decision; or
- meeting minutes only when formally approved by the documented decision-maker and containing the complete decision, attendees/roles, date, scope, conditions, and approval of the minutes.

An unsigned draft, checkbox without identity, verbal recollection, chat paraphrase, technical recommendation, code review, test result, “looks good,” silence, attendance, or approval for a different environment/policy is not verified approval.

### 5.2 Mandatory evidence content

Every submission must contain:

1. approval ID (`A1`–`A11` or `PO-AUTH`);
2. exact decision: `APPROVE`, `REJECT`, or `DEFER`; conditional approval must list every condition;
3. approver name and documented decision-making role;
4. decision date/time and timezone;
5. policy/version and authoritative documents referenced;
6. exact scope, including selected values and explicit exclusions;
7. repository branch/baseline when implementation is involved;
8. effective period or expiry/review trigger;
9. related evidence/approval dependencies;
10. signature, authenticated source, or other attribution mechanism; and
11. confirmation that approval does not authorize activities outside the stated scope.

Recommended minimum wording:

> Decision `[APPROVE / REJECT / DEFER]` for `[approval ID and exact requirement]`. I am acting as `[documented role]`. This decision applies to policy `five-role-read-only-v1`, Phase 24A.20 revision, and scope `[exact scope]` as of `[date/time/timezone]`. Conditions: `[conditions or none]`. Exclusions: `[explicit exclusions]`. Valid until/review trigger: `[value]`. Evidence reference: `[reference]`.

Project-owner authorization must additionally quote or incorporate section 4's exact included/excluded scope, safeguards, tests, deliverables, and stop conditions.

### 5.3 Evidence identification and handling

- Assign a stable reference such as `A4-YYYYMMDD-v1`; do not rename evidence after verification.
- Record the authoritative location, cryptographic hash where practical, received date, submitter, and access restrictions. Do not copy credentials, contact details, clinical data, or signatures into public logs or chat.
- Link one item to each approval it explicitly addresses. One document may support multiple approvals only when each decision is individually stated and each required role has authority.
- Verify signer role against a project-owner-approved responsibility register; authors and implementers cannot self-approve unless formally assigned that authority with conflict review.
- Compare policy version, branch/baseline, values, exclusions, conditions, expiry, and dependencies with the current package.
- Record ambiguity as `EVIDENCE RECEIVED – NOT VERIFIED` with exact questions. Never infer missing scope or consent.
- A later explicit decision supersedes earlier evidence only when it identifies what it supersedes. Retain both references and the supersession chain; do not overwrite history.
- If documents conflict and priority is not explicit, neither conflicting approval is verified until the authorized role resolves the conflict in writing.
- A changed policy, effective route table, implementation scope, environment identity, or baseline triggers applicability review and may return the item to pending/unverified.
- Where an approval includes both a stakeholder policy decision and later operational proof (for example runtime health or listener evidence), record the decision and proof as separate linked evidence. The decision may satisfy an offline implementation prerequisite only when the package says so; operational startup/demo gates remain unmet until the later proof verifies.

### 5.4 Verification outcome

The verifier records one allowed status from section 2, supporting reasoning, conditions, and next action. Evidence verification confirms only the stated approval; it does not automatically recalculate the overall implementation gate without the decision process in section 8.

## 6. Approval tracking template

Copy this table into a future evidence-intake report. Do not pre-populate approvers, dates, references, or decisions.

| Approval ID | Requirement | Stakeholder role | Evidence reference/location/hash | Date received | Verification status | Conditions/expiry | Outstanding questions | Next action |
|---|---|---|---|---|---|---|---|---|
| A1 | Named demo environment and machine | Project/environment owner | `[pending]` | `[pending]` | **PENDING** | `[none recorded]` | `[machine/OS/ports/DB/launcher]` | Request completed A1 decision |
| A2 | Environment owner/operator | Project owner | `[pending]` | `[pending]` | **PENDING** | `[none recorded]` | `[name/duties/reviewer/window]` | Request completed A2 decision |
| A3 | Approved demo viewers | Clinic/project authority | `[pending]` | `[pending]` | **PENDING** | `[none recorded]` | `[viewers/purpose/window]` | Required later before browser/presentation |
| A4 | Approved workflow list | Clinic/product/security authority | `[pending]` | `[pending]` | **PENDING** | `[none recorded]` | `[18-entry table/subset/exclusions]` | Request completed A4 decision |
| A5 | Fictional dataset approval | Clinic/data owner | `[pending]` | `[pending]` | **PENDING** | `[none recorded]` | `[records/provenance/retention/prohibited fields]` | Required later before preparation |
| A6 | Demo account roles and access | Security/account owner | `[pending]` | `[pending]` | **PENDING** | `[none recorded]` | `[roles/creation/activation/custody]` | Required later before preparation |
| A7 | Network exposure boundary | Environment/security owner | `[pending]` | `[pending]` | **PENDING** | `[none recorded]` | `[ports/Host/origin/proxy/verification]` | Request completed A7 decision |
| A8 | Payment-disabled confirmation | Payment/security owner | `[pending]` | `[pending]` | **PENDING** | `[none recorded]` | `[disabled settings/routes/worker evidence]` | Request completed A8 decision |
| A9 | Storage and scanner exclusions | Security/storage owner | `[pending]` | `[pending]` | **PENDING** | `[none recorded]` | `[file routes/data/scanner/storage exclusion]` | Request completed A9 decision |
| A10 | Start, stop and abort authority | Operational owner | `[pending]` | `[pending]` | **PENDING** | `[none recorded]` | `[people/rules/observer/window]` | Required later before launcher/runtime |
| A11 | Disposable-data cleanup approval | Data/operational owner | `[pending]` | `[pending]` | **PENDING** | `[none recorded]` | `[retain/clean/targets/confirmation/evidence]` | Required later before preparation/demo |
| PO-AUTH | Narrow offline backend-policy implementation | Project owner | `[pending]` | `[pending]` | **PENDING** | `[none recorded]` | `[scope/baseline/tests/safeguards/stop/expiry]` | Request only after A1/A2/A4/A7/A8/A9 verify |

The tracker represents partial progress, not authorization. The overall gate is closed unless section 8 evaluates every mandatory condition as met for the same current baseline.

## 7. Stakeholder communication drafts

These drafts are not sent by this milestone. Replace every bracketed placeholder; remove no scope limitation without technical review.

### 7.1 Concise initial approval-request email

**Subject:** Decision requested: PhysioCare restricted local-demo security milestone

> Hello `[recipient name/role]`,
>
> We are requesting your decision on `[A1 / A2 / A4 / A7 / A8 / A9]` for the proposed PhysioCare five-role, read-only local demonstration design. The design has completed independent technical specification review, but it is not implemented, authorized, or production-ready.
>
> The immediate request is limited to an offline backend security-policy milestone: default-disabled environment guards, exact Host/method/path/CORS denial controls, preservation of existing authentication/role/ownership checks, and focused offline tests. It excludes role-specific frontend views, accounts or fictional data, database/index/migration work, launchers, service/browser startup, payments, files/PDFs, external services, deployment, and demonstration.
>
> Please review request `[approval ID]` in the attached Phase 24A.23 package and respond with `APPROVE`, `REJECT`, or `DEFER`, completing the approver role, exact scope/values, conditions, date/timezone, and validity window. Approval of one item does not authorize implementation; a separate project-owner authorization is required after all prerequisite approvals verify.
>
> Requested response date: `[date]`. Questions or requested changes: `[approved response channel]`.
>
> Thank you,
> `[sender name/role]`

### 7.2 Detailed technical approval brief

**Title:** PhysioCare `five-role-read-only-v1` — stakeholder decision brief

> **Decision requested:** `[approval ID and exact requirement]` by `[documented stakeholder role]`.
>
> **Problem:** normal PhysioCare APIs and pages include mutations, clinical details, payments, and file workflows. A controlled demo cannot rely on a presenter avoiding those features.
>
> **Reviewed design:** an immutable, default-off backend policy permits only an exact reviewed route table while retaining current session, CSRF, active-account, role, patient-owner, doctor-assignment, and laboratorian-assignment controls. Notifications, payments, files/PDFs, uploads, real data, staging, production, and public/LAN access are excluded. Technical reviews Phase 24A.19–21 found the revised specification ready with conditions, not implemented.
>
> **First milestone requested:** offline implementation of the Settings/policy boundary, environment guards, exact Host/method/path/CORS/route-inventory denial, and tests T01–T06/T16. It stops for independent review.
>
> **Not requested:** authentication-schema or role-data endpoint changes; frontend; accounts/data; DB/Beanie/index/migration work; launcher; services/browser; payment/file integrations; infrastructure/deployment; local or connected demo.
>
> **Your decision scope:** `[paste the full matching request from section 3]`.
>
> **Required evidence:** use section 5 wording and include role, date/timezone, exact values/scope, conditions, exclusions, policy version, validity, and attribution.
>
> **Gate effect:** an approved and verified response satisfies only `[approval ID]`. Implementation remains unauthorized until A1, A2, A4, A7, A8, A9 and PO-AUTH all verify for one baseline.

### 7.3 Follow-up reminder template

**Subject:** Reminder: decision pending for PhysioCare `[approval ID]`

> Hello `[recipient name/role]`,
>
> The decision for `[approval ID and requirement]` remains **PENDING**. No implementation, environment, database, or demo work has started. The requested scope and exclusions remain those in Phase 24A.23 dated 2026-11-02.
>
> Please provide an explicit `APPROVE`, `REJECT`, or `DEFER` decision using the evidence standard, or identify questions/changes needed. If no decision is provided, the gate remains closed; silence will not be treated as consent.
>
> Current evidence reference: `[none / unverified reference]`. Requested response date: `[date]`.
>
> Thank you,
> `[sender name/role]`

### 7.4 Rejection or deferral acknowledgement template

**Subject:** Recorded: `[REJECTED / DEFERRED]` — PhysioCare `[approval ID]`

> Hello `[recipient name/role]`,
>
> We acknowledge your `[rejection/deferral]` of `[approval ID and exact scope]` dated `[date/timezone]`, subject to `[conditions/reasons]`. The implementation gate remains closed, no work is authorized, and no stakeholder decision has been inferred beyond your stated scope.
>
> Evidence reference: `[reference]`. Outstanding questions or reconsideration trigger: `[details or none]`. Any revised proposal will be documented and resubmitted rather than treated as an approval.
>
> Thank you,
> `[sender name/role]`

## 8. Implementation authorization decision rules

1. **Intake:** log evidence without changing approval status; assign stable reference, source, received time, and integrity/access metadata.
2. **Attribution:** verify the named person holds the documented decision-making role and has authority for the exact item. A technical reviewer or implementer is not automatically an approver.
3. **Content:** verify explicit decision, policy version, scope/values, exclusions, conditions, date/timezone, validity, and dependency references. Ambiguity produces `EVIDENCE RECEIVED – NOT VERIFIED`.
4. **Applicability:** confirm the evidence applies to the current Phase 24A.20 policy/table, Phase 24A.22 subset, branch/baseline, and requested milestone and has not expired or been superseded.
5. **Conflict:** identify conflicting/superseded evidence. A conflict keeps the item unverified until the authorized role resolves priority explicitly.
6. **Item decision:** assign exactly one allowed status with rationale; never infer consent from silence, technical recommendation, or a different approval.
7. **Prerequisite gate:** require `APPROVED – VERIFIED` for A1, A2, A4, A7, A8, and A9 for the same compatible scope.
8. **Owner gate:** independently verify PO-AUTH after prerequisites. It must match section 4, repository safeguards, tests, exclusions, stop conditions, and baseline.
9. **Technical consistency:** confirm Phase 24A.20 is still authoritative, Phase 24A.21 conditions are accepted, route inventory/policy are unchanged, and the security regression strategy is defined.
10. **Repository gate:** recapture branch/HEAD/upstream/staged/tracked/untracked state and resolve any authorized-path overlap without destroying existing work.
11. **Decision:** grant only the exact milestone if every mandatory criterion passes simultaneously. Otherwise implementation remains `NOT AUTHORIZED`.
12. **No automatic carry-forward:** implementation completion does not authorize frontend, DB, launcher, startup, browser, demo, connected, or Phase 24B work. Each needs a later gate.

Creating this package, receiving one approval, or filling the tracker never automatically opens the gate.

## 9. Outstanding approval dependencies

Immediate prerequisite set for the proposed narrow milestone:

- A1 environment/machine — **PENDING**;
- A2 owner/operator — **PENDING**;
- A4 workflow list — **PENDING**;
- A7 network boundary — **PENDING**;
- A8 payment-disabled scope — **PENDING**;
- A9 file/storage/scanner exclusion — **PENDING**; and
- PO-AUTH project-owner authorization — **PENDING**, and cannot be verified before the six items above.

Later dependencies remain:

- A3 viewers before current-spec browser verification/presentation;
- A5 dataset and A6 accounts before preparation/browser;
- A10 lifecycle authority before launcher/startup/browser/presentation;
- A11 retention/cleanup before preparation/presentation;
- separate launcher, DB/index operation, browser, and presentation authorizations; and
- all applicable connected-gate evidence before any connected client claim.

All eight connected gates remain **BLOCKED**: connected multi-clinician authorization; MongoDB query plans/scale; actual index verification; socket-capable ClamAV; private storage; browser end-to-end journeys; production proxy/TLS/cookie/cache; backup/restore.

## 10. Current authorization status

| Item | Current status |
|---|---|
| Approval requirements recovered | **11/11** |
| Qualifying approval evidence already available | **0** |
| Verified approvals | **0** |
| Six prerequisite requests | **PREPARED, UNSENT, UNDECIDED** |
| Project-owner authorization request | **PREPARED, UNSIGNED, NOT VERIFIED** |
| Evidence standard/tracker | **PREPARED FOR FUTURE INTAKE** |
| Implementation authorization | **NOT GRANTED / NOT AUTHORIZED** |
| Authorized implementation scope | **NONE** |
| Demo implementation | **NOT STARTED** |
| Actual controlled local demo | **NO-GO** |
| Connected client demo | **NO-GO** |
| Connected release gates | **8/8 BLOCKED** |
| Phase 24B | **BLOCKED / NOT STARTED** |

No communication was sent and no stakeholder was contacted. This document records requests, not decisions.

### Repository preservation record

| Item | Before Phase 24A.23 | After Phase 24A.23 documentation |
|---|---|---|
| Branch | `codex/physiocare-integration-2026-10-31` | Unchanged |
| HEAD | `5eaced696a156ca74233fd04252fea52345d8af8` | Unchanged |
| Upstream | `origin/codex/physiocare-integration-2026-10-31`; 0 ahead / 0 behind | Unchanged |
| Staged paths | 0 | 0 |
| Tracked modifications | 114 | 114 |
| Untracked paths | 100 | 101 |
| Total dirty paths | 214 | 215 |

The only Phase 24A.23 repository addition is this untracked documentation file. Previous milestone documents remain unchanged.

## 11. Recommended next action

An authorized project coordinator should distribute only the relevant section 3 request to each documented decision-making role, together with the executive brief and evidence standard. Recipient identities and authority must be supplied by the project owner; this package does not invent them.

When evidence is returned, perform a new documentation-only intake. Verify attribution, authority, exact wording, date, policy/baseline, scope, exclusions, conditions, expiry, dependency compatibility, and supersession. Update the tracker without erasing history. Do not request PO-AUTH verification until A1, A2, A4, A7, A8, and A9 are all verified for one compatible scope.

If the package is incomplete, contradictory, deferred, expired, or rejected, implementation remains unauthorized. If it becomes complete, issue a separate gate decision; do not begin implementation automatically from the evidence submission itself.

Stop after Phase 24A.23 and await actual stakeholder evidence.
