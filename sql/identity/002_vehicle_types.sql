-- ============================================================
-- AutoPulse Fabric
-- Vehicle Type Classification
--
-- Purpose:
-- Separate the broad vPIC universe from the AutoPulse
-- automobile analytics scope.
-- ============================================================

CREATE TABLE IF NOT EXISTS identity.vehicle_types (

    vehicle_type_id BIGINT
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    source_system VARCHAR(100)
        NOT NULL,

    source_vehicle_type_id INTEGER,

    vehicle_type_name VARCHAR(150)
        NOT NULL,

    automobile_scope_flag BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_vehicle_type
        UNIQUE (
            source_system,
            vehicle_type_name
        )
);


CREATE TABLE IF NOT EXISTS identity.make_vehicle_types (

    make_id BIGINT
        NOT NULL,

    vehicle_type_id BIGINT
        NOT NULL,

    source_system VARCHAR(100)
        NOT NULL,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        make_id,
        vehicle_type_id,
        source_system
    ),

    CONSTRAINT fk_make_vehicle_type_make
        FOREIGN KEY (make_id)
        REFERENCES identity.makes(make_id),

    CONSTRAINT fk_make_vehicle_type_type
        FOREIGN KEY (vehicle_type_id)
        REFERENCES identity.vehicle_types(vehicle_type_id)
);


CREATE INDEX IF NOT EXISTS
    ix_make_vehicle_types_make

ON identity.make_vehicle_types (
    make_id
);