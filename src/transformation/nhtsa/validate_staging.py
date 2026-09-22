from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq


# ============================================================
# AutoPulse AI
# NHTSA Vehicle Complaint Staging Validation
# ============================================================

PARQUET_PATH = Path(
    "data/staging/nhtsa/complaints/"
    "nhtsa_vehicle_complaints_2025_2026.parquet"
)

METADATA_PATH = Path(
    "data/staging/nhtsa/complaints/"
    "nhtsa_vehicle_complaints_2025_2026.metadata.json"
)


EXPECTED_COLUMNS = [
    "source_line_number",
    "cmpl_id",
    "odi_number",
    "manufacturer_name",
    "make",
    "model",
    "model_year",
    "model_year_unknown",
    "crash_flag",
    "incident_date",
    "fire_flag",
    "injuries",
    "deaths",
    "component_description",
    "date_added_to_file",
    "complaint_received_date",
    "mileage_at_failure",
    "occurrence_count",
    "complaint_description",
    "complaint_type",
    "police_report_flag",
    "purchase_date",
    "original_owner_flag",
    "anti_lock_brakes_flag",
    "cruise_control_flag",
    "number_of_cylinders",
    "drive_train",
    "fuel_system",
    "fuel_type",
    "transmission_type",
    "vehicle_speed",
    "medical_attention_flag",
    "vehicle_towed_flag",
    "incident_state",
]


SENSITIVE_FIELDS_THAT_MUST_NOT_EXIST = {
    "VIN",
    "vin",
    "CITY",
    "city",
    "STATE",
    "consumer_state",
    "DEALER_NAME",
    "DEALER_TEL",
    "DEALER_CITY",
    "DEALER_STATE",
    "DEALER_ZIP",
    "VEHICLE_OPERATOR",
    "vehicle_operator",
}


MIN_MODEL_YEAR = 1900

MAX_MODEL_YEAR = (
    datetime.now(timezone.utc).year + 1
)


def count_true(column) -> int:
    """
    Count True values in a nullable boolean Arrow column.
    """

    result = pc.sum(
        pc.cast(
            pc.fill_null(
                column,
                False,
            ),
            "int64",
        )
    )

    return int(
        result.as_py() or 0
    )


