# Dorwaila Hotel API

Starter REST API for the DORWAILA INN'S & SUIT HOTEL Management System. It currently provides account management, role-scoped department activity, rooms and reservations, multi-currency reservation payments, expense submission/approval, and Admin-only expense reports.

## Requirements

- Python 3.12+ for local development, or Docker Desktop with Compose.
- PostgreSQL for a shared deployment. SQLite can be used for local experimentation.

## Run locally with SQLite

From this `backend` directory in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
```

Edit `.env`: set `SECRET_KEY` to a random value of at least 32 characters, and set `DATABASE_URL=sqlite:///./dorwaila_dev.db`.

Then install and start:

```powershell
python -m pip install -r requirements.txt
python -m app.bootstrap_admin
uvicorn app.main:app --reload
```

Before running `bootstrap_admin`, set the first account details in the current PowerShell session; do not put a real password in source code:

```powershell
$env:BOOTSTRAP_ADMIN_EMAIL = "admin@your-hotel.example"
$env:BOOTSTRAP_ADMIN_NAME = "Hotel Administrator"
$env:BOOTSTRAP_ADMIN_PASSWORD = Read-Host "Initial Admin password"
python -m app.bootstrap_admin
Remove-Item Env:BOOTSTRAP_ADMIN_EMAIL, Env:BOOTSTRAP_ADMIN_NAME, Env:BOOTSTRAP_ADMIN_PASSWORD
```

Open `http://127.0.0.1:8000/docs` for the interactive OpenAPI page. Sign in at `/api/v1/auth/token` with the Admin email as the OAuth2 username and the password. The first Admin account can then create departmental accounts.

## Run with Docker Compose and PostgreSQL

Copy `.env.example` to `.env`, then set a unique `SECRET_KEY` (at least 32 characters) and a strong URL-safe `POSTGRES_PASSWORD`. From this directory:

```powershell
docker compose up --build -d
docker compose exec api python -m app.bootstrap_admin
```

Pass the bootstrap values into the one-time container process. In PowerShell:

```powershell
$env:BOOTSTRAP_ADMIN_EMAIL = "admin@your-hotel.example"
$env:BOOTSTRAP_ADMIN_NAME = "Hotel Administrator"
$env:BOOTSTRAP_ADMIN_PASSWORD = Read-Host "Initial Admin password"
docker compose exec -e BOOTSTRAP_ADMIN_EMAIL -e BOOTSTRAP_ADMIN_NAME -e BOOTSTRAP_ADMIN_PASSWORD api python -m app.bootstrap_admin
Remove-Item Env:BOOTSTRAP_ADMIN_EMAIL, Env:BOOTSTRAP_ADMIN_NAME, Env:BOOTSTRAP_ADMIN_PASSWORD
```

The API is available at `http://localhost:8000` for local use; production deployments must terminate HTTPS and restrict database access.

## Implemented endpoint groups

- `POST /api/v1/auth/token`, `GET /api/v1/auth/me`
- Admin user management: `GET/POST /api/v1/admin/users`, and enable/disable account endpoints
- Room and reservation operations: `/api/v1/rooms`, `/api/v1/reservations`
- Reservation payments: `/api/v1/reservations/{id}/payments`
- Department activity: `/api/v1/departments/{department}/activities`
- Expenses and approvals: `/api/v1/expenses`
- Admin reporting and audit history: `/api/v1/admin/reports/*`, `/api/v1/admin/audit-logs`

FastAPI's generated API documentation lists request fields and response shapes.

## Important limitations before production

- The bootstrap command creates tables for a fresh database. Use versioned Alembic migrations before deploying schema changes to production.
- Room conflict checking is implemented in application logic; high-concurrency production booking needs a database-level exclusion/locking strategy to prevent two simultaneous requests from reserving the same room.
- Report totals are grouped by original currency. Exchange-rate capture and SLE conversion, receipt uploads, inventory workflows, HR records, and full department-specific screens are not implemented yet.
- The first increment records payments but does not yet provide refund/void workflows or accounting-ledger reconciliation.
- Production deployment also needs HTTPS, a managed secret store, database and document backups, restore checks, monitoring, and an Admin recovery procedure.

## Design reference

See [`../docs/SYSTEM_DESIGN.md`](../docs/SYSTEM_DESIGN.md) for the full product requirements and target data model.
