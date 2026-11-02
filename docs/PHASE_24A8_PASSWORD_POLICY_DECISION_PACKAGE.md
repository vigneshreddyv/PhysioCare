# Phase 24A.8 Password, Email Ownership, Recovery, and Staff Onboarding Decision Package

Assessment date: 2026-11-02

Repository branch: `codex/physiocare-integration-2026-10-31`

Assessment baseline: `5eaced696a156ca74233fd04252fea52345d8af8`

## Decision status

**APPROVAL REQUIRED — POLICY DECISION REQUIRED.** No authoritative clinic-approved password, email-ownership, account-recovery, or staff-onboarding policy was found in the repository. This package records existing behavior and offers recommendations for an authorized clinic/security decision. It does not approve or implement those recommendations.

No authentication, registration, password, email, recovery, or staff-onboarding behavior was changed in Phase 24A.8.

## 1. Current behavior

| Area | Status | Current behavior and source evidence |
|---|---|---|
| Public patient registration | **EXISTING BEHAVIOR** | `backend/app/schemas/auth.py:9-12` accepts a password of 6 or more characters. `frontend/src/pages/common/Register.jsx:9-17` requires 8 or more characters and confirmation. The browser posts the password to `POST /auth/register` (`Register.jsx:29-36`). |
| Staff account creation | **EXISTING BEHAVIOR** | The backend and frontend both require 8 or more characters (`backend/app/schemas/auth.py:14-19`; `frontend/src/utils/staffManagement.js:20-31`; `frontend/src/pages/admin/StaffManagement.jsx:126-135`). Only an administrator can call `POST /users/staff` (`backend/app/api/users.py:47-57`). |
| Login | **EXISTING BEHAVIOR** | `UserLogin.password` has no creation-policy minimum (`backend/app/schemas/auth.py:36-38`). This permits existing credentials to be checked without retroactively applying a new-registration rule. Unknown, wrong-password, and inactive-account cases receive the same generic error (`backend/app/services/auth_service.py:156-169`). |
| Password storage | **EXISTING BEHAVIOR** | Passwords are hashed with the existing Passlib bcrypt context and verified against stored hashes (`backend/app/core/security.py:8-20`). Registration hashes before persistence (`backend/app/services/auth_service.py:93-126`). Passwords are not returned by the reviewed registration responses or staff directory schemas. |
| Public duplicate registration | **EXISTING BEHAVIOR** | The public route returns a neutral HTTP 202 message (`backend/app/api/auth.py:20-28`). The service performs password-hash work before duplicate detection and suppresses the duplicate result for public registration (`backend/app/services/auth_service.py:93-153`). |
| Account activation | **EXISTING BEHAVIOR** | `User.is_active` defaults to `True`; there is no email-verified field (`backend/app/models/user.py:9-16`). Public and staff accounts can therefore authenticate immediately after successful creation. |
| Email ownership verification | **NOT IMPLEMENTED** | No verification state, verification token, verification endpoint, resend flow, or email-change reverification workflow exists in the reviewed models, routes, services, schemas, or tests. |
| Password change/reset/recovery | **NOT IMPLEMENTED** | No password-change, forgot-password, reset-token, recovery-code, SMS recovery, or administrator-assisted recovery route/model/service was found. Consequently there is no reset/change password rule to compare with registration. |
| Staff onboarding | **EXISTING BEHAVIOR** | An administrator chooses the initial password. The account is active immediately and the UI tells the administrator to share the password securely (`frontend/src/pages/admin/StaffManagement.jsx:44-50,106-108`). There is no invitation, first-login password setup, forced change, or ownership verification flow. |
| Deactivation | **EXISTING BEHAVIOR** | An inactive user is rejected at login and during refresh validation (`backend/app/services/auth_service.py:156-169,307-316`). No staff-deactivation action was found in the reviewed staff-management API/UI, so the connected administrative lifecycle is **NOT VERIFIED**. |

## 2. Exact frontend and backend validation rules

| Flow | Frontend rule | Backend rule | Consistent? |
|---|---:|---:|---|
| Public patient registration | Minimum 8; confirmation must match | Minimum 6 | **No** |
| Staff registration | Minimum 8; confirmation must match | Minimum 8 | **Yes** |
| Email login | Frontend currently requires 6 characters before submission | No minimum beyond a string; bcrypt verifies the stored credential | Intentionally not a creation-policy check |
| Password change | **NOT IMPLEMENTED** | **NOT IMPLEMENTED** | Not applicable |
| Password reset | **NOT IMPLEMENTED** | **NOT IMPLEMENTED** | Not applicable |

