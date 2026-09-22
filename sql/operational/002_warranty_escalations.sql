-- ============================================================
-- AutoPulse Fabric
-- Warranty Escalations
--
-- Grain:
-- One row per warranty escalation event.
--
-- Business problem:
-- A service order may be reassigned after an escalation occurs.
-- Analytics must attribute the escalation to the advisor who
-- owned the service order when the event actually happened,
-- not simply to the current advisor.
-- ============================================================


CREATE TABLE IF NOT EXISTS operational.warranty_escalations (

    escalation_id BIGINT
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    escalation_number VARCHAR(40)
        NOT NULL
        UNIQUE,

    service_order_id BIGINT
        NOT NULL,

    escalated_at TIMESTAMPTZ
        NOT NULL,

    escalation_type VARCHAR(100)
        NOT NULL,

    severity VARCHAR(30)
        NOT NULL,

    estimated_cost NUMERIC(12, 2),

    escalation_status VARCHAR(40)
        NOT NULL DEFAULT 'OPEN',

    description TEXT,

    created_at TIMESTAMPTZ
        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_warranty_escalation_service_order
        FOREIGN KEY (service_order_id)
        REFERENCES operational.service_orders(service_order_id),

    CONSTRAINT chk_warranty_estimated_cost
        CHECK (
            estimated_cost IS NULL
            OR estimated_cost >= 0
        ),

    CONSTRAINT chk_warranty_severity
        CHECK (
            severity IN (
                'LOW',
                'MEDIUM',
                'HIGH',
                'CRITICAL'
            )
        )

);


CREATE INDEX IF NOT EXISTS
    ix_warranty_escalation_service_order_time

ON operational.warranty_escalations (
    service_order_id,
    escalated_at
);