def validate_staging() -> list[str]:
    """
    Validate staging schema, counts, identities,
    model-year handling and privacy rules.

    Returns a list of validation failures.
    """

    failures = []

    print("=" * 70)
    print("AUTOPULSE — VALIDATE NHTSA VEHICLE STAGING")
    print("=" * 70)

    # --------------------------------------------------------
    # File existence
    # --------------------------------------------------------

    if not PARQUET_PATH.exists():
        raise FileNotFoundError(
            f"Parquet file not found: {PARQUET_PATH}"
        )

    if not METADATA_PATH.exists():
        raise FileNotFoundError(
            f"Metadata file not found: {METADATA_PATH}"
        )

    # --------------------------------------------------------
    # Read metadata
    # --------------------------------------------------------

    with open(
        METADATA_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        build_metadata = json.load(file)

    parquet_file = pq.ParquetFile(
        PARQUET_PATH
    )

    parquet_row_count = (
        parquet_file.metadata.num_rows
    )

    parquet_column_count = (
        parquet_file.metadata.num_columns
    )

    # --------------------------------------------------------
    # Schema validation
    # --------------------------------------------------------

    actual_columns = (
        parquet_file.schema_arrow.names
    )

    print(
        f"Rows in Parquet: "
        f"{parquet_row_count:,}"
    )

    print(
        f"Columns in Parquet: "
        f"{parquet_column_count:,}"
    )

    if actual_columns != EXPECTED_COLUMNS:

        failures.append(
            "Parquet column schema does not "
            "match expected staging schema."
        )

    # --------------------------------------------------------
    # Compare build metadata to actual file
    # --------------------------------------------------------

    expected_rows = (
        build_metadata[
            "vehicle_rows_written"
        ]
    )

    if parquet_row_count != expected_rows:

        failures.append(
            "Parquet row count does not match "
            "staging build metadata."
        )

    # --------------------------------------------------------
    # Privacy / governance validation
    # --------------------------------------------------------

    sensitive_fields_found = (
        set(actual_columns)
        & SENSITIVE_FIELDS_THAT_MUST_NOT_EXIST
    )

    if sensitive_fields_found:

        failures.append(
            "Sensitive fields found in curated dataset: "
            + ", ".join(
                sorted(
                    sensitive_fields_found
                )
            )
        )

    # --------------------------------------------------------
    # Load selected columns for semantic validation
    # --------------------------------------------------------

    table = pq.read_table(
        PARQUET_PATH,
        columns=[
            "cmpl_id",
            "odi_number",
            "make",
            "model",
            "model_year",
            "model_year_unknown",
            "injuries",
            "deaths",
        ],
    )

    # --------------------------------------------------------
    # CMPLID validation
    # --------------------------------------------------------

    cmpl_ids = table[
        "cmpl_id"
    ]

    null_cmpl_ids = (
        cmpl_ids.null_count
    )

    unique_cmpl_ids = pc.count_distinct(
        cmpl_ids
    ).as_py()

    duplicate_cmpl_ids = (
        parquet_row_count
        - unique_cmpl_ids
    )

    print(
        f"Null CMPLID values: "
        f"{null_cmpl_ids:,}"
    )

    print(
        f"Unique CMPLID values: "
        f"{unique_cmpl_ids:,}"
    )

    print(
        f"Duplicate CMPLID values: "
        f"{duplicate_cmpl_ids:,}"
    )

    if null_cmpl_ids != 0:

        failures.append(
            "CMPLID contains null values."
        )

    if duplicate_cmpl_ids != 0:

        failures.append(
            "CMPLID is not unique."
        )

    # --------------------------------------------------------
    # ODI complaint-grain validation
    # --------------------------------------------------------

    odi_numbers = table[
        "odi_number"
    ]

    null_odi_numbers = (
        odi_numbers.null_count
    )

    unique_odi_numbers = pc.count_distinct(
        odi_numbers
    ).as_py()

    print(
        f"Null ODI numbers: "
        f"{null_odi_numbers:,}"
    )

    print(
        f"Unique ODI complaints: "
        f"{unique_odi_numbers:,}"
    )

    expected_unique_odi = (
        build_metadata[
            "unique_odi_complaints"
        ]
    )

    if (
        unique_odi_numbers
        != expected_unique_odi
    ):

        failures.append(
            "Unique ODI count does not match "
            "build metadata."
        )

    # --------------------------------------------------------
    # Make / model validation
    # --------------------------------------------------------

    null_makes = (
        table["make"].null_count
    )

    null_models = (
        table["model"].null_count
    )

    print(
        f"Null makes: "
        f"{null_makes:,}"
    )

    print(
        f"Null models: "
        f"{null_models:,}"
    )

    if null_makes != 0:

        failures.append(
            "Make contains null values."
        )

    if null_models != 0:

        failures.append(
            "Model contains null values."
        )

    # --------------------------------------------------------
    # Model-year validation
    # --------------------------------------------------------

    model_years = table[
        "model_year"
    ]

    unknown_flags = table[
        "model_year_unknown"
    ]

    unknown_count = count_true(
        unknown_flags
    )

    null_model_year_count = (
        model_years.null_count
    )

    print(
        f"Unknown model-year flags: "
        f"{unknown_count:,}"
    )

    print(
        f"Null model years: "
        f"{null_model_year_count:,}"
    )

    if (
        unknown_count
        != null_model_year_count
    ):

        failures.append(
            "Unknown-year flag count does not match "
            "null model-year count."
        )

    expected_unknown_years = (
        build_metadata[
            "unknown_model_year_rows"
        ]
    )

    if (
        unknown_count
        != expected_unknown_years
    ):

        failures.append(
            "Unknown model-year count does not "
            "match build metadata."
        )

    valid_years = pc.drop_null(
        model_years
    )

    if len(valid_years) > 0:

        min_year = pc.min(
            valid_years
        ).as_py()

        max_year = pc.max(
            valid_years
        ).as_py()

    else:

        min_year = None
        max_year = None

    print(
        f"Known model-year range: "
        f"{min_year} to {max_year}"
    )

    if (
        min_year is not None
        and min_year < MIN_MODEL_YEAR
    ):

        failures.append(
            "Model year below expected minimum."
        )

    if (
        max_year is not None
        and max_year > MAX_MODEL_YEAR
    ):

        failures.append(
            "Model year above expected maximum."
        )

    # --------------------------------------------------------
    # Injury / fatality validation
    # --------------------------------------------------------

    injuries = table[
        "injuries"
    ]

    deaths = table[
        "deaths"
    ]

    negative_injuries = count_true(
        pc.less(
            injuries,
            0,
        )
    )

    negative_deaths = count_true(
        pc.less(
            deaths,
            0,
        )
    )

    print(
        f"Negative injury rows: "
        f"{negative_injuries:,}"
    )

    print(
        f"Negative death rows: "
        f"{negative_deaths:,}"
    )

    if negative_injuries != 0:

        failures.append(
            "Negative injury values found."
        )

    if negative_deaths != 0:

        failures.append(
            "Negative death values found."
        )

    # --------------------------------------------------------
    # Privacy result
    # --------------------------------------------------------

    print(
        f"Sensitive staging fields found: "
        f"{len(sensitive_fields_found)}"
    )

    return failures


def main():

    failures = validate_staging()

    print("\n" + "=" * 70)

    if failures:

        print("STAGING VALIDATION FAILED")
        print("=" * 70)

        for failure in failures:

            print(
                f"[FAIL] {failure}"
            )

        raise SystemExit(1)

    print("STAGING VALIDATION PASSED")
    print("=" * 70)

    print(
        "All structural, identity, semantic "
        "and privacy checks passed."
    )


if __name__ == "__main__":
    main()