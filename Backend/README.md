# ColdChain Pulse — Backend (FastAPI)

REST API for MedSwift Logistics' cold-chain tracking MVP. Covers every backend item in the capstone brief:
RBAC (5 roles), shipments/dispatch, telemetry + alert engine, QR+PIN handoffs, offline sync, append-only
tamper-evident logs, PDF/CSV audit reports, IoT simulator, migrations.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
python -m app.seed --shipments 50                       # demo users + shipments (password: Passw0rd!demo)
uvicorn app.main:app --reload                           # docs at http://localhost:8000/docs
python scripts/simulate.py --interval 30                # IoT simulator (30 s, as in the brief)
pytest                                                  # 28 tests
```
Demo logins: `admin@medswift.io`, `dispatcher@medswift.io`, `driver1@medswift.io`, `clinic1@medswift.io`,
`auditor@medswift.io` (all `Passw0rd!demo`; demo PIN `123456`).

## Roles
| Role | Can |
|---|---|
| admin | everything, create users, run simulator, audit logs |
| dispatcher | create/assign/update shipments, vehicles, alerts, reports |
| driver | own shipments only: pickup handoff, push telemetry, `/sync`, acknowledge alerts |
| clinic_receiver | own shipments only: delivery handoff |
| auditor | read-only: shipments, alerts, reports, audit logs |

## Endpoints (all need `Authorization: Bearer <token>` except /health and /auth/login)
| Method & path | Who | Purpose |
|---|---|---|
| POST /auth/login · GET /auth/me | all | JWT login (5 failed tries → 15 min lock; every failure audited) |
| POST/GET /users · POST/GET /vehicles | admin, dispatcher | users & fleet |
| POST /shipments | dispatcher, admin | create; response shows `qr_token` + 2 PINs **once** |
| GET /shipments?status=&alert_state=&page=&page_size= | all (scoped) | paginated list (max 200) |
| GET/PATCH /shipments/{id} · GET /shipments/{id}/qr | dispatcher, admin | detail, re-assign, thresholds, ETA; QR payload to print |
| GET /shipments/{id}/telemetry · /handoffs | all (scoped) | history |
| POST /shipments/{id}/handoffs | driver (pickup) / clinic_receiver (delivery) | QR + PIN or signature, GPS, condition |
| POST /telemetry | admin, driver | single reading or batch; idempotent via `client_uuid` |
| POST /sync | driver, clinic_receiver | **offline queue flush**: telemetry + handoffs in one call, retry-safe |
| GET /alerts?since=&level=&unacknowledged= · POST /alerts/{id}/acknowledge | admin, dispatcher, driver | Warning / Critical alerts (poll with `since`) |
| GET /dashboard/summary | staff, driver | counts by status / alert state (SQL aggregates) |
| GET /reports/shipments/{id}.csv · .pdf · /verify | admin, dispatcher, auditor | audit reports + hash-chain verification |
| GET /audit-logs | admin, auditor | failed logins etc. |
| POST /simulator/tick | admin | one temp/humidity reading for every in-transit shipment |

## How the key rules are met
* **Alerts**: Warning = within 1 °C of a limit or just left range; Critical = continuously out of range ≥ 10 min
  (uses sensor timestamps, so offline-synced data is judged correctly). One alert per upward transition → no spam.
* **Append-only**: no PUT/PATCH/DELETE routes for logs + ORM guard raises `AppendOnlyError` on update/delete +
  per-shipment SHA-256 hash chain; `/reports/.../verify` detects direct DB edits and deleted rows.
* **Security**: bcrypt hashes, JWT, role check on every route, row-level scoping, security headers, audit log.
* **Offline-first** (frontend contract): the PWA generates a `client_uuid` (UUID v4) for every reading/handoff
  when it is *created*, stores it in IndexedDB, and uploads with `POST /sync` when online. Re-sending is safe.
* **Migrations**: `alembic revision --autogenerate -m "msg"` then `alembic upgrade head`.

## Deploy (Vercel + free Postgres)
Vercel's disk is not persistent, so use a hosted Postgres (Neon or Supabase, free tier).
1. Create the DB, copy its URL. Run migrations once from your laptop:
   `DATABASE_URL="postgresql://..." AUTO_CREATE_TABLES=0 alembic upgrade head` then
   `DATABASE_URL="postgresql://..." python -m app.seed --shipments 50`
2. Import the repo in Vercel (this folder = root). Env vars: `DATABASE_URL`, `SECRET_KEY` (long random),
   `CORS_ORIGINS` (frontend URL), `AUTO_CREATE_TABLES=0`.
3. Vercel can't run a background loop, so run the simulator from any machine:
   `python scripts/simulate.py --base-url https://<your-app>.vercel.app`

## Push to GitHub
```bash
git add . && git commit -m "feat(backend): ..." && git push origin <your-branch>
```
