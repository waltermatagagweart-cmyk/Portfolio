-- =============================================================================
--  AIRCRAFT MAINTENANCE LOG  —  DATABASE SCHEMA
--  Author : Walter Matagagwe
--  Engine : PostgreSQL 14+
--  Purpose: Track aircraft, the components installed in them, the maintenance
--           performed, who signed it off, and full part-installation history —
--           to airworthiness-record standards.
--
--  This file is idempotent: it drops and recreates everything, so you can run it
--  as many times as you like. Load order below is deliberate — parents before
--  children — so foreign keys always point at something that already exists.
-- =============================================================================

-- ---- clean slate (child objects first) -------------------------------------
DROP VIEW  IF EXISTS v_event_signoffs, v_component_location,
                     v_overdue_inspections, v_fleet_status              CASCADE;
DROP TABLE IF EXISTS event_technician, component_installation,
                     maintenance_event, component, aircraft,
                     technician, part_catalog, aircraft_model           CASCADE;
DROP FUNCTION IF EXISTS set_updated_at()                                CASCADE;
DROP FUNCTION IF EXISTS sync_component_location()                       CASCADE;
DROP FUNCTION IF EXISTS fn_component_hours_remaining(INT)               CASCADE;
DROP TYPE IF EXISTS tech_role                                          CASCADE;

-- A custom ENUM domain for the ONE set that is genuinely fixed and tiny.
-- (Extensible sets like statuses use CHECK constraints instead — see DESIGN.md.)
CREATE TYPE tech_role AS ENUM ('Performer', 'Inspector', 'Supervisor');


-- =============================================================================
--  1. LOOKUP TABLES  — these exist to reach 3rd Normal Form.
--     They hold facts that depend on a TYPE, not on a physical instance,
--     so we store each such fact once instead of repeating it on every row.
-- =============================================================================

-- An aircraft MODEL. Fixes the transitive dependency model -> manufacturer:
-- a "Cessna 172S" is always a Cessna, so manufacturer belongs to the model,
-- not to every individual airframe.
CREATE TABLE aircraft_model (
    model_id       SERIAL PRIMARY KEY,
    manufacturer   VARCHAR(60) NOT NULL,
    model_name     VARCHAR(60) NOT NULL,
    type_category  VARCHAR(30) NOT NULL
                   CHECK (type_category IN ('SEP','MEP','Turboprop','Jet','Helicopter')),
    typical_seats  SMALLINT CHECK (typical_seats > 0),
    UNIQUE (manufacturer, model_name)
);

-- A part CATALOGUE entry (a "kind of part"), keyed by its manufacturer part
-- number. Fixes the transitive dependency part_number -> component_type:
-- the type/description belong to the part number, not to each serial-numbered
-- physical unit.
CREATE TABLE part_catalog (
    part_number               VARCHAR(40) PRIMARY KEY,   -- natural key: a real catalogue number
    component_type            VARCHAR(40) NOT NULL,
    description               VARCHAR(120) NOT NULL,
    is_life_limited           BOOLEAN NOT NULL DEFAULT FALSE,
    default_life_limit_hours  NUMERIC(10,1)
                              CHECK (default_life_limit_hours IS NULL OR default_life_limit_hours > 0),
    -- integrity rule: a life-limited part MUST declare a limit, and vice-versa
    CHECK ( (is_life_limited AND default_life_limit_hours IS NOT NULL)
         OR (NOT is_life_limited AND default_life_limit_hours IS NULL) )
);


-- =============================================================================
--  2. CORE ENTITIES — the "things that exist" (they persist over time).
-- =============================================================================

