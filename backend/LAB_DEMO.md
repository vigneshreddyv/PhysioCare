# Isolated Laboratory Demo

The demo runs independently of the normal PhysioCare services:

| Service | Demo address |
| --- | --- |
| MongoDB | `127.0.0.1:27018` |
| FastAPI | `127.0.0.1:8001` |
| Vite frontend | `127.0.0.1:5175` |
| Database | `physiocare_lab_demo` |

The backend only loads the protected per-user configuration created by the
PowerShell helper. In demo mode it fails startup unless the database name,
loopback MongoDB listener, backend bind address, payment settings, CORS origin,
and report-storage location all match the dedicated demo values. Database
initialization repeats the guard immediately before connecting. Do not copy
application environment values or credentials into the demo configuration.

## Start the isolated services

From the repository root, start the dedicated, loopback-only MongoDB container:

```powershell
docker compose -f backend\docker-compose.lab-demo.yml up -d
```

Create the protected demo configuration once:

```powershell
.\backend\scripts\LabDemo.ps1 -Action configure
```

In separate PowerShell windows, start the demo backend and frontend:

```powershell
.\backend\scripts\LabDemo.ps1 -Action start
```

```powershell
.\backend\scripts\LabDemo.ps1 -Action frontend
```

The normal services on ports 8000 and 5173 are not changed. The frontend is at
`http://127.0.0.1:5175`. Use separate browser profiles for Admin, Laboratorian,
and Patient because their sessions use cookies.

## Prepare and rehearse

The prepare command creates/reuses only tagged demo accounts and one pending,
fictional clinic laboratory request. It does not create appointments or payment
records. The bundled report is clearly marked as fictional demo data, with
illustrative values that are not clinical results. Generated passwords and the
JWT signing secrets are kept in protected per-user files and never printed:

```powershell
.\backend\scripts\LabDemo.ps1 -Action prepare
```

After reviewing the demo pages, run the authenticated workflow. This command
approves and assigns the request, uploads the sample PDF, and publishes it:

```powershell
.\backend\scripts\LabDemo.ps1 -Action rehearse
```

The prepare action requires typing `PREPARE LAB DEMO`; rehearsal requires
`RUN LAB REHEARSAL`. Their underlying CLI commands also require `--confirm`.
They refuse to run unless the protected demo configuration is selected and the
isolated MongoDB listener is reachable.

The workflow uses the existing login, staff, laboratory-request, assignment,
upload, publication, and patient-report APIs. A short-lived, tagged second
laboratorian is created only for the cross-assignment denial check and removed
after that check. The rehearsal never creates appointments or payments.

## Cleanup

Cleanup is separate and never runs automatically:

```powershell
.\backend\scripts\LabDemo.ps1 -Action cleanup
```

It verifies the exact demo database and storage paths, refuses unexpected
untagged records or files, and requires typing the full confirmation phrase.
It deletes only records with the fixed laboratory-rehearsal tag, their report
files in the dedicated storage directory, and the protected demo credentials.
It does not drop the database, remove the storage directory, or remove the
MongoDB container.

## Manual visual checks

After preparation, sign in through the existing shared login page in separate
browser profiles and inspect:

- Admin: `/admin/staff`, `/admin/laboratory`, and `/admin/demo-services`.
- Laboratorian: `/laboratory/dashboard`.
- Patient: `/patient/laboratory` (Released laboratory reports section).

The automated rehearsal checks the corresponding authenticated APIs and
workflow states. The demo credentials remain in the protected per-user
credentials file; do not copy them into source control, chat, or logs.
