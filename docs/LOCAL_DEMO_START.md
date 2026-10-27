# PhysioCare Local Demo Start

These commands are suitable for a fresh clone on macOS, Linux, or Windows (using the equivalent PowerShell activation command). They do not depend on machine-specific absolute paths or temporary runtime copies.

## Before starting

- Keep all services bound to `127.0.0.1`; do not expose the demo publicly.
- Install Python 3.11 or newer, Node.js 20 or newer, and MongoDB Community Edition.
- Copy `backend/.env.example` to `backend/.env`, set two distinct strong JWT secrets, and keep that file local. Never commit it.
- Copy `frontend/.env.example` to `frontend/.env.local` if the API is not running at the example URL.
- Start the development MongoDB listener referenced by `backend/.env`. Do not point a demo clone at production or real patient data.

## Install dependencies

From `PhysioCare/backend`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

From `PhysioCare/frontend`:

```bash
npm ci
```

## Start the API

From `PhysioCare/backend`:

```bash
source .venv/bin/activate
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Expected startup messages:

```text
Application startup complete.
Uvicorn running on http://127.0.0.1:8000
```

## Start the frontend

From `PhysioCare/frontend` in a second terminal:

```bash
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`.

## Verify before the walkthrough

```bash
curl --fail http://127.0.0.1:8000/api/users/public/doctors
```

The command should return the fictional local clinician directory. Then confirm the public page and one fictional role login before presenting.

## Stop cleanly

Press `Ctrl+C` once in the frontend terminal and once in the API terminal. Keep the local database intact for the next rehearsal.

## Verification

From `PhysioCare/backend` with the virtual environment active:

```bash
pytest -q
```

From `PhysioCare/frontend`:

```bash
npm test
npm run lint
npm run build -- --configLoader native
```
