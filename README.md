# 🏥 PhysioCare Pro

> **A Complete Digital Healthcare & Physiotherapy Management Platform**

![Status](https://img.shields.io/badge/Status-Under%20Development-orange)
![Backend](https://img.shields.io/badge/Backend-FastAPI-green)
![Frontend](https://img.shields.io/badge/Frontend-React-blue)
![Database](https://img.shields.io/badge/Database-MongoDB-brightgreen)
![License](https://img.shields.io/badge/License-Private-red)

---

# 📖 About

PhysioCare Pro is a modern digital healthcare platform designed to simplify clinic management and enhance patient experience.

The platform enables patients to:

- Book physiotherapy appointments
- Schedule home visits
- Attend online consultations
- Book laboratory tests
- Request home sample collection
- Access prescriptions and laboratory reports
- Make secure online payments
- Manage healthcare services from one place

It also provides dedicated portals for doctors, receptionists, laboratory technicians, and administrators to efficiently manage daily clinic operations.

The platform is designed with scalability in mind and will support AI-powered healthcare services in future releases.

---

# 🎯 Project Objectives

- Digitize clinic operations
- Reduce manual paperwork
- Improve patient experience
- Simplify appointment scheduling
- Enable online consultations
- Provide home healthcare services
- Digitize laboratory workflows
- Create a scalable healthcare ecosystem

---

# 👥 User Roles

## 👤 Patient

- Register & Login
- Book Clinic Appointments
- Book Home Visits
- Book Online Consultations
- Book Laboratory Tests
- View Medical History
- Download Prescriptions
- Download Laboratory Reports
- Online Payments
- Membership Management

---

## 👨‍⚕️ Doctor

- Dashboard
- View Appointments
- Manage Availability
- Upload Prescriptions
- Upload Exercise Plans
- View Patient History
- Recommend Laboratory Tests
- Online Consultation Management

---

## 🏥 Receptionist

- Register Walk-in Patients
- Book Appointments
- Book Laboratory Tests
- Queue Management
- Patient Check-In
- Payment Collection
- Receipt Generation
- Manage Doctor Schedule

---

## 🧪 Laboratory Technician

- Dashboard
- Assigned Home Collections
- Update Sample Status
- Upload Laboratory Reports
- Daily Schedule
- Booking Management

---

## ⚙️ Administrator

- Dashboard
- Manage Doctors
- Manage Patients
- Manage Receptionists
- Manage Laboratory Staff
- Manage Appointments
- Manage Laboratory Tests
- Membership Management
- Reports & Analytics
- Website Management

---

# 🌟 Core Modules

## 🏥 Physiotherapy Module

- Clinic Appointment
- Home Visit
- Online Consultation
- Appointment History
- Prescription Management
- Exercise Plans

---

## 🧪 Laboratory Module

- Laboratory Test Catalogue
- Home Sample Collection
- Health Packages
- Digital Reports
- Previous Reports
- Laboratory Booking Management

---

## 💳 Payment Module

- Online Payments
- Pay at Clinic
- Invoice Generation
- Payment History

---

## ⭐ PhysioCare Plus Membership

Membership is optional.

Patients receive benefits such as:

- Free Laboratory Tests
- Discounts on Laboratory Tests
- Discounts on Home Visits
- Exclusive Health Packages
- Seasonal Offers
- Priority Booking (Future)

---

## 🔔 Notification Module

- Appointment Confirmation
- Appointment Reminder
- Laboratory Report Ready
- Payment Confirmation
- Membership Renewal Reminder

---

# 🛠 Tech Stack

## Frontend

- React
- Vite
- Tailwind CSS
- Stitch AI (UI Design)

---

## Backend

- FastAPI
- Python

---

## Database

- MongoDB

---

## Authentication

- JWT Authentication
- Role-Based Access Control (RBAC)

---

## Version Control

- Git
- GitHub

---

# 💻 Local Development Setup

The active codebase lives in `backend/` (FastAPI) and `frontend/` (React + Vite). The `apps/` portals are legacy placeholders and are not part of the current build.

## Prerequisites

- **Node.js** 20.19+ or 22.12+ (tested with v26) and **npm** 10+
- **Python** 3.13 (tested with 3.13.5)
- **MongoDB** — a local MongoDB instance or a MongoDB Atlas cluster
- **Git**

## 1. Clone and check out the development branch

```bash
git clone https://github.com/vigneshreddyv/PhysioCare.git
cd PhysioCare
git checkout feature/auth-and-patient-ui
```

## 2. Backend setup (FastAPI — port 8000)

```bash
cd backend
python -m venv venv
```

Activate the virtual environment:

```bash
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
```

Install dependencies and create the local environment file:

```bash
pip install -r requirements.txt
cp .env.example .env   # Windows: copy .env.example .env
```

Edit `.env` and set your own values. **Never commit `.env`** (it is gitignored) and never reuse real production secrets in development:

| Variable | Where to get the value |
| --- | --- |
| `MONGODB_URL` | Your local MongoDB (`mongodb://localhost:27017`) or your MongoDB Atlas connection string |
| `DATABASE_NAME` | Any local database name, e.g. `physiocare` |
| `JWT_SECRET`, `JWT_REFRESH_SECRET` | Generate random strings; the values in `.env.example` are placeholders and must be replaced |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` | Razorpay Dashboard → Settings → API Keys (**test mode** keys) |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay Dashboard → Settings → Webhooks (only needed to test webhooks locally) |
| `PAYMENT_RECONCILIATION_ENABLED`, `REFUND_RECONCILIATION_ENABLED` | Leave `false` — no automatic expiry/reconciliation policy is approved by default |

Optional seed scripts (populate doctors, patients, and the laboratory test catalogue):

```bash
python seed.py
python seed_laboratory_tests.py
```

Start the backend:

```bash
python run.py
# API + docs at http://localhost:8000 (OpenAPI at /docs)
```

## 3. Frontend setup (React + Vite — port 5173)

```bash
cd frontend
npm install
cp .env.example .env   # Windows: copy .env.example .env
```

`.env` contains only the API endpoint (safe placeholder default):

```env
VITE_API_URL=http://localhost:8000/api
```

Start the dev server:

```bash
npm run dev
# App at http://localhost:5173
```

> CORS note: the backend currently allows origins `http://localhost:5173`, `http://127.0.0.1:5173` and a LAN address. If you serve the frontend from a different host/port on the new machine, add that origin to `allow_origins` in `backend/app/main.py`.

## 4. Tests, lint, and build

```bash
# Backend test suite (677 tests, no database or network required)
cd backend
python -m pytest tests/ -q

# Frontend lint and production build
cd frontend
npm run lint
npm run build
```

Frontend QA harness scripts live in `frontend/qa/` (Puppeteer-based; they require the frontend dev server and a running backend to be useful).

## 5. Configure separately on each machine (NOT in Git)

- `backend/.env` — MongoDB credentials, JWT secrets, Razorpay keys/webhook secret
- `frontend/.env` — API URL
- A MongoDB database with seed data (Git does **not** transfer database contents)
- Razorpay **test** credentials from your Razorpay account

---

# 📂 Project Structure

```text
PhysioCare/

├── apps/
│   ├── patient-web/
│   ├── doctor-portal/
│   ├── reception-portal/
│   ├── admin-portal/
│   └── lab-portal/
│
├── backend/
│   └── app/
│       ├── auth/
│       ├── patient/
│       ├── doctor/
│       ├── reception/
│       ├── laboratory/
│       ├── appointments/
│       ├── payments/
│       ├── membership/
│       ├── notifications/
│       ├── common/
│       ├── config/
│       └── models/
│
├── database/
│   ├── schema/
│   ├── seed/
│   └── diagrams/
│
├── api/
│   ├── docs/
│   └── postman/
│
├── docs/
├── scripts/
├── shared/
└── .github/
```

---

# 🚀 Development Roadmap

## ✅ Phase 1

- Repository Setup
- GitHub Workflow
- Documentation
- Project Architecture

---

## 🚧 Phase 2

- Database Design
- API Design
- Authentication System

---

## 📌 Phase 3

- Backend Development

---

## 📌 Phase 4

- Patient Portal

---

## 📌 Phase 5

- Doctor Portal

---

## 📌 Phase 6

- Reception Portal

---

## 📌 Phase 7

- Laboratory Portal

---

## 📌 Phase 8

- Admin Portal

---

## 📌 Phase 9

- Integration & Testing

---

## 📌 Phase 10

- Deployment

---

## 📌 Phase 11

- AI Features

---

# 🔮 Future Enhancements

- AI Receptionist
- Voice AI Assistant
- WhatsApp Appointment Booking
- AI Healthcare Assistant
- AI Analytics Dashboard
- Multi-Clinic Support
- Mobile Applications (Android & iOS)
- Pharmacy Module
- Radiology Module
- Nutrition Module

---

# 👨‍💻 Development Workflow

```text
Requirement
      ↓
Database Design
      ↓
API Design
      ↓
Backend Development
      ↓
Frontend UI (Stitch)
      ↓
Frontend Integration
      ↓
Testing
      ↓
Deployment
```

---

# 🤝 Contributors

### Project Lead

**Vignesh Reddy V**

### Contributors

- Contributor 1
- Contributor 2

---

# 📄 License

This repository is currently under active development for a client project.

All rights reserved.