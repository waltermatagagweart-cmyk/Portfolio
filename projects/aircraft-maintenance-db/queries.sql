-- =============================================================================
--  AIRCRAFT MAINTENANCE LOG — DEMONSTRATION QUERIES
--  Run these after schema.sql to see the design answer real-world questions.
-- =============================================================================

\echo '\n=== Q1. Fleet status — every airframe, its model, hours and open work ==='
SELECT registration_number, manufacturer, model_name,
       total_airframe_hours, status, open_work_items
FROM   v_fleet_status
ORDER  BY registration_number;

\echo '\n=== Q2. OVERDUE INSPECTIONS — the safety report (open work past its due point) ==='
SELECT registration_number, description, next_due_hours,
       total_airframe_hours, hours_overdue, next_due_date
FROM   v_overdue_inspections
ORDER  BY hours_overdue DESC NULLS LAST;

\echo '\n=== Q3. Parts installed per aircraft (the parts-per-aircraft count) ==='
SELECT current_aircraft AS registration_number,
       COUNT(*)          AS parts_installed,
       STRING_AGG(component_type, ', ' ORDER BY component_type) AS parts
FROM   v_component_location
WHERE  current_aircraft IS NOT NULL
GROUP  BY current_aircraft
ORDER  BY current_aircraft;

\echo '\n=== Q4. Full installation history of transponder GTX-99120 (traceability) ==='
SELECT c.serial_number, a.registration_number, ci.position,
       ci.installed_date, ci.removed_date,
       COALESCE(ci.removed_reason, '(still installed)') AS status
FROM   component_installation ci
JOIN   component c ON c.component_id = ci.component_id
JOIN   aircraft  a ON a.aircraft_id  = ci.aircraft_id
WHERE  c.serial_number = 'GTX-99120'      -- the transponder that moved
ORDER  BY ci.installed_date;

\echo '\n=== Q5. Life-limited components ranked by hours remaining (retirement planning) ==='
SELECT serial_number, part_number,
       time_since_new_hours, life_limit_hours,
       fn_component_hours_remaining(component_id) AS hours_remaining
FROM   component
WHERE  life_limit_hours IS NOT NULL
ORDER  BY hours_remaining ASC;

\echo '\n=== Q6. Legal signoffs — who performed and who inspected each event ==='
SELECT registration_number, event_date, description,
       performed_by, inspected_by
FROM   v_event_signoffs
ORDER  BY event_date;

\echo '\n=== Q7. Technician workload (how many events each person is on) ==='
SELECT t.first_name || ' ' || t.last_name AS technician,
       t.certification_type,
       COUNT(*) AS events_worked
FROM   event_technician et
JOIN   technician t ON t.technician_id = et.technician_id
GROUP  BY t.technician_id
ORDER  BY events_worked DESC;

\echo '\n=== Q8. Spares in stock (components installed nowhere) ==='
SELECT serial_number, component_type, description, status
FROM   v_component_location
WHERE  current_aircraft IS NULL;
