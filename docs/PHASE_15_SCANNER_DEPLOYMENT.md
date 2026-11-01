# Phase 15 scanner architecture and local adapter

Assessment: 2026-11-01. **Code implemented; operational scanner not deployed or validated.** Both clinical and laboratory uploads remain fail-closed by default.

## Option review

| Option | Trade-off | Decision |
|---|---|---|
| Self-hosted `clamd` over a private Unix socket | Keeps clinical bytes within the approved host/security boundary and supports streaming; needs signature updates, memory headroom, socket permissions, monitoring and lifecycle ownership | Preferred staging candidate, subject to owner/security review |
| Per-upload `clamscan` subprocess | No persistent daemon but repeatedly loads signatures and needs tight process/resource control | Not selected for the request path |
| Third-party scanning API | Simpler infrastructure but transmits clinical content to another processor and creates privacy/contract dependencies | Not approved; do not use without a separate decision |

ClamAV documents `INSTREAM` as length-prefixed chunks terminated by a zero chunk, with `stream: OK` or `... FOUND` responses. Its TCP socket is unauthenticated and unencrypted, so this adapter uses only a Unix socket. Official container guidance recommends at least 3 GiB and preferably 4 GiB RAM because signatures and reloads are memory intensive. Signatures must be maintained with FreshClam. Sources: [clamd protocol](https://docs.clamav.net/manual/Usage/ClamdProtocol.html), [Docker memory guidance](https://docs.clamav.net/manual/Installing/Docker.html), [signature management](https://docs.clamav.net/manual/Usage/SignatureManagement.html).

## Implemented boundary

- `backend/app/services/pdf_malware_scanner.py` contains `ClamAvUnixScanner`. It streams only the quarantined file bytes over `zINSTREAM`; it never sends a clinical file path to the daemon. It maps exact clean replies to `clean`, detection replies to `malicious`, and errors/malformed/disconnected replies to `error`. It discards raw signature names, paths and daemon text.
- `backend/app/main.py` selects one scanner for both clinical and laboratory storage only when `PDF_SCANNER_MODE=clamav_unix`. Startup requires a bounded `PING` response before database initialization. An absent/unresponsive daemon prevents startup. The default `disabled` mode selects the fail-closed unavailable scanner.
- `backend/app/core/config.py` requires an absolute, non-symlinked socket path in configured mode. `backend/staging.env.example` retains `disabled` and a blank socket path. No daemon, image, volume or signature database has been created.
- The existing storage layer enforces byte limits, a total scanner timeout, private quarantine, clean-only atomic promotion and safe audit fields. It returns 422 on detection and 503 on scanner error/unavailability. Both report paths use this layer.
- Local tests use a fake private Unix socket for clean, detection, protocol error, disconnect, absent socket and timeout, including both clinical and laboratory upload paths; they do not prove ClamAV signature detection.

## Operational approval and validation still required

1. Approve exact ClamAV version/image digest, maintenance and FreshClam update path; verify licensed signature use, freshness alerts and update-failure response. Keep daemon access private and grant only the API service user/group socket access.
2. Configure `StreamMaxLength` greater than or equal to the application upload cap plus protocol overhead; bound `MaxThreads`, `MaxQueue`, memory, CPU, temporary storage and scan time. A limit-exceeded or heuristic result must never be interpreted as clean. Test concurrent uploads and daemon restart/reload.
3. Use only approved, inert test fixtures in isolated staging. Verify clean, invalid, oversized and malformed PDFs; the owner's EICAR test fixture, approved polyglot, timeout, crash, malformed reply, unavailable socket and promotion failure for **both** clinical and laboratory paths. Confirm rejected files are never downloadable and no raw scanner details enter logs/audits.
4. Document false-positive triage without bypassing quarantine, audit retention, signature/version evidence, health/alert ownership and storage cleanup reconciliation. Re-run the full suite and independent review after any adapter/config change.

The scanner is **not operational** until these service and connected test gates pass. Enabling a mode string alone is not evidence of safe scanning.
