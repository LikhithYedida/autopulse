-- ============================================================
-- AutoPulse Fabric
-- Canonical Vehicle Identity Layer
--
-- Purpose:
-- Create a source-independent automotive master-data model
-- capable of reconciling different vehicle naming conventions
-- across NHTSA, VIN decoding, service systems, warranty systems,
-- and future international data sources.
-- ============================================================


CREATE SCHEMA IF NOT EXISTS identity
AUTHORIZATION autopulse_app;


-- ============================================================
-- Manufacturers
--
-- Grain:
-- One row per automotive manufacturer / corporate entity.
--
-- Examples:
-- BMW AG
-- Toyota Motor Corporation
-- Ford Motor Company
-- ============================================================

CREATE TABLE IF NOT EXISTS identity.manufacturers (

    manufacturer_id BIGINT
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    canonical_name VARCHAR(200)
        NOT NULL,

    country_code VARCHAR(3),

    active_flag BOOLEAN
        NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_manufacturer_name
        UNIQUE (canonical_name)

);


-- ============================================================
-- Makes / Brands
--
-- Grain:
-- One row per consumer-facing automotive make.
--
-- Manufacturer and make are separated intentionally.
--
-- Example:
-- Toyota Motor Corporation -> TOYOTA
-- BMW AG                  -> BMW
-- Volkswagen Group        -> AUDI
-- ============================================================

CREATE TABLE IF NOT EXISTS identity.makes (

    make_id BIGINT
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    manufacturer_id BIGINT,

    canonical_make_name VARCHAR(150)
        NOT NULL,

    active_flag BOOLEAN
        NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_make_manufacturer
        FOREIGN KEY (manufacturer_id)
        REFERENCES identity.manufacturers(
            manufacturer_id
        ),

    CONSTRAINT uq_make_name
        UNIQUE (canonical_make_name)

);


-- ============================================================
-- Models
--
-- Grain:
-- One row per canonical make/model combination.
--
-- Examples:
-- BMW 3 SERIES
-- TOYOTA CAMRY
-- FORD F-150
-- ============================================================

CREATE TABLE IF NOT EXISTS identity.models (

    model_id BIGINT
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    make_id BIGINT
        NOT NULL,

    canonical_model_name VARCHAR(200)
        NOT NULL,

    active_flag BOOLEAN
        NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_model_make
        FOREIGN KEY (make_id)
        REFERENCES identity.makes(
            make_id
        ),

    CONSTRAINT uq_make_model
        UNIQUE (
            make_id,
            canonical_model_name
        )

);


-- ============================================================
-- Vehicle Configurations
--
-- Grain:
-- One row per model-year / model / variant configuration.
--
-- This is more precise than simply storing Make + Model.
--
-- Example:
-- 2021 BMW 3 SERIES / 330I XDRIVE
-- 2024 TOYOTA CAMRY / XSE
-- ============================================================

CREATE TABLE IF NOT EXISTS identity.vehicle_configurations (

    vehicle_configuration_id BIGINT
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    model_id BIGINT
        NOT NULL,

    model_year SMALLINT
        NOT NULL,

    variant_name VARCHAR(200),

    trim_name VARCHAR(200),

    body_style VARCHAR(100),

    drive_type VARCHAR(100),

    fuel_type VARCHAR(100),

    engine_description VARCHAR(250),

    transmission_description VARCHAR(250),

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_configuration_model
        FOREIGN KEY (model_id)
        REFERENCES identity.models(
            model_id
        ),

    CONSTRAINT chk_configuration_year
        CHECK (
            model_year BETWEEN 1900 AND 2100
        ),

    CONSTRAINT uq_vehicle_configuration
        UNIQUE (
            model_id,
            model_year,
            variant_name,
            trim_name
        )

);


