# Phase 14 Dependency Audit

Assessment date: 2026-10-31

Remediation update 2026-11-01: the lock contract now compares each normalized
direct dependency's exact version with `requirements.lock`; presence by package
name alone is no longer sufficient.

## Deterministic installation

- Backend direct dependencies are exact-pinned in `backend/requirements.txt`.
- The complete Python 3.13 graph is exact-pinned in
  `backend/requirements.lock`; CI installs and audits that file.
- Frontend dependencies retain `frontend/package-lock.json`; CI uses `npm ci`.
- CI cache keys follow the corresponding lock file.
- Automated lock tests reject unpinned Python lines, require the direct graph to
  be contained in the lock and verify Python 3.13/CI wiring.

## Vulnerability findings and remediation

The first Phase 14 audit identified PyJWT 2.10.1 advisories. The direct and lock
pins were updated to PyJWT 2.15.0, the smallest audited fixed version that
covered the reported set. The project already used PyJWT rather than the
unmaintained `python-jose` dependency.

Final executed results:

- `python3.13 -m pip_audit -r requirements.lock`: **no known vulnerabilities**.
- `npm audit --audit-level=low`: **0 vulnerabilities**.
- clean temporary Python 3.13 lock installation: **succeeded**.
- full backend suite from that clean target: **382 passed**.
- frontend tests/lint/build/bundle checks: **passed**.

No application package was removed merely because an import was not obvious,
and no broad arbitrary upgrade was performed.

## Operational policy

Regenerate the lock only in a reviewed dependency change. Require a clean Python
3.13 install, full tests, compilation, `pip-audit`, frontend lock install/tests,
`npm audit` and secret scan before merging. Advisory results are time-sensitive;
the clean result records 2026-10-31 and must be repeated for release.

`pip-audit==2.10.1` is pinned as CI tooling. It is installed alongside, but is
not part of, the application runtime lock. A future supply-chain hardening phase
may add artifact hashes and a separately locked tooling environment.
