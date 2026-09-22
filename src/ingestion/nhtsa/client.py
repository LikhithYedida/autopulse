import json
import requests

from src.ingestion.nhtsa.config import (
    NHTSA_BASE_URL,
    NHTSA_ENDPOINTS,
)


def get_recalls_by_vehicle(
    make: str,
    model: str,
    model_year: int,
):
    """
    Fetch recall records from NHTSA for a specific vehicle.
    """

    url = f"{NHTSA_BASE_URL}{NHTSA_ENDPOINTS['recalls_by_vehicle']}"

    params = {
        "make": make,
        "model": model,
        "modelYear": model_year,
    }

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    return payload.get("results", [])


def get_complaints_by_vehicle(
    make: str,
    query_model: str,
    model_year: int,
):
    """
    Fetch complaint records using the NHTSA complaint
    taxonomy / search model.
    """

    url = f"{NHTSA_BASE_URL}{NHTSA_ENDPOINTS['complaints_by_vehicle']}"

    params = {
        "make": make,
        "model": query_model,
        "modelYear": model_year,
    }

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    return payload.get("results", [])


def filter_exact_vehicle_complaints(
    complaints: list,
    make: str,
    model: str,
    model_year: int,
):
    """
    Filter broader NHTSA complaint search results
    to complaints that explicitly reference the
    requested vehicle in the products array.
    """

    target_make = make.strip().upper()
    target_model = model.strip().upper()
    target_year = str(model_year)

    matched_complaints = []

    for complaint in complaints:

        products = complaint.get("products") or []

        for product in products:

            product_type = str(
                product.get("type", "")
            ).strip().upper()

            product_make = str(
                product.get("productMake", "")
            ).strip().upper()

            product_model = str(
                product.get("productModel", "")
            ).strip().upper()

            product_year = str(
                product.get("productYear", "")
            ).strip()

            if (
                product_type == "VEHICLE"
                and product_make == target_make
                and product_model == target_model
                and product_year == target_year
            ):
                matched_complaints.append(complaint)
                break

    return matched_complaints


if __name__ == "__main__":

    # --------------------------------------------------------
    # Test vehicle
    # --------------------------------------------------------

    make = "BMW"
    target_model = "330I"
    model_year = 2021

    # NHTSA complaint search taxonomy.
    # This is temporary. Later AutoPulse will resolve
    # this dynamically through the vehicle identity layer.
    complaint_query_model = "3 SERIES"

    # --------------------------------------------------------
    # Recall ingestion
    # --------------------------------------------------------

    recalls = get_recalls_by_vehicle(
        make=make,
        model=target_model,
        model_year=model_year,
    )

    # --------------------------------------------------------
    # Complaint ingestion
    # --------------------------------------------------------

    raw_complaints = get_complaints_by_vehicle(
        make=make,
        query_model=complaint_query_model,
        model_year=model_year,
    )

    exact_complaints = filter_exact_vehicle_complaints(
        complaints=raw_complaints,
        make=make,
        model=target_model,
        model_year=model_year,
    )

    # --------------------------------------------------------
    # Validation output
    # --------------------------------------------------------

    print("=" * 70)
    print(f"AUTOPULSE VEHICLE TEST")
    print("=" * 70)

    print(f"Vehicle: {model_year} {make} {target_model}")

    print(
        f"NHTSA complaint query model: "
        f"{complaint_query_model}"
    )

    print("-" * 70)

    print(f"Recall records returned: {len(recalls)}")
    print(
        f"Broad complaint records returned: "
        f"{len(raw_complaints)}"
    )
    print(
        f"Exact {target_model} complaints: "
        f"{len(exact_complaints)}"
    )

    # --------------------------------------------------------
    # Recall samples
    # --------------------------------------------------------

    print("\nSAMPLE RECALLS")

    for recall in recalls[:3]:

        print("-" * 70)

        print(
            "Campaign:",
            recall.get("NHTSACampaignNumber"),
        )

        print(
            "Component:",
            recall.get("Component"),
        )

        print(
            "Report Received:",
            recall.get("ReportReceivedDate"),
        )

        print(
            "Summary:",
            recall.get("Summary"),
        )

    # --------------------------------------------------------
    # Exact vehicle complaint samples
    # --------------------------------------------------------

    print("\nEXACT VEHICLE COMPLAINTS")

    for complaint in exact_complaints[:5]:

        print("-" * 70)

        print(
            "ODI Number:",
            complaint.get("odiNumber"),
        )

        print(
            "Component:",
            complaint.get("components"),
        )

        print(
            "Crash:",
            complaint.get("crash"),
        )

        print(
            "Fire:",
            complaint.get("fire"),
        )

        print(
            "Injuries:",
            complaint.get("numberOfInjuries"),
        )

        print(
            "Deaths:",
            complaint.get("numberOfDeaths"),
        )

        print(
            "Incident Date:",
            complaint.get("dateOfIncident"),
        )

        print(
            "Complaint Filed:",
            complaint.get("dateComplaintFiled"),
        )

        print(
            "VIN:",
            complaint.get("vin"),
        )

        print(
            "Products:",
            complaint.get("products"),
        )

        print(
            "Summary:",
            complaint.get("summary"),
        )

    # --------------------------------------------------------
    # Raw schema validation
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("RAW COMPLAINT SCHEMA")
    print("=" * 70)

    if raw_complaints:

        print("Available fields:")

        print(
            list(
                raw_complaints[0].keys()
            )
        )

        print("\nFirst raw complaint record:")

        print(
            json.dumps(
                raw_complaints[0],
                indent=2,
                ensure_ascii=False,
            )
        )