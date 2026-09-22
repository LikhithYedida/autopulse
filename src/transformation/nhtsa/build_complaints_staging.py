from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zipfile import ZipFile

import pyarrow as pa
import pyarrow.parquet as pq

from src.ingestion.nhtsa.schema import (
    EXPECTED_COMPLAINT_COLUMN_COUNT,
    NHTSA_COMPLAINT_COLUMNS,
)


# ============================================================
# AutoPulse AI
# NHTSA Vehicle Complaint Staging Builder
#
# Purpose:
# - Read the immutable NHTSA bulk complaint archive
# - Keep vehicle complaints only (PROD_TYPE = V)
# - Apply typed transformations
# - Remove unnecessary personal / identifying fields
# - Preserve complaint and component grain
# - Write analytics-ready Parquet
# ============================================================


SOURCE_ZIP_PATH = Path(
    "data/raw/nhtsa/complaints/"
    "COMPLAINTS_RECEIVED_2025-2026.zip"
)

OUTPUT_DIR = Path(
    "data/staging/nhtsa/complaints"
)

OUTPUT_PARQUET_PATH = (
    OUTPUT_DIR
    / "nhtsa_vehicle_complaints_2025_2026.parquet"
)

OUTPUT_METADATA_PATH = (
    OUTPUT_DIR
    / "nhtsa_vehicle_complaints_2025_2026.metadata.json"
)


BATCH_SIZE = 25_000

UNKNOWN_MODEL_YEAR = "9999"


# ============================================================
# Explicit staging schema
# ============================================================

STAGING_SCHEMA = pa.schema(
    [
        (
            "source_line_number",
            pa.int64(),
        ),
        (
            "cmpl_id",
            pa.string(),
        ),
        (
            "odi_number",
            pa.string(),
        ),
        (
            "manufacturer_name",
            pa.string(),
        ),
        (
            "make",
            pa.string(),
        ),
        (
            "model",
            pa.string(),
        ),
        (
            "model_year",
            pa.int16(),
        ),
        (
            "model_year_unknown",
            pa.bool_(),
        ),
        (
            "crash_flag",
            pa.bool_(),
        ),
        (
            "incident_date",
            pa.date32(),
        ),
        (
            "fire_flag",
            pa.bool_(),
        ),
        (
            "injuries",
            pa.int32(),
        ),
        (
            "deaths",
            pa.int32(),
        ),
        (
            "component_description",
            pa.string(),
        ),
        (
            "date_added_to_file",
            pa.date32(),
        ),
        (
            "complaint_received_date",
            pa.date32(),
        ),
        (
            "mileage_at_failure",
            pa.int64(),
        ),
        (
            "occurrence_count",
            pa.int32(),
        ),
        (
            "complaint_description",
            pa.string(),
        ),
        (
            "complaint_type",
            pa.string(),
        ),
        (
            "police_report_flag",
            pa.bool_(),
        ),
        (
            "purchase_date",
            pa.date32(),
        ),
        (
            "original_owner_flag",
            pa.bool_(),
        ),
        (
            "anti_lock_brakes_flag",
            pa.bool_(),
        ),
        (
            "cruise_control_flag",
            pa.bool_(),
        ),
        (
            "number_of_cylinders",
            pa.int32(),
        ),
        (
            "drive_train",
            pa.string(),
        ),
        (
            "fuel_system",
            pa.string(),
        ),
        (
            "fuel_type",
            pa.string(),
        ),
        (
            "transmission_type",
            pa.string(),
        ),
        (
            "vehicle_speed",
            pa.int32(),
        ),
        (
            "medical_attention_flag",
            pa.bool_(),
        ),
        (
            "vehicle_towed_flag",
            pa.bool_(),
        ),
        (
            "incident_state",
            pa.string(),
        ),
    ]
)


# ============================================================
# Utility functions
# ============================================================

def normalize(
    value: str,
) -> str:
    """
    Strip leading and trailing whitespace.
    """

    return value.strip()


def nullable_string(
    value: str,
) -> str | None:
    """
    Convert blank source strings to None.
    """

    cleaned = normalize(value)

    if cleaned == "":
        return None

    return cleaned


