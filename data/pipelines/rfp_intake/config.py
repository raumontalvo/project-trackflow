DEPARTMENTS = {
    "warehouse": {
        "name": "Warehouse Operations",
        "owner": "Ana Whitfield",
    },
    "lastmile": {
        "name": "Last Mile and Carrier Management",
        "owner": "Carlos Vega",
    },
    "reverse": {
        "name": "Reverse Logistics",
        "owner": "Sofía Ramos",
    },
}

SERVICE_TO_DEPARTMENT = {
    "warehousing": "warehouse",
    "last_mile": "lastmile",
    "returns": "reverse",
}

COUNTRY_TO_CURRENCY = {
    "US": "USD",
    "Spain": "EUR",
}

VALID_DEPARTMENT_IDS = tuple(DEPARTMENTS.keys())
VALID_SERVICE_IDS = tuple(SERVICE_TO_DEPARTMENT.keys())
VALID_COUNTRIES = tuple(COUNTRY_TO_CURRENCY.keys())