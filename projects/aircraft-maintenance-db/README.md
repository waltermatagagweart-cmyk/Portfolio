# ✈️ Aircraft Maintenance Log — PostgreSQL Database

A relational database that tracks aircraft, the components installed in them, the
maintenance performed, who signed it off, and the full installation history of every
part — designed to airworthiness-record standards.

Built by **Walter Matagagwe** as a demonstration of relational database design in
PostgreSQL.

## What's in here

| File | What it is |
|---|---|
| [`schema.sql`](schema.sql) | The full database — tables, constraints, triggers, indexes, views, functions, and sample data. Re-runnable. |
| [`queries.sql`](queries.sql) | Eight demonstration queries that answer real maintenance questions. |
| [`DESIGN.md`](DESIGN.md) | The design write-up: every decision and **why it works**. Start here. |

## The model at a glance

Eight tables across three kinds:
- **Things** that persist — `aircraft`, `component`, `technician`
- **An event** that happened — `maintenance_event`
- **Lookups & links** — `aircraft_model`, `part_catalog`, `event_technician` (junction),
  `component_installation` (history)

## Highlights

- **3rd Normal Form**, with lookup tables that remove transitive dependencies
  (`model → manufacturer`, `part_number → component_type`).
- A **many-to-many** (event ↔ technician) resolved with a junction table carrying a
  `role`, so a mechanic *and* an inspector can both sign off one event.
- Full **part-installation history** with a **partial unique index** enforcing "one part,
  one location at a time," kept in sync with a fast current-location pointer by a
  **trigger**.
- Declarative **CHECK constraints**, an **ENUM** type, deliberate **referential actions**
  (`RESTRICT` protects legal records), indexed foreign keys, a **partial index** for the
  overdue report, and **views** as a stable query API.

## Run it

Fastest path (Supabase or any Postgres SQL editor): paste `schema.sql`, run it, then
paste `queries.sql`. Full instructions — including a one-line Docker setup — are in
[DESIGN.md §9](DESIGN.md).
