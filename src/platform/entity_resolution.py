from __future__ import annotations

import os
import re
from dataclasses import dataclass

import psycopg
from rapidfuzz import fuzz


# ============================================================
# AutoPulse Fabric
# Explainable Vehicle Entity Resolution
#
# Purpose:
#
# Resolve source-specific vehicle model names against the
# canonical AutoPulse vehicle catalog without silently forcing
# uncertain matches.
#
# Resolution strategy:
#
# 1. Match source makes to canonical makes using a conservative
#    normalized-exact rule. A normalized make key is usable only
#    when it maps to exactly one canonical make.
#
# 2. Compare models ONLY within the resolved canonical make.
#
# 3. Normalize model punctuation and spacing.
#
# 4. Auto-approve ONLY normalized-exact model matches.
#
# 5. Fuzzy algorithms are used only for candidate discovery.
#
# 6. Dangerous short partial matches are heavily penalized.
#
# 7. Persist top candidates and their scoring evidence.
#
# 8. Keep uncertain records unresolved for future review,
#    vehicle-type evidence, VIN evidence and model-year logic.
#
# 9. Create model-year configurations idempotently using the
#    database uniqueness rule on (model_id, model_year).
# ============================================================


TOP_CANDIDATES = 3
SOURCE_SYSTEM = "NHTSA_COMPLAINTS"


# ============================================================
# Candidate data structure
# ============================================================


@dataclass
class Candidate:
    model_id: int
    model_name: str
    normalized_model: str
    score: float
    rule: str


# ============================================================
# Database
# ============================================================


def get_connection() -> psycopg.Connection:
    """
    Connect to AutoPulse PostgreSQL.

    Password is supplied through the PowerShell environment
    variable AUTOPULSE_DB_PASSWORD.
    """

    password = os.environ.get(
        "AUTOPULSE_DB_PASSWORD"
    )

    if not password:
        raise RuntimeError(
            "AUTOPULSE_DB_PASSWORD is not set."
        )

    return psycopg.connect(
        host="localhost",
        port=5432,
        dbname="autopulse_ops",
        user="autopulse_app",
        password=password,
    )


# ============================================================
# Normalization
# ============================================================


