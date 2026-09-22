-- ============================================================
-- AutoPulse Fabric
-- Controlled Historical Assignment Scenario
--
-- Business case:
-- A warranty escalation occurs while Advisor Alex owns
-- the service order.
--
-- The service order is later reassigned to Advisor Maya.
--
-- Current ownership therefore differs from ownership
-- at the time of the escalation.
-- ============================================================

BEGIN;


-- ============================================================
-- Clean up this controlled scenario if script is rerun
-- ============================================================

DELETE FROM operational.warranty_escalations
WHERE service_order_id IN (
    SELECT service_order_id
    FROM operational.service_orders
    WHERE service_order_number = 'SO-2026-0001'
);


DELETE FROM operational.service_assignment_history
WHERE service_order_id IN (
    SELECT service_order_id
    FROM operational.service_orders
    WHERE service_order_number = 'SO-2026-0001'
);


DELETE FROM operational.service_orders
WHERE service_order_number = 'SO-2026-0001';


DELETE FROM operational.service_advisors
WHERE advisor_code IN (
    'ADV-ALEX-001',
    'ADV-MAYA-002'
);


DELETE FROM operational.vehicles
WHERE vin = 'TESTVIN0000000001';


-- ============================================================
-- Vehicle
-- ============================================================

INSERT INTO operational.vehicles (
    vin,
    model_year,
    make,
    model,
    trim
)
VALUES (
    'TESTVIN0000000001',
    2022,
    'TOYOTA',
    'CAMRY',
    'XSE'
);


-- ============================================================
-- Advisors
-- ============================================================

INSERT INTO operational.service_advisors (
    advisor_code,
    first_name,
    last_name,
    service_center
)
VALUES
(
    'ADV-ALEX-001',
    'Alex',
    'Morgan',
    'Detroit Service Center'
),
(
    'ADV-MAYA-002',
    'Maya',
    'Patel',
    'Detroit Service Center'
);


-- ============================================================
-- Service Order
--
-- IMPORTANT:
-- Maya is the CURRENT advisor.
-- ============================================================

INSERT INTO operational.service_orders (
    service_order_number,
    vehicle_id,
    current_advisor_id,
    opened_at,
    service_status,
    priority
)
SELECT
    'SO-2026-0001',
    v.vehicle_id,
    a.advisor_id,
    TIMESTAMPTZ '2026-09-01 09:00:00-04',
    'IN_PROGRESS',
    'HIGH'
FROM operational.vehicles v
JOIN operational.service_advisors a
    ON a.advisor_code = 'ADV-MAYA-002'
WHERE v.vin = 'TESTVIN0000000001';


-- ============================================================
-- Historical Assignment 1
--
-- Alex owns the order from Sep 1 through Sep 10.
-- ============================================================

INSERT INTO operational.service_assignment_history (
    service_order_id,
    advisor_id,
    assigned_at,
    unassigned_at,
    assignment_reason
)
SELECT
    so.service_order_id,
    a.advisor_id,
    TIMESTAMPTZ '2026-09-01 09:00:00-04',
    TIMESTAMPTZ '2026-09-10 10:00:00-04',
    'INITIAL_ASSIGNMENT'
FROM operational.service_orders so
JOIN operational.service_advisors a
    ON a.advisor_code = 'ADV-ALEX-001'
WHERE so.service_order_number = 'SO-2026-0001';


-- ============================================================
-- Historical Assignment 2
--
-- Maya becomes the current owner on Sep 10.
-- ============================================================

INSERT INTO operational.service_assignment_history (
    service_order_id,
    advisor_id,
    assigned_at,
    unassigned_at,
    assignment_reason
)
SELECT
    so.service_order_id,
    a.advisor_id,
    TIMESTAMPTZ '2026-09-10 10:00:00-04',
    NULL,
    'WORKLOAD_REASSIGNMENT'
FROM operational.service_orders so
JOIN operational.service_advisors a
    ON a.advisor_code = 'ADV-MAYA-002'
WHERE so.service_order_number = 'SO-2026-0001';


-- ============================================================
-- Warranty Escalation
--
-- Sep 6:
-- This occurs while Alex owns the service order.
-- ============================================================

INSERT INTO operational.warranty_escalations (
    escalation_number,
    service_order_id,
    escalated_at,
    escalation_type,
    severity,
    estimated_cost,
    escalation_status,
    description
)
SELECT
    'WE-2026-0001',
    so.service_order_id,
    TIMESTAMPTZ '2026-09-06 14:30:00-04',
    'POWERTRAIN_WARRANTY_REVIEW',
    'HIGH',
    4200.00,
    'OPEN',
    'Repeated transmission issue requires warranty escalation.'
FROM operational.service_orders so
WHERE so.service_order_number = 'SO-2026-0001';


COMMIT;