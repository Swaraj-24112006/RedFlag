# KSPG RedFlag Backend Service (Django REST Framework)

Decoupled manufacturing backend service for the **KSPG Cockpit Enterprise Gateway**. Built using **Django 5.1**, **Django REST Framework**, **SimpleJWT**, **PostgreSQL**, and **MinIO (S3)**.

---

## 🚀 Quick Start with Docker Compose

To spin up all services (PostgreSQL, MinIO with automated bucket provisioning, and Django backend):

```bash
docker compose up -d
```

Once running:
* **API Endpoints**: `http://localhost:8000/api/`
* **Health Check**: `http://localhost:8000/api/health/`
* **Swagger API Docs**: `http://localhost:8000/api/docs/`
* **MinIO Console**: `http://localhost:9001/` (Login: `minioadmin` / `minioadmin`)

---

## 🛠 Local Development Setup (Direct Python)

### 1. Create and Activate Virtual Environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Migrations
```bash
python manage.py migrate
```

### 4. Seed Master Data & Demo Users
```bash
python manage.py seed_masterdata
python manage.py seed_demo_users
```

### 5. Start Development Server
```bash
python manage.py runserver 0.0.0.0:8000
```

---

## 👥 Seeded Demo Users (Password for all: `demo12345`)

| Username | Role | Department | Employee ID | Description |
|---|---|---|---|---|
| `operator` | `OPERATOR` | Production | `EMP-OP-001` | Shop floor operator (can raise flags) |
| `supervisor` | `SUPERVISOR` | Production | `EMP-SUP-002` | Line shift supervisor |
| `deptlead` | `DEPT_LEAD` | Production | `EMP-DL-003` | Department leader |
| `qainspector`| `QA_INSPECTOR`| Quality | `EMP-QA-004` | Quality inspector |
| `qacustodian`| `QA_CUSTODIAN`| Quality | `EMP-QC-005` | QA Custodian (Default flag assignment) |
| `planthead` | `PLANT_HEAD` | Production | `EMP-PH-006` | Plant manager |
| `admin` | `ADMIN` | Quality | `EMP-ADM-007` | System admin (`is_superuser=True`) |

---

## 🧪 Testing and Linting

Run the automated test suite:
```bash
pytest
```

Run Ruff linter:
```bash
ruff check .
```

---

## 📡 Key API Endpoints (Phase 1)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/health/` | Service health check (checks DB & MinIO) | No |
| `POST` | `/api/auth/token/` | Obtain JWT access + refresh token | No |
| `POST` | `/api/auth/token/refresh/` | Refresh JWT access token | No |
| `GET` | `/api/auth/me/` | Current user profile, role, & dept | Yes (Bearer token) |
| `GET` | `/api/masterdata/departments/` | List departments (`?is_internal=true`) | Yes |
| `GET` | `/api/masterdata/plants/` | List plants (MF1, MF2, MF3) | Yes |
| `GET` | `/api/masterdata/lines/` | List lines (`?plant=<id>`) | Yes |
| `GET` | `/api/masterdata/stations/` | List stations (`?line=<id>`) | Yes |
| `GET` | `/api/schema/` | OpenAPI 3.0 YAML/JSON schema | No |
| `GET` | `/api/docs/` | Interactive Swagger UI | No |
