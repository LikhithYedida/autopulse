-- =====================================================================
-- AutoPulse
-- 007_entity_resolution_review_queue.sql
--
-- Purpose:
-- Build an explainable review layer for unresolved vehicle identities.
--
-- IMPORTANT:
-- This script DOES NOT resolve any identity automatically.
--
-- It:
--   1. Selects the strongest candidate per unresolved alias.
--   2. Exposes runner-up evidence.
--   3. Calculates model-name length evidence.
--   4. Identifies candidate ambiguity.
--   5. Assigns a REVIEW PRIORITY tier.
--   6. Creates a persistent human-review decision table.
-- =====================================================================


BEGIN;


-- =====================================================================
-- 1. HUMAN REVIEW DECISION TABLE
-- =====================================================================

CREATE TABLE IF NOT EXISTS identity.entity_resolution_reviews (

    alias_id BIGINT PRIMARY KEY
        REFERENCES identity.source_vehicle_aliases(alias_id),

    candidate_model_id BIGINT
        REFERENCES identity.models(model_id),

    review_decision VARCHAR(50) NOT NULL,

    reviewer_note TEXT,

    reviewed_by VARCHAR(150),

    reviewed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT chk_entity_resolution_review_decision
        CHECK (
            review_decision IN (
                'PENDING',
                'APPROVED',
                'REJECTED',
                'NEEDS_RESEARCH'
            )
        )
);


CREATE INDEX IF NOT EXISTS
    idx_entity_resolution_reviews_decision

ON identity.entity_resolution_reviews (
    review_decision
);


-- =====================================================================
-- 2. REVIEW QUEUE VIEW
-- =====================================================================

CREATE OR REPLACE VIEW
    identity.entity_resolution_review_queue

AS

WITH ranked_candidates AS (

    SELECT

        er.alias_id,

        er.candidate_model_id,

        er.rank_position,

        er.normalized_source_model,

        er.normalized_candidate_model,

        er.similarity_score,

        er.score_gap_to_next,

        er.match_rule,

        er.decision_status,

        ROW_NUMBER() OVER (
            PARTITION BY er.alias_id
            ORDER BY er.rank_position
        ) AS candidate_order

    FROM
        identity.entity_resolution_candidates er
),


candidate_summary AS (

    SELECT

        alias_id,

        MAX(candidate_model_id)
            FILTER (
                WHERE candidate_order = 1
            )
            AS top_candidate_model_id,

        MAX(normalized_candidate_model)
            FILTER (
                WHERE candidate_order = 1
            )
            AS top_candidate_model,

        MAX(similarity_score)
            FILTER (
                WHERE candidate_order = 1
            )
            AS top_score,

        MAX(score_gap_to_next)
            FILTER (
                WHERE candidate_order = 1
            )
            AS score_gap,

        MAX(match_rule)
            FILTER (
                WHERE candidate_order = 1
            )
            AS match_rule,

        MAX(decision_status)
            FILTER (
                WHERE candidate_order = 1
            )
            AS candidate_decision,

        MAX(normalized_candidate_model)
            FILTER (
                WHERE candidate_order = 2
            )
            AS second_candidate_model,

        MAX(similarity_score)
            FILTER (
                WHERE candidate_order = 2
            )
            AS second_score,

        MAX(normalized_candidate_model)
            FILTER (
                WHERE candidate_order = 3
            )
            AS third_candidate_model,

        MAX(similarity_score)
            FILTER (
                WHERE candidate_order = 3
            )
            AS third_score,

        COUNT(*) AS candidate_count

    FROM ranked_candidates

    GROUP BY
        alias_id
),


normalized_makes AS (

    SELECT

        make_id,

        canonical_make_name,

        REGEXP_REPLACE(
            UPPER(TRIM(canonical_make_name)),
            '[^A-Z0-9]+',
            '',
            'g'
        ) AS normalized_make

    FROM identity.makes
),


unique_normalized_makes AS (

    SELECT

        normalized_make,

        MIN(make_id) AS make_id,

        MIN(canonical_make_name)
            AS canonical_make_name

    FROM normalized_makes

    WHERE
        normalized_make IS NOT NULL

        AND normalized_make <> ''

    GROUP BY
        normalized_make

    HAVING COUNT(*) = 1
),


review_base AS (

    SELECT

        a.alias_id,

        a.source_make,

        a.source_model,

        a.source_model_year,

        COALESCE(
            ma.canonical_make_id,
            unm.make_id
        ) AS resolved_make_id,

        COALESCE(
            verified_make.canonical_make_name,
            unm.canonical_make_name
        ) AS canonical_make_name,

        CASE

            WHEN ma.canonical_make_id
                IS NOT NULL
                THEN 'VPIC_VERIFIED_ALIAS'

            WHEN unm.make_id
                IS NOT NULL
                THEN 'NORMALIZED_MAKE'

            ELSE 'UNRESOLVED_MAKE'

        END AS make_resolution_method,

        cs.top_candidate_model_id,

        cs.top_candidate_model,

        cs.top_score,

        cs.score_gap,

        cs.match_rule,

        cs.candidate_decision,

        cs.second_candidate_model,

        cs.second_score,

        cs.third_candidate_model,

        cs.third_score,

        cs.candidate_count

    FROM
        identity.source_vehicle_aliases a

    JOIN candidate_summary cs
      ON cs.alias_id =
         a.alias_id

    LEFT JOIN identity.make_aliases ma

      ON ma.source_system =
         a.source_system

     AND UPPER(
             TRIM(
                 ma.source_make
             )
         )
         =
         UPPER(
             TRIM(
                 a.source_make
             )
         )

    LEFT JOIN identity.makes verified_make

      ON verified_make.make_id =
         ma.canonical_make_id

    LEFT JOIN unique_normalized_makes unm

      ON unm.normalized_make =
         REGEXP_REPLACE(
             UPPER(TRIM(a.source_make)),
             '[^A-Z0-9]+',
             '',
             'g'
         )

    WHERE

        a.source_system =
            'NHTSA_COMPLAINTS'

        AND a.canonical_model_id
            IS NULL

        AND cs.candidate_decision =
            'REVIEW'
),


