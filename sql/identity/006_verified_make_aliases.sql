-- =====================================================================
-- AutoPulse
-- 006_verified_make_aliases.sql
--
-- Purpose:
--   1. Create governed source-make -> canonical-make mappings.
--   2. Seed only externally verified vPIC make aliases.
--   3. Give the AutoPulse application read access.
--
-- Safe to rerun.
-- =====================================================================

BEGIN;


-- =====================================================================
-- 1. GOVERNED MAKE-ALIAS TABLE
-- =====================================================================

CREATE TABLE IF NOT EXISTS identity.make_aliases (

    source_system VARCHAR(100) NOT NULL,

    source_make VARCHAR(200) NOT NULL,

    canonical_make_id BIGINT NOT NULL,

    match_method VARCHAR(100) NOT NULL,

    confidence NUMERIC(5,4) NOT NULL,

    evidence_source VARCHAR(100),

    evidence_note TEXT,

    reviewed_flag BOOLEAN NOT NULL
        DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT pk_make_aliases
        PRIMARY KEY (
            source_system,
            source_make
        ),

    CONSTRAINT fk_make_aliases_make
        FOREIGN KEY (
            canonical_make_id
        )
        REFERENCES identity.makes (
            make_id
        ),

    CONSTRAINT chk_make_aliases_confidence
        CHECK (
            confidence >= 0
            AND confidence <= 1
        )
);


-- =====================================================================
-- 2. INDEX
-- =====================================================================

CREATE INDEX IF NOT EXISTS
    idx_make_aliases_canonical_make_id

ON identity.make_aliases (
    canonical_make_id
);


-- =====================================================================
-- 3. VERIFIED MAKE ALIASES
--
-- These mappings come from the direct vPIC GetModelsForMake probe.
--
-- We intentionally DO NOT include ambiguous mappings such as:
--
--   THOR MOTOR COACH
--   FLEETWOOD
--   INDIAN
--   ATC
--   HORTON
--   ZERO
--   UNKNOWN
--
-- Those remain unresolved.
-- =====================================================================

WITH verified_aliases (
    source_make,
    canonical_make_name,
    evidence_note
) AS (

    VALUES

        (
            'GRAND DESIGN',
            'GRAND DESIGN RECREATIONAL',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'TIFFIN',
            'TIFFIN MOTORHOMES, INC',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'NEWMAR',
            'NEWMAR CORPORATION',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'DYNAMAX',
            'DYNAMAX CORPORATION',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'VANLEIGH',
            'VANLEIGH RV',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'GENESIS SUPREME',
            'GENESIS SUPREME RV, INC',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'GREAT DANE',
            'GREAT DANE TRAILERS',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'INTECH',
            'INTECH TRAILERS',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'GULF STREAM',
            'GULF STREAM COACH, INC.',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            '4-STAR TRAILER',
            '4-STAR TRAILERS INC.',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'DIAMOND CITY',
            'DIAMOND CITY TRAILER',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'GENUINE SCOOTER',
            'GENUINE SCOOTERS',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'HYUNDAI TRANSLEAD',
            'HYUNDAI TRANSLEAD TRAILERS',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'INTERSTATE WEST',
            'INTERSTATE WEST CORP',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'MAGIC TILT',
            'MAGIC TILT TRAILERS',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'MERCEDES',
            'MERCEDES-BENZ',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'SOLAR MOTORS',
            'SOLAR MOTORS INC.',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'STOUGHTON',
            'STOUGHTON TRAILERS',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'T & B WELDING & TRAILER',
            'T & B WELDING & TRAILERS',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'TAKE 3 TRAILERS',
            'TAKE 3 TRAILERS INC',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'TAXA',
            'TAXA INC.',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'TESKE',
            'TESKE MANUFACTURING',
            'Direct NHTSA vPIC GetModelsForMake verification'
        ),

        (
            'TIMPTE',
            'TIMPTE, INC',
            'Direct NHTSA vPIC GetModelsForMake verification'
        )
),


-- =====================================================================
-- Normalize canonical make names.
-- =====================================================================

normalized_canonical_makes AS (

    SELECT

        make_id,

        canonical_make_name,

        REGEXP_REPLACE(
            UPPER(
                TRIM(
                    canonical_make_name
                )
            ),
            '[^A-Z0-9]+',
            '',
            'g'
        ) AS normalized_make

    FROM identity.makes
),


-- =====================================================================
-- Require exactly one canonical make for each verified target.
--
-- This prevents a verified alias from silently becoming ambiguous
-- if duplicate normalized canonical names appear later.
-- =====================================================================

resolved_verified_aliases AS (

    SELECT

        va.source_make,

        MIN(
            ncm.make_id
        ) AS canonical_make_id,

        va.evidence_note

    FROM verified_aliases va

    JOIN normalized_canonical_makes ncm

      ON ncm.normalized_make =
         REGEXP_REPLACE(
             UPPER(
                 TRIM(
                     va.canonical_make_name
                 )
             ),
             '[^A-Z0-9]+',
             '',
             'g'
         )

    GROUP BY
        va.source_make,
        va.evidence_note

    HAVING COUNT(*) = 1
)


-- =====================================================================
-- Insert / refresh mappings.
-- =====================================================================

INSERT INTO identity.make_aliases (

    source_system,

    source_make,

    canonical_make_id,

    match_method,

    confidence,

    evidence_source,

    evidence_note,

    reviewed_flag
)

SELECT

    'NHTSA_COMPLAINTS',

    source_make,

    canonical_make_id,

    'VPIC_VERIFIED_ALIAS',

    1.0000,

    'NHTSA_VPIC_DIRECT',

    evidence_note,

    TRUE

FROM resolved_verified_aliases

ON CONFLICT (
    source_system,
    source_make
)

DO UPDATE SET

    canonical_make_id =
        EXCLUDED.canonical_make_id,

    match_method =
        EXCLUDED.match_method,

    confidence =
        EXCLUDED.confidence,

    evidence_source =
        EXCLUDED.evidence_source,

    evidence_note =
        EXCLUDED.evidence_note,

    reviewed_flag =
        EXCLUDED.reviewed_flag;


-- =====================================================================
-- 4. APPLICATION PERMISSIONS
--
-- IMPORTANT:
-- entity_resolution.py connects as autopulse_app.
--
-- The resolver only needs to READ this governance table.
-- =====================================================================

GRANT USAGE
ON SCHEMA identity
TO autopulse_app;


GRANT SELECT
ON TABLE identity.make_aliases
TO autopulse_app;


COMMIT;


-- =====================================================================
-- 5. VALIDATION
-- =====================================================================

SELECT

    ma.source_make,

    m.canonical_make_name,

    ma.match_method,

    ma.confidence,

    ma.evidence_source,

    ma.reviewed_flag

FROM identity.make_aliases ma

JOIN identity.makes m
  ON m.make_id =
     ma.canonical_make_id

WHERE
    ma.source_system =
        'NHTSA_COMPLAINTS'

ORDER BY
    ma.source_make;


-- =====================================================================
-- 6. PERMISSION VALIDATION
-- =====================================================================

SELECT

    grantee,

    privilege_type

FROM information_schema.role_table_grants

WHERE
    table_schema = 'identity'

    AND table_name =
        'make_aliases'

    AND grantee =
        'autopulse_app'

ORDER BY
    privilege_type;