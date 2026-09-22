from __future__ import annotations

import math
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import psycopg
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row


# ============================================================
# AutoPulse
# Vehicle Intelligence API
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="AutoPulse Vehicle Intelligence API",
    description=(
        "VIN-first vehicle intelligence, safety analytics, "
        "entity resolution and ownership decision support."
    ),
    version="1.0.0",
)
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


VPIC_BASE_URL = (
    "https://vpic.nhtsa.dot.gov/api/vehicles"
)

SOURCE_SYSTEM = "NHTSA_COMPLAINTS"


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
        row_factory=dict_row,
    )


# ============================================================
# VIN helpers
# ============================================================


def clean_vin(vin: str) -> str:

    vin = vin.upper().strip()

    vin = re.sub(
        r"\s+",
        "",
        vin,
    )

    return vin


def validate_vin(vin: str) -> str:

    vin = clean_vin(vin)

    if len(vin) != 17:
        raise HTTPException(
            status_code=400,
            detail="VIN must contain exactly 17 characters.",
        )

    if not re.fullmatch(
        r"[A-HJ-NPR-Z0-9]{17}",
        vin,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "VIN contains invalid characters. "
                "VINs do not use I, O or Q."
            ),
        )

    return vin


# ============================================================
# vPIC
# ============================================================


def decode_vin_from_vpic(
    vin: str,
) -> dict[str, Any]:

    url = (
        f"{VPIC_BASE_URL}"
        f"/DecodeVinValuesExtended/"
        f"{vin}"
        f"?format=json"
    )

    try:

        response = requests.get(
            url,
            timeout=30,
        )

        response.raise_for_status()

        payload = response.json()

    except requests.RequestException as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to reach the vehicle "
                "reference provider."
            ),
        ) from exc

    results = payload.get(
        "Results",
        [],
    )

    if not results:

        raise HTTPException(
            status_code=404,
            detail="No VIN decode result returned.",
        )

    return results[0]


def value_or_none(
    value: Any,
):

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    if value.lower() in {
        "not applicable",
        "null",
        "none",
    }:
        return None

    return value


# ============================================================
# Health
# ============================================================


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health")
def health():

    database_status = "available"

    try:

        with get_connection() as connection:

            with connection.cursor() as cursor:

                cursor.execute(
                    "SELECT 1;"
                )

                cursor.fetchone()

    except Exception:

        database_status = "unavailable"

    return {
        "api": "healthy",
        "database": database_status,
        "vin_provider": "NHTSA_VPIC",
        "carfax": "integration_ready",
    }


# ============================================================
# VIN Intelligence
# ============================================================


@app.get("/api/v1/vin/{vin}")
def decode_vin(
    vin: str,
):

    vin = validate_vin(
        vin
    )

    raw = decode_vin_from_vpic(
        vin
    )

    error_code = value_or_none(
        raw.get("ErrorCode")
    )

    return {

        "vin": vin,

        "identity": {

            "make":
                value_or_none(
                    raw.get("Make")
                ),

            "model":
                value_or_none(
                    raw.get("Model")
                ),

            "model_year":
                value_or_none(
                    raw.get("ModelYear")
                ),

            "manufacturer":
                value_or_none(
                    raw.get(
                        "Manufacturer"
                    )
                ),

            "vehicle_type":
                value_or_none(
                    raw.get(
                        "VehicleType"
                    )
                ),
        },

        "configuration": {

            "body_class":
                value_or_none(
                    raw.get(
                        "BodyClass"
                    )
                ),

            "drive_type":
                value_or_none(
                    raw.get(
                        "DriveType"
                    )
                ),

            "fuel_type_primary":
                value_or_none(
                    raw.get(
                        "FuelTypePrimary"
                    )
                ),

            "fuel_type_secondary":
                value_or_none(
                    raw.get(
                        "FuelTypeSecondary"
                    )
                ),

            "electrification_level":
                value_or_none(
                    raw.get(
                        "ElectrificationLevel"
                    )
                ),

            "engine_cylinders":
                value_or_none(
                    raw.get(
                        "EngineCylinders"
                    )
                ),

            "engine_displacement_l":
                value_or_none(
                    raw.get(
                        "DisplacementL"
                    )
                ),

            "transmission_style":
                value_or_none(
                    raw.get(
                        "TransmissionStyle"
                    )
                ),

            "doors":
                value_or_none(
                    raw.get("Doors")
                ),

            "series":
                value_or_none(
                    raw.get("Series")
                ),

            "trim":
                value_or_none(
                    raw.get("Trim")
                ),
        },

        "manufacturing": {

            "plant_city":
                value_or_none(
                    raw.get(
                        "PlantCity"
                    )
                ),

            "plant_state":
                value_or_none(
                    raw.get(
                        "PlantState"
                    )
                ),

            "plant_country":
                value_or_none(
                    raw.get(
                        "PlantCountry"
                    )
                ),
        },

        "decode": {

            "provider":
                "NHTSA_VPIC",

            "error_code":
                error_code,

            "error_text":
                value_or_none(
                    raw.get(
                        "ErrorText"
                    )
                ),
        },
    }


