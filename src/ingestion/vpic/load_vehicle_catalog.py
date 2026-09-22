from __future__ import annotations

import os
from typing import Any

import psycopg
import requests


# ============================================================
# AutoPulse
# NHTSA vPIC Canonical Vehicle Catalog Loader
#
# Purpose:
# - Pull real make/model master data from NHTSA vPIC
# - Populate AutoPulse canonical make/model tables
# - Create source aliases for the vPIC representation
#
# This replaces manually inserting a few demo vehicles.
# ============================================================


VPIC_BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles"


def get_db_connection() -> psycopg.Connection:
    """
    Create PostgreSQL connection.

    Password is requested from environment so credentials
    are not hard-coded in source control.
    """

    password = os.environ.get(
        "AUTOPULSE_DB_PASSWORD"
    )

    if not password:
        raise RuntimeError(
            "AUTOPULSE_DB_PASSWORD environment variable is not set."
        )

    return psycopg.connect(
        host="localhost",
        port=5432,
        dbname="autopulse_ops",
        user="autopulse_app",
        password=password,
    )


def request_json(
    endpoint: str,
    timeout: int = 120,
) -> list[dict[str, Any]]:
    """
    Execute a vPIC request and return its Results collection.
    """

    url = f"{VPIC_BASE_URL}/{endpoint}"

    response = requests.get(
        url,
        params={"format": "json"},
        timeout=timeout,
    )

    response.raise_for_status()

    payload = response.json()

    return payload.get(
        "Results",
        [],
    )


def fetch_all_makes() -> list[dict[str, Any]]:
    """
    Fetch every make available in vPIC.
    """

    print("Fetching vPIC makes...")

    results = request_json(
        "GetAllMakes"
    )

    print(
        f"vPIC makes returned: "
        f"{len(results):,}"
    )

    return results


def fetch_all_models() -> list[dict[str, Any]]:
    """
    Fetch model records across all make IDs.

    vPIC supports MakeId=0 for all makes.
    """

    print("Fetching vPIC models...")

    results = request_json(
        "GetModelsForMakeId/0",
        timeout=300,
    )

    print(
        f"vPIC model records returned: "
        f"{len(results):,}"
    )

    return results


def normalize_text(
    value: Any,
) -> str | None:
    """
    Normalize source strings while preserving business text.
    """

    if value is None:
        return None

    cleaned = str(value).strip()

    if not cleaned:
        return None

    return cleaned.upper()


def load_makes(
    connection: psycopg.Connection,
    makes: list[dict[str, Any]],
) -> dict[int, int]:
    """
    Insert canonical makes.

    Returns:
        vPIC Make_ID -> AutoPulse make_id
    """

    make_id_map: dict[int, int] = {}

    with connection.cursor() as cursor:

        for record in makes:

            source_make_id = record.get(
                "Make_ID"
            )

            make_name = normalize_text(
                record.get("Make_Name")
            )

            if (
                source_make_id is None
                or make_name is None
            ):
                continue

            cursor.execute(
                """
                INSERT INTO identity.makes (
                    canonical_make_name
                )
                VALUES (%s)

                ON CONFLICT (
                    canonical_make_name
                )
                DO UPDATE SET
                    canonical_make_name =
                        EXCLUDED.canonical_make_name

                RETURNING make_id;
                """,
                (
                    make_name,
                ),
            )

            autopulse_make_id = (
                cursor.fetchone()[0]
            )

            make_id_map[
                int(source_make_id)
            ] = autopulse_make_id

    connection.commit()

    print(
        f"Canonical makes loaded: "
        f"{len(make_id_map):,}"
    )

    return make_id_map


