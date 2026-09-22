-- ============================================================
-- AutoPulse Fabric
-- Warranty Escalation Historical Attribution
--
-- Business problem:
-- service_orders.current_advisor_id only identifies the
-- CURRENT owner.
--
-- Warranty escalations must instead be attributed to the
-- advisor responsible when the escalation actually occurred.
--
-- Grain:
-- One row per warranty escalation.
-- ============================================================


CREATE SCHEMA IF NOT EXISTS analytics
AUTHORIZATION autopulse_app;


CREATE OR REPLACE VIEW
analytics.warranty_escalation_attribution
AS


SELECT

    -- ========================================================
    -- Escalation identity
    -- ========================================================

    we.escalation_id,

    we.escalation_number,

    we.escalated_at,

    we.escalation_type,

    we.severity,

    we.estimated_cost,

    we.escalation_status,


    -- ========================================================
    -- Service order
    -- ========================================================

    so.service_order_id,

    so.service_order_number,

    so.opened_at AS service_order_opened_at,

    so.closed_at AS service_order_closed_at,

    so.service_status,

    so.priority,


    -- ========================================================
    -- Vehicle
    -- ========================================================

    v.vehicle_id,

    v.model_year,

    v.make,

    v.model,

    v.trim,


    -- ========================================================
    -- CURRENT advisor
    --
    -- Useful operationally, but should not be used for
    -- historical event attribution.
    -- ========================================================

    current_advisor.advisor_id
        AS current_advisor_id,

    current_advisor.advisor_code
        AS current_advisor_code,

    current_advisor.first_name
        || ' '
        || current_advisor.last_name
        AS current_advisor_name,


    -- ========================================================
    -- Advisor responsible AT TIME OF ESCALATION
    -- ========================================================

    historical_advisor.advisor_id
        AS escalation_owner_advisor_id,

    historical_advisor.advisor_code
        AS escalation_owner_advisor_code,

    historical_advisor.first_name
        || ' '
        || historical_advisor.last_name
        AS escalation_owner_advisor_name,


    -- ========================================================
    -- Historical assignment interval
    -- ========================================================

    sah.assigned_at
        AS owner_assigned_at,

    sah.unassigned_at
        AS owner_unassigned_at,


    -- ========================================================
    -- Governance / analytical signal
    --
    -- Makes ownership changes visible to downstream users.
    -- ========================================================

    CASE

        WHEN current_advisor.advisor_id
             = historical_advisor.advisor_id

            THEN FALSE

        ELSE TRUE

    END AS ownership_changed_since_escalation


FROM operational.warranty_escalations we


JOIN operational.service_orders so

    ON we.service_order_id
       = so.service_order_id


JOIN operational.vehicles v

    ON so.vehicle_id
       = v.vehicle_id


LEFT JOIN operational.service_advisors current_advisor

    ON so.current_advisor_id
       = current_advisor.advisor_id


LEFT JOIN operational.service_assignment_history sah

    ON we.service_order_id
       = sah.service_order_id

    AND we.escalated_at
        >= sah.assigned_at

    AND (
        sah.unassigned_at IS NULL

        OR we.escalated_at
           < sah.unassigned_at
    )


LEFT JOIN operational.service_advisors historical_advisor

    ON sah.advisor_id
       = historical_advisor.advisor_id;