# ============================================================
# Vehicle History
# ============================================================


@app.get(
    "/api/v1/vehicle-history/{vin}"
)
def vehicle_history(
    vin: str,
):

    vin = validate_vin(
        vin
    )

    decoded = decode_vin_from_vpic(
        vin
    )

    return {

        "vin": vin,

        "vehicle": {

            "make":
                value_or_none(
                    decoded.get("Make")
                ),

            "model":
                value_or_none(
                    decoded.get("Model")
                ),

            "model_year":
                value_or_none(
                    decoded.get(
                        "ModelYear"
                    )
                ),
        },

        "history_sources": {

            "carfax": {

                "status":
                    "LICENSE_REQUIRED",

                "integration":
                    "READY",

                "available_fields": [
                    "accident_history",
                    "title_history",
                    "odometer_history",
                    "ownership_history",
                    "service_history",
                    "usage_history",
                ],

                "note": (
                    "AutoPulse supports an "
                    "authorized CARFAX provider "
                    "adapter. Live CARFAX data "
                    "requires licensed access."
                ),
            },

            "autopulse": {

                "status":
                    "AVAILABLE",

                "available_fields": [
                    "safety_complaints",
                    "recalls",
                    "failure_patterns",
                    "risk_signals",
                    "model_year_trends",
                    "entity_confidence",
                ],
            },
        },
    }


# ============================================================
# Canonical vehicle search
# ============================================================


@app.get(
    "/api/v1/vehicles/search"
)
def search_vehicles(

    make: str | None = Query(
        default=None
    ),

    model: str | None = Query(
        default=None
    ),

    year: int | None = Query(
        default=None
    ),

    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
):

    conditions = []

    parameters = []

    if make:

        conditions.append(
            """
            UPPER(ma.canonical_make_name)
            LIKE UPPER(%s)
            """
        )

        parameters.append(
            f"%{make.strip()}%"
        )

    if model:

        conditions.append(
            """
            UPPER(m.canonical_model_name)
            LIKE UPPER(%s)
            """
        )

        parameters.append(
            f"%{model.strip()}%"
        )

    if year is not None:

        conditions.append(
            "vc.model_year = %s"
        )

        parameters.append(
            year
        )

    where_clause = ""

    if conditions:

        where_clause = (
            "WHERE "
            + " AND ".join(
                conditions
            )
        )

    query = f"""
        SELECT

            vc.vehicle_configuration_id,

            ma.canonical_make_name
                AS make,

            m.canonical_model_name
                AS model,

            vc.model_year,

            vc.variant_name,

            vc.trim_name,

            vc.body_style,

            vc.drive_type,

            vc.fuel_type,

            vc.engine_description,

            vc.transmission_description

        FROM
            identity.vehicle_configurations vc

        JOIN
            identity.models m

          ON m.model_id =
             vc.model_id

        JOIN
            identity.makes ma

          ON ma.make_id =
             m.make_id

        {where_clause}

        ORDER BY
            ma.canonical_make_name,
            m.canonical_model_name,
            vc.model_year DESC

        LIMIT %s;
    """

    parameters.append(
        limit
    )

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                query,
                parameters,
            )

            rows = cursor.fetchall()

    return {

        "filters": {
            "make": make,
            "model": model,
            "year": year,
        },

        "count": len(rows),

        "vehicles": rows,
    }


# ============================================================
# Vehicle configuration
# ============================================================


