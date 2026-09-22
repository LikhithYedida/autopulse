from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from src.ingestion.nhtsa.schema import (
    EXPECTED_COMPLAINT_COLUMN_COUNT,
    NHTSA_COMPLAINT_COLUMNS,
)


# ============================================================
# AutoPulse AI
# NHTSA Complaint Raw Data Profiler
# ============================================================

ZIP_PATH = Path(
    "data/raw/nhtsa/complaints/"
    "COMPLAINTS_RECEIVED_2025-2026.zip"
)

PROFILE_OUTPUT_PATH = Path(
    "data/raw/nhtsa/complaints/"
    "COMPLAINTS_RECEIVED_2025-2026.profile.json"
)


KEY_FIELDS = [
    "CMPLID",
    "ODINO",
    "MFR_NAME",
    "MAKETXT",
    "MODELTXT",
    "YEARTXT",
    "CRASH",
    "FAILDATE",
    "FIRE",
    "INJURED",
    "DEATHS",
    "COMPDESC",
    "VIN",
    "DATEA",
    "MILES",
    "CDESCR",
]


def normalize(value: str) -> str:
    """
    Trim whitespace while preserving source values.
    """

    return value.strip()


def is_missing(value: str) -> bool:
    """
    Determine whether a raw NHTSA field is effectively missing.
    """

    cleaned = normalize(value)

    return cleaned == ""


def profile_complaints() -> dict:
    """
    Stream the NHTSA complaint file directly from the ZIP
    and create a raw-data quality profile.

    The file is not extracted to disk.
    """

    total_rows = 0
    valid_rows = 0
    malformed_rows = 0

    crash_yes = 0
    fire_yes = 0

    total_injuries = 0
    total_deaths = 0

    makes = Counter()
    models = Counter()
    years = Counter()
    manufacturers = Counter()
    components = Counter()

    missing_counts = Counter()

    malformed_examples = []

    column_index = {
        column: index
        for index, column in enumerate(
            NHTSA_COMPLAINT_COLUMNS
        )
    }

    print("=" * 70)
    print("AUTOPULSE — NHTSA COMPLAINT DATA PROFILE")
    print("=" * 70)

    print(f"Archive: {ZIP_PATH}")
    print(
        f"Expected columns: "
        f"{EXPECTED_COMPLAINT_COLUMN_COUNT}"
    )

    with ZipFile(ZIP_PATH) as archive:

        files = archive.namelist()

        if len(files) != 1:
            raise ValueError(
                "Expected exactly one file inside "
                f"the NHTSA archive but found {len(files)}."
            )

        internal_file = files[0]

        print(f"Internal file: {internal_file}")
        print("\nProfiling records...\n")

        with archive.open(internal_file) as raw_file:

            for line_number, raw_line in enumerate(
                raw_file,
                start=1,
            ):
                total_rows += 1

                line = raw_line.decode(
                    "latin-1",
                    errors="replace",
                )

                values = line.rstrip(
                    "\r\n"
                ).split("\t")

                if (
                    len(values)
                    != EXPECTED_COMPLAINT_COLUMN_COUNT
                ):
                    malformed_rows += 1

                    if len(malformed_examples) < 10:
                        malformed_examples.append(
                            {
                                "line_number": line_number,
                                "column_count": len(values),
                                "preview": line[:300],
                            }
                        )

                    continue

                valid_rows += 1

                record = {
                    column: values[index]
                    for column, index
                    in column_index.items()
                }

                # ------------------------------------------------
                # Missingness
                # ------------------------------------------------

                for field in KEY_FIELDS:

                    if is_missing(record[field]):
                        missing_counts[field] += 1

                # ------------------------------------------------
                # Vehicle identity
                # ------------------------------------------------

                make = normalize(
                    record["MAKETXT"]
                )

                model = normalize(
                    record["MODELTXT"]
                )

                year = normalize(
                    record["YEARTXT"]
                )

                manufacturer = normalize(
                    record["MFR_NAME"]
                )

                component = normalize(
                    record["COMPDESC"]
                )

                if make:
                    makes[make] += 1

                if model:
                    models[model] += 1

                if year:
                    years[year] += 1

                if manufacturer:
                    manufacturers[manufacturer] += 1

                if component:
                    components[component] += 1

                # ------------------------------------------------
                # Safety severity signals
                # ------------------------------------------------

                crash = normalize(
                    record["CRASH"]
                ).upper()

                fire = normalize(
                    record["FIRE"]
                ).upper()

                if crash == "Y":
                    crash_yes += 1

                if fire == "Y":
                    fire_yes += 1

                injuries = normalize(
                    record["INJURED"]
                )

                deaths = normalize(
                    record["DEATHS"]
                )

                if injuries.isdigit():
                    total_injuries += int(injuries)

                if deaths.isdigit():
                    total_deaths += int(deaths)

                # Progress indicator
                if total_rows % 100000 == 0:
                    print(
                        f"Processed "
                        f"{total_rows:,} records..."
                    )

    valid_pct = (
        valid_rows / total_rows * 100
        if total_rows
        else 0
    )

    profile = {
        "source": "NHTSA",
        "dataset": "consumer_complaints",
        "archive": str(ZIP_PATH),
        "expected_column_count": (
            EXPECTED_COMPLAINT_COLUMN_COUNT
        ),
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "malformed_rows": malformed_rows,
        "valid_row_pct": round(
            valid_pct,
            4,
        ),
        "unique_makes": len(makes),
        "unique_models": len(models),
        "unique_manufacturers": len(manufacturers),
        "year_min": (
            min(years.keys())
            if years
            else None
        ),
        "year_max": (
            max(years.keys())
            if years
            else None
        ),
        "crash_complaints": crash_yes,
        "fire_complaints": fire_yes,
        "total_reported_injuries": (
            total_injuries
        ),
        "total_reported_deaths": (
            total_deaths
        ),
        "missing_key_fields": dict(
            missing_counts
        ),
        "top_20_makes": (
            makes.most_common(20)
        ),
        "top_20_models": (
            models.most_common(20)
        ),
        "top_20_components": (
            components.most_common(20)
        ),
        "malformed_examples": (
            malformed_examples
        ),
    }

    return profile


