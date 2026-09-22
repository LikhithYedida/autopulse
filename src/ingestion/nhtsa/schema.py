# ============================================================
# AutoPulse AI
# NHTSA Consumer Complaint Raw Schema
#
# Source:
# NHTSA CMPL.txt data dictionary
#
# Current schema:
# 51 tab-delimited fields
# ============================================================


NHTSA_COMPLAINT_COLUMNS = [
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
    "CITY",
    "STATE",
    "VIN",
    "DATEA",
    "LDATE",
    "MILES",
    "OCCURENCES",
    "CDESCR",
    "CMPL_TYPE",
    "POLICE_RPT_YN",
    "PURCH_DT",
    "ORIG_OWNER_YN",
    "ANTI_BRAKES_YN",
    "CRUISE_CONT_YN",
    "NUM_CYLS",
    "DRIVE_TRAIN",
    "FUEL_SYS",
    "FUEL_TYPE",
    "TRANS_TYPE",
    "VEH_SPEED",
    "DOT",
    "TIRE_SIZE",
    "LOC_OF_TIRE",
    "TIRE_FAIL_TYPE",
    "ORIG_EQUIP_YN",
    "MANUF_DT",
    "SEAT_TYPE",
    "RESTRAINT_TYPE",
    "DEALER_NAME",
    "DEALER_TEL",
    "DEALER_CITY",
    "DEALER_STATE",
    "DEALER_ZIP",
    "PROD_TYPE",
    "REPAIRED_YN",
    "MEDICAL_ATTN",
    "VEHICLES_TOWED_YN",
    "STATE_OF_INCIDENT",
    "VEHICLE_OPERATOR",
]


EXPECTED_COMPLAINT_COLUMN_COUNT = 51


def validate_complaint_schema() -> None:
    """
    Validate that the AutoPulse raw NHTSA complaint schema
    matches the current NHTSA flat-file specification.
    """

    actual_count = len(NHTSA_COMPLAINT_COLUMNS)

    if actual_count != EXPECTED_COMPLAINT_COLUMN_COUNT:
        raise ValueError(
            "NHTSA complaint schema mismatch. "
            f"Expected {EXPECTED_COMPLAINT_COLUMN_COUNT} "
            f"columns but defined {actual_count}."
        )


validate_complaint_schema()