@app.get(
    "/api/v1/vehicles/{configuration_id}"
)
def vehicle_configuration(
    configuration_id: int,
):

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT

                    vc.vehicle_configuration_id,

                    ma.make_id,

                    ma.canonical_make_name
                        AS make,

                    m.model_id,

                    m.canonical_model_name
                        AS model,

                    vc.model_year,

                    vc.variant_name,

                    vc.trim_name,

                    vc.body_style,

                    vc.drive_type,

                    vc.fuel_type,

                    vc.engine_description,

                    vc.transmission_description,

                    vc.created_at

                FROM
                    identity.vehicle_configurations vc

                JOIN identity.models m

                  ON m.model_id =
                     vc.model_id

                JOIN identity.makes ma

                  ON ma.make_id =
                     m.make_id

                WHERE
                    vc.vehicle_configuration_id =
                    %s;
                """,
                (
                    configuration_id,
                ),
            )

            row = cursor.fetchone()

    if not row:

        raise HTTPException(
            status_code=404,
            detail=(
                "Vehicle configuration "
                "not found."
            ),
        )

    return row


# ============================================================
# Entity Resolution / Data Confidence
# ============================================================


@app.get(
    "/api/v1/data-confidence"
)
def data_confidence():

    with get_connection() as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT

                    COUNT(*) AS total,

                    COUNT(*) FILTER (
                        WHERE canonical_model_id
                        IS NOT NULL
                    ) AS resolved,

                    COUNT(*) FILTER (
                        WHERE canonical_model_id
                        IS NULL
                    ) AS unresolved

                FROM
                    identity.source_vehicle_aliases

                WHERE
                    source_system = %s;
                """,
                (
                    SOURCE_SYSTEM,
                ),
            )

            identity_counts = (
                cursor.fetchone()
            )

            cursor.execute(
                """
                SELECT
                    review_priority,
                    COUNT(*) AS aliases

                FROM
                    identity.entity_resolution_review_queue

                GROUP BY
                    review_priority;
                """
            )

            review_tiers = (
                cursor.fetchall()
            )

            cursor.execute(
                """
                SELECT
                    audit_class,
                    COUNT(*) AS relationships,
                    SUM(alias_count) AS aliases

                FROM
                    identity.model_alias_audit

                GROUP BY
                    audit_class;
                """
            )

            audit_classes = (
                cursor.fetchall()
            )

    total = (
        identity_counts["total"]
        or 0
    )

    resolved = (
        identity_counts["resolved"]
        or 0
    )

    resolution_rate = (
        round(
            resolved
            / total
            * 100,
            2,
        )
        if total
        else 0
    )

    return {

        "identity_resolution": {

            **identity_counts,

            "resolution_rate_pct":
                resolution_rate,

            "policy":
                (
                    "Ambiguous vehicle identities "
                    "remain unresolved rather than "
                    "being force-matched."
                ),
        },

        "review_queue":
            review_tiers,

        "high_evidence_audit":
            audit_classes,
    }
# ============================================================
# SAFETY + OWNERSHIP DECISION ENGINE
# ============================================================


NHTSA_API_BASE = "https://api.nhtsa.gov"


def _nhtsa_request(
    endpoint: str,
    params: dict[str, Any],
) -> dict[str, Any]:

    try:
        response = requests.get(
            f"{NHTSA_API_BASE}{endpoint}",
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as exc:

        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to retrieve NHTSA "
                "safety evidence."
            ),
        ) from exc


