# Aircraft Maintenance Log — Database Design

**Author:** Walter Matagagwe · **Engine:** PostgreSQL 14+ · **Files:** [`schema.sql`](schema.sql) · [`queries.sql`](queries.sql)

This document explains *how* the database is built and *why each decision works*. The
schema itself is heavily commented; this is the narrative behind it — the part that
shows the reasoning, not just the result.

---

## 1. What the database is for

An aircraft maintenance log has to answer questions that are, in real aviation,
**legally required** and safety-critical:

- Which parts are installed on which aircraft *right now*?
- What maintenance has been done, when, and on what?
- Who performed the work, and who inspected and signed it off?
- Where has a given part been over its whole life? (airworthiness traceability)
- What is *overdue* or due soon?

Every design choice below traces back to answering one of those questions correctly.

---

## 2. The core modelling idea — *things* vs *events*

The first and most important distinction: some entities **exist and persist**
(an aircraft, a part, a technician), while others are a **record of something that
happened at a point in time** (a maintenance action).

- `aircraft`, `component`, `technician` → *things*
- `maintenance_event` → an *event*

**Why this matters:** events reference things; things never reference events. Getting
this right up front is what keeps the relationships clean later — a maintenance event
points at the aircraft it happened to, but an aircraft never stores a list of its
events (that would not fit in a single row, and would violate 1NF).

---

## 3. The tables

| Table | Kind | Answers |
|---|---|---|
| `aircraft_model` | lookup | "what make/model is this?" |
| `part_catalog` | lookup | "what kind of part is this?" |
| `aircraft` | thing | "which airplane?" |
| `component` | thing | "which physical part?" |
| `technician` | thing | "who is this person?" |
| `maintenance_event` | event | "what work, when, on what?" |
| `event_technician` | junction | "who worked on this event, in what role?" |
| `component_installation` | history | "where has this part been?" |

---

## 4. Relationships and why the keys land where they do

| Relationship | Type | Foreign key lives on | Why |
|---|---|---|---|
| Aircraft → Component | 1-to-many | `component.current_aircraft_id` | one airframe holds many parts; a part sits in one airframe at a time — so the reference goes on the "many" side |
| Aircraft → Maintenance_Event | 1-to-many | `maintenance_event.aircraft_id` | many events per airframe; each event is about one airframe |
| Component → Maintenance_Event | 1-to-many (optional) | `maintenance_event.component_id` | component-level events point at a part; airframe-level events leave it `NULL` |
| Maintenance_Event ↔ Technician | **many-to-many** | `event_technician` (junction) | an event can have a mechanic *and* an inspector; a technician works many events — this cannot be a single column, so it needs its own table |
| Component ↔ Aircraft over time | **many-to-many over time** | `component_installation` | a part moves between airframes; each stay is one row |

**The general rule applied throughout:** in a one-to-many, the foreign key goes on the
"many" side. A single flat row cannot hold a list, so the side that would need the list
is the side that instead gets pointed *at*.

---

## 5. Primary keys — surrogate vs natural

Every "thing" has a genuine real-world identifier — a **tail number**, a part
**serial number**, a **licence number**. Each is truly unique. Yet the primary key of
each of those tables is an *invented* integer (`aircraft_id`, `component_id`,
`technician_id`), and the natural identifier is kept as a separate `UNIQUE NOT NULL`
column.

**Why invent a key when a natural one exists?** Because real-world identifiers can
change: an aircraft gets re-registered when sold across borders; a serial gets a typo
corrected; formats vary between authorities. Relationships built on a value that can
change are fragile — every referencing row would have to be updated. An internal key
that *means nothing outside the database and never changes* is a stable anchor. This is
a standard, deliberate pattern, not a normalization quirk.

**The one exception — the junction table.** `event_technician` uses a **composite
primary key** `(event_id, technician_id)` instead of a new surrogate. This table does
not represent a "thing" with its own identity; it exists purely to record a pair. The
correctness rule we want — *no technician recorded twice on the same event* — is
exactly that pair being unique. Adding a third invented column would add bookkeeping
without adding meaning, so here the natural composite key is the right call.

---

## 6. Normalization — reaching 3NF on purpose

The design is in **Third Normal Form**, and the two lookup tables are the reason.

- **Transitive dependency `model → manufacturer`.** A "Cessna 172S" is always a Cessna.
  If `manufacturer` lived on `aircraft`, the same fact would repeat on every airframe of
  that model, and correcting a manufacturer name would mean editing many rows. Moving it
  to `aircraft_model` stores it **once**. `aircraft` just references the model.
- **Transitive dependency `part_number → component_type/description`.** Every "GTX-345"
  is a Garmin transponder. That belongs to the *part number* in `part_catalog`, not to
  each serial-numbered `component`.

Both are classic 3NF fixes: an attribute that depends on a non-key attribute is lifted
into its own table keyed by that attribute. The payoff is no update anomalies — one
place to change each fact, and impossible to have two contradictory copies.

> **Portfolio note:** spotting and *naming* these transitive dependencies is worth more
> than silently avoiding them. The schema comments call them out explicitly.

