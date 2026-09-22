from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

from src.ingestion.nhtsa.schema import (
    EXPECTED_COMPLAINT_COLUMN_COUNT,
    NHTSA_COMPLAINT_COLUMNS,
)


# ============================================================
# AutoPulse AI
# NHTSA Complaint Semantic Data Quality Validation
# ============================================================

ZIP_PATH = Path(
    "data/raw/nhtsa/complaints/"
    "COMPLAINTS_RECEIVED_2025-2026.zip"
)

OUTPUT_PATH = Path(
    "data/raw/nhtsa/complaints/"
    "COMPLAINTS_RECEIVED_2025-2026.quality.json"
)


CURRENT_YEAR = datetime.now(timezone.utc).year

MIN_REASONABLE_MODEL_YEAR = 1900
MAX_REASONABLE_MODEL_YEAR = CURRENT_YEAR + 1

# NHTSA-defined sentinel:
# YEARTXT = 9999 means UNKNOWN / N/A.
UNKNOWN_MODEL_YEAR = "9999"


VALID_YN_VALUES = {
    "",
    "Y",
    "N",
}


VALID_PRODUCT_TYPES = {
    "V",  # Vehicle
    "T",  # Tire
    "E",  # Equipment
    "C",  # Child restraint
}


YN_FIELDS = [
    "CRASH",
    "FIRE",
    "POLICE_RPT_YN",
    "ORIG_OWNER_YN",
    "ANTI_BRAKES_YN",
    "CRUISE_CONT_YN",
    "ORIG_EQUIP_YN",
    "REPAIRED_YN",
    "MEDICAL_ATTN",
    "VEHICLES_TOWED_YN",
]


def normalize(value: str) -> str:
    return value.strip()


def parse_integer(value: str):
    value = normalize(value)

    if value == "":
        return None

    try:
        return int(value)
    except ValueError:
        return None


