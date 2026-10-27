# PhysioCare Isolated Laboratory Rehearsal — 2026-10-25

This record contains no passwords, tokens, report contents, or real patient data.

## Isolation

- Rehearsal database: `physiocare_lab_rehearsal_20261025_100449` on the loopback-only MongoDB listener at `127.0.0.1:27018`.
- Existing database `physiocare_local_verification_6077c2718ea1` was read only. Its before-and-after counts remained: 4 users, 3 patients, 1 doctor, 1 appointment, and 4 laboratory requests.
- Finalized report storage was restricted to `/tmp/physiocare_lab_rehearsal_20261025_100449/reports`.
- Four fresh fictional accounts were used only in the disposable database: patient, administrator, Laboratorian, and doctor. Passwords were generated in process memory and were never printed, written to the repository, saved in Keychain, or used to reset an existing account.
- One fictional clinic appointment linked the fictional patient to the fictional doctor solely to exercise assigned-doctor report access.

## Connected results

The loopback API returned the expected result for every step:

1. Patient public registration: passed (`201`).
2. Administrator login and protected Laboratorian/doctor creation: passed (`200`/`201`).
3. Patient clinic appointment and laboratory request creation: passed (`201`).
4. Patient access to administrator and Laboratorian queues: denied (`403`).
5. Doctor access to the unpublished file: hidden (`404`).
6. Administrator request approval and Laboratorian assignment: passed (`200`).
7. Assigned Laboratorian queue isolation and finalized PDF upload: passed (`200`).
8. Laboratorian attempt to publish: denied (`403`).
9. Patient access to the unpublished file: hidden (`404`).
10. Administrator publication: passed (`200`).
11. Repeated administrator publication: idempotent (`200`) with one audit entry.
12. Patient released-report list and PDF download: passed (`200`).
13. Assigned-doctor released-report list and PDF download: passed (`200`).
14. Downloaded bytes matched the finalized fictional PDF.

The disposable database contained exactly 4 users, 1 patient profile, 1 doctor profile, 1 appointment, 1 laboratory request, 4 sessions, 1 publication-audit entry, and 1 temporary PDF before cleanup.

## Runtime observation

The rehearsal completed successfully. Passlib emitted its known compatibility warning while reading the installed bcrypt package version metadata, but password hashing and all four authenticated sessions succeeded. No package versions or environment settings were changed during this run.

After cleanup, the reusable rehearsal runner passed a no-bytecode syntax parse, 9 lab-named backend contract tests passed with 77 unrelated tests deselected, and `git diff --check` passed. The earlier complete publication implementation verification remains 86 backend tests, 29 frontend tests, frontend lint, and a fresh production build.

## Cleanup

- The isolated API on port `8001` was stopped.
- Database `physiocare_lab_rehearsal_20261025_100449` was dropped and a fresh database listing confirmed it was absent.
- `/tmp/physiocare_lab_rehearsal_20261025_100449` and its one fictional PDF were removed.
- All four in-memory HTTP clients were closed. No browser login session was created, so there were no rehearsal browser cookies to retain or clear.
- The MongoDB listener started for this rehearsal was stopped. Final checks found no listeners on ports `8001` or `27018`.
- The existing database remained unchanged at 4 users, 3 patients, 1 doctor, 1 appointment, and 4 laboratory requests.
