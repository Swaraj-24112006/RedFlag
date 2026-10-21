# KSPG RedFlag & SFC Manufacturing Platform

Enterprise Shop Floor Control (SFC) and Red Flag Management System for KSPG manufacturing plants, engineered according to the **KSPG Cockpit Integration Specification**.

---

## 🏗 System Architecture

```text
SFC/
├── frontend/               # React 18 SPA (Vite + TailwindCSS + Lucide Icons)
│   ├── src/                # SFC & RedFlag frontend modules & components
│   ├── package.json
│   └── vite.config.ts      # Configured to proxy /api requests to backend
│
├── backend/                # Django REST Framework Microservice
│   ├── apps/
│   │   ├── accounts/       # Custom User model, Roles, JWT Token endpoints
│   │   ├── masterdata/     # Departments, Plants (MF1-MF3), Lines, Stations
│   │   ├── common/         # MinIO S3 storage, permissions, exceptions, /health
│   │   └── redflag/        # RedFlag domain models (Phase 2 ready)
│   ├── config/             # Django settings (base, dev, prod) & URL routing
│   ├── tests/              # pytest test suite & factory-boy fixtures
│   ├── docker-compose.yml  # PostgreSQL + MinIO + Backend orchestration
│   ├── Dockerfile
│   └── requirements.txt
│
├── .github/workflows/      # Automated CI workflow (Ruff lint + Pytest)
└── MODULE_INTEGRATION_SPEC.md # Enterprise Gateway & Microservice Contract
```

---

## 🚀 Running the Stack

### 1. Backend (Django + PostgreSQL + MinIO)
Using Docker Compose:
```bash
cd backend
docker compose up -d
```
* API Server: `http://localhost:8000/api/`
* Swagger UI: `http://localhost:8000/api/docs/`
* Health Check: `http://localhost:8000/api/health/`
* MinIO Console: `http://localhost:9001/` (minioadmin / minioadmin)

Or running locally with Python:
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_masterdata
python manage.py seed_demo_users
python manage.py runserver 0.0.0.0:8000
```

### 2. Frontend (React 18 + Vite)
```bash
cd frontend
npm install
npm run dev
```
* Frontend Application: `http://localhost:5173/`

---

## 👥 Seeded Demo Users (Password: `demo12345`)
* `operator` (OPERATOR, Production, `EMP-OP-001`)
* `supervisor` (SUPERVISOR, Production, `EMP-SUP-002`)
* `deptlead` (DEPT_LEAD, Production, `EMP-DL-003`)
* `qainspector` (QA_INSPECTOR, Quality, `EMP-QA-004`)
* `qacustodian` (QA_CUSTODIAN, Quality, `EMP-QC-005` - Default assigned custodian)
* `planthead` (PLANT_HEAD, Production, `EMP-PH-006`)
* `admin` (ADMIN, Quality, `EMP-ADM-007` - Superuser)

---

## 🧪 Automated Testing
```bash
cd backend
pytest
```