def validate_complaints() -> dict:

    total_rows = 0
    structurally_valid_rows = 0

    missing_cmplid_rows = 0
    missing_odi_rows = 0
    missing_make_rows = 0
    missing_model_rows = 0

    duplicate_cmplid_rows = 0

    unknown_model_year_rows = 0
    invalid_model_year_rows = 0

    negative_injury_rows = 0
    negative_death_rows = 0

    invalid_yn_rows = 0
    invalid_product_type_rows = 0

    vehicle_rows = 0
    tire_rows = 0
    equipment_rows = 0
    child_restraint_rows = 0

    cmplid_seen = set()

    odi_counts = Counter()
    product_type_counts = Counter()

    invalid_model_year_values = Counter()
    invalid_yn_values = Counter()

    invalid_examples = []

    column_index = {
        column: index
        for index, column
        in enumerate(NHTSA_COMPLAINT_COLUMNS)
    }

    print("=" * 70)
    print("AUTOPULSE — CORRECTED SEMANTIC DATA QUALITY VALIDATION")
    print("=" * 70)

    print(f"Archive: {ZIP_PATH}")

    print(
        f"Valid known model-year range: "
        f"{MIN_REASONABLE_MODEL_YEAR} "
        f"to {MAX_REASONABLE_MODEL_YEAR}"
    )

    print(
        f"NHTSA unknown-year sentinel: "
        f"{UNKNOWN_MODEL_YEAR}"
    )

    with ZipFile(ZIP_PATH) as archive:

        files = archive.namelist()

        if len(files) != 1:
            raise ValueError(
                "Expected exactly one source file "
                f"inside archive, found {len(files)}."
            )

        internal_file = files[0]

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
                    continue

                structurally_valid_rows += 1

                record = {
                    column: values[index]
                    for column, index
                    in column_index.items()
                }

                row_issues = []

                # =================================================
                # Unique row identity
                # =================================================

                cmplid = normalize(
                    record["CMPLID"]
                )

                if not cmplid:

                    missing_cmplid_rows += 1

                    row_issues.append(
                        "missing_cmplid"
                    )

                elif cmplid in cmplid_seen:

                    duplicate_cmplid_rows += 1

                    row_issues.append(
                        "duplicate_cmplid"
                    )

                else:

                    cmplid_seen.add(
                        cmplid
                    )

                # =================================================
                # ODI complaint/reference identity
                #
                # ODINO is NOT required to be unique.
                # NHTSA allows the same ODINO across components.
                # =================================================

                odi_number = normalize(
                    record["ODINO"]
                )

                if not odi_number:

                    missing_odi_rows += 1

                    row_issues.append(
                        "missing_odi_number"
                    )

                else:

                    odi_counts[
                        odi_number
                    ] += 1

                # =================================================
                # Vehicle/product identity
                # =================================================

                make = normalize(
                    record["MAKETXT"]
                )

                model = normalize(
                    record["MODELTXT"]
                )

                if not make:

                    missing_make_rows += 1

                    row_issues.append(
                        "missing_make"
                    )

                if not model:

                    missing_model_rows += 1

                    row_issues.append(
                        "missing_model"
                    )

                # =================================================
                # Product type
                # =================================================

                product_type = normalize(
                    record["PROD_TYPE"]
                ).upper()

                product_type_counts[
                    product_type
                ] += 1

                if product_type == "V":

                    vehicle_rows += 1

                elif product_type == "T":

                    tire_rows += 1

                elif product_type == "E":

                    equipment_rows += 1

                elif product_type == "C":

                    child_restraint_rows += 1

                if (
                    product_type
                    not in VALID_PRODUCT_TYPES
                ):

                    invalid_product_type_rows += 1

                    row_issues.append(
                        "invalid_product_type"
                    )

                # =================================================
                # Model year
                # =================================================

                year_raw = normalize(
                    record["YEARTXT"]
                )

                if (
                    year_raw
                    == UNKNOWN_MODEL_YEAR
                ):

                    unknown_model_year_rows += 1

                else:

                    try:

                        model_year = int(
                            year_raw
                        )

                        if not (
                            MIN_REASONABLE_MODEL_YEAR
                            <= model_year
                            <= MAX_REASONABLE_MODEL_YEAR
                        ):
                            raise ValueError

                    except (
                        ValueError,
                        TypeError,
                    ):

                        invalid_model_year_rows += 1

                        invalid_model_year_values[
                            year_raw
                        ] += 1

                        row_issues.append(
                            "invalid_model_year"
                        )

                # =================================================
                # Injury / fatality validation
                # =================================================

                injuries = parse_integer(
                    record["INJURED"]
                )

                deaths = parse_integer(
                    record["DEATHS"]
                )

                if (
                    injuries is not None
                    and injuries < 0
                ):

                    negative_injury_rows += 1

                    row_issues.append(
                        "negative_injuries"
                    )

                if (
                    deaths is not None
                    and deaths < 0
                ):

                    negative_death_rows += 1

                    row_issues.append(
                        "negative_deaths"
                    )

                # =================================================
                # Y/N validation
                # =================================================

                row_has_invalid_yn = False

                for field in YN_FIELDS:

                    value = normalize(
                        record[field]
                    ).upper()

                    if (
                        value
                        not in VALID_YN_VALUES
                    ):

                        invalid_yn_values[
                            f"{field}:{value}"
                        ] += 1

                        row_has_invalid_yn = True

                if row_has_invalid_yn:

                    invalid_yn_rows += 1

                    row_issues.append(
                        "invalid_yes_no_value"
                    )

                # =================================================
                # Capture true quality issue examples
                # =================================================

                if (
                    row_issues
                    and len(invalid_examples) < 25
                ):

                    invalid_examples.append(
                        {
                            "line_number": line_number,
                            "cmplid": cmplid,
                            "odi_number": odi_number,
                            "make": make,
                            "model": model,
                            "model_year": year_raw,
                            "product_type": product_type,
                            "issues": row_issues,
                        }
                    )

                if total_rows % 100000 == 0:

                    print(
                        f"Validated "
                        f"{total_rows:,} rows..."
                    )

    # =========================================================
    # Complaint/reference grain analysis
    # =========================================================

    unique_odi_numbers = len(
        odi_counts
    )

    odi_numbers_with_multiple_rows = sum(
        1
        for count in odi_counts.values()
        if count > 1
    )

    additional_component_rows = sum(
        count - 1
        for count in odi_counts.values()
        if count > 1
    )

    report = {

        "source": "NHTSA",

        "dataset": (
            "consumer_complaints"
        ),

        "validated_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),

        "total_rows": total_rows,

        "structurally_valid_rows": (
            structurally_valid_rows
        ),

        "unique_cmplid_count": len(
            cmplid_seen
        ),

        "unique_odi_count": (
            unique_odi_numbers
        ),

        "odi_numbers_with_multiple_rows": (
            odi_numbers_with_multiple_rows
        ),

        "additional_component_rows": (
            additional_component_rows
        ),

        "model_year": {

            "unknown_9999_rows": (
                unknown_model_year_rows
            ),

            "truly_invalid_rows": (
                invalid_model_year_rows
            ),

            "invalid_values": (
                invalid_model_year_values
                .most_common(25)
            ),
        },

        "product_type_counts": dict(
            product_type_counts
        ),

        "vehicle_rows": vehicle_rows,

        "issues": {

            "missing_cmplid_rows": (
                missing_cmplid_rows
            ),

            "duplicate_cmplid_rows": (
                duplicate_cmplid_rows
            ),

            "missing_odi_rows": (
                missing_odi_rows
            ),

            "missing_make_rows": (
                missing_make_rows
            ),

            "missing_model_rows": (
                missing_model_rows
            ),

            "invalid_model_year_rows": (
                invalid_model_year_rows
            ),

            "invalid_product_type_rows": (
                invalid_product_type_rows
            ),

            "invalid_yn_rows": (
                invalid_yn_rows
            ),

            "negative_injury_rows": (
                negative_injury_rows
            ),

            "negative_death_rows": (
                negative_death_rows
            ),
        },

        "invalid_yn_values": (
            invalid_yn_values
            .most_common(25)
        ),

        "invalid_examples": (
            invalid_examples
        ),
    }

    return report


