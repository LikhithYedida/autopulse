-- ============================================================
-- AutoPulse Fabric
-- Entity Resolution Candidate Layer
--
-- Grain:
-- One row per source alias / candidate canonical model pair.
--
-- Purpose:
-- Preserve explainable candidate scoring instead of
-- silently applying fuzzy matches.
-- ============================================================


CREATE TABLE IF NOT EXISTS identity.entity_resolution_candidates (

    candidate_id BIGINT
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    alias_id BIGINT
        NOT NULL,

    candidate_model_id BIGINT
        NOT NULL,

    rank_position SMALLINT
        NOT NULL,

    normalized_source_model VARCHAR(250)
        NOT NULL,

    normalized_candidate_model VARCHAR(250)
        NOT NULL,

    similarity_score NUMERIC(6, 2)
        NOT NULL,

    score_gap_to_next NUMERIC(6, 2),

    match_rule VARCHAR(100)
        NOT NULL,

    decision_status VARCHAR(30)
        NOT NULL
        DEFAULT 'REVIEW',

    created_at TIMESTAMPTZ
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_resolution_alias
        FOREIGN KEY (alias_id)
        REFERENCES identity.source_vehicle_aliases(alias_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_resolution_model
        FOREIGN KEY (candidate_model_id)
        REFERENCES identity.models(model_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_resolution_score
        CHECK (
            similarity_score >= 0
            AND similarity_score <= 100
        ),

    CONSTRAINT chk_resolution_decision
        CHECK (
            decision_status IN (
                'AUTO_APPROVED',
                'REVIEW',
                'REJECTED'
            )
        ),

    CONSTRAINT uq_resolution_candidate
        UNIQUE (
            alias_id,
            candidate_model_id
        )
);


CREATE INDEX IF NOT EXISTS
    ix_resolution_alias

ON identity.entity_resolution_candidates (
    alias_id,
    rank_position
);


CREATE INDEX IF NOT EXISTS
    ix_resolution_decision

ON identity.entity_resolution_candidates (
    decision_status,
    similarity_score DESC
);