**EXISTING BEHAVIOR:** A direct API client can bypass the public browser's 8-character check and register with a 6- or 7-character password. The backend public-registration schema is the authoritative security boundary and is weaker than the UI. Staff creation is consistently 8 characters at both boundaries.

No reviewed code logs a password or includes it in a response. That conclusion is limited to the inspected repository paths and executed offline tests; runtime log aggregation and connected observability are **NOT VERIFIED**.

## 3. Security implications

- **EXISTING BEHAVIOR:** Six-character public credentials provide a smaller search space than the 8-character browser message implies. A non-browser client can exercise the weaker rule.
- **EXISTING BEHAVIOR:** Login throttling, generic authentication errors, neutral public registration, bcrypt hashing, session rotation, and inactive-account checks reduce separate threats but do not make a short password strong.
- **EXISTING BEHAVIOR:** Email uniqueness prevents two stored users from sharing one email value, but it does not prove that the registrant controls that mailbox.
- **EXISTING BEHAVIOR:** Immediate staff activation plus administrator-selected initial credentials creates a credential-distribution risk and means the administrator temporarily knows the staff member's password.
- **NOT IMPLEMENTED:** Without a recovery mechanism, a forgotten password can lead to account lockout or pressure for an undocumented manual workaround.

## 4. Existing-account compatibility

**EXISTING BEHAVIOR:** Login does not reapply a registration minimum, so existing 6- or 7-character credentials remain usable. This is the compatibility-preserving behavior.

**RECOMMENDATION:** Apply any approved stronger minimum only to new credentials: new registration, initial invitation password setup, password change, and password reset. Do not invalidate existing hashes or force a password change until the clinic approves a migration, communication, support, and exception plan. Preserve the no-minimum login schema so valid legacy credentials can still be verified during an approved transition.

**APPROVAL REQUIRED:** The clinic must decide whether and when existing users must upgrade credentials, how notice and support will work, and what happens to dormant or inaccessible accounts. No migration is authorized by this package.

## 5. Recommended minimum password policy

**RECOMMENDATION — NOT APPROVED:** For this currently single-factor application, use a consistent minimum of **15 characters** for every newly established password. Support at least 64 characters, allow spaces and passphrases, avoid mandatory composition rules and routine expiry, and reject known-compromised passwords only through an approved privacy-preserving mechanism. If the clinic later adopts verified multi-factor authentication, it may approve a different minimum after a documented risk review.

The recommendation would cover:

- public patient registration;
- staff invitation/initial setup;
- future password-change flows;
- future password-reset flows; and
- any administrator-assisted credential replacement.

**APPROVAL REQUIRED:** The clinic/security owner must approve the actual minimum, maximum, permitted characters, breached-password screening method, rate limits, accessibility/support exceptions, and legacy-account transition. Until then, the current 6/8 behavior remains unchanged.

## 6. Email ownership verification recommendation

**NOT IMPLEMENTED:** The system has no proof-of-email-ownership state or workflow. Unverified accounts can authenticate immediately; registration relies on email syntax and database uniqueness. The reviewed patient-profile update does not offer email change, and no alternative email-change route was found.

**RECOMMENDATION — NOT APPROVED:** Require verification before sensitive portal use or account activation. Use a high-entropy, short-lived, single-use token stored only as a hash; provide an enumeration-neutral registration/resend response; rate-limit issuance and verification; record auditable state transitions; and require reverification before a changed email becomes authoritative. Staff should receive an invitation at a clinic-verified address rather than a reusable password chosen by an administrator.

**APPROVAL REQUIRED:** The clinic must define when access is blocked, token lifetime, resend limits, address-correction and support procedures, staff identity proofing, clinical continuity exceptions, notification wording, and retention/audit requirements. Email delivery infrastructure is not authorized or implemented here.

## 7. Account recovery recommendation

**NOT IMPLEMENTED:** There are no password-reset routes, reset tokens, expiry/single-use controls, recovery codes, staff recovery, or administrator-assisted recovery workflow. Enumeration resistance and session revocation after password reset are therefore not implemented for recovery.

**RECOMMENDATION — NOT APPROVED:** Implement recovery only after email ownership policy is approved. A patient recovery request should always return a neutral response, be rate-limited, issue a high-entropy hashed single-use short-lived token, invalidate the token after success, revoke existing sessions after credential replacement, and emit an auditable security event without logging the token or new password. Staff recovery should use a separately governed identity-verification and authorization process; an administrator should not be able to retrieve or view a password.