CREATE TABLE aircraft (
    aircraft_id           SERIAL PRIMARY KEY,          -- stable surrogate key
    registration_number   VARCHAR(10) NOT NULL UNIQUE, -- natural id (tail number), kept unique
    model_id              INT NOT NULL
                          REFERENCES aircraft_model(model_id)
                          ON UPDATE CASCADE ON DELETE RESTRICT,
    msn                   VARCHAR(30) UNIQUE,           -- manufacturer serial of the airframe
    total_airframe_hours  NUMERIC(10,1) NOT NULL DEFAULT 0 CHECK (total_airframe_hours  >= 0),
    total_airframe_cycles INT           NOT NULL DEFAULT 0 CHECK (total_airframe_cycles >= 0),
    status                VARCHAR(20)   NOT NULL DEFAULT 'Active'
                          CHECK (status IN ('Active','In Maintenance','Stored','Retired')),
    created_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE component (
    component_id          SERIAL PRIMARY KEY,
    serial_number         VARCHAR(40) NOT NULL UNIQUE,  -- natural id of the physical part
    part_number           VARCHAR(40) NOT NULL
                          REFERENCES part_catalog(part_number)
                          ON UPDATE CASCADE ON DELETE RESTRICT,
    -- WHERE THE PART IS RIGHT NOW. Named "current_" on purpose: it is a fast
    -- denormalised pointer, kept in sync by a trigger from component_installation.
    -- NULL = the part is a spare, sitting in stores, installed nowhere.
    current_aircraft_id   INT
                          REFERENCES aircraft(aircraft_id)
                          ON UPDATE CASCADE ON DELETE SET NULL,
    time_since_new_hours  NUMERIC(10,1) NOT NULL DEFAULT 0 CHECK (time_since_new_hours  >= 0),
    time_since_new_cycles INT           NOT NULL DEFAULT 0 CHECK (time_since_new_cycles >= 0),
    life_limit_hours      NUMERIC(10,1) CHECK (life_limit_hours IS NULL OR life_limit_hours > 0),
    status                VARCHAR(20)   NOT NULL DEFAULT 'In Stock'
                          CHECK (status IN ('Installed','In Stock','Removed','Scrapped')),
    created_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE technician (
    technician_id      SERIAL PRIMARY KEY,
    license_number     VARCHAR(30) NOT NULL UNIQUE,     -- natural id
    first_name         VARCHAR(50) NOT NULL,
    last_name          VARCHAR(50) NOT NULL,
    certification_type VARCHAR(40) NOT NULL
                       CHECK (certification_type IN ('A&P','IA','Avionics','Repairman')),
    email              VARCHAR(120) UNIQUE,
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- =============================================================================
--  3. THE EVENT — the "thing that happened" (a record of an occurrence).
--     Events reference things; things never reference events.
-- =============================================================================

CREATE TABLE maintenance_event (
    event_id                 SERIAL PRIMARY KEY,        -- invented: no natural key exists
    aircraft_id              INT NOT NULL               -- every event happened to an airframe
                             REFERENCES aircraft(aircraft_id)
                             ON UPDATE CASCADE ON DELETE RESTRICT,   -- audit records are never orphaned/deleted
    component_id             INT                        -- NULL = airframe-level event (e.g. annual)
                             REFERENCES component(component_id)
                             ON UPDATE CASCADE ON DELETE SET NULL,
    event_date               DATE NOT NULL DEFAULT CURRENT_DATE,
    event_type               VARCHAR(40) NOT NULL
                             CHECK (event_type IN ('Scheduled Inspection','Unscheduled Repair',
                                                   'Overhaul','Replacement',
                                                   'Airworthiness Directive','Modification')),
    description              VARCHAR(255) NOT NULL,
    aircraft_hours_at_event  NUMERIC(10,1) NOT NULL CHECK (aircraft_hours_at_event >= 0),
    component_hours_at_event NUMERIC(10,1) CHECK (component_hours_at_event IS NULL OR component_hours_at_event >= 0),
    next_due_hours           NUMERIC(10,1) CHECK (next_due_hours IS NULL OR next_due_hours >= 0),
    next_due_date            DATE,
    work_status              VARCHAR(20) NOT NULL DEFAULT 'Completed'
                             CHECK (work_status IN ('Open','Completed','Deferred')),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- you can only record component-hours if the event is about a component
    CHECK (component_id IS NOT NULL OR component_hours_at_event IS NULL)
);

-- JUNCTION for the Maintenance_Event <-> Technician many-to-many.
-- One row = "this technician took this role on this event." The composite PK
-- guarantees the same person cannot be recorded twice on the same event.
CREATE TABLE event_technician (
    event_id      INT NOT NULL
                  REFERENCES maintenance_event(event_id)
                  ON UPDATE CASCADE ON DELETE CASCADE,
    technician_id INT NOT NULL
                  REFERENCES technician(technician_id)
                  ON UPDATE CASCADE ON DELETE RESTRICT,   -- keep the signoff trail intact
    role          tech_role NOT NULL,
    PRIMARY KEY (event_id, technician_id)
);


-- =============================================================================
--  4. INSTALLATION HISTORY — full traceability of where each part has been.
--     A single "current_aircraft_id" can hold only one fact; airworthiness
--     needs the whole timeline, so each install/removal is its own row.
-- =============================================================================

CREATE TABLE component_installation (
    installation_id  SERIAL PRIMARY KEY,
    component_id     INT NOT NULL
                     REFERENCES component(component_id)
                     ON UPDATE CASCADE ON DELETE RESTRICT,
    aircraft_id      INT NOT NULL
                     REFERENCES aircraft(aircraft_id)
                     ON UPDATE CASCADE ON DELETE RESTRICT,
    position         VARCHAR(40) NOT NULL,              -- e.g. 'Engine #1', 'Nose gear'
    installed_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    installed_hours  NUMERIC(10,1) NOT NULL CHECK (installed_hours >= 0),
    removed_date     DATE,                              -- NULL = still installed
    removed_reason   VARCHAR(120),
    CHECK (removed_date IS NULL OR removed_date >= installed_date),
    CHECK (removed_date IS NOT NULL OR removed_reason IS NULL)
);

-- Business rule enforced in the schema itself: a physical component can be
-- installed in exactly ONE place at a time (at most one "open" installation).
CREATE UNIQUE INDEX uq_component_open_install
    ON component_installation (component_id)
    WHERE removed_date IS NULL;


-- =============================================================================
--  5. TRIGGERS — keep derived/denormalised data honest automatically.
-- =============================================================================

-- (a) touch updated_at on every UPDATE, so we never rely on the app to set it.
CREATE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_aircraft_touch  BEFORE UPDATE ON aircraft
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_component_touch BEFORE UPDATE ON component
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- (b) keep component.current_aircraft_id + status in step with the history table.
--     Installing a part points it at the airframe; recording a removal frees it.
CREATE FUNCTION sync_component_location() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.removed_date IS NULL THEN
        UPDATE component
           SET current_aircraft_id = NEW.aircraft_id, status = 'Installed'
         WHERE component_id = NEW.component_id;
    ELSIF TG_OP = 'UPDATE' AND NEW.removed_date IS NOT NULL AND OLD.removed_date IS NULL THEN
        UPDATE component
           SET current_aircraft_id = NULL, status = 'In Stock'
         WHERE component_id = NEW.component_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_installation_sync
    AFTER INSERT OR UPDATE ON component_installation
    FOR EACH ROW EXECUTE FUNCTION sync_component_location();


-- =============================================================================
--  6. INDEXES — every foreign key gets one (Postgres does NOT auto-index FKs),
--     plus a partial index on just the open work the reports actually scan.
-- =============================================================================
CREATE INDEX idx_component_aircraft  ON component(current_aircraft_id);
CREATE INDEX idx_component_part      ON component(part_number);
CREATE INDEX idx_event_aircraft      ON maintenance_event(aircraft_id);
CREATE INDEX idx_event_component     ON maintenance_event(component_id);
CREATE INDEX idx_event_next_due_date ON maintenance_event(next_due_date);
CREATE INDEX idx_evt_tech_technician ON event_technician(technician_id);
CREATE INDEX idx_install_component   ON component_installation(component_id);
CREATE INDEX idx_install_aircraft    ON component_installation(aircraft_id);
-- Partial index: only rows that are NOT completed — tiny, and it is exactly the
-- set the overdue-inspection report reads.
CREATE INDEX idx_event_open ON maintenance_event(aircraft_id)
    WHERE work_status <> 'Completed';


-- =============================================================================
--  7. A FUNCTION — hours left before a life-limited part must be retired.
-- =============================================================================
CREATE FUNCTION fn_component_hours_remaining(p_component_id INT)
RETURNS NUMERIC AS $$
    SELECT CASE WHEN life_limit_hours IS NULL THEN NULL
                ELSE life_limit_hours - time_since_new_hours END
      FROM component WHERE component_id = p_component_id;
$$ LANGUAGE sql STABLE;


-- =============================================================================
--  8. VIEWS — the questions the log is built to answer, named once and reused.
-- =============================================================================

-- Fleet at a glance: each airframe, its model, hours, and how much open work it has.
CREATE VIEW v_fleet_status AS
SELECT a.aircraft_id, a.registration_number,
       m.manufacturer, m.model_name, m.type_category,
       a.total_airframe_hours, a.status,
       COUNT(e.event_id) FILTER (WHERE e.work_status <> 'Completed') AS open_work_items
  FROM aircraft a
  JOIN aircraft_model m       ON m.model_id   = a.model_id
  LEFT JOIN maintenance_event e ON e.aircraft_id = a.aircraft_id
 GROUP BY a.aircraft_id, m.manufacturer, m.model_name, m.type_category;

-- Overdue inspections: open/deferred work whose hour- or date-threshold has passed.
CREATE VIEW v_overdue_inspections AS
SELECT e.event_id, a.registration_number, e.event_type, e.description,
       e.next_due_hours, a.total_airframe_hours,
       (a.total_airframe_hours - e.next_due_hours) AS hours_overdue,
       e.next_due_date, e.work_status
  FROM maintenance_event e
  JOIN aircraft a ON a.aircraft_id = e.aircraft_id
 WHERE e.work_status IN ('Open','Deferred')
   AND ( (e.next_due_hours IS NOT NULL AND a.total_airframe_hours >= e.next_due_hours)
      OR (e.next_due_date  IS NOT NULL AND e.next_due_date <= CURRENT_DATE) );

-- Where every component currently is (spares show a NULL aircraft).
CREATE VIEW v_component_location AS
SELECT c.component_id, c.serial_number, pc.component_type, pc.description,
       c.status, a.registration_number AS current_aircraft,
       ci.position, ci.installed_date, ci.installed_hours
  FROM component c
  JOIN part_catalog pc ON pc.part_number = c.part_number
  LEFT JOIN aircraft a ON a.aircraft_id = c.current_aircraft_id
  LEFT JOIN component_installation ci
         ON ci.component_id = c.component_id AND ci.removed_date IS NULL;

-- Legal signoff view: who performed and who inspected each event, side by side.
CREATE VIEW v_event_signoffs AS
SELECT e.event_id, e.event_date, a.registration_number, e.description,
       MAX(t.first_name||' '||t.last_name) FILTER (WHERE et.role = 'Performer') AS performed_by,
       MAX(t.first_name||' '||t.last_name) FILTER (WHERE et.role = 'Inspector') AS inspected_by
  FROM maintenance_event e
  JOIN aircraft a           ON a.aircraft_id   = e.aircraft_id
  LEFT JOIN event_technician et ON et.event_id = e.event_id
  LEFT JOIN technician t     ON t.technician_id = et.technician_id
 GROUP BY e.event_id, a.registration_number;


-- =============================================================================
--  9. SELF-DOCUMENTING COMMENTS (visible in any GUI / \d+ in psql)
-- =============================================================================
COMMENT ON TABLE  maintenance_event IS 'A single maintenance action at a point in time (an EVENT). Always references an aircraft; optionally one component.';
COMMENT ON TABLE  component_installation IS 'Full install/removal history. Source of truth for "where has this part been?".';
COMMENT ON COLUMN component.current_aircraft_id IS 'Denormalised current-location pointer, kept in sync by trigger. NULL = spare in stock.';
COMMENT ON INDEX  uq_component_open_install IS 'Enforces one open installation per component (a part is in one place at a time).';


-- =============================================================================
--  10. SAMPLE DATA — a small but realistic fleet so the views return real rows.
--      Note: components are inserted as spares, then the INSTALLATION rows place
--      them via the trigger — proving the sync logic works end to end.
-- =============================================================================

INSERT INTO aircraft_model (manufacturer, model_name, type_category, typical_seats) VALUES
 ('Cessna',                 '172S Skyhawk',      'SEP',       4),   -- 1
 ('Cessna',                 '208B Grand Caravan','Turboprop', 14),  -- 2
 ('De Havilland Canada',    'DHC-8-400',         'Turboprop', 78);  -- 3

INSERT INTO part_catalog (part_number, component_type, description, is_life_limited, default_life_limit_hours) VALUES
 ('IO-360-L2A', 'Engine',        'Lycoming IO-360 piston engine',      TRUE,  2000.0),
 ('PT6A-114A',  'Engine',        'Pratt & Whitney PT6A turboprop',     TRUE,  3600.0),
 ('GTX-345',    'Avionics',      'Garmin GTX 345 transponder',         FALSE, NULL),
 ('MLG-172-01', 'Landing Gear',  'Main landing gear assembly (172)',   FALSE, NULL),
 ('ALT-5934PD', 'Instrument',    'Barometric altimeter',               FALSE, NULL);

INSERT INTO technician (license_number, first_name, last_name, certification_type, email) VALUES
 ('AP-45021', 'James',  'Otieno',  'A&P',      'james.otieno@example.com'),   -- 1 mechanic
 ('IA-10233', 'Grace',  'Wanjiru', 'IA',       'grace.wanjiru@example.com'),  -- 2 inspector
 ('AV-77120', 'Peter',  'Kamau',   'Avionics', 'peter.kamau@example.com');    -- 3 avionics

INSERT INTO aircraft (registration_number, model_id, msn, total_airframe_hours, total_airframe_cycles, status) VALUES
 ('5Y-ABC', 1, '172S-1123', 4180.5,  5200, 'Active'),          -- 1
 ('5Y-KLM', 2, '208B-0456', 8900.0,  9100, 'Active'),          -- 2
 ('5Y-DHC', 3, '4400-0789', 21450.0, 18700,'In Maintenance');  -- 3

-- Components start life as spares (In Stock, no aircraft). Installations place them.
INSERT INTO component (serial_number, part_number, time_since_new_hours, time_since_new_cycles, life_limit_hours) VALUES
 ('L-360-88771', 'IO-360-L2A', 1450.0, 3100, 2000.0),  -- 1 engine, ~72% of life used
 ('PT6-33012',   'PT6A-114A',  2200.0, 4300, 3600.0),  -- 2 engine
 ('GTX-99120',   'GTX-345',     3000.0, 0,    NULL),    -- 3 transponder (will be removed later)
 ('GTX-99121',   'GTX-345',     0.0,    0,    NULL),    -- 4 transponder (stays a spare)
 ('ALT-55010',   'ALT-5934PD',  900.0,  0,    NULL);    -- 5 altimeter

-- Installation history (trigger sets each component's current location + status).
-- comp 3 shows a completed lifecycle: installed, then removed -> back to stock.
INSERT INTO component_installation (component_id, aircraft_id, position, installed_date, installed_hours, removed_date, removed_reason) VALUES
 (1, 1, 'Engine #1',    '2019-03-10', 0.0,    NULL,         NULL),
 (2, 2, 'Engine #1',    '2017-06-01', 0.0,    NULL,         NULL),
 (3, 1, 'Avionics Bay', '2020-01-15', 3000.0, '2023-05-20', 'Unit upgraded to ADS-B'),
 (5, 1, 'Panel',        '2021-08-02', 3600.0, NULL,         NULL);

INSERT INTO maintenance_event
 (aircraft_id, component_id, event_date, event_type, description,
  aircraft_hours_at_event, component_hours_at_event, next_due_hours, next_due_date, work_status) VALUES
 (1, NULL, '2024-11-01', 'Scheduled Inspection', '100-hour airframe inspection', 4100.0, NULL, 4200.0, '2025-05-01', 'Completed'), -- e1
 (1, 1,    '2024-11-01', 'Scheduled Inspection', 'Engine borescope inspection',  4100.0, 1370.0, NULL,   NULL,        'Completed'), -- e2
 (1, NULL, '2025-06-15', 'Scheduled Inspection', 'Annual inspection (airframe)', 4180.5, NULL, 4150.0, '2025-06-01', 'Open'),      -- e3 OVERDUE
 (2, 2,    '2023-02-20', 'Overhaul',             'Hot-section engine overhaul',  8600.0, 2100.0, NULL,   NULL,        'Completed'), -- e4
 (3, NULL, '2025-07-01', 'Airworthiness Directive','AD 2025-14: wing spar check',21450.0, NULL, NULL,  '2025-08-15', 'Open');      -- e5

-- Who did what. Note e1 and e4 carry both a Performer and an Inspector.
INSERT INTO event_technician (event_id, technician_id, role) VALUES
 (1, 1, 'Performer'),
 (1, 2, 'Inspector'),
 (2, 1, 'Performer'),
 (3, 1, 'Performer'),
 (4, 1, 'Performer'),
 (4, 2, 'Inspector'),
 (5, 2, 'Inspector');

-- =============================================================================
--  Done. Run queries.sql to see the database answer real questions.
-- =============================================================================