def normalize_model(
    value: str,
) -> str:
    """
    Standardize a model name while retaining token boundaries.

    Examples:

    F-150
        -> F 150

    GLA-250
        -> GLA 250

    E-TRON QUATTRO
        -> E TRON QUATTRO
    """

    value = value.upper().strip()

    value = re.sub(
        r"[^A-Z0-9]+",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value


def compact_model(
    value: str,
) -> str:
    """
    Remove spaces after normalization.

    Examples:

    F-150
        -> F150

    F 150
        -> F150
    """

    return normalize_model(
        value
    ).replace(
        " ",
        "",
    )


# ============================================================
# Similarity scoring
# ============================================================


def score_candidate(
    source: str,
    candidate: str,
) -> tuple[float, str]:
    """
    Score a source model against one canonical candidate.

    IMPORTANT:

    Only NORMALIZED_EXACT is eligible for automatic approval.

    Fuzzy scores are candidate-ranking evidence only.
    """

    source_norm = normalize_model(
        source
    )

    candidate_norm = normalize_model(
        candidate
    )

    source_compact = compact_model(
        source
    )

    candidate_compact = compact_model(
        candidate
    )

    # ========================================================
    # Rule 1
    # Normalized exact match
    #
    # Examples:
    #
    # F-150       -> F150
    # GLA 250     -> GLA250
    # BASECAMP    -> BASE CAMP
    #
    # This is the ONLY rule currently eligible for
    # automatic resolution.
    # ========================================================

    if (
        source_compact
        == candidate_compact
    ):
        return (
            100.0,
            "NORMALIZED_EXACT",
        )

    # ========================================================
    # Fuzzy candidate discovery
    # ========================================================

    ratio = fuzz.ratio(
        source_norm,
        candidate_norm,
    )

    token_sort = fuzz.token_sort_ratio(
        source_norm,
        candidate_norm,
    )

    token_set = fuzz.token_set_ratio(
        source_norm,
        candidate_norm,
    )

    partial = fuzz.partial_ratio(
        source_norm,
        candidate_norm,
    )

    scores = {
        "RATIO": float(
            ratio
        ),
        "TOKEN_SORT": float(
            token_sort
        ),
        "TOKEN_SET": float(
            token_set
        ),
        "PARTIAL": float(
            partial
        ),
    }

    rule = max(
        scores,
        key=scores.get,
    )

    score = scores[
        rule
    ]

    # ========================================================
    # Partial-match protection
    #
    # RapidFuzz can legitimately return:
    #
    # TLX TYPE S -> TL = 100 partial
    # E-TRON QUATTRO -> TT = 100 partial
    # EXPRESS 3500 -> SS = 100 partial
    #
    # Those are useful candidate-discovery signals,
    # but absolutely NOT safe identity matches.
    # ========================================================

    if rule == "PARTIAL":

        source_length = len(
            source_compact
        )

        candidate_length = len(
            candidate_compact
        )

        maximum_length = max(
            source_length,
            candidate_length,
        )

        if maximum_length > 0:

            length_ratio = (
                min(
                    source_length,
                    candidate_length,
                )
                /
                maximum_length
            )

        else:

            length_ratio = 0.0

        if length_ratio < 0.70:

            score = min(
                score,
                75.0,
            )

            rule = (
                "PARTIAL_LENGTH_PENALTY"
            )

    # ========================================================
    # Token subset protection
    #
    # Example:
    #
    # SILVERADO 1500
    # SILVERADO
    #
    # This might be related, but not necessarily identical.
    # Keep it as a candidate for review.
    # ========================================================

    source_tokens = set(
        source_norm.split()
    )

    candidate_tokens = set(
        candidate_norm.split()
    )

    token_subset = (

        source_tokens
        != candidate_tokens

        and (

            source_tokens.issubset(
                candidate_tokens
            )

            or

            candidate_tokens.issubset(
                source_tokens
            )
        )
    )

    if token_subset:

        score = min(
            score,
            94.0,
        )

        rule = (
            f"{rule}_TOKEN_SUBSET"
        )

    return (
        round(
            score,
            2,
        ),
        rule,
    )


# ============================================================
# Source aliases
# ============================================================


def fetch_unresolved_aliases(
    connection: psycopg.Connection,
):
    """
    Retrieve unresolved NHTSA complaint identities.

    Make resolution priority:

    1. Explicit vPIC-verified make aliases.
    2. Unique punctuation/spacing-normalized make match.
    3. Otherwise remain unresolved.

    Model candidate generation remains restricted to exactly
    one canonical make.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            WITH normalized_makes AS (

                SELECT
                    make_id,

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

            unique_normalized_makes AS (

                SELECT
                    normalized_make,

                    MIN(make_id)
                        AS make_id

                FROM normalized_makes

                WHERE
                    normalized_make
                        IS NOT NULL

                    AND normalized_make
                        <> ''

                GROUP BY
                    normalized_make

                HAVING COUNT(*) = 1
            ),

            source_with_make AS (

                SELECT

                    a.alias_id,

                    a.source_make,

                    a.source_model,

                    a.source_model_year,

                    COALESCE(
                        vma.canonical_make_id,
                        unm.make_id
                    ) AS make_id

                FROM
                    identity.source_vehicle_aliases a

                LEFT JOIN
                    identity.make_aliases vma

                  ON vma.source_system =
                     a.source_system

                 AND UPPER(
                         TRIM(
                             vma.source_make
                         )
                     )
                     =
                     UPPER(
                         TRIM(
                             a.source_make
                         )
                     )

                LEFT JOIN
                    unique_normalized_makes unm

                  ON unm.normalized_make =
                     REGEXP_REPLACE(
                         UPPER(
                             TRIM(
                                 a.source_make
                             )
                         ),
                         '[^A-Z0-9]+',
                         '',
                         'g'
                     )

                WHERE
                    a.source_system = %s

                    AND a.canonical_model_id
                        IS NULL

                    AND a.source_make
                        IS NOT NULL

                    AND a.source_model
                        IS NOT NULL
            )

            SELECT
                alias_id,
                source_make,
                source_model,
                source_model_year,
                make_id

            FROM source_with_make

            WHERE
                make_id
                IS NOT NULL

            ORDER BY
                alias_id;
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        return cursor.fetchall()

# ============================================================
# Canonical models
# ============================================================


def fetch_models_for_make(
    connection: psycopg.Connection,
    make_id: int,
):
    """
    Retrieve canonical models belonging to one make.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT

                model_id,

                canonical_model_name

            FROM identity.models

            WHERE
                make_id = %s

                AND canonical_model_name
                    IS NOT NULL

            ORDER BY
                canonical_model_name;
            """,
            (
                make_id,
            ),
        )

        return cursor.fetchall()


# ============================================================
# Candidate generation
# ============================================================


def generate_candidates(
    source_model: str,
    canonical_models,
) -> list[Candidate]:
    """
    Score all models within the same make and retain only
    the strongest candidates.
    """

    candidates: list[
        Candidate
    ] = []

    for (
        model_id,
        model_name,
    ) in canonical_models:

        score, rule = (
            score_candidate(
                source_model,
                model_name,
            )
        )

        candidates.append(
            Candidate(

                model_id=model_id,

                model_name=model_name,

                normalized_model=(
                    normalize_model(
                        model_name
                    )
                ),

                score=score,

                rule=rule,
            )
        )

    candidates.sort(
        key=lambda item: (
            item.score,
            len(
                item.normalized_model
            ),
        ),
        reverse=True,
    )

    return candidates[
        :TOP_CANDIDATES
    ]


# ============================================================
# Candidate persistence
# ============================================================


def persist_candidates(
    connection: psycopg.Connection,
    alias_id: int,
    source_model: str,
    candidates: list[Candidate],
) -> None:
    """
    Persist candidate ranking and matching evidence.

    Only rank-1 NORMALIZED_EXACT candidates are automatically
    approved.

    Every fuzzy candidate remains REVIEW.

    Existing candidate rows for the alias are always cleared
    first so reruns cannot leave stale candidate evidence.
    """

    with connection.cursor() as cursor:

        # ----------------------------------------------------
        # Rerun-safe:
        # replace candidates for this alias.
        # ----------------------------------------------------

        cursor.execute(
            """
            DELETE FROM
                identity.entity_resolution_candidates

            WHERE alias_id = %s;
            """,
            (
                alias_id,
            ),
        )

        if not candidates:

            connection.commit()
            return

        for (
            index,
            candidate,
        ) in enumerate(
            candidates
        ):

            rank_position = (
                index + 1
            )

            next_score = None

            if (
                index + 1
                <
                len(
                    candidates
                )
            ):

                next_score = (
                    candidates[
                        index + 1
                    ].score
                )

            score_gap = None

            if next_score is not None:

                score_gap = round(
                    candidate.score
                    - next_score,
                    2,
                )

            # ------------------------------------------------
            # Conservative governance decision
            # ------------------------------------------------

            decision = "REVIEW"

            if (

                rank_position == 1

                and candidate.rule
                    == "NORMALIZED_EXACT"

            ):

                decision = (
                    "AUTO_APPROVED"
                )

            cursor.execute(
                """
                INSERT INTO
                    identity.entity_resolution_candidates
                (
                    alias_id,

                    candidate_model_id,

                    rank_position,

                    normalized_source_model,

                    normalized_candidate_model,

                    similarity_score,

                    score_gap_to_next,

                    match_rule,

                    decision_status
                )

                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                );
                """,
                (
                    alias_id,

                    candidate.model_id,

                    rank_position,

                    normalize_model(
                        source_model
                    ),

                    candidate.normalized_model,

                    candidate.score,

                    score_gap,

                    candidate.rule,

                    decision,
                ),
            )

    connection.commit()


# ============================================================
# Automatic resolution
# ============================================================


def apply_auto_approved_matches(
    connection: psycopg.Connection,
) -> int:
    """
    Apply only safely auto-approved candidate matches.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            UPDATE
                identity.source_vehicle_aliases a

            SET

                canonical_model_id =
                    er.candidate_model_id,

                match_method =
                    er.match_rule,

                match_confidence =
                    er.similarity_score
                    / 100.0,

                reviewed_flag =
                    FALSE

            FROM
                identity.entity_resolution_candidates er

            WHERE

                a.alias_id =
                    er.alias_id

                AND a.source_system = %s

                AND er.rank_position = 1

                AND er.decision_status =
                    'AUTO_APPROVED'

                AND a.canonical_model_id
                    IS NULL;
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        count = cursor.rowcount

    connection.commit()

    return count