**APPROVAL REQUIRED:** The clinic must choose recovery channels, identity proofing, token lifetime, resend and retry limits, session-revocation behavior, lost-mailbox handling, staff escalation, emergency access, audit retention, and support ownership. No email or SMS provider may be connected on this recommendation alone.

## 8. Staff onboarding recommendation

**EXISTING BEHAVIOR:** Only an administrator can create staff accounts. The administrator supplies a minimum-8-character password, the account becomes active immediately, and the password must be shared outside the application. Staff cannot change it through the reviewed application.

**RECOMMENDATION — NOT APPROVED:** Retain administrator authorization to initiate onboarding, but replace shared initial passwords with a time-limited, single-use invitation. Verify the staff identity and clinic-approved role before invitation, let the staff member establish a compliant password, activate only after the approved verification step, and revoke active sessions promptly on deactivation. Separate clinical access approval from mere mailbox ownership.

**APPROVAL REQUIRED:** The clinic must define who approves each role, invitation lifetime/resend, identity checks, activation timing, first-login requirements, deactivation authority, termination timing, break-glass handling, and audit review. No role or permission change is authorized here.

## 9. Decisions requiring clinic approval

| Decision | Required clinic/security choice | Current status |
|---|---|---|
| New-password length | Minimum, maximum, passphrase/character rules, breached-password control | **APPROVAL REQUIRED** |
| Existing users | Grandfathering, upgrade trigger, forced-change/migration and exception plan | **APPROVAL REQUIRED** |
| Email ownership | Activation/access boundary, token life, resend, email change, support and audit | **APPROVAL REQUIRED** |
| Patient recovery | Approved channels, identity proofing, expiry, single use, rate limits, session revocation | **APPROVAL REQUIRED** |
| Staff onboarding/recovery | Role approvers, invitation, activation, identity proofing, deactivation and emergency process | **APPROVAL REQUIRED** |
| Infrastructure/privacy | Mail/SMS provider, secrets, data processing, retention, monitoring and operational ownership | **APPROVAL REQUIRED** |

No repository document examined in Phase 24A.8 constitutes this approval.

## 10. Risks of retaining current behavior

1. Direct API clients can create 6- or 7-character patient passwords even though the public UI says 8.
2. A mistyped or third-party email address can become an active account identifier without ownership proof.
3. Users have no self-service credential recovery or change path, creating lockout and unsafe manual-workaround pressure.
4. Administrators must know and transmit initial staff passwords; accounts are active before any staff-controlled setup.
5. Deactivation is enforced when `is_active` is false, but the reviewed staff UI/API does not establish an operational deactivation workflow.
6. Future reset, change, invitation, or email-change work has no approved common policy and could introduce inconsistent rules if built prematurely.

These are release-policy risks; they are not authorization to change behavior.

## 11. Implementation changes that would follow each decision

All items below are **NOT IMPLEMENTED** and require an approved decision plus a separately reviewed implementation plan.

| Approved decision | Likely implementation scope after approval |
|---|---|
| Consistent new-password rule | Central backend policy validator; align patient/staff schemas and UI; apply to future reset/change/invitation; add boundary and legacy-login tests; do not rewrite existing hashes. |
| Existing-account migration | Versioned transition logic, notice/support process, metrics and exceptions; preserve login until the approved trigger; session handling and rollback plan. |
| Email verification | Verification state and timestamps, hashed token model, neutral issue/resend/verify endpoints, expiry/single-use/rate-limit/audit controls, UI states and authorized mail integration. |
| Patient recovery | Neutral request endpoint, hashed reset tokens, single-use/expiry, compliant password validation, session revocation, notifications, audit and abuse tests. |
| Staff invitation/onboarding | Admin-only invitation, clinic role approval, single-use setup token, staff-controlled password establishment, activation/deactivation lifecycle, session revocation and audit. |
| Email change | Pending address, confirmation and reverification, conflict handling, notification to old/new address, session/risk decision and audit. |

## Decision requested

The authorized clinic/security owner should approve, reject, or amend each decision in section 9 in writing. Until that evidence is added and its authority verified, the repository classification remains **POLICY DECISION REQUIRED**, Phase 24A remains conditionally closed only for its offline scope, and Phase 24B, client demonstration, staging, and production authorization remain blocked.
