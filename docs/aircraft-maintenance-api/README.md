# Aircraft Maintenance Log API

An async REST API serving the [Aircraft Maintenance Database](../aircraft-maintenance-db/README.md) — turns the SQL schema into a real, running backend service. Built to be the kind of API an MRO (maintenance, repair & overhaul) shop or fleet operator would actually deploy.

**Stack:** FastAPI · SQLAlchemy 2.0 (async) · asyncpg · Pydantic v2 · PostgreSQL · pytest + httpx · Docker

**Live demo:** https://aircraft-maintenance-api.onrender.com/docs (Swagger UI — free tier, first request after inactivity takes ~50s to wake up)

---

## Why this project

The [aircraft maintenance database](../aircraft-maintenance-db/README.md) project designed the data model. This project puts a service in front of it — the layer that a real fleet-management tool, a technician's tablet app, or an integration with another system would actually talk to. It demonstrates:

- **Async I/O end to end** — FastAPI + SQLAlchemy's async engine + asyncpg, not blocking sync calls wrapped in threads
- **Validation that mirrors the database's own rules** — Pydantic models enforce the same domain constraints as the SQL `CHECK` constraints (valid statuses, valid event types, valid certification types), so bad data is rejected before it reaches Postgres
- **Reusing the database's own views** — the report endpoints (`/reports/*`) query `v_fleet_status`, `v_overdue_inspections`, and `v_component_location` directly, instead of re-implementing that logic in Python
- **Proper HTTP semantics** — 201 on create, 404 on missing resources, 422 on validation failure, 400 on database-level constraint violations (e.g. a maintenance event pointing at a nonexistent aircraft)
- **Token auth on the routes that change data** — JWT bearer tokens, bcrypt-hashed credentials, reads left open so the API stays explorable
- **Rate limiting** with the standard `X-RateLimit-*` response headers
- **A real, idempotent integration test suite** — 18 tests exercising the actual HTTP layer against a live PostgreSQL instance, safely re-runnable without a fresh database

---

## Running it

### Option 1 — Docker Compose (easiest)

```bash
docker compose up
```

This starts Postgres, loads `schema.sql` from the sibling `aircraft-maintenance-db` project automatically, and starts the API. Docs live at **http://localhost:8000/docs**.

### Option 2 — local Python

```bash
# 1. Start Postgres and load the schema (see aircraft-maintenance-db/README.md)
# 2. Install dependencies
pip install -r requirements.txt

# 3. Point at your database
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/maintenance_log"

# 4. Run
uvicorn main:app --reload
```

Then open **http://localhost:8000/docs** for interactive Swagger UI, or **http://localhost:8000/redoc** for ReDoc.

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/aircraft` | Register a new aircraft |
| `GET` | `/aircraft/{id}` | Get one aircraft |
| `GET` | `/aircraft` | List aircraft (paginated) |
| `PUT` | `/aircraft/{id}` | Update an aircraft |
| `POST` | `/components` | Register a new component (part) |
| `GET` | `/components/{id}` | Get one component |
| `GET` | `/components` | List components (paginated) |
| `POST` | `/technicians` | Register a technician |
| `GET` | `/technicians/{id}` | Get one technician |
| `GET` | `/technicians` | List technicians (paginated) |
| `POST` | `/events` | Record a maintenance event |
| `GET` | `/events/{id}` | Get one event |
| `GET` | `/events?aircraft_id=` | List events, optionally filtered by aircraft |
| `GET` | `/reports/fleet-status` | Fleet at a glance — hours, status, open work count |
| `GET` | `/reports/overdue-inspections` | Inspections past their hour or date threshold |
| `GET` | `/reports/component-location` | Where every component is right now |
| `GET` | `/health` | Liveness + database connectivity check |
| `POST` | `/auth/token` | Exchange demo credentials for a bearer token |

Every `GET` is open. Every `POST` and `PUT` needs a bearer token.

---

## Authentication

Reads are public so anyone can explore the API without signing up for anything. Writes need a token.

```bash
# 1. Get a token
curl -X POST http://localhost:8000/auth/token \
  -d 'username=recruiter&password=aircraft-demo'
# -> {"access_token":"eyJhbGci...","token_type":"bearer"}

# 2. Use it
curl -X POST http://localhost:8000/aircraft \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"registration_number":"5Y-TST","model_id":1,"status":"Active"}'
```

In Swagger UI, the **Authorize** button does the same thing.

There is one demo account, set through `DEMO_USERNAME` and `DEMO_PASSWORD` rather than a users table. This is a portfolio demo over a small fake fleet, not a multi-tenant system, so a single shared credential is the right amount of auth for what it protects. The password is still hashed and checked with bcrypt rather than compared as a plain string, so the code path is the one a real multi-user version would use. Tokens are HS256 JWTs and expire after an hour by default.

Missing, malformed, expired, and forged tokens all return 401 with a `WWW-Authenticate` header.

## Rate limiting

A fixed-window limiter keyed by client IP, defaulting to 60 requests per minute. Every response carries `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`; going over returns 429. `/health` is exempt so a host's own health checks can't rate-limit the service into looking unhealthy.

The counters live in the process's own memory. That is correct for a single instance, which is what the free-tier deploy runs, but it would under-count across several instances since each would keep its own tally. A multi-instance deploy would need a shared store such as Redis. Stated here rather than left for someone to discover.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/maintenance_log` | Accepts `postgres://`, `postgresql://`, or `postgresql+asyncpg://`. SSL is required automatically for any non-local host. |
| `JWT_SECRET_KEY` | `dev-only-insecure-secret-change-me` | Set a real value anywhere that isn't your laptop. |
| `JWT_EXPIRE_MINUTES` | `60` | Token lifetime. |
| `DEMO_USERNAME` | `recruiter` | Demo account name. |
| `DEMO_PASSWORD` | `aircraft-demo` | Demo account password. |
| `RATE_LIMIT_MAX_REQUESTS` | `60` | Requests allowed per window. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Window length. |
| `RUN_DB_BOOTSTRAP` | `false` | Apply `schema.sql` on startup. Left off locally because docker-compose already loads it; turned on for hosted deploys. |

