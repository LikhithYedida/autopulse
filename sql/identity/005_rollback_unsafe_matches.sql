-- ============================================================
-- AutoPulse Fabric
-- Reset Unsafe Entity Resolution Matches
--
-- Purpose:
-- Keep only the original safe exact Make + Model matches.
--
-- All matches produced by the entity-resolution engine are
-- reset and rebuilt from scratch so the candidate audit table
-- remains consistent with the current matching logic.
-- ============================================================


BEGIN;


-- ============================================================
-- Remove model-year configuration links from aliases that
-- were resolved by the entity-resolution engine.
--
-- Keep only original EXACT_MAKE_MODEL resolutions.
-- ============================================================

UPDATE identity.source_vehicle_aliases

SET
    canonical_model_id = NULL,
    vehicle_configuration_id = NULL,
    match_method = 'UNRESOLVED',
    match_confidence = NULL,
    reviewed_flag = FALSE

WHERE
    source_system = 'NHTSA_COMPLAINTS'

    AND canonical_model_id IS NOT NULL

    AND match_method <> 'EXACT_MAKE_MODEL';


-- ============================================================
-- Clear old candidate decisions.
--
-- They will be regenerated using the corrected engine.
-- ============================================================

DELETE FROM identity.entity_resolution_candidates;


COMMIT;