def load_models(
    connection: psycopg.Connection,
    models: list[dict[str, Any]],
    make_id_map: dict[int, int],
) -> tuple[int, int]:
    """
    Insert canonical models and source aliases.

    Returns:
        models_loaded
        aliases_loaded
    """

    model_count = 0
    alias_count = 0

    with connection.cursor() as cursor:

        for record in models:

            source_make_id = record.get(
                "Make_ID"
            )

            source_make_name = normalize_text(
                record.get("Make_Name")
            )

            source_model_name = normalize_text(
                record.get("Model_Name")
            )

            if (
                source_make_id is None
                or source_model_name is None
            ):
                continue

            autopulse_make_id = (
                make_id_map.get(
                    int(source_make_id)
                )
            )

            if autopulse_make_id is None:
                continue

            # ---------------------------------------------
            # Canonical model
            # ---------------------------------------------

            cursor.execute(
                """
                INSERT INTO identity.models (
                    make_id,
                    canonical_model_name
                )
                VALUES (
                    %s,
                    %s
                )

                ON CONFLICT (
                    make_id,
                    canonical_model_name
                )
                DO UPDATE SET
                    canonical_model_name =
                        EXCLUDED.canonical_model_name

                RETURNING model_id;
                """,
                (
                    autopulse_make_id,
                    source_model_name,
                ),
            )

            model_id = (
                cursor.fetchone()[0]
            )

            model_count += 1

            # ---------------------------------------------
            # Source alias
            # ---------------------------------------------

            cursor.execute(
                """
                SELECT alias_id
                FROM identity.source_vehicle_aliases
                WHERE source_system = 'NHTSA_VPIC'
                  AND source_make IS NOT DISTINCT FROM %s
                  AND source_model IS NOT DISTINCT FROM %s
                  AND source_model_year IS NULL
                  AND source_variant IS NULL
                LIMIT 1;
                """,
                (
                    source_make_name,
                    source_model_name,
                ),
            )

            existing_alias = (
                cursor.fetchone()
            )

            if existing_alias is None:

                cursor.execute(
                    """
                    INSERT INTO identity.source_vehicle_aliases (
                        source_system,
                        source_make,
                        source_model,
                        canonical_model_id,
                        match_method,
                        match_confidence,
                        reviewed_flag
                    )
                    VALUES (
                        'NHTSA_VPIC',
                        %s,
                        %s,
                        %s,
                        'SOURCE_NATIVE',
                        1.0000,
                        TRUE
                    );
                    """,
                    (
                        source_make_name,
                        source_model_name,
                        model_id,
                    ),
                )

                alias_count += 1

    connection.commit()

    print(
        f"Canonical model records processed: "
        f"{model_count:,}"
    )

    print(
        f"New vPIC aliases created: "
        f"{alias_count:,}"
    )

    return (
        model_count,
        alias_count,
    )


def validate_catalog(
    connection: psycopg.Connection,
) -> None:
    """
    Print basic catalog validation metrics.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM identity.makes;
            """
        )

        make_count = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM identity.models;
            """
        )

        model_count = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM identity.source_vehicle_aliases
            WHERE source_system = 'NHTSA_VPIC';
            """
        )

        alias_count = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT
                m.canonical_make_name,
                COUNT(*) AS model_count
            FROM identity.models mo
            JOIN identity.makes m
              ON mo.make_id = m.make_id
            GROUP BY
                m.canonical_make_name
            ORDER BY
                model_count DESC,
                m.canonical_make_name
            LIMIT 15;
            """
        )

        largest_makes = cursor.fetchall()

    print("\n" + "=" * 70)
    print("AUTOPULSE VEHICLE CATALOG")
    print("=" * 70)

    print(
        f"Canonical makes: "
        f"{make_count:,}"
    )

    print(
        f"Canonical models: "
        f"{model_count:,}"
    )

    print(
        f"vPIC aliases: "
        f"{alias_count:,}"
    )

    print(
        "\nLargest make catalogs:"
    )

    for (
        make_name,
        count,
    ) in largest_makes:

        print(
            f"  {make_name:<30} "
            f"{count:>6,} models"
        )


def main() -> None:

    print("=" * 70)
    print("AUTOPULSE — VPIC VEHICLE MASTER LOAD")
    print("=" * 70)

    makes = fetch_all_makes()

    models = fetch_all_models()

    with get_db_connection() as connection:

        make_id_map = load_makes(
            connection=connection,
            makes=makes,
        )

        load_models(
            connection=connection,
            models=models,
            make_id_map=make_id_map,
        )

        validate_catalog(
            connection
        )


if __name__ == "__main__":
    main()