def _results(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:

    rows = (
        payload.get("results")
        or payload.get("Results")
        or []
    )

    if isinstance(rows, list):
        return rows

    return []


def _truthy(
    value: Any,
) -> bool:

    if isinstance(value, bool):
        return value

    if value is None:
        return False

    return str(value).strip().upper() in {
        "Y",
        "YES",
        "TRUE",
        "1",
    }


def _integer(
    value: Any,
) -> int:

    try:

        if value in (
            None,
            "",
            "null",
        ):
            return 0

        return int(
            float(value)
        )

    except (
        TypeError,
        ValueError,
    ):
        return 0


def get_vehicle_complaints(
    make: str,
    model: str,
    year: int,
) -> list[dict[str, Any]]:

    payload = _nhtsa_request(
        "/complaints/complaintsByVehicle",
        {
            "make": make,
            "model": model,
            "modelYear": year,
        },
    )

    return _results(payload)


def get_vehicle_recalls(
    make: str,
    model: str,
    year: int,
) -> list[dict[str, Any]]:

    payload = _nhtsa_request(
        "/recalls/recallsByVehicle",
        {
            "make": make,
            "model": model,
            "modelYear": year,
        },
    )

    return _results(payload)


def calculate_vehicle_decision(
    make: str,
    model: str,
    year: int,
) -> dict[str, Any]:

    complaints = get_vehicle_complaints(
        make,
        model,
        year,
    )

    recalls = get_vehicle_recalls(
        make,
        model,
        year,
    )

    complaint_count = len(
        complaints
    )

    recall_count = len(
        recalls
    )

    crash_count = 0
    fire_count = 0
    injuries = 0
    deaths = 0

    component_counter: Counter = (
        Counter()
    )

    for complaint in complaints:

        if _truthy(
            complaint.get("crash")
            or complaint.get("Crash")
        ):
            crash_count += 1

        if _truthy(
            complaint.get("fire")
            or complaint.get("Fire")
        ):
            fire_count += 1

        injuries += _integer(
            complaint.get(
                "numberOfInjuries"
            )
            or complaint.get(
                "NumberOfInjuries"
            )
        )

        deaths += _integer(
            complaint.get(
                "numberOfDeaths"
            )
            or complaint.get(
                "NumberOfDeaths"
            )
        )

        component = (
            complaint.get("components")
            or complaint.get("Components")
            or complaint.get("component")
        )

        if component:

            parts = re.split(
                r"[,;]",
                str(component),
            )

            for part in parts:

                cleaned = (
                    part.strip().upper()
                )

                if cleaned:
                    component_counter[
                        cleaned
                    ] += 1

    # --------------------------------------------------------
    # Complaint-severity ratios
    # --------------------------------------------------------

    denominator = max(
        complaint_count,
        1,
    )

    crash_rate = (
        crash_count
        / denominator
    )

    fire_rate = (
        fire_count
        / denominator
    )

    injury_rate = (
        injuries
        / denominator
    )

    death_rate = (
        deaths
        / denominator
    )

    # --------------------------------------------------------
    # Explainable AutoPulse Risk Signal
    #
    # This is NOT an official NHTSA safety rating.
    #
    # It is an evidence-intensity indicator combining:
    # complaint burden
    # crash/fire evidence
    # injuries/deaths
    # recall burden
    #
    # Score range: 0–100
    # --------------------------------------------------------

    complaint_component = min(
        20.0,
        (
            math.log1p(
                complaint_count
            )
            / math.log(201)
        )
        * 20.0,
    )

    crash_component = min(
        20.0,
        crash_rate
        / 0.10
        * 20.0,
    )

    fire_component = min(
        15.0,
        fire_rate
        / 0.05
        * 15.0,
    )

    injury_component = min(
        15.0,
        injury_rate
        / 0.05
        * 15.0,
    )

    death_component = min(
        15.0,
        death_rate
        / 0.01
        * 15.0,
    )

    recall_component = min(
        15.0,
        recall_count
        * 2.5,
    )

    risk_score = round(
        min(
            100.0,
            complaint_component
            + crash_component
            + fire_component
            + injury_component
            + death_component
            + recall_component,
        ),
        1,
    )

    # --------------------------------------------------------
    # Evidence confidence
    # --------------------------------------------------------

    if complaint_count >= 100:
        evidence_confidence = "HIGH"

    elif complaint_count >= 25:
        evidence_confidence = "MODERATE"

    elif complaint_count > 0:
        evidence_confidence = "LIMITED"

    else:
        evidence_confidence = (
            "INSUFFICIENT"
        )

    # --------------------------------------------------------
    # Decision band
    # --------------------------------------------------------

    if risk_score >= 75:

        attention_level = "HIGH"

        ownership_decision = (
            "HIGH ATTENTION"
        )

        recommendation = (
            "Perform a detailed pre-purchase "
            "inspection, verify recall completion, "
            "and investigate the recurring safety "
            "issues before making an ownership decision."
        )

    elif risk_score >= 50:

        attention_level = "ELEVATED"

        ownership_decision = (
            "CAUTION — VERIFY BEFORE PURCHASE"
        )

        recommendation = (
            "Review the major complaint categories "
            "and recall history and complete a targeted "
            "inspection before purchase."
        )

    elif risk_score >= 25:

        attention_level = "MODERATE"

        ownership_decision = (
            "CONSIDER WITH TARGETED CHECKS"
        )

        recommendation = (
            "The vehicle can remain under consideration, "
            "but the recurring issue categories and recall "
            "history should be checked before purchase."
        )

    else:

        attention_level = "LOW"

        ownership_decision = (
            "CONSIDER WITH STANDARD CHECKS"
        )

        recommendation = (
            "Current NHTSA evidence shows a lower "
            "AutoPulse attention signal. Standard "
            "pre-purchase inspection and recall "
            "verification are still recommended."
        )

    # --------------------------------------------------------
    # Top complaint components
    # --------------------------------------------------------

    top_components = [

        {
            "component": component,
            "complaints": count,
            "share_pct": round(
                count
                / denominator
                * 100,
                2,
            ),
        }

        for component, count
        in component_counter.most_common(
            8
        )
    ]

    # --------------------------------------------------------
    # Recall summaries
    # --------------------------------------------------------

    recall_details = []

    for recall in recalls[:10]:

        recall_details.append(
            {
                "campaign_number":
                    recall.get(
                        "NHTSACampaignNumber"
                    ),

                "component":
                    recall.get(
                        "Component"
                    ),

                "subject":
                    recall.get(
                        "Subject"
                    ),

                "summary":
                    recall.get(
                        "Summary"
                    ),

                "consequence":
                    recall.get(
                        "Consequence"
                    ),

                "remedy":
                    recall.get(
                        "Remedy"
                    ),

                "report_received_date":
                    recall.get(
                        "ReportReceivedDate"
                    ),
            }
        )

    # --------------------------------------------------------
    # Explainability
    # --------------------------------------------------------

    drivers = []

    if complaint_count:
        drivers.append(
            f"{complaint_count:,} NHTSA complaint records"
        )

    if recall_count:
        drivers.append(
            f"{recall_count:,} recall campaigns"
        )

    if crash_count:
        drivers.append(
            f"{crash_count:,} complaints involving crashes"
        )

    if fire_count:
        drivers.append(
            f"{fire_count:,} complaints involving fires"
        )

    if injuries:
        drivers.append(
            f"{injuries:,} reported injuries"
        )

    if deaths:
        drivers.append(
            f"{deaths:,} reported deaths"
        )

    if top_components:

        drivers.append(
            "Most reported component: "
            + top_components[0][
                "component"
            ]
        )

    return {

        "vehicle": {
            "make": make.upper(),
            "model": model.upper(),
            "model_year": year,
        },

        "decision": {

            "autopulse_risk_score":
                risk_score,

            "attention_level":
                attention_level,

            "ownership_decision":
                ownership_decision,

            "evidence_confidence":
                evidence_confidence,

            "recommendation":
                recommendation,
        },

        "safety_evidence": {

            "complaints":
                complaint_count,

            "recalls":
                recall_count,

            "crash_complaints":
                crash_count,

            "fire_complaints":
                fire_count,

            "reported_injuries":
                injuries,

            "reported_deaths":
                deaths,
        },

        "risk_components": {

            "complaint_burden":
                round(
                    complaint_component,
                    1,
                ),

            "crash_signal":
                round(
                    crash_component,
                    1,
                ),

            "fire_signal":
                round(
                    fire_component,
                    1,
                ),

            "injury_signal":
                round(
                    injury_component,
                    1,
                ),

            "fatality_signal":
                round(
                    death_component,
                    1,
                ),

            "recall_signal":
                round(
                    recall_component,
                    1,
                ),
        },

        "top_issue_components":
            top_components,

        "recall_details":
            recall_details,

        "why_this_score":
            drivers,

        "coverage": {

            "safety_market":
                "United States",

            "complaints_provider":
                "NHTSA",

            "recalls_provider":
                "NHTSA",

            "vehicle_identity":
                "vPIC",

            "carfax":
                "LICENSE_REQUIRED",
        },

        "methodology_note": (
            "AutoPulse Risk Score is an explainable "
            "portfolio decision-support indicator. "
            "It is not an official NHTSA safety rating "
            "and does not estimate the probability of "
            "vehicle failure."
        ),
    }


# ============================================================
# Make / Model / Year Decision
# ============================================================


@app.get(
    "/api/v1/decision"
)
def vehicle_decision(

    make: str = Query(...),

    model: str = Query(...),

    year: int = Query(
        ...,
        ge=1980,
        le=2035,
    ),
):

    return calculate_vehicle_decision(
        make=make.strip(),
        model=model.strip(),
        year=year,
    )


# ============================================================
# VIN → Decision
# ============================================================


@app.get(
    "/api/v1/decision/vin/{vin}"
)
def vehicle_decision_by_vin(
    vin: str,
):

    vin = validate_vin(
        vin
    )

    decoded = decode_vin_from_vpic(
        vin
    )

    make = value_or_none(
        decoded.get("Make")
    )

    model = value_or_none(
        decoded.get("Model")
    )

    year_value = value_or_none(
        decoded.get("ModelYear")
    )

    if (
        not make
        or not model
        or not year_value
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "VIN was decoded but did not "
                "return enough make/model/year "
                "information for safety analysis."
            ),
        )

    try:
        year = int(year_value)

    except ValueError as exc:

        raise HTTPException(
            status_code=422,
            detail=(
                "VIN returned an invalid "
                "model year."
            ),
        ) from exc

    decision = (
        calculate_vehicle_decision(
            make=make,
            model=model,
            year=year,
        )
    )

    decision["vin"] = {
        "vin": vin,

        "manufacturer":
            value_or_none(
                decoded.get(
                    "Manufacturer"
                )
            ),

        "vehicle_type":
            value_or_none(
                decoded.get(
                    "VehicleType"
                )
            ),

        "body_class":
            value_or_none(
                decoded.get(
                    "BodyClass"
                )
            ),

        "fuel_type":
            value_or_none(
                decoded.get(
                    "FuelTypePrimary"
                )
            ),

        "drive_type":
            value_or_none(
                decoded.get(
                    "DriveType"
                )
            ),

        "plant_country":
            value_or_none(
                decoded.get(
                    "PlantCountry"
                )
            ),
    }

    return decision