def parse_boolean(
    value: str,
) -> bool | None:
    """
    Convert NHTSA Y/N flags into true boolean values.
    """

    cleaned = normalize(
        value
    ).upper()

    if cleaned == "Y":
        return True

    if cleaned == "N":
        return False

    return None


def parse_integer(
    value: str,
) -> int | None:
    """
    Convert numeric source fields to integers.
    """

    cleaned = normalize(value)

    if cleaned == "":
        return None

    try:
        return int(cleaned)

    except ValueError:
        return None


def parse_date(
    value: str,
    field_name: str,
    invalid_date_counts: Counter,
) -> date | None:
    """
    Convert NHTSA YYYYMMDD dates to Python date objects.

    Invalid non-empty values are counted rather than
    silently discarded.
    """

    cleaned = normalize(value)

    if cleaned == "":
        return None

    if cleaned in {
        "0",
        "00000000",
    }:
        return None

    try:
        return datetime.strptime(
            cleaned,
            "%Y%m%d",
        ).date()

    except ValueError:

        invalid_date_counts[
            f"{field_name}:{cleaned}"
        ] += 1

        return None


def parse_model_year(
    value: str,
) -> tuple[int | None, bool]:
    """
    NHTSA uses 9999 to represent unknown / N/A.

    Return:
        model_year
        model_year_unknown
    """

    cleaned = normalize(value)

    if cleaned == UNKNOWN_MODEL_YEAR:
        return None, True

    try:
        return int(cleaned), False

    except ValueError:
        return None, False


# ============================================================
# Record transformation
# ============================================================

def transform_vehicle_record(
    record: dict[str, str],
    line_number: int,
    invalid_date_counts: Counter,
) -> dict:
    """
    Convert one raw NHTSA vehicle row into the
    analytics-safe AutoPulse staging structure.

    Intentionally excluded from staging:
    - consumer city
    - consumer state
    - VIN
    - dealer contact details
    - vehicle operator name

    These fields are not required for the analytical
    use cases currently defined for AutoPulse.
    """

    (
        model_year,
        model_year_unknown,
    ) = parse_model_year(
        record["YEARTXT"]
    )

    return {
        "source_line_number": (
            line_number
        ),

        "cmpl_id": (
            nullable_string(
                record["CMPLID"]
            )
        ),

        "odi_number": (
            nullable_string(
                record["ODINO"]
            )
        ),

        "manufacturer_name": (
            nullable_string(
                record["MFR_NAME"]
            )
        ),

        "make": (
            nullable_string(
                record["MAKETXT"]
            )
        ),

        "model": (
            nullable_string(
                record["MODELTXT"]
            )
        ),

        "model_year": (
            model_year
        ),

        "model_year_unknown": (
            model_year_unknown
        ),

        "crash_flag": (
            parse_boolean(
                record["CRASH"]
            )
        ),

        "incident_date": (
            parse_date(
                record["FAILDATE"],
                "FAILDATE",
                invalid_date_counts,
            )
        ),

        "fire_flag": (
            parse_boolean(
                record["FIRE"]
            )
        ),

        "injuries": (
            parse_integer(
                record["INJURED"]
            )
        ),

        "deaths": (
            parse_integer(
                record["DEATHS"]
            )
        ),

        "component_description": (
            nullable_string(
                record["COMPDESC"]
            )
        ),

        "date_added_to_file": (
            parse_date(
                record["DATEA"],
                "DATEA",
                invalid_date_counts,
            )
        ),

        "complaint_received_date": (
            parse_date(
                record["LDATE"],
                "LDATE",
                invalid_date_counts,
            )
        ),

        "mileage_at_failure": (
            parse_integer(
                record["MILES"]
            )
        ),

        "occurrence_count": (
            parse_integer(
                record["OCCURENCES"]
            )
        ),

        "complaint_description": (
            nullable_string(
                record["CDESCR"]
            )
        ),

        "complaint_type": (
            nullable_string(
                record["CMPL_TYPE"]
            )
        ),

        "police_report_flag": (
            parse_boolean(
                record["POLICE_RPT_YN"]
            )
        ),

        "purchase_date": (
            parse_date(
                record["PURCH_DT"],
                "PURCH_DT",
                invalid_date_counts,
            )
        ),

        "original_owner_flag": (
            parse_boolean(
                record["ORIG_OWNER_YN"]
            )
        ),

        "anti_lock_brakes_flag": (
            parse_boolean(
                record["ANTI_BRAKES_YN"]
            )
        ),

        "cruise_control_flag": (
            parse_boolean(
                record["CRUISE_CONT_YN"]
            )
        ),

        "number_of_cylinders": (
            parse_integer(
                record["NUM_CYLS"]
            )
        ),

        "drive_train": (
            nullable_string(
                record["DRIVE_TRAIN"]
            )
        ),

        "fuel_system": (
            nullable_string(
                record["FUEL_SYS"]
            )
        ),

        "fuel_type": (
            nullable_string(
                record["FUEL_TYPE"]
            )
        ),

        "transmission_type": (
            nullable_string(
                record["TRANS_TYPE"]
            )
        ),

        "vehicle_speed": (
            parse_integer(
                record["VEH_SPEED"]
            )
        ),

        "medical_attention_flag": (
            parse_boolean(
                record["MEDICAL_ATTN"]
            )
        ),

        "vehicle_towed_flag": (
            parse_boolean(
                record[
                    "VEHICLES_TOWED_YN"
                ]
            )
        ),

        "incident_state": (
            nullable_string(
                record[
                    "STATE_OF_INCIDENT"
                ]
            )
        ),
    }


