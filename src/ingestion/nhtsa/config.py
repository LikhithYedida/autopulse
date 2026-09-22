# ============================================================
# AutoPulse AI
# NHTSA Source Configuration
# ============================================================

NHTSA_BASE_URL = "https://api.nhtsa.gov"

NHTSA_ENDPOINTS = {
    "recalls_by_vehicle": "/recalls/recallsByVehicle",
    "complaints_by_vehicle": "/complaints/complaintsByVehicle",
}

VPIC_BASE_URL = "https://vpic.nhtsa.dot.gov/api"

VPIC_ENDPOINTS = {
    "decode_vin": "/vehicles/DecodeVinValues",
}