# ============================================================
# Model-year configurations
# ============================================================


def create_configurations_for_resolved_aliases(
    connection: psycopg.Connection,
) -> int:
    """
    When an alias becomes safely resolved, create the matching
    model-year configuration if one does not already exist.

    Requires the database uniqueness rule:

        UNIQUE (model_id, model_year)
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            INSERT INTO identity.vehicle_configurations (
                model_id,
                model_year
            )

            SELECT DISTINCT

                canonical_model_id,

                source_model_year

            FROM
                identity.source_vehicle_aliases

            WHERE

                source_system = %s

                AND canonical_model_id
                    IS NOT NULL

                AND source_model_year
                    IS NOT NULL

            ON CONFLICT (
                model_id,
                model_year
            )
            DO NOTHING;
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        created = cursor.rowcount

    connection.commit()

    return created


def attach_configurations(
    connection: psycopg.Connection,
) -> int:
    """
    Attach resolved source aliases to their canonical
    model-year configuration.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            UPDATE
                identity.source_vehicle_aliases a

            SET
                vehicle_configuration_id =
                    vc.vehicle_configuration_id

            FROM
                identity.vehicle_configurations vc

            WHERE

                a.source_system = %s

                AND a.canonical_model_id =
                    vc.model_id

                AND a.source_model_year =
                    vc.model_year

                AND a.vehicle_configuration_id
                    IS NULL;
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        attached = cursor.rowcount

    connection.commit()

    return attached


