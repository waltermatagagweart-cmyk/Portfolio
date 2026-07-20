# Aircraft Maintenance Log API

An async REST API serving the [Aircraft Maintenance Database](../aircraft-maintenance-db/README.md) — turns the SQL schema into a real, running backend service. Built to be the kind of API an MRO (maintenance, repair & overhaul) shop or fleet operator would actually deploy.

**Stack:** FastAPI · SQLAlchemy 2.0 (async) · asyncpg · Pydantic v2 · PostgreSQL · pytest + httpx · Docker

---

## Why this project

The [aircraft maintenance database](../aircraft-maintenance-db/README.md) project designed the data model. This project puts a service in front of it — the layer that a real fleet-management tool, a technician's tablet app, or an integration with another system would actually talk to. It demonstrates:

- **Async I/O end to end** — FastAPI + SQLAlchemy's async engine + asyncpg, not blocking sync calls wrapped in threads
- **Validation that mirrors the database's own rules** — Pydantic models enforce the same domain constraints as the SQL `CHECK` constraints (valid statuses, valid event types, valid certification types), so bad data is rejected before it reaches Postgres
- **Reusing the database's own views** — the report endpoints (`/reports/*`) query `v_fleet_status`, `v_overdue_inspections`, and `v_component_location` directly, instead of re-implementing that logic in Python
- **Proper HTTP semantics** — 201 on create, 404 on missing resources, 422 on validation failure, 400 on database-level constraint violations (e.g. a maintenance event pointing at a nonexistent aircraft)
- **A real, idempotent integration test suite** — 12 tests exercising the actual HTTP layer against a live PostgreSQL instance, safely re-runnable without a fresh database

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

**12 integration tests**, run against a real PostgreSQL instance via `httpx.ASGITransport` (so they exercise routing, validation, and serialization — not just isolated unit logic):

- Health check
- Create + retrieve aircraft, technicians
- 404 on missing resources
- 422 on schema-violating input (bad status, bad certification type)
- 400 on database-level constraint violations (event referencing a nonexistent aircraft; component hours recorded without a component)
- All three report endpoints return valid data shaped correctly

The suite is **idempotent** — a fixture cleans up its own test rows before and after the session, so it can be run back-to-back without a fresh database each time (verified: ran twice consecutively, 12/12 passed both times).

### A real bug this caught

Windows' default `ProactorEventLoop` doesn't support the raw socket operations `asyncpg` needs, and pytest-asyncio's default per-test event loop doesn't match a module-level async engine's connection pool — together these produced cascading `RuntimeError: Event loop is closed` failures that had nothing to do with the API logic itself. Fixed by switching to `WindowsSelectorEventLoopPolicy` and pinning pytest-asyncio to a single session-scoped loop (`conftest.py`, `pytest.ini`). Documented here because it's a real, non-obvious cross-platform async gotcha, not something swept under the rug.

---

## Design notes

- **ORM models mirror `schema.sql` exactly** — same tables, same `CHECK` constraints (expressed as Pydantic `pattern`/`ge`/`gt` validators), same nullable/required rules. `schema.sql` remains the single source of truth for the database itself; the ORM models here are a typed view onto it, not a competing definition.
- **One exception:** the partial unique index (`uq_component_open_install` — "a component can be installed in at most one place at a time") isn't expressible as a portable SQLAlchemy `UniqueConstraint`, so that rule is enforced by the database itself via `schema.sql`, exactly as it was in the original project. Noted directly in `main.py` rather than silently dropped.
- **Reports call the SQL views directly** (`SELECT * FROM v_fleet_status`, etc.) via `text()`, instead of re-deriving the same joins and aggregates in SQLAlchemy's query builder — the view is already correct and tested; duplicating its logic in Python would just create a second place for it to drift out of sync.