# ============================================================
# NCAP SAFETY RATINGS
# ============================================================


def get_ncap_ratings(
    make: str,
    model: str,
    year: int,
) -> dict[str, Any]:

    make_path = quote(
        make.strip(),
        safe="",
    )

    model_path = quote(
        model.strip(),
        safe="",
    )

    url = (
        f"{NHTSA_API_BASE}"
        f"/SafetyRatings/modelyear/{year}"
        f"/make/{make_path}"
        f"/model/{model_path}"
    )

    try:

        response = requests.get(
            url,
            timeout=30,
        )

        response.raise_for_status()

        payload = response.json()

    except requests.RequestException as exc:

        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve NCAP safety ratings.",
        ) from exc

    variants = _results(payload)

    rating_results = []

    for variant in variants[:10]:

        vehicle_id = (
            variant.get("VehicleId")
            or variant.get("vehicleId")
        )

        if not vehicle_id:
            continue

        try:

            rating_response = requests.get(
                (
                    f"{NHTSA_API_BASE}"
                    f"/SafetyRatings/VehicleId/"
                    f"{vehicle_id}"
                ),
                timeout=30,
            )

            rating_response.raise_for_status()

            rating_payload = (
                rating_response.json()
            )

            detailed = _results(
                rating_payload
            )

        except requests.RequestException:
            continue

        for rating in detailed:

            rating_results.append(
                {
                    "vehicle_id":
                        vehicle_id,

                    "vehicle_description":
                        (
                            variant.get(
                                "VehicleDescription"
                            )
                            or rating.get(
                                "VehicleDescription"
                            )
                        ),

                    "overall_rating":
                        value_or_none(
                            rating.get(
                                "OverallRating"
                            )
                        ),

                    "front_crash_rating":
                        value_or_none(
                            rating.get(
                                "OverallFrontCrashRating"
                            )
                        ),

                    "side_crash_rating":
                        value_or_none(
                            rating.get(
                                "OverallSideCrashRating"
                            )
                        ),

                    "rollover_rating":
                        value_or_none(
                            rating.get(
                                "RolloverRating"
                            )
                        ),

                    "side_pole_rating":
                        value_or_none(
                            rating.get(
                                "SidePoleCrashRating"
                            )
                        ),

                    "rollover_possibility":
                        value_or_none(
                            rating.get(
                                "RolloverPossibility"
                            )
                        ),
                }
            )

    return {
        "vehicle": {
            "make": make.upper(),
            "model": model.upper(),
            "model_year": year,
        },

        "tested_variants":
            len(rating_results),

        "ratings":
            rating_results,

        "provider":
            "NHTSA_NCAP",

        "coverage_note":
            (
                "NCAP ratings are available only "
                "for vehicles tested by NHTSA."
            ),
    }


