-- ============================================================
-- AutoPulse Fabric
-- Source Vehicle Alias Natural-Key Protection
--
-- Prevent duplicate source identities when ingestion
-- pipelines are rerun.
-- ============================================================


CREATE UNIQUE INDEX IF NOT EXISTS
    ux_source_vehicle_alias_natural_key

ON identity.source_vehicle_aliases (

    source_system,

    COALESCE(
        source_make,
        ''
    ),

    COALESCE(
        source_model,
        ''
    ),

    COALESCE(
        source_model_year,
        -1
    ),

    COALESCE(
        source_variant,
        ''
    )
);