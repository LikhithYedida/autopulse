-- =====================================================================
-- AutoPulse
-- 008_model_alias_audit.sql
--
-- Purpose:
-- Classify HIGH-evidence model relationships before any additional
-- automatic entity resolution is allowed.
--
-- IMPORTANT:
-- This script changes NO canonical identity assignments.
-- It is an audit / governance layer only.
-- =====================================================================


CREATE OR REPLACE VIEW
identity.model_alias_audit
AS

WITH relationships AS (

    SELECT

        source_make,

        source_model,

        canonical_make_name,

        top_candidate_model_id,

        top_candidate_model,

        COUNT(*) AS alias_count,

        MIN(source_model_year)
            AS first_year,

        MAX(source_model_year)
            AS last_year,

        ROUND(
            AVG(top_score)::NUMERIC,
            2
        ) AS avg_score,

        ROUND(
            AVG(score_gap)::NUMERIC,
            2
        ) AS avg_gap,

        ROUND(
            AVG(length_ratio)::NUMERIC,
            4
        ) AS avg_length_ratio

    FROM
        identity.entity_resolution_review_queue

    WHERE
        review_priority =
            'HIGH_EVIDENCE_REVIEW'

    GROUP BY

        source_make,

        source_model,

        canonical_make_name,

        top_candidate_model_id,

        top_candidate_model
),

classified AS (

    SELECT

        r.*,

        -- =============================================================
        -- Normalized strings
        -- =============================================================

        REGEXP_REPLACE(
            UPPER(TRIM(r.source_model)),
            '[^A-Z0-9]+',
            ' ',
            'g'
        ) AS normalized_source_model,

        REGEXP_REPLACE(
            UPPER(TRIM(r.top_candidate_model)),
            '[^A-Z0-9]+',
            ' ',
            'g'
        ) AS normalized_candidate_model,


        -- =============================================================
        -- Semantic variant flags
        --
        -- These terms carry real vehicle meaning and should not
        -- automatically disappear during entity resolution.
        -- =============================================================

        CASE
            WHEN UPPER(r.source_model)
                ~ '(^|[ -])(EV|PHEV|HEV|HYBRID)([ -]|$)'
            THEN TRUE
            ELSE FALSE
        END AS has_powertrain_suffix,


        CASE
            WHEN UPPER(r.source_model)
                ~ '(^|[ -])(S|SE|SEL|GT|GTS|RS|ST|SPORT|LIMITED|PREMIUM|PLATINUM|TOURING)([ -]|$)'
            THEN TRUE
            ELSE FALSE
        END AS has_trim_suffix,


        CASE
            WHEN UPPER(r.source_model)
                ~ '(^|[ -])(AWD|4WD|4X4|ALL4|QUATTRO)([ -]|$)'
            THEN TRUE
            ELSE FALSE
        END AS has_drivetrain_suffix,


        CASE
            WHEN UPPER(r.source_model)
                ~ '(^|[ -])(COUPE|SEDAN|WAGON|VAN|BUS|CAB)([ -]|$)'
            THEN TRUE
            ELSE FALSE
        END AS has_body_style_suffix,


        -- =============================================================
        -- Suspicious numeric-only candidate
        --
        -- Example:
        -- C 300 -> 300
        -- E 350 -> 350
        -- S 500 -> 500
        --
        -- These should never be approved simply because the number
        -- is contained in the source model.
        -- =============================================================

        CASE
            WHEN REGEXP_REPLACE(
                    UPPER(TRIM(r.top_candidate_model)),
                    '[^A-Z0-9]+',
                    '',
                    'g'
                 )
                 ~ '^[0-9]+$'
            THEN TRUE
            ELSE FALSE
        END AS numeric_only_candidate

    FROM relationships r
)


SELECT

    c.*,

    CASE

        -- =============================================================
        -- Clearly unsafe fuzzy relationship
        -- =============================================================

        WHEN numeric_only_candidate
        THEN 'BLOCK_AUTO_RESOLUTION'


        -- =============================================================
        -- Variant-bearing relationship
        --
        -- Likely same model family, but resolving it now could throw
        -- away powertrain / trim / drivetrain / body-style evidence.
        -- =============================================================

        WHEN
               has_powertrain_suffix
            OR has_trim_suffix
            OR has_drivetrain_suffix
            OR has_body_style_suffix

        THEN 'PRESERVE_VARIANT_EVIDENCE'


        -- =============================================================
        -- Ford Super Duty source convention
        --
        -- Still REVIEW, not auto-approved.
        -- We isolate it because it is a repeatable naming pattern.
        -- =============================================================

        WHEN
            UPPER(source_make) = 'FORD'

            AND UPPER(source_model)
                ~ '^F[- ]?[0-9]{3}[ ]+SD$'

            AND UPPER(top_candidate_model)
                ~ '^F[ ]?[0-9]{3}$'

        THEN 'FAMILY_ALIAS_CANDIDATE'


        -- =============================================================
        -- Everything else needs individual evidence.
        -- =============================================================

        ELSE 'MANUAL_RELATIONSHIP_REVIEW'

    END AS audit_class,


    CASE

        WHEN numeric_only_candidate
        THEN
            'Candidate is numeric-only and may discard model-family context'

        WHEN has_powertrain_suffix
        THEN
            'Source contains powertrain identity that must be preserved'

        WHEN has_trim_suffix
        THEN
            'Source contains trim/performance identity that must be preserved'

        WHEN has_drivetrain_suffix
        THEN
            'Source contains drivetrain identity that must be preserved'

        WHEN has_body_style_suffix
        THEN
            'Source contains body-style identity that must be preserved'

        WHEN
            UPPER(source_make) = 'FORD'

            AND UPPER(source_model)
                ~ '^F[- ]?[0-9]{3}[ ]+SD$'

        THEN
            'Repeatable Ford SD naming pattern; candidate for explicit family alias'

        ELSE
            'High fuzzy evidence exists, but no deterministic identity rule established'

    END AS audit_reason

FROM classified c;