-- ============================================================
-- WMI Registry
--
-- WMI = first three characters of a VIN.
--
-- Grain:
-- One row per World Manufacturer Identifier.
--
-- This provides the first bridge between VIN-level identity
-- and canonical manufacturer/make information.
-- ============================================================

CREATE TABLE IF NOT EXISTS identity.wmi_registry (

    wmi VARCHAR(3)
        PRIMARY KEY,

    manufacturer_id BIGINT,

    make_id BIGINT,

    country_code VARCHAR(3),

    source_system VARCHAR(100),

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_wmi_manufacturer
        FOREIGN KEY (manufacturer_id)
        REFERENCES identity.manufacturers(
            manufacturer_id
        ),

    CONSTRAINT fk_wmi_make
        FOREIGN KEY (make_id)
        REFERENCES identity.makes(
            make_id
        )

);


-- ============================================================
-- Source Vehicle Aliases
--
-- One of the most important tables in AutoPulse.
--
-- Grain:
-- One row per source-specific representation of a vehicle.
--
-- Example:
--
-- Source = NHTSA_COMPLAINTS
-- Make   = BMW
-- Model  = 3 SERIES
--
-- Source = NHTSA_RECALLS
-- Make   = BMW
-- Model  = 330I
--
-- Both may resolve to the same canonical AutoPulse model /
-- configuration.
-- ============================================================

CREATE TABLE IF NOT EXISTS identity.source_vehicle_aliases (

    alias_id BIGINT
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    source_system VARCHAR(100)
        NOT NULL,

    source_make VARCHAR(200),

    source_model VARCHAR(250),

    source_model_year SMALLINT,

    source_variant VARCHAR(250),

    canonical_model_id BIGINT,

    vehicle_configuration_id BIGINT,

    match_method VARCHAR(50)
        NOT NULL
        DEFAULT 'UNRESOLVED',

    match_confidence NUMERIC(5, 4),

    reviewed_flag BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_alias_model
        FOREIGN KEY (canonical_model_id)
        REFERENCES identity.models(
            model_id
        ),

    CONSTRAINT fk_alias_configuration
        FOREIGN KEY (vehicle_configuration_id)
        REFERENCES identity.vehicle_configurations(
            vehicle_configuration_id
        ),

    CONSTRAINT chk_match_confidence
        CHECK (
            match_confidence IS NULL
            OR (
                match_confidence >= 0
                AND match_confidence <= 1
            )
        )

);


CREATE INDEX IF NOT EXISTS
    ix_source_vehicle_alias_lookup

ON identity.source_vehicle_aliases (
    source_system,
    source_make,
    source_model,
    source_model_year
);


-- ============================================================
-- Vehicle Instances
--
-- Grain:
-- One row per known physical vehicle instance.
--
-- Full VIN is intentionally NOT stored here.
-- Analytics uses a SHA-256 fingerprint plus limited
-- non-sensitive identity attributes.
--
-- Full VIN handling will live behind the lookup/API layer.
-- ============================================================

CREATE TABLE IF NOT EXISTS identity.vehicle_instances (

    vehicle_instance_id BIGINT
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    vehicle_configuration_id BIGINT,

    vin_sha256 CHAR(64)
        UNIQUE,

    vin_last8 VARCHAR(8),

    wmi VARCHAR(3),

    identity_source VARCHAR(100),

    first_seen_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    last_seen_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_instance_configuration
        FOREIGN KEY (vehicle_configuration_id)
        REFERENCES identity.vehicle_configurations(
            vehicle_configuration_id
        ),

    CONSTRAINT fk_instance_wmi
        FOREIGN KEY (wmi)
        REFERENCES identity.wmi_registry(
            wmi
        )

);


-- ============================================================
-- Helpful lookup indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS
    ix_vehicle_configuration_year

ON identity.vehicle_configurations (
    model_year
);


CREATE INDEX IF NOT EXISTS
    ix_vehicle_instance_configuration

ON identity.vehicle_instances (
    vehicle_configuration_id
);