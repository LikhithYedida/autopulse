from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pyarrow.parquet as pq


# ============================================================
# AutoPulse
# NHTSA Complaint Vehicle Identity Loader
#
# Purpose:
# - Extract distinct real Make / Model / Model-Year identities
#   from the validated NHTSA complaint staging dataset.
# - Persist them as source-specific vehicle aliases.
# - Resolve only safe EXACT canonical matches.
# - Preserve unresolved aliases for later entity resolution.
# ============================================================


PARQUET_PATH = Path(
    "data/staging/nhtsa/complaints/"
    "nhtsa_vehicle_complaints_2025_2026.parquet"
)

SOURCE_SYSTEM = "NHTSA_COMPLAINTS"


def get_db_connection() -> psycopg.Connection:

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
    value,
) -> str | None:

    if value is None:
        return None

    cleaned = str(value).strip().upper()

    if cleaned == "":
        return None

    return cleaned


def extract_distinct_vehicle_identities():
    """
    Read only the columns required for master-data identity.

    No complaint narratives or sensitive information
    are loaded into PostgreSQL here.
    """

    print(
        f"Reading staged complaint identities from:\n"
        f"{PARQUET_PATH}"
    )

    table = pq.read_table(
        PARQUET_PATH,
        columns=[
            "make",
            "model",
            "model_year",
            "model_year_unknown",
        ],
    )

    makes = table["make"].to_pylist()
    models = table["model"].to_pylist()
    years = table["model_year"].to_pylist()
    unknown_flags = (
        table[
            "model_year_unknown"
        ].to_pylist()
    )

    identities = set()

    unknown_year_rows = 0

    for (
        make,
        model,
        year,
        year_unknown,
    ) in zip(
        makes,
        models,
        years,
        unknown_flags,
    ):

        make = normalize_text(make)
        model = normalize_text(model)

        if (
            make is None
            or model is None
        ):
            continue

        if year_unknown:
            unknown_year_rows += 1
            year = None

        identities.add(
            (
                make,
                model,
                year,
            )
        )

    print(
        f"Distinct source identities: "
        f"{len(identities):,}"
    )

    print(
        f"Rows carrying unknown model year: "
        f"{unknown_year_rows:,}"
    )

    return identities


def load_source_aliases(
    connection: psycopg.Connection,
    identities,
) -> int:
    """
    Insert NHTSA complaint identities.

    They begin unresolved because source labels are not
    automatically assumed to equal the canonical model.
    """

    inserted = 0

    with connection.cursor() as cursor:

        for (
            make,
            model,
            model_year,
        ) in identities:

            cursor.execute(
                """
                INSERT INTO identity.source_vehicle_aliases (
                    source_system,
                    source_make,
                    source_model,
                    source_model_year,
                    match_method,
                    reviewed_flag
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    'UNRESOLVED',
                    FALSE
                )

                ON CONFLICT DO NOTHING

                RETURNING alias_id;
                """,
                (
                    SOURCE_SYSTEM,
                    make,
                    model,
                    model_year,
                ),
            )

            if cursor.fetchone() is not None:
                inserted += 1

    connection.commit()

    return inserted


def resolve_exact_matches(
    connection: psycopg.Connection,
) -> int:
    """
    Resolve only source make/model combinations that have
    an exact canonical make + canonical model match.

    This deliberately does NOT use fuzzy matching.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            UPDATE identity.source_vehicle_aliases a

            SET
                canonical_model_id =
                    mo.model_id,

                match_method =
                    'EXACT_MAKE_MODEL',

                match_confidence =
                    1.0000,

                reviewed_flag =
                    TRUE

            FROM identity.makes ma

            JOIN identity.models mo
              ON ma.make_id = mo.make_id

            WHERE
                a.source_system =
                    'NHTSA_COMPLAINTS'

                AND a.canonical_model_id
                    IS NULL

                AND UPPER(
                    TRIM(
                        a.source_make
                    )
                )
                =
                UPPER(
                    TRIM(
                        ma.canonical_make_name
                    )
                )

                AND UPPER(
                    TRIM(
                        a.source_model
                    )
                )
                =
                UPPER(
                    TRIM(
                        mo.canonical_model_name
                    )
                );
            """
        )

        resolved = cursor.rowcount

    connection.commit()

    return resolved


def create_exact_configurations(
    connection: psycopg.Connection,
) -> int:
    """
    Create model-year configurations for exact-resolved
    complaint identities where model year is known.
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

            FROM identity.source_vehicle_aliases

            WHERE
                source_system =
                    'NHTSA_COMPLAINTS'

                AND canonical_model_id
                    IS NOT NULL

                AND source_model_year
                    IS NOT NULL

            ON CONFLICT (
                model_id,
                model_year
            )
            DO NOTHING;
            """
        )

        created = cursor.rowcount

    connection.commit()

    return created


def attach_configurations(
    connection: psycopg.Connection,
) -> int:
    """
    Link exact-resolved aliases to their model-year
    configuration.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            UPDATE identity.source_vehicle_aliases a

            SET vehicle_configuration_id =
                vc.vehicle_configuration_id

            FROM identity.vehicle_configurations vc

            WHERE
                a.source_system =
                    'NHTSA_COMPLAINTS'

                AND a.canonical_model_id =
                    vc.model_id

                AND a.source_model_year =
                    vc.model_year

                AND a.vehicle_configuration_id
                    IS NULL;
            """
        )

        attached = cursor.rowcount

    connection.commit()

    return attached


def print_quality_summary(
    connection: psycopg.Connection,
) -> None:

    with connection.cursor() as cursor:

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM identity.source_vehicle_aliases
            WHERE source_system =
                'NHTSA_COMPLAINTS';
            """
        )

        total_aliases = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM identity.source_vehicle_aliases
            WHERE source_system =
                'NHTSA_COMPLAINTS'
              AND canonical_model_id
                  IS NOT NULL;
            """
        )

        resolved = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM identity.source_vehicle_aliases
            WHERE source_system =
                'NHTSA_COMPLAINTS'
              AND canonical_model_id
                  IS NULL;
            """
        )

        unresolved = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM identity.vehicle_configurations;
            """
        )

        configurations = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT
                source_make,
                source_model,
                COUNT(*) AS year_count

            FROM identity.source_vehicle_aliases

            WHERE
                source_system =
                    'NHTSA_COMPLAINTS'

                AND canonical_model_id
                    IS NULL

            GROUP BY
                source_make,
                source_model

            ORDER BY
                year_count DESC,
                source_make,
                source_model

            LIMIT 20;
            """
        )

        unresolved_examples = (
            cursor.fetchall()
        )

    resolution_rate = (
        resolved / total_aliases * 100
        if total_aliases
        else 0
    )

    print("\n" + "=" * 70)
    print("AUTOPULSE — SOURCE IDENTITY RESOLUTION")
    print("=" * 70)

    print(
        f"NHTSA complaint identities: "
        f"{total_aliases:,}"
    )

    print(
        f"Exact canonical matches: "
        f"{resolved:,}"
    )

    print(
        f"Unresolved identities: "
        f"{unresolved:,}"
    )

    print(
        f"Exact-match resolution rate: "
        f"{resolution_rate:.2f}%"
    )

    print(
        f"Vehicle configurations: "
        f"{configurations:,}"
    )

    print(
        "\nTop unresolved source identities:"
    )

    for (
        make,
        model,
        year_count,
    ) in unresolved_examples:

        print(
            f"  {make:<20} "
            f"{model:<35} "
            f"{year_count:>3} observed years"
        )


def main() -> None:

    print("=" * 70)
    print("AUTOPULSE — NHTSA VEHICLE IDENTITY LOAD")
    print("=" * 70)

    identities = (
        extract_distinct_vehicle_identities()
    )

    with get_db_connection() as connection:

        inserted = load_source_aliases(
            connection,
            identities,
        )

        print(
            f"New complaint aliases inserted: "
            f"{inserted:,}"
        )

        resolved = resolve_exact_matches(
            connection
        )

        print(
            f"New exact matches resolved: "
            f"{resolved:,}"
        )

        configurations = (
            create_exact_configurations(
                connection
            )
        )

        print(
            f"New model-year configurations: "
            f"{configurations:,}"
        )

        attached = attach_configurations(
            connection
        )

        print(
            f"Aliases linked to configurations: "
            f"{attached:,}"
        )

        print_quality_summary(
            connection
        )


if __name__ == "__main__":
    main()