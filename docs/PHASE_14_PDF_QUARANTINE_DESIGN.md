# Phase 14 PDF Quarantine Design

Assessment date: 2026-10-31

Remediation update 2026-11-01: scanner-provided engine and reason metadata is
restricted to a lowercase 64-character safe-token grammar with fixed fallbacks.
Arbitrary scanner output is never copied to audit JSON. Cleanup failures now emit
only the storage category and exception type. Staging rejects approved scanner mode
until an operational adapter has been implemented and reviewed.

## Implemented scope and safety boundary

The general clinical-report and active laboratory-report upload paths now use a
shared private quarantine workflow with separate approved/quarantine roots. It
does not claim that malware scanning infrastructure exists. The runtime default
scanner returns `scanner_unavailable`; the upload fails closed with 503, the
content is removed, and a private audit record is retained.

## Lifecycle

```text
Uploaded → Quarantined → Scanning → Approved
                                  ↘ Rejected
```

1. The API first enforces `application/pdf`, a `.pdf` filename, and the
   configured declared-size limit.
2. Content streams into a generated opaque `.pdf` key in the private quarantine
   directory with file mode `0600`; both roots use `0700`.
3. The streaming size limit is enforced even when content length is absent.
4. Basic structure validation requires a PDF version signature at byte zero and
   an EOF marker near the end. This is defense in depth, not malware detection.
5. The file remains absent from approved storage while the scanner runs.
6. A clean verdict atomically promotes the file into the approved private root.
7. Malicious, scanner-error, scanner-exception, invalid-structure, or final
   audit-write failures
   remove content and retain a protected audit sidecar. Rejected files have no
   approved key and cannot be resolved by the download path.

`ClinicalReportStorage.resolve` and `LabReportStorage.resolve` see only their
approved roots. Approved and quarantine roots cannot equal or contain one
another. Quarantine and audit paths are never returned by the API, never public
URLs, and reject traversal/symlink use. Report database failures and losing
concurrent laboratory replacements remove promoted files and add `Removed`
audit events; a successful replacement removes the superseded file.

The current filesystem adapter requires each approved/quarantine pair to be on
the same filesystem so `os.replace` provides atomic promotion. Object storage or
cross-filesystem deployment requires a separately reviewed adapter with the
same no-read-before-approval invariant; it must not emulate promotion with a
temporarily public copy.

## Scanner abstraction

`PdfMalwareScanner.scan(path)` returns one of:

- `clean`: promotion may proceed;
- `malicious`: reject with 422;
- `error`: reject with 503.

`UnavailablePdfMalwareScanner` is the deployed default for both report paths and
fails closed. `DeterministicTestPdfScanner` is marked test-only and must never be
selected by a runtime configuration. No paid scanner, external API, daemon, or
cloud resource was introduced or contacted.

Every scan is bounded by `PDF_SCAN_TIMEOUT_SECONDS` (default 30 seconds, allowed
range 0.1–300). A timeout, transport exception, or return value that is not the
declared `ScanResult` type is recorded with a safe reason code, returns a generic
503, and removes all report content. Raw scanner errors are never copied into the
audit record or API response.

An approved staging adapter must provide local/private scanning, bounded timeout,
resource limits, signature/version reporting, health monitoring, and a safe
reason code. It must not send patient files to an unapproved third party.

## Audit record

Each accepted upload envelope has an owner-only JSON sidecar containing the
opaque key, uploader internal ID, current state, UTC event times, scanner engine,
and non-sensitive reason codes. It excludes report content, patient identity,
clinical metadata, original filename, and scanner payload output.

File-system sidecars provide lifecycle evidence for the current local-storage
architecture. Production staging must define durable audit ingestion, retention,
backup, access review, and reconciliation with report database records.

## Verification and remaining gates

Tests cover MIME/extension/size/signature/EOF validation, generated names,
permissions, cleanup, unavailable scanner, malicious verdict, inaccessible
quarantine, approved promotion, audit sequence, database/concurrency cleanup,
laboratory integration, scanner timeout, invalid scanner response, and patient
report ownership.

Before protected use:

1. approve and implement a real scanner adapter;
2. test malformed/polyglot/active-content corpora and scanner timeout/recovery
   against the approved operational adapter;
3. approve separate encrypted storage, retention and deletion policies;
4. test restrictive response headers and separate-origin serving;
5. run failure/recovery tests in isolated staging.