def save_report(
    report: dict,
) -> None:

    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            indent=2,
            ensure_ascii=False,
        )


def main():

    report = validate_complaints()

    save_report(
        report
    )

    issues = report[
        "issues"
    ]

    print("\n" + "=" * 70)
    print("QUALITY VALIDATION COMPLETE")
    print("=" * 70)

    print(
        f"Total source rows: "
        f"{report['total_rows']:,}"
    )

    print(
        f"Unique CMPLID rows: "
        f"{report['unique_cmplid_count']:,}"
    )

    print(
        f"Duplicate CMPLID rows: "
        f"{issues['duplicate_cmplid_rows']:,}"
    )

    print(
        f"Unique ODI complaints: "
        f"{report['unique_odi_count']:,}"
    )

    print(
        f"ODI numbers with multiple rows: "
        f"{report['odi_numbers_with_multiple_rows']:,}"
    )

    print(
        f"Additional component rows: "
        f"{report['additional_component_rows']:,}"
    )

    print(
        f"Vehicle product rows: "
        f"{report['vehicle_rows']:,}"
    )

    print(
        f"Unknown model year (9999): "
        f"{report['model_year']['unknown_9999_rows']:,}"
    )

    print(
        f"Truly invalid model years: "
        f"{issues['invalid_model_year_rows']:,}"
    )

    print(
        f"Missing makes: "
        f"{issues['missing_make_rows']:,}"
    )

    print(
        f"Missing models: "
        f"{issues['missing_model_rows']:,}"
    )

    print(
        f"Invalid product types: "
        f"{issues['invalid_product_type_rows']:,}"
    )

    print(
        f"Invalid Y/N rows: "
        f"{issues['invalid_yn_rows']:,}"
    )

    print(
        f"Negative injury rows: "
        f"{issues['negative_injury_rows']:,}"
    )

    print(
        f"Negative death rows: "
        f"{issues['negative_death_rows']:,}"
    )

    print(
        "\nProduct-type counts:"
    )

    for (
        product_type,
        count,
    ) in report[
        "product_type_counts"
    ].items():

        print(
            f"  {repr(product_type)}: "
            f"{count:,}"
        )

    print(
        f"\nQuality report saved to: "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()