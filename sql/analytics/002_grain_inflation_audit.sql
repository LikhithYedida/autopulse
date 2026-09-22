-- ============================================================
-- AutoPulse Fabric
-- Grain Inflation Audit
--
-- Purpose:
-- Detect whether joining an event-level dataset to a
-- historical one-to-many table inflates business metrics.
--
-- Example:
-- 1 warranty escalation
-- x
-- 2 historical assignments
-- =
-- 2 joined rows
--
-- This is NOT two escalations.
-- ============================================================


CREATE OR REPLACE VIEW
analytics.warranty_grain_inflation_audit
AS


WITH actual_events AS (

    SELECT

        service_order_id,

        COUNT(
            DISTINCT escalation_id
        ) AS actual_escalation_count

    FROM operational.warranty_escalations

    GROUP BY
        service_order_id

),


naive_join AS (

    SELECT

        we.service_order_id,

        COUNT(*) AS naive_join_row_count

    FROM operational.warranty_escalations we

    JOIN operational.service_assignment_history sah

        ON we.service_order_id
           = sah.service_order_id

    GROUP BY
        we.service_order_id

),


point_in_time_join AS (

    SELECT

        we.service_order_id,

        COUNT(*) AS point_in_time_row_count

    FROM operational.warranty_escalations we

    JOIN operational.service_assignment_history sah

        ON we.service_order_id
           = sah.service_order_id

        AND we.escalated_at
            >= sah.assigned_at

        AND (
            sah.unassigned_at IS NULL

            OR we.escalated_at
               < sah.unassigned_at
        )

    GROUP BY
        we.service_order_id

)


SELECT

    so.service_order_number,

    ae.actual_escalation_count,

    nj.naive_join_row_count,

    pj.point_in_time_row_count,


    ROUND(
        nj.naive_join_row_count::NUMERIC
        /
        NULLIF(
            ae.actual_escalation_count,
            0
        ),
        2
    ) AS naive_inflation_factor,


    CASE

        WHEN nj.naive_join_row_count
             >
             ae.actual_escalation_count

            THEN TRUE

        ELSE FALSE

    END AS grain_risk_detected,


    CASE

        WHEN pj.point_in_time_row_count
             =
             ae.actual_escalation_count

            THEN TRUE

        ELSE FALSE

    END AS point_in_time_join_preserves_grain


FROM actual_events ae


JOIN operational.service_orders so

    ON ae.service_order_id
       = so.service_order_id


JOIN naive_join nj

    ON ae.service_order_id
       = nj.service_order_id


JOIN point_in_time_join pj

    ON ae.service_order_id
       = pj.service_order_id;