---

## 7. Modern techniques used — and why each one works

This is where the design goes beyond a textbook schema.

### 7.1 Declarative integrity (let the database enforce the rules)
- **`CHECK` constraints** encode business rules the data can never violate: hours are
  never negative; a life-limited part *must* carry a life limit; a removal date can't
  precede its install date; component-hours can only be recorded when an event actually
  references a component. Putting these in the schema means a bug in *any* application
  can't corrupt the data — the database refuses it.
- **`ENUM` type for `tech_role`** — the role set (Performer/Inspector/Supervisor) is
  genuinely fixed and tiny, so a custom type documents it and constrains it at the type
  level. Statuses that are *likely to grow* (event types, component states) use `CHECK`
  lists instead, which are trivially extended with one line. Choosing the right tool per
  set — not blanket-applying one — is the actual skill.

### 7.2 A partial UNIQUE index as a business rule
```sql
CREATE UNIQUE INDEX uq_component_open_install
    ON component_installation (component_id) WHERE removed_date IS NULL;
```
This enforces *"a physical part can be installed in only one place at a time"* — there
can be at most one **open** installation (no removal date) per component. A plain unique
constraint couldn't express "only among the open rows"; a partial index can. The rule
lives in the schema, so it holds no matter how data gets inserted.

### 7.3 Triggers to keep derived data honest
- `set_updated_at()` stamps `updated_at` on every `UPDATE`, so freshness never depends
  on the application remembering to.
- `sync_component_location()` keeps the fast `component.current_aircraft_id` pointer and
  the component `status` in step with the `component_installation` history: inserting an
  installation places the part; recording a removal frees it back to stock. This lets us
  keep **both** a cheap "where is it now?" lookup **and** a full history, without them
  ever drifting apart.

### 7.4 Deliberate referential actions
Foreign keys don't just exist — each declares what happens on delete:
- Maintenance and signoff records use **`ON DELETE RESTRICT`** — airworthiness records
  are legally retained, so the database *forbids* deleting an aircraft or technician that
  still has history. Safety by refusal.
- `component.current_aircraft_id` uses **`ON DELETE SET NULL`** — retiring an airframe
  shouldn't delete the parts; they simply become unassigned.
- Most keys use **`ON UPDATE CASCADE`** so surrogate-key changes propagate cleanly.

### 7.5 Performance built in, not bolted on
- **Every foreign key is indexed.** PostgreSQL indexes primary keys automatically but
  *not* the foreign keys that point at them, so joins and cascade checks would do
  sequential scans without these.
- The **partial index** `idx_event_open` covers only non-completed work — a small index
  that is exactly the set the overdue report scans.

### 7.6 Views as a stable query API
The recurring questions (`v_fleet_status`, `v_overdue_inspections`,
`v_component_location`, `v_event_signoffs`) are defined once as views. Applications query
a clean, stable name instead of re-deriving multi-table joins — and the join logic lives
in one place. The signoff view uses the modern **`FILTER (WHERE …)`** aggregate to pivot
performer and inspector into separate columns.

### 7.7 Timestamps and self-documentation
- `TIMESTAMPTZ` (timezone-aware) everywhere, so a maintenance action is unambiguous
  across regions — the correct modern default over naive timestamps.
- `COMMENT ON` metadata on key tables/columns/indexes means the schema explains itself
  inside any database GUI or `\d+` in psql.

---

## 8. How the target questions get answered

| Question | How |
|---|---|
| Overdue inspections | `v_overdue_inspections` — open work whose hour- or date-threshold has passed |
| Parts per aircraft | `v_component_location` grouped by aircraft (see `queries.sql` Q3) |
| Part history / traceability | `component_installation`, one row per install (Q4) |
| Life-limited retirement planning | `fn_component_hours_remaining()` (Q5) |
| Legal signoffs | `v_event_signoffs` — performer + inspector per event (Q6) |

---

## 9. How to run it

**Option A — Supabase / any Postgres (no install):** open the SQL editor, paste
`schema.sql`, run it, then paste `queries.sql`.

**Option B — local, with Docker:**
```bash
docker run -d --name amdb -e POSTGRES_PASSWORD=pw -e POSTGRES_DB=maint postgres:16
docker exec -i amdb psql -U postgres -d maint < schema.sql
docker exec -i amdb psql -U postgres -d maint < queries.sql
```

**Option C — existing local Postgres:**
```bash
createdb maint && psql -d maint -f schema.sql && psql -d maint -f queries.sql
```

---

## 10. Deliberately deferred (a v2 roadmap)

Scope was kept honest. These are known, intentional extensions:

- **Time-based maintenance programs** — a `maintenance_schedule` table defining recurring
  tasks (every N hours / months), so "due" is computed rather than hand-entered per event.
- **Work orders** grouping several events into one shop visit.
- **Row-level security & roles** (natural next step given the Supabase stack) so mechanics
  and auditors see appropriate slices.
- **Parts inventory / supplier** tables for procurement.

Each is additive — it bolts on new tables without reworking the eight here, which is
itself a sign the core model is sound.