---

## Deploying it

`render.yaml` at the repository root is a Render Blueprint that provisions a free Postgres instance and the API together. In the Render dashboard: **New → Blueprint**, pick this repo, and set `DEMO_PASSWORD` when prompted. Everything else, including a generated `JWT_SECRET_KEY`, is handled by the blueprint.

Two details worth knowing about how this deploys:

**The image carries `schema.sql`.** Render's managed Postgres starts genuinely empty and has no init-script hook the way the local docker-compose Postgres does, so the API applies the schema itself on boot when `RUN_DB_BOOTSTRAP=true`. That is also why the Docker build context is the parent `projects/` directory rather than this folder: Docker cannot copy files from outside its build context, and the schema lives in the sibling database project. `schema.sql` is idempotent, so re-running it on every redeploy is safe.

**Free tier spins down.** After a period of inactivity the first request takes roughly 50 seconds while the service wakes up. Worth mentioning before sending anyone the link.

---

## Example: catching an out-of-domain value

The database schema constrains `aircraft.status` to `Active | In Maintenance | Stored | Retired` via a `CHECK` constraint. The API enforces the *same* rule at the HTTP boundary, so a bad request never reaches Postgres:

```bash
curl -X POST http://localhost:8000/aircraft \
  -H "Content-Type: application/json" \
  -d '{"registration_number":"5Y-BAD","model_id":1,"status":"Flying"}'

# -> 422 Unprocessable Entity
# "status": "Flying" doesn't match pattern '^(Active|In Maintenance|Stored|Retired)$'
```

## Example: reusing a database view

```bash
curl http://localhost:8000/reports/overdue-inspections
```
```json
[
  {
    "event_id": 3,
    "registration_number": "5Y-ABC",
    "event_type": "Scheduled Inspection",
    "description": "Annual inspection (airframe)",
    "next_due_hours": 4150.0,
    "total_airframe_hours": 4180.5,
    "hours_overdue": 30.5,
    "next_due_date": "2025-06-01",
    "work_status": "Open"
  }
]
```

This is the exact same result the `v_overdue_inspections` SQL view returns — the API is a thin, honest layer over logic that already lives correctly in the database.

---

## Testing

```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/maintenance_log"
pytest test_api.py -v
```

**18 integration tests**, run against a real PostgreSQL instance via `httpx.ASGITransport` (so they exercise routing, validation, and serialization — not just isolated unit logic):

- Health check
- Create + retrieve aircraft, technicians
- 404 on missing resources
- 422 on schema-violating input (bad status, bad certification type)
- 400 on database-level constraint violations (event referencing a nonexistent aircraft; component hours recorded without a component)
- All three report endpoints return valid data shaped correctly
- Writes rejected with no token, and with a forged one
- Login rejected on a wrong password, accepted on the right one, and the issued token then works on a write
- 429 once the rate limit is crossed, with the `X-RateLimit-*` headers present, and `/health` exempt from it

The suite is **idempotent** — a fixture cleans up its own test rows before and after the session, so it can be run back-to-back without a fresh database each time (verified: ran twice consecutively, 18/18 passed both times).

### A real bug this caught

Windows' default `ProactorEventLoop` doesn't support the raw socket operations `asyncpg` needs, and pytest-asyncio's default per-test event loop doesn't match a module-level async engine's connection pool — together these produced cascading `RuntimeError: Event loop is closed` failures that had nothing to do with the API logic itself. Fixed by switching to `WindowsSelectorEventLoopPolicy` and pinning pytest-asyncio to a single session-scoped loop (`conftest.py`, `pytest.ini`). Documented here because it's a real, non-obvious cross-platform async gotcha, not something swept under the rug.

---

## Design notes

- **ORM models mirror `schema.sql` exactly** — same tables, same `CHECK` constraints (expressed as Pydantic `pattern`/`ge`/`gt` validators), same nullable/required rules. `schema.sql` remains the single source of truth for the database itself; the ORM models here are a typed view onto it, not a competing definition.
- **One exception:** the partial unique index (`uq_component_open_install` — "a component can be installed in at most one place at a time") isn't expressible as a portable SQLAlchemy `UniqueConstraint`, so that rule is enforced by the database itself via `schema.sql`, exactly as it was in the original project. Noted directly in `main.py` rather than silently dropped.
- **Reports call the SQL views directly** (`SELECT * FROM v_fleet_status`, etc.) via `text()`, instead of re-deriving the same joins and aggregates in SQLAlchemy's query builder — the view is already correct and tested; duplicating its logic in Python would just create a second place for it to drift out of sync.