@app.get(
    "/api/v1/safety-ratings"
)
def safety_ratings(

    make: str = Query(...),

    model: str = Query(...),

    year: int = Query(
        ...,
        ge=1990,
        le=2035,
    ),
):

    return get_ncap_ratings(
        make,
        model,
        year,
    )


# ============================================================
# EMERGING RISK / COMPLAINT TREND ENGINE
# ============================================================


def extract_year_from_date(
    value: Any,
) -> int | None:

    if value is None:
        return None

    match = re.search(
        r"(19|20)\d{2}",
        str(value),
    )

    if not match:
        return None

    try:
        return int(match.group())

    except ValueError:
        return None


def calculate_complaint_trend(
    make: str,
    model: str,
    year: int,
) -> dict[str, Any]:

    complaints = get_vehicle_complaints(
        make,
        model,
        year,
    )

    current_year = (
        datetime.now().year
    )

    latest_complete_year = (
        current_year - 1
    )

    yearly_counts: Counter = (
        Counter()
    )

    yearly_components: dict[
        int,
        Counter,
    ] = {}

    for complaint in complaints:

        complaint_date = (

            complaint.get(
                "dateComplaintFiled"
            )

            or complaint.get(
                "DateComplaintFiled"
            )

            or complaint.get(
                "dateOfIncident"
            )

            or complaint.get(
                "DateOfIncident"
            )
        )

        complaint_year = (
            extract_year_from_date(
                complaint_date
            )
        )

        if not complaint_year:
            continue

        yearly_counts[
            complaint_year
        ] += 1

        component = (

            complaint.get(
                "components"
            )

            or complaint.get(
                "Components"
            )

            or complaint.get(
                "component"
            )
        )

        if complaint_year not in yearly_components:

            yearly_components[
                complaint_year
            ] = Counter()

        if component:

            for part in re.split(
                r"[,;]",
                str(component),
            ):

                clean_component = (
                    part.strip().upper()
                )

                if clean_component:

                    yearly_components[
                        complaint_year
                    ][
                        clean_component
                    ] += 1

    # --------------------------------------------------------
    # Use complete calendar years only.
    # Avoid false drops caused by partial current-year data.
    # --------------------------------------------------------

    recent_year = (
        latest_complete_year
    )

    baseline_years = [
        recent_year - 3,
        recent_year - 2,
        recent_year - 1,
    ]

    recent_count = yearly_counts.get(
        recent_year,
        0,
    )

    baseline_values = [

        yearly_counts.get(
            y,
            0,
        )

        for y
        in baseline_years
    ]

    baseline_average = (
        sum(baseline_values)
        / len(baseline_values)
    )

    if baseline_average > 0:

        acceleration_pct = round(
            (
                (
                    recent_count
                    - baseline_average
                )
                / baseline_average
            )
            * 100,
            2,
        )

    else:

        acceleration_pct = None

    # --------------------------------------------------------
    # Trend classification
    # --------------------------------------------------------

    if (
        acceleration_pct is None
        or sum(baseline_values) < 5
    ):

        trend_signal = (
            "INSUFFICIENT_HISTORY"
        )

    elif acceleration_pct >= 50:

        trend_signal = (
            "SHARP_INCREASE"
        )

    elif acceleration_pct >= 20:

        trend_signal = (
            "INCREASING"
        )

    elif acceleration_pct <= -30:

        trend_signal = (
            "DECLINING"
        )

    else:

        trend_signal = (
            "STABLE"
        )

    # --------------------------------------------------------
    # Top recent issue components
    # --------------------------------------------------------

    recent_components = (
        yearly_components.get(
            recent_year,
            Counter(),
        )
    )

    top_recent_components = [

        {
            "component":
                component,

            "complaints":
                count,
        }

        for component, count
        in recent_components.most_common(
            6
        )
    ]

    timeline = [

        {
            "year": y,
            "complaints":
                yearly_counts.get(
                    y,
                    0,
                ),
        }

        for y in sorted(
            yearly_counts.keys()
        )
    ]

    return {

        "vehicle": {
            "make": make.upper(),
            "model": model.upper(),
            "model_year": year,
        },

        "trend": {

            "signal":
                trend_signal,

            "latest_complete_year":
                recent_year,

            "latest_year_complaints":
                recent_count,

            "baseline_years":
                baseline_years,

            "baseline_average":
                round(
                    baseline_average,
                    2,
                ),

            "complaint_acceleration_pct":
                acceleration_pct,
        },

        "top_recent_components":
            top_recent_components,

        "timeline":
            timeline,

        "methodology_note": (
            "Trend compares the latest complete "
            "calendar year with the average of the "
            "three preceding complete years. "
            "This is an emerging-attention indicator, "
            "not a prediction of mechanical failure."
        ),
    }