review_features AS (

    SELECT

        rb.*,

        LENGTH(
            REGEXP_REPLACE(
                UPPER(rb.source_model),
                '[^A-Z0-9]+',
                '',
                'g'
            )
        ) AS source_model_length,

        LENGTH(
            REGEXP_REPLACE(
                UPPER(rb.top_candidate_model),
                '[^A-Z0-9]+',
                '',
                'g'
            )
        ) AS candidate_model_length,

        CASE

            WHEN GREATEST(
                LENGTH(
                    REGEXP_REPLACE(
                        UPPER(rb.source_model),
                        '[^A-Z0-9]+',
                        '',
                        'g'
                    )
                ),

                LENGTH(
                    REGEXP_REPLACE(
                        UPPER(rb.top_candidate_model),
                        '[^A-Z0-9]+',
                        '',
                        'g'
                    )
                )
            ) = 0
            THEN NULL

            ELSE ROUND(
                (
                    LEAST(
                        LENGTH(
                            REGEXP_REPLACE(
                                UPPER(rb.source_model),
                                '[^A-Z0-9]+',
                                '',
                                'g'
                            )
                        ),

                        LENGTH(
                            REGEXP_REPLACE(
                                UPPER(rb.top_candidate_model),
                                '[^A-Z0-9]+',
                                '',
                                'g'
                            )
                        )
                    )::NUMERIC

                    /

                    GREATEST(
                        LENGTH(
                            REGEXP_REPLACE(
                                UPPER(rb.source_model),
                                '[^A-Z0-9]+',
                                '',
                                'g'
                            )
                        ),

                        LENGTH(
                            REGEXP_REPLACE(
                                UPPER(rb.top_candidate_model),
                                '[^A-Z0-9]+',
                                '',
                                'g'
                            )
                        )
                    )
                ),
                4
            )

        END AS length_ratio

    FROM review_base rb
),


prioritized AS (

    SELECT

        rf.*,

        CASE

            -- =================================================
            -- HIGH EVIDENCE
            --
            -- Token subset relationships can be meaningful,
            -- but still require a human because:
            --
            -- SILVERADO
            -- SILVERADO 1500
            --
            -- are not necessarily identical products.
            -- =================================================

            WHEN
                rf.match_rule LIKE
                    '%TOKEN_SUBSET%'

                AND rf.top_score >= 92

                AND COALESCE(
                    rf.score_gap,
                    0
                ) >= 10

                AND rf.length_ratio >= 0.60

            THEN
                'HIGH_EVIDENCE_REVIEW'


            -- =================================================
            -- MEDIUM EVIDENCE
            -- =================================================

            WHEN
                rf.top_score >= 80

                AND COALESCE(
                    rf.score_gap,
                    0
                ) >= 5

                AND rf.match_rule
                    <> 'PARTIAL_LENGTH_PENALTY'

            THEN
                'MEDIUM_EVIDENCE_REVIEW'


            -- =================================================
            -- LOW EVIDENCE
            --
            -- Includes dangerous partial-length matches,
            -- weak ratios and small separation from runner-up.
            -- =================================================

            ELSE
                'LOW_EVIDENCE_REVIEW'

        END AS review_priority,


        CASE

            WHEN
                rf.match_rule =
                    'PARTIAL_LENGTH_PENALTY'

            THEN
                'SHORT_PARTIAL_MATCH_RISK'

            WHEN
                COALESCE(
                    rf.score_gap,
                    0
                ) < 5

            THEN
                'AMBIGUOUS_TOP_CANDIDATE'

            WHEN
                rf.length_ratio < 0.60

            THEN
                'MODEL_LENGTH_MISMATCH'

            WHEN
                rf.match_rule LIKE
                    '%TOKEN_SUBSET%'

            THEN
                'TOKEN_SUBSET_REQUIRES_REVIEW'

            ELSE
                'GENERAL_FUZZY_MATCH'

        END AS review_reason

    FROM review_features rf
)


SELECT

    p.alias_id,

    p.source_make,

    p.source_model,

    p.source_model_year,

    p.canonical_make_name,

    p.make_resolution_method,

    p.top_candidate_model_id,

    p.top_candidate_model,

    p.top_score,

    p.score_gap,

    p.match_rule,

    p.second_candidate_model,

    p.second_score,

    p.third_candidate_model,

    p.third_score,

    p.candidate_count,

    p.source_model_length,

    p.candidate_model_length,

    p.length_ratio,

    p.review_priority,

    p.review_reason,

    COALESCE(
        r.review_decision,
        'PENDING'
    ) AS human_review_decision,

    r.reviewer_note,

    r.reviewed_by,

    r.reviewed_at

FROM prioritized p

LEFT JOIN
    identity.entity_resolution_reviews r

  ON r.alias_id =
     p.alias_id;