# ============================================================
# Parquet writing
# ============================================================

def write_batch(
    writer: pq.ParquetWriter,
    records: list[dict],
) -> None:
    """
    Convert a batch of Python records to Arrow
    and append it to the Parquet dataset.
    """

    if not records:
        return

    table = pa.Table.from_pylist(
        records,
        schema=STAGING_SCHEMA,
    )

    writer.write_table(
        table
    )


# ============================================================
# Staging build
# ============================================================

def build_staging_dataset() -> dict:
    """
    Stream raw NHTSA records directly from the ZIP,
    transform vehicle records, and write Parquet
    incrementally.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if OUTPUT_PARQUET_PATH.exists():
        OUTPUT_PARQUET_PATH.unlink()

    total_source_rows = 0
    vehicle_rows = 0
    non_vehicle_rows = 0
    malformed_rows = 0

    unknown_model_year_rows = 0

    unique_odi_numbers = set()
    unique_cmpl_ids = set()

    invalid_date_counts = Counter()

    records_batch = []

    column_index = {
        column: index
        for index, column
        in enumerate(
            NHTSA_COMPLAINT_COLUMNS
        )
    }

    print("=" * 70)
    print("AUTOPULSE — BUILD NHTSA VEHICLE STAGING DATASET")
    print("=" * 70)

    print(
        f"Source: {SOURCE_ZIP_PATH}"
    )

    print(
        f"Output: {OUTPUT_PARQUET_PATH}"
    )

    print(
        f"Batch size: {BATCH_SIZE:,}"
    )

    print(
        "Privacy rule: VIN, consumer location, dealer contact "
        "details and vehicle operator are excluded."
    )

    print()

    with ZipFile(
        SOURCE_ZIP_PATH
    ) as archive:

        files = archive.namelist()

        if len(files) != 1:
            raise ValueError(
                "Expected exactly one file inside "
                f"source archive, found {len(files)}."
            )

        source_file = files[0]

        writer = pq.ParquetWriter(
            where=str(
                OUTPUT_PARQUET_PATH
            ),
            schema=STAGING_SCHEMA,
            compression="zstd",
            use_dictionary=True,
        )

        try:

            with archive.open(
                source_file
            ) as raw_file:

                for (
                    line_number,
                    raw_line,
                ) in enumerate(
                    raw_file,
                    start=1,
                ):

                    total_source_rows += 1

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
                        continue

                    record = {
                        column: values[index]
                        for (
                            column,
                            index,
                        ) in column_index.items()
                    }

                    product_type = normalize(
                        record["PROD_TYPE"]
                    ).upper()

                    if product_type != "V":

                        non_vehicle_rows += 1
                        continue

                    vehicle_rows += 1

                    if (
                        normalize(
                            record["YEARTXT"]
                        )
                        == UNKNOWN_MODEL_YEAR
                    ):
                        unknown_model_year_rows += 1

                    cmpl_id = normalize(
                        record["CMPLID"]
                    )

                    odi_number = normalize(
                        record["ODINO"]
                    )

                    if cmpl_id:
                        unique_cmpl_ids.add(
                            cmpl_id
                        )

                    if odi_number:
                        unique_odi_numbers.add(
                            odi_number
                        )

                    transformed = (
                        transform_vehicle_record(
                            record=record,
                            line_number=(
                                line_number
                            ),
                            invalid_date_counts=(
                                invalid_date_counts
                            ),
                        )
                    )

                    records_batch.append(
                        transformed
                    )

                    if (
                        len(records_batch)
                        >= BATCH_SIZE
                    ):

                        write_batch(
                            writer,
                            records_batch,
                        )

                        records_batch.clear()

                        print(
                            f"Written "
                            f"{vehicle_rows:,} "
                            f"vehicle rows..."
                        )

            # Final partial batch
            write_batch(
                writer,
                records_batch,
            )

            records_batch.clear()

        finally:

            writer.close()

    output_size_bytes = (
        OUTPUT_PARQUET_PATH
        .stat()
        .st_size
    )

    metadata = {
        "source_system": "NHTSA",

        "dataset": (
            "consumer_complaints"
        ),

        "staging_dataset": (
            "nhtsa_vehicle_complaints"
        ),

        "built_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),

        "source_archive": (
            str(SOURCE_ZIP_PATH)
        ),

        "source_rows": (
            total_source_rows
        ),

        "vehicle_rows_written": (
            vehicle_rows
        ),

        "non_vehicle_rows_excluded": (
            non_vehicle_rows
        ),

        "malformed_rows_excluded": (
            malformed_rows
        ),

        "unique_cmpl_ids": (
            len(
                unique_cmpl_ids
            )
        ),

        "unique_odi_complaints": (
            len(
                unique_odi_numbers
            )
        ),

        "unknown_model_year_rows": (
            unknown_model_year_rows
        ),

        "invalid_date_values": (
            dict(
                invalid_date_counts
            )
        ),

        "output_file": (
            str(
                OUTPUT_PARQUET_PATH
            )
        ),

        "output_size_bytes": (
            output_size_bytes
        ),

        "output_size_mb": round(
            output_size_bytes
            / 1024
            / 1024,
            2,
        ),

        "compression": "zstd",

        "batch_size": (
            BATCH_SIZE
        ),

        "excluded_sensitive_fields": [
            "CITY",
            "STATE",
            "VIN",
            "DEALER_NAME",
            "DEALER_TEL",
            "DEALER_CITY",
            "DEALER_STATE",
            "DEALER_ZIP",
            "VEHICLE_OPERATOR",
        ],
    }

    return metadata


# ============================================================
# Metadata
# ============================================================

def save_metadata(
    metadata: dict,
) -> None:
    """
    Persist transformation metadata.
    """

    with open(
        OUTPUT_METADATA_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metadata,
            file,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# Main
# ============================================================

def main():

    metadata = (
        build_staging_dataset()
    )

    save_metadata(
        metadata
    )

    print("\n" + "=" * 70)
    print("STAGING BUILD COMPLETE")
    print("=" * 70)

    print(
        f"Source rows: "
        f"{metadata['source_rows']:,}"
    )

    print(
        f"Vehicle rows written: "
        f"{metadata['vehicle_rows_written']:,}"
    )

    print(
        f"Non-vehicle rows excluded: "
        f"{metadata['non_vehicle_rows_excluded']:,}"
    )

    print(
        f"Malformed rows excluded: "
        f"{metadata['malformed_rows_excluded']:,}"
    )

    print(
        f"Unique CMPLID rows: "
        f"{metadata['unique_cmpl_ids']:,}"
    )

    print(
        f"Unique ODI complaints: "
        f"{metadata['unique_odi_complaints']:,}"
    )

    print(
        f"Unknown model years: "
        f"{metadata['unknown_model_year_rows']:,}"
    )

    print(
        f"Invalid date values found: "
        f"{sum(metadata['invalid_date_values'].values()):,}"
    )

    print(
        f"Parquet size: "
        f"{metadata['output_size_mb']:.2f} MB"
    )

    print(
        f"\nParquet: "
        f"{OUTPUT_PARQUET_PATH}"
    )

    print(
        f"Metadata: "
        f"{OUTPUT_METADATA_PATH}"
    )


if __name__ == "__main__":
    main()