@app.get(
    "/api/v1/trends"
)
def vehicle_trends(

    make: str = Query(...),

    model: str = Query(...),

    year: int = Query(
        ...,
        ge=1980,
        le=2035,
    ),
):

    return calculate_complaint_trend(
        make,
        model,
        year,
    )


# ============================================================
# VEHICLE COMPARISON
# ============================================================


def _primary_ncap_rating(
    ncap: dict[str, Any],
) -> str | None:

    ratings = ncap.get(
        "ratings",
        [],
    )

    values = [

        row.get(
            "overall_rating"
        )

        for row in ratings

        if row.get(
            "overall_rating"
        )
    ]

    if not values:
        return None

    # Do not pretend multiple variants
    # have one identical crash-test result.
    return (
        values[0]
        if len(set(values)) == 1
        else "VARIES_BY_CONFIGURATION"
    )


@app.get(
    "/api/v1/compare"
)
def compare_vehicles(

    make_a: str = Query(...),
    model_a: str = Query(...),
    year_a: int = Query(...),

    make_b: str = Query(...),
    model_b: str = Query(...),
    year_b: int = Query(...),
):

    vehicle_a = (
        calculate_vehicle_decision(
            make_a,
            model_a,
            year_a,
        )
    )

    vehicle_b = (
        calculate_vehicle_decision(
            make_b,
            model_b,
            year_b,
        )
    )

    ncap_a = get_ncap_ratings(
        make_a,
        model_a,
        year_a,
    )

    ncap_b = get_ncap_ratings(
        make_b,
        model_b,
        year_b,
    )

    safety_a = vehicle_a[
        "safety_evidence"
    ]

    safety_b = vehicle_b[
        "safety_evidence"
    ]

    score_a = vehicle_a[
        "decision"
    ][
        "autopulse_risk_score"
    ]

    score_b = vehicle_b[
        "decision"
    ][
        "autopulse_risk_score"
    ]

    return {

        "vehicle_a": {

            "identity":
                vehicle_a[
                    "vehicle"
                ],

            "risk_score":
                score_a,

            "attention_level":
                vehicle_a[
                    "decision"
                ][
                    "attention_level"
                ],

            "evidence_confidence":
                vehicle_a[
                    "decision"
                ][
                    "evidence_confidence"
                ],

            "complaints":
                safety_a[
                    "complaints"
                ],

            "recalls":
                safety_a[
                    "recalls"
                ],

            "crash_complaints":
                safety_a[
                    "crash_complaints"
                ],

            "fire_complaints":
                safety_a[
                    "fire_complaints"
                ],

            "injuries":
                safety_a[
                    "reported_injuries"
                ],

            "deaths":
                safety_a[
                    "reported_deaths"
                ],

            "ncap_overall_rating":
                _primary_ncap_rating(
                    ncap_a
                ),

            "top_issues":
                vehicle_a[
                    "top_issue_components"
                ][:5],
        },

        "vehicle_b": {

            "identity":
                vehicle_b[
                    "vehicle"
                ],

            "risk_score":
                score_b,

            "attention_level":
                vehicle_b[
                    "decision"
                ][
                    "attention_level"
                ],

            "evidence_confidence":
                vehicle_b[
                    "decision"
                ][
                    "evidence_confidence"
                ],

            "complaints":
                safety_b[
                    "complaints"
                ],

            "recalls":
                safety_b[
                    "recalls"
                ],

            "crash_complaints":
                safety_b[
                    "crash_complaints"
                ],

            "fire_complaints":
                safety_b[
                    "fire_complaints"
                ],

            "injuries":
                safety_b[
                    "reported_injuries"
                ],

            "deaths":
                safety_b[
                    "reported_deaths"
                ],

            "ncap_overall_rating":
                _primary_ncap_rating(
                    ncap_b
                ),

            "top_issues":
                vehicle_b[
                    "top_issue_components"
                ][:5],
        },

        "differences": {

            "risk_score_delta_a_minus_b":
                round(
                    score_a
                    - score_b,
                    1,
                ),

            "complaint_delta_a_minus_b":
                (
                    safety_a[
                        "complaints"
                    ]
                    - safety_b[
                        "complaints"
                    ]
                ),

            "recall_delta_a_minus_b":
                (
                    safety_a[
                        "recalls"
                    ]
                    - safety_b[
                        "recalls"
                    ]
                ),
        },

        "interpretation_note": (
            "Raw complaint and recall counts are "
            "contextual evidence and are not normalized "
            "for sales volume, mileage or fleet exposure. "
            "AutoPulse therefore presents the evidence "
            "rather than claiming failure probability."
        ),
    }