# ============================================================
# Quality / governance summary
# ============================================================


def print_summary(
    connection: psycopg.Connection,
) -> None:
    """
    Print entity-resolution quality metrics.
    """

    with connection.cursor() as cursor:

        # ----------------------------------------------------
        # Total identities
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM identity.source_vehicle_aliases

            WHERE source_system = %s;
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        total = (
            cursor.fetchone()[0]
        )

        # ----------------------------------------------------
        # Resolved
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM identity.source_vehicle_aliases

            WHERE
                source_system = %s

                AND canonical_model_id
                    IS NOT NULL;
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        resolved = (
            cursor.fetchone()[0]
        )

        # ----------------------------------------------------
        # Unresolved
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM identity.source_vehicle_aliases

            WHERE
                source_system = %s

                AND canonical_model_id
                    IS NULL;
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        unresolved = (
            cursor.fetchone()[0]
        )

        # ----------------------------------------------------
        # Original exact matches
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM identity.source_vehicle_aliases

            WHERE
                source_system = %s

                AND match_method =
                    'EXACT_MAKE_MODEL';
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        exact_matches = (
            cursor.fetchone()[0]
        )

        # ----------------------------------------------------
        # Normalized exact matches
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM identity.source_vehicle_aliases

            WHERE
                source_system = %s

                AND match_method =
                    'NORMALIZED_EXACT';
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        normalized_exact = (
            cursor.fetchone()[0]
        )

        # ----------------------------------------------------
        # Candidate aliases requiring review
        #
        # Only unresolved aliases whose rank-1 candidate is
        # REVIEW are counted.
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(
                DISTINCT er.alias_id
            )

            FROM
                identity.entity_resolution_candidates er

            JOIN
                identity.source_vehicle_aliases a

              ON a.alias_id =
                 er.alias_id

            WHERE
                a.source_system = %s

                AND a.canonical_model_id
                    IS NULL

                AND er.rank_position = 1

                AND er.decision_status =
                    'REVIEW';
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        review_count = (
            cursor.fetchone()[0]
        )

        # ----------------------------------------------------
        # Number of auto-approved candidate aliases
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(
                DISTINCT er.alias_id
            )

            FROM
                identity.entity_resolution_candidates er

            JOIN
                identity.source_vehicle_aliases a

              ON a.alias_id =
                 er.alias_id

            WHERE
                a.source_system = %s

                AND er.decision_status =
                    'AUTO_APPROVED';
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        auto_approved = (
            cursor.fetchone()[0]
        )

        # ----------------------------------------------------
        # Model-year configurations
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM identity.vehicle_configurations;
            """
        )

        configuration_count = (
            cursor.fetchone()[0]
        )

        # ----------------------------------------------------
        # Strongest rank-1 candidates for inspection
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT

                a.source_make,

                a.source_model,

                a.source_model_year,

                m.canonical_model_name,

                er.similarity_score,

                er.score_gap_to_next,

                er.match_rule,

                er.decision_status

            FROM
                identity.entity_resolution_candidates er

            JOIN
                identity.source_vehicle_aliases a

              ON er.alias_id =
                 a.alias_id

            JOIN
                identity.models m

              ON er.candidate_model_id =
                 m.model_id

            WHERE
                a.source_system = %s

                AND er.rank_position = 1

            ORDER BY

                CASE

                    WHEN er.decision_status =
                        'AUTO_APPROVED'
                        THEN 0

                    ELSE 1

                END,

                er.similarity_score DESC,

                a.source_make,

                a.source_model,

                a.source_model_year

            LIMIT 30;
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        examples = (
            cursor.fetchall()
        )

    resolution_rate = (

        resolved
        /
        total
        *
        100

        if total

        else 0
    )

    # ========================================================
    # Console summary
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "AUTOPULSE — ENTITY RESOLUTION RESULTS"
    )

    print(
        "=" * 70
    )

    print(
        f"Total complaint identities: "
        f"{total:,}"
    )

    print(
        f"Original exact matches: "
        f"{exact_matches:,}"
    )

    print(
        f"Normalized exact matches: "
        f"{normalized_exact:,}"
    )

    print(
        f"Resolved identities: "
        f"{resolved:,}"
    )

    print(
        f"Still unresolved: "
        f"{unresolved:,}"
    )

    print(
        f"Overall resolution rate: "
        f"{resolution_rate:.2f}%"
    )

    print(
        f"Auto-approved normalized identities: "
        f"{auto_approved:,}"
    )

    print(
        f"Unresolved aliases queued for review: "
        f"{review_count:,}"
    )

    print(
        f"Vehicle configurations: "
        f"{configuration_count:,}"
    )

    print(
        "\nTop generated candidates:"
    )

    for row in examples:

        (
            make,
            source_model,
            year,
            candidate,
            score,
            gap,
            rule,
            status,
        ) = row

        print(
            "\n"
            f"{make} | "
            f"{source_model} | "
            f"{year}"
        )

        print(
            f"  Candidate: "
            f"{candidate}"
        )

        print(
            f"  Score: "
            f"{score}"
        )

        print(
            f"  Gap: "
            f"{gap}"
        )

        print(
            f"  Rule: "
            f"{rule}"
        )

        print(
            f"  Decision: "
            f"{status}"
        )


# ============================================================
# Main
# ============================================================


def main() -> None:

    print(
        "=" * 70
    )

    print(
        "AUTOPULSE — EXPLAINABLE ENTITY RESOLUTION"
    )

    print(
        "=" * 70
    )

    with get_connection() as connection:

        # ----------------------------------------------------
        # Find unresolved source identities
        # ----------------------------------------------------

        aliases = (
            fetch_unresolved_aliases(
                connection
            )
        )

        print(
            f"Unresolved aliases to evaluate: "
            f"{len(aliases):,}"
        )

        # ----------------------------------------------------
        # Cache canonical models per make
        #
        # Prevent repeatedly querying the same make catalog.
        # ----------------------------------------------------

        make_cache = {}

        processed = 0

        # ----------------------------------------------------
        # Generate candidates
        # ----------------------------------------------------

        for (
            alias_id,
            source_make,
            source_model,
            source_model_year,
            make_id,
        ) in aliases:

            if (
                make_id
                not in make_cache
            ):

                make_cache[
                    make_id
                ] = (
                    fetch_models_for_make(
                        connection,
                        make_id,
                    )
                )

            canonical_models = (
                make_cache[
                    make_id
                ]
            )

            candidates = (
                generate_candidates(
                    source_model=(
                        source_model
                    ),
                    canonical_models=(
                        canonical_models
                    ),
                )
            )

            persist_candidates(
                connection=connection,
                alias_id=alias_id,
                source_model=source_model,
                candidates=candidates,
            )

            processed += 1

            if (
                processed % 500
                == 0
            ):

                print(
                    f"Evaluated "
                    f"{processed:,} "
                    f"aliases..."
                )

        # ----------------------------------------------------
        # Apply only safe automatic matches
        # ----------------------------------------------------

        auto_applied = (
            apply_auto_approved_matches(
                connection
            )
        )

        print(
            "\n"
            f"Auto-approved matches applied: "
            f"{auto_applied:,}"
        )

        # ----------------------------------------------------
        # Build model-year configurations for newly
        # resolved aliases.
        # ----------------------------------------------------

        configurations_created = (
            create_configurations_for_resolved_aliases(
                connection
            )
        )

        print(
            f"New vehicle configurations created: "
            f"{configurations_created:,}"
        )

        # ----------------------------------------------------
        # Attach aliases to configuration IDs
        # ----------------------------------------------------

        configurations_attached = (
            attach_configurations(
                connection
            )
        )

        print(
            f"Aliases linked to configurations: "
            f"{configurations_attached:,}"
        )

        # ----------------------------------------------------
        # Governance summary
        # ----------------------------------------------------

        print_summary(
            connection
        )


if __name__ == "__main__":

    main()
