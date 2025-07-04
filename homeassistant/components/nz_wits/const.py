"""Constants for the NZ WITS Spot Price integration."""

DOMAIN = "nz_wits"

# OAuth2 URLs
OAUTH2_AUTHORIZE = "https://api.electricityinfo.co.nz/login/oauth2/authorize"
OAUTH2_TOKEN = "https://api.electricityinfo.co.nz/login/oauth2/token"

# API Configuration
API_BASE_URL = "https://api.electricityinfo.co.nz"
PRICES_URL = f"{API_BASE_URL}/api/market-prices/v1/prices"

# Sensor schedules
SCHEDULE_RTD = "RTD"
SCHEDULE_INTERIM = "Interim"
SCHEDULE_PRSS = "PRSS"
SCHEDULE_PRSL = "PRSL"

SCHEDULE_TYPES = {
    SCHEDULE_RTD: {
        "name": "Real Time Dispatch (RTD)",
        "params": {"schedules": SCHEDULE_RTD, "marketType": "E", "offset": 0},
    },
    SCHEDULE_INTERIM: {
        "name": "Interim Price",
        "params": {"schedules": "Interim", "marketType": "E", "back": 3, "offset": 0},
    },
    SCHEDULE_PRSS: {
        "name": "Price Responsive Schedule Short (PRSS)",
        "params": {
            "schedules": SCHEDULE_PRSS,
            "marketType": "E",
            "forward": 6,
            "offset": 0,
        },
    },
    SCHEDULE_PRSL: {
        "name": "Price Responsive Schedule Long (PRSL)",
        "params": {
            "schedules": SCHEDULE_PRSL,
            "marketType": "E",
            "forward": 48,
            "offset": 0,
        },
    },
}

# Configuration constants
CONF_NODE = "node"
CONF_UPDATE_RTD = "update_rtd"
CONF_UPDATE_INTERIM = "update_interim"
CONF_UPDATE_PRSS = "update_prss"
CONF_UPDATE_PRSL = "update_prsl"

# Node options for configuration - major grid exit points
NODE_OPTIONS = [
    "TGA0331",  # Taranaki
    "TGA0111",  # Northland
    "TGA0221",  # Auckland
    "TGA0261",  # Waikato
    "TGA0321",  # Bay of Plenty
    "TGA0371",  # Gisborne
    "TGA0421",  # Hawke's Bay
    "TGA0432",  # Manawatu
    "TGA0541",  # Tasman
    "TGA0571",  # West Coast
    "TGA0611",  # Canterbury
    "TGA0661",  # Otago
    "TGA0721",  # Southland
]