def save_profile(
    profile: dict,
) -> None:
    """
    Save the profiling results as JSON.
    """

    PROFILE_OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        PROFILE_OUTPUT_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            profile,
            file,
            indent=2,
            ensure_ascii=False,
        )


def main():
    profile = profile_complaints()

    save_profile(profile)

    print("\n" + "=" * 70)
    print("PROFILE COMPLETE")
    print("=" * 70)

    print(
        f"Total rows: "
        f"{profile['total_rows']:,}"
    )

    print(
        f"Valid rows: "
        f"{profile['valid_rows']:,}"
    )

    print(
        f"Malformed rows: "
        f"{profile['malformed_rows']:,}"
    )

    print(
        f"Valid row rate: "
        f"{profile['valid_row_pct']:.4f}%"
    )

    print(
        f"Unique makes: "
        f"{profile['unique_makes']:,}"
    )

    print(
        f"Unique models: "
        f"{profile['unique_models']:,}"
    )

    print(
        f"Model year range: "
        f"{profile['year_min']} "
        f"to "
        f"{profile['year_max']}"
    )

    print(
        f"Crash complaints: "
        f"{profile['crash_complaints']:,}"
    )

    print(
        f"Fire complaints: "
        f"{profile['fire_complaints']:,}"
    )

    print(
        f"Reported injuries: "
        f"{profile['total_reported_injuries']:,}"
    )

    print(
        f"Reported deaths: "
        f"{profile['total_reported_deaths']:,}"
    )

    print(
        f"\nProfile saved to: "
        f"{PROFILE_OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()