from __future__ import annotations

import csv
import os
import time
from pathlib import Path
from urllib.parse import quote

import psycopg
import requests


# ============================================================
# AutoPulse
# Probe unresolved source makes against NHTSA vPIC
# ============================================================


SOURCE_SYSTEM = "NHTSA_COMPLAINTS"

VPIC_BASE_URL = (
    "https://vpic.nhtsa.dot.gov/api/vehicles"
)

OUTPUT_PATH = Path(
    "data/reference/vpic/missing_make_probe.csv"
)

REQUEST_DELAY_SECONDS = 0.20
REQUEST_TIMEOUT_SECONDS = 60


# ============================================================
# Database
# ============================================================


def get_connection() -> psycopg.Connection:

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
# Fetch currently unmapped makes
# ============================================================


def fetch_unmapped_makes(
    connection: psycopg.Connection,
):
    """
    Return unresolved source makes that do not have a unique
    punctuation/spacing-normalized canonical make match.
    """

    with connection.cursor() as cursor:

        cursor.execute(
            """
            WITH canonical_normalized AS (

                SELECT

                    REGEXP_REPLACE(
                        UPPER(
                            TRIM(
                                canonical_make_name
                            )
                        ),
                        '[^A-Z0-9]+',
                        '',
                        'g'
                    ) AS normalized_make,

                    COUNT(*) AS canonical_count

                FROM identity.makes

                GROUP BY
                    REGEXP_REPLACE(
                        UPPER(
                            TRIM(
                                canonical_make_name
                            )
                        ),
                        '[^A-Z0-9]+',
                        '',
                        'g'
                    )
            )

            SELECT

                a.source_make,

                COUNT(*) AS alias_count

            FROM identity.source_vehicle_aliases a

            LEFT JOIN canonical_normalized cn

              ON cn.normalized_make =
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

                AND (
                    cn.normalized_make
                        IS NULL

                    OR

                    cn.canonical_count
                        <> 1
                )

            GROUP BY
                a.source_make

            ORDER BY
                alias_count DESC,
                a.source_make;
            """,
            (
                SOURCE_SYSTEM,
            ),
        )

        return cursor.fetchall()


# ============================================================
# vPIC
# ============================================================


def fetch_vpic_models(
    session: requests.Session,
    source_make: str,
) -> list[dict]:

    encoded_make = quote(
        source_make,
        safe="",
    )

    url = (
        f"{VPIC_BASE_URL}"
        f"/GetModelsForMake/"
        f"{encoded_make}"
        f"?format=json"
    )

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    payload = response.json()

    return payload.get(
        "Results",
        [],
    )


# ============================================================
# Main
# ============================================================


def main() -> None:

    print(
        "=" * 70
    )

    print(
        "AUTOPULSE — VPIC MISSING MAKE PROBE"
    )

    print(
        "=" * 70
    )

    with get_connection() as connection:

        unresolved_makes = (
            fetch_unmapped_makes(
                connection
            )
        )

    print(
        f"Unmapped source makes to probe: "
        f"{len(unresolved_makes):,}"
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent":
                "AutoPulse-Portfolio-Analytics/1.0"
        }
    )

    output_rows = []

    makes_with_models = 0
    makes_without_models = 0
    errors = 0

    for index, (
        source_make,
        alias_count,
    ) in enumerate(
        unresolved_makes,
        start=1,
    ):

        try:

            results = fetch_vpic_models(
                session=session,
                source_make=source_make,
            )

            model_count = len(
                results
            )

            returned_make_names = sorted(
                {
                    str(
                        row.get(
                            "Make_Name"
                        )
                    ).strip()

                    for row in results

                    if row.get(
                        "Make_Name"
                    )
                }
            )

            returned_make_ids = sorted(
                {
                    str(
                        row.get(
                            "Make_ID"
                        )
                    )

                    for row in results

                    if row.get(
                        "Make_ID"
                    )
                    is not None
                }
            )

            example_models = [

                str(
                    row.get(
                        "Model_Name"
                    )
                ).strip()

                for row in results[:10]

                if row.get(
                    "Model_Name"
                )
            ]

            if model_count > 0:

                status = (
                    "MODELS_FOUND"
                )

                makes_with_models += 1

            else:

                status = (
                    "NO_MODELS_FOUND"
                )

                makes_without_models += 1

            output_rows.append(
                {
                    "source_make":
                        source_make,

                    "alias_count":
                        alias_count,

                    "status":
                        status,

                    "models_returned":
                        model_count,

                    "returned_make_ids":
                        " | ".join(
                            returned_make_ids
                        ),

                    "returned_make_names":
                        " | ".join(
                            returned_make_names
                        ),

                    "example_models":
                        " | ".join(
                            example_models
                        ),
                }
            )

            print()

            print(
                f"[{index:>2}/"
                f"{len(unresolved_makes)}] "
                f"{source_make}"
            )

            print(
                f"  Complaint aliases: "
                f"{alias_count}"
            )

            print(
                f"  vPIC models: "
                f"{model_count}"
            )

            if returned_make_names:

                print(
                    "  Returned make: "
                    + " | ".join(
                        returned_make_names
                    )
                )

            if example_models:

                print(
                    "  Example models: "
                    + " | ".join(
                        example_models[:5]
                    )
                )

        except Exception as exc:

            errors += 1

            output_rows.append(
                {
                    "source_make":
                        source_make,

                    "alias_count":
                        alias_count,

                    "status":
                        "ERROR",

                    "models_returned":
                        0,

                    "returned_make_ids":
                        "",

                    "returned_make_names":
                        "",

                    "example_models":
                        str(exc),
                }
            )

            print()

            print(
                f"[{index:>2}/"
                f"{len(unresolved_makes)}] "
                f"{source_make}"
            )

            print(
                f"  ERROR: {exc}"
            )

        time.sleep(
            REQUEST_DELAY_SECONDS
        )

    # ========================================================
    # Save evidence
    # ========================================================

    with OUTPUT_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "source_make",
                "alias_count",
                "status",
                "models_returned",
                "returned_make_ids",
                "returned_make_names",
                "example_models",
            ],
        )

        writer.writeheader()

        writer.writerows(
            output_rows
        )

    # ========================================================
    # Final summary
    # ========================================================

    print()

    print(
        "=" * 70
    )

    print(
        "AUTOPULSE — VPIC PROBE RESULTS"
    )

    print(
        "=" * 70
    )

    print(
        f"Makes probed: "
        f"{len(unresolved_makes):,}"
    )

    print(
        f"Makes with vPIC models: "
        f"{makes_with_models:,}"
    )

    print(
        f"Makes with no vPIC models: "
        f"{makes_without_models:,}"
    )

    print(
        f"Request errors: "
        f"{errors:,}"
    )

    print(
        f"Evidence written to: "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":

    main()