from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import psycopg
import requests


# ============================================================
# AutoPulse
# vPIC Vehicle-Type Classification Loader
#
# Purpose:
# - Preserve the full vPIC universe
# - Identify makes that belong to road-automobile categories
# - Populate identity.vehicle_types
# - Populate identity.make_vehicle_types
#
# We do NOT delete motorcycles, trailers, RVs, etc.
# They remain in the canonical source catalog.
# ============================================================


VPIC_BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles"


# ============================================================
# AutoPulse automobile scope
#
# These represent motorized road-vehicle categories that are
# relevant to the broader AutoPulse automotive platform.
#
# We deliberately exclude:
# - Motorcycle
# - Trailer
# - Incomplete Vehicle
#
# Those remain available in the full source universe.
# ============================================================

AUTOMOBILE_VEHICLE_TYPES = [
    "Passenger Car",
    "Truck",
    "Multipurpose Passenger Vehicle (MPV)",
    "Bus",
    "Low Speed Vehicle (LSV)",
]


def get_db_connection() -> psycopg.Connection:
    """
    Connect to the AutoPulse operational PostgreSQL database.
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


def normalize_text(
    value: Any,
) -> str | None:
    """
    Normalize textual identifiers for matching.
    """

    if value is None:
        return None

    cleaned = str(value).strip()

    if not cleaned:
        return None

    return cleaned.upper()


def fetch_makes_for_vehicle_type(
    vehicle_type: str,
) -> list[dict[str, Any]]:
    """
    Retrieve all makes associated with one vPIC
    vehicle-type classification.
    """

    encoded_type = quote(
        vehicle_type,
        safe="",
    )

    url = (
        f"{VPIC_BASE_URL}/"
        f"GetMakesForVehicleType/"
        f"{encoded_type}"
    )

    print(
        f"Fetching: {vehicle_type}"
    )

    response = requests.get(
        url,
        params={
            "format": "json",
        },
        timeout=120,
    )

    response.raise_for_status()

    payload = response.json()

    results = payload.get(
        "Results",
        [],
    )

    print(
        f"  Returned "
        f"{len(results):,} make/type rows"
    )

    return results


def get_result_value(
    record: dict[str, Any],
    *possible_keys: str,
):
    """
    vPIC response fields can occasionally differ in
    capitalization/format between endpoints.

    Resolve a value safely from several expected names.
    """

    for key in possible_keys:

        if key in record:
            return record[key]

    return None


def upsert_vehicle_type(
    cursor,
    vehicle_type_name: str,
    source_vehicle_type_id: int | None,
) -> int:
    """
    Insert/update one vPIC vehicle type and return its
    AutoPulse vehicle_type_id.
    """

    cursor.execute(
        """
        INSERT INTO identity.vehicle_types (
            source_system,
            source_vehicle_type_id,
            vehicle_type_name,
            automobile_scope_flag
        )
        VALUES (
            'NHTSA_VPIC',
            %s,
            %s,
            TRUE
        )

        ON CONFLICT (
            source_system,
            vehicle_type_name
        )
        DO UPDATE SET

            source_vehicle_type_id =
                COALESCE(
                    EXCLUDED.source_vehicle_type_id,
                    identity.vehicle_types.source_vehicle_type_id
                ),

            automobile_scope_flag = TRUE

        RETURNING vehicle_type_id;
        """,
        (
            source_vehicle_type_id,
            vehicle_type_name,
        ),
    )

    return cursor.fetchone()[0]


def find_make_id(
    cursor,
    make_name: str,
) -> int | None:
    """
    Resolve the existing AutoPulse canonical make.
    """

    cursor.execute(
        """
        SELECT make_id

        FROM identity.makes

        WHERE canonical_make_name = %s

        LIMIT 1;
        """,
        (
            make_name,
        ),
    )

    result = cursor.fetchone()

    if result is None:
        return None

    return result[0]


def load_vehicle_type_results(
    connection: psycopg.Connection,
    requested_vehicle_type: str,
    results: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """
    Populate vehicle types and make/type relationships.

    Returns:
        mapped_rows
        unmatched_makes
        new_relationships
    """

    mapped_rows = 0
    unmatched_makes = 0
    new_relationships = 0

    with connection.cursor() as cursor:

        for record in results:

            source_make_name = normalize_text(
                get_result_value(
                    record,
                    "MakeName",
                    "Make_Name",
                    "MakeName ",
                )
            )

            source_vehicle_type_name = (
                get_result_value(
                    record,
                    "VehicleTypeName",
                    "VehicleType_Name",
                )
            )

            source_vehicle_type_id = (
                get_result_value(
                    record,
                    "VehicleTypeId",
                    "VehicleType_ID",
                )
            )

            # Some vPIC responses may not repeat the
            # requested type text. Use our requested
            # classification as the safe fallback.
            vehicle_type_name = normalize_text(
                source_vehicle_type_name
                or requested_vehicle_type
            )

            if (
                source_make_name is None
                or vehicle_type_name is None
            ):
                continue

            if source_vehicle_type_id is not None:

                try:
                    source_vehicle_type_id = int(
                        source_vehicle_type_id
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    source_vehicle_type_id = None

            vehicle_type_id = (
                upsert_vehicle_type(
                    cursor=cursor,
                    vehicle_type_name=vehicle_type_name,
                    source_vehicle_type_id=(
                        source_vehicle_type_id
                    ),
                )
            )

            make_id = find_make_id(
                cursor=cursor,
                make_name=source_make_name,
            )

            if make_id is None:

                unmatched_makes += 1
                continue

            cursor.execute(
                """
                INSERT INTO identity.make_vehicle_types (
                    make_id,
                    vehicle_type_id,
                    source_system
                )
                VALUES (
                    %s,
                    %s,
                    'NHTSA_VPIC'
                )

                ON CONFLICT (
                    make_id,
                    vehicle_type_id,
                    source_system
                )
                DO NOTHING

                RETURNING make_id;
                """,
                (
                    make_id,
                    vehicle_type_id,
                ),
            )

            inserted = cursor.fetchone()

            if inserted is not None:
                new_relationships += 1

            mapped_rows += 1

    connection.commit()

    return (
        mapped_rows,
        unmatched_makes,
        new_relationships,
    )


def validate_classification(
    connection: psycopg.Connection,
) -> None:
    """
    Print scope metrics after classification.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT
                vehicle_type_name,
                COUNT(DISTINCT mvt.make_id)
                    AS make_count

            FROM identity.vehicle_types vt

            JOIN identity.make_vehicle_types mvt
              ON vt.vehicle_type_id
                 = mvt.vehicle_type_id

            WHERE vt.automobile_scope_flag = TRUE

            GROUP BY
                vehicle_type_name

            ORDER BY
                make_count DESC,
                vehicle_type_name;
            """
        )

        type_counts = cursor.fetchall()

        cursor.execute(
            """
            SELECT
                COUNT(DISTINCT mvt.make_id)

            FROM identity.make_vehicle_types mvt

            JOIN identity.vehicle_types vt
              ON mvt.vehicle_type_id
                 = vt.vehicle_type_id

            WHERE vt.automobile_scope_flag = TRUE;
            """
        )

        automobile_make_count = (
            cursor.fetchone()[0]
        )

        cursor.execute(
            """
            SELECT
                COUNT(DISTINCT mo.model_id)

            FROM identity.models mo

            JOIN identity.make_vehicle_types mvt
              ON mo.make_id = mvt.make_id

            JOIN identity.vehicle_types vt
              ON mvt.vehicle_type_id
                 = vt.vehicle_type_id

            WHERE vt.automobile_scope_flag = TRUE;
            """
        )

        automobile_model_count = (
            cursor.fetchone()[0]
        )

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM identity.makes;
            """
        )

        full_make_count = (
            cursor.fetchone()[0]
        )

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM identity.models;
            """
        )

        full_model_count = (
            cursor.fetchone()[0]
        )

    print("\n" + "=" * 70)
    print("AUTOPULSE VEHICLE-TYPE CLASSIFICATION")
    print("=" * 70)

    print(
        f"Full vPIC make universe: "
        f"{full_make_count:,}"
    )

    print(
        f"Full vPIC model universe: "
        f"{full_model_count:,}"
    )

    print(
        f"\nAutomobile-scope makes: "
        f"{automobile_make_count:,}"
    )

    print(
        f"Models belonging to automobile-scope makes: "
        f"{automobile_model_count:,}"
    )

    print(
        "\nMakes by automobile vehicle type:"
    )

    for (
        vehicle_type,
        count,
    ) in type_counts:

        print(
            f"  {vehicle_type:<40} "
            f"{count:>6,}"
        )


def main() -> None:

    print("=" * 70)
    print("AUTOPULSE — VPIC VEHICLE TYPE LOAD")
    print("=" * 70)

    all_results = {}

    for vehicle_type in (
        AUTOMOBILE_VEHICLE_TYPES
    ):

        results = (
            fetch_makes_for_vehicle_type(
                vehicle_type
            )
        )

        all_results[
            vehicle_type
        ] = results

    with get_db_connection() as connection:

        total_mapped = 0
        total_unmatched = 0
        total_new_relationships = 0

        for (
            vehicle_type,
            results,
        ) in all_results.items():

            (
                mapped,
                unmatched,
                new_relationships,
            ) = load_vehicle_type_results(
                connection=connection,
                requested_vehicle_type=(
                    vehicle_type
                ),
                results=results,
            )

            total_mapped += mapped
            total_unmatched += unmatched
            total_new_relationships += (
                new_relationships
            )

        print(
            f"\nMapped make/type rows: "
            f"{total_mapped:,}"
        )

        print(
            f"New relationships created: "
            f"{total_new_relationships:,}"
        )

        print(
            f"Unmatched source makes: "
            f"{total_unmatched:,}"
        )

        validate_classification(
            connection
        )


if __name__ == "__main__":
    main()