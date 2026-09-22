-- ============================================================
-- AutoPulse Fabric
-- Operational Service Domain
--
-- Purpose:
-- Model automotive service operations with historical
-- assignment tracking so events can be attributed to the
-- advisor responsible at the time the event occurred.
-- ============================================================


-- ============================================================
-- Vehicles
-- Grain: one row per vehicle
-- ============================================================

CREATE TABLE IF NOT EXISTS operational.vehicles (

    vehicle_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    vin VARCHAR(17) UNIQUE,

    model_year SMALLINT NOT NULL,

    make VARCHAR(100) NOT NULL,

    model VARCHAR(150) NOT NULL,

    trim VARCHAR(150),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_vehicle_model_year
        CHECK (model_year BETWEEN 1900 AND 2100)

);


-- ============================================================
-- Service Advisors
-- Grain: one row per advisor
-- ============================================================

CREATE TABLE IF NOT EXISTS operational.service_advisors (

    advisor_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    advisor_code VARCHAR(30) NOT NULL UNIQUE,

    first_name VARCHAR(100) NOT NULL,

    last_name VARCHAR(100) NOT NULL,

    service_center VARCHAR(150) NOT NULL,

    active_flag BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP

);


-- ============================================================
-- Service Orders
-- Grain: one row per service order
--
-- current_advisor_id represents CURRENT ownership only.
-- It must NOT be used for historical event attribution.
-- ============================================================

CREATE TABLE IF NOT EXISTS operational.service_orders (

    service_order_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    service_order_number VARCHAR(40) NOT NULL UNIQUE,

    vehicle_id BIGINT NOT NULL,

    current_advisor_id BIGINT,

    opened_at TIMESTAMPTZ NOT NULL,

    closed_at TIMESTAMPTZ,

    service_status VARCHAR(50) NOT NULL,

    priority VARCHAR(30) NOT NULL DEFAULT 'NORMAL',

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_service_order_vehicle
        FOREIGN KEY (vehicle_id)
        REFERENCES operational.vehicles(vehicle_id),

    CONSTRAINT fk_service_order_current_advisor
        FOREIGN KEY (current_advisor_id)
        REFERENCES operational.service_advisors(advisor_id),

    CONSTRAINT chk_service_order_dates
        CHECK (
            closed_at IS NULL
            OR closed_at >= opened_at
        )

);


-- ============================================================
-- Service Assignment History
--
-- Grain:
-- One row per advisor-assignment interval.
--
-- Example:
--
-- RO-1001
-- Advisor A | Sep 1 09:00 -> Sep 8 14:30
-- Advisor B | Sep 8 14:30 -> NULL
--
-- This enables point-in-time ownership attribution.
-- ============================================================

CREATE TABLE IF NOT EXISTS operational.service_assignment_history (

    assignment_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    service_order_id BIGINT NOT NULL,

    advisor_id BIGINT NOT NULL,

    assigned_at TIMESTAMPTZ NOT NULL,

    unassigned_at TIMESTAMPTZ,

    assignment_reason VARCHAR(100),

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_assignment_service_order
        FOREIGN KEY (service_order_id)
        REFERENCES operational.service_orders(service_order_id),

    CONSTRAINT fk_assignment_advisor
        FOREIGN KEY (advisor_id)
        REFERENCES operational.service_advisors(advisor_id),

    CONSTRAINT chk_assignment_interval
        CHECK (
            unassigned_at IS NULL
            OR unassigned_at > assigned_at
        )

);


-- ============================================================
-- Prevent more than one CURRENT assignment for the same
-- service order.
-- ============================================================

CREATE UNIQUE INDEX IF NOT EXISTS
    ux_service_assignment_current

ON operational.service_assignment_history (
    service_order_id
)

WHERE unassigned_at IS NULL;


-- ============================================================
-- Performance index for point-in-time attribution
-- ============================================================

CREATE INDEX IF NOT EXISTS
    ix_service_assignment_history_lookup

ON operational.service_assignment_history (
    service_order_id,
    assigned_at,
    unassigned_at
);