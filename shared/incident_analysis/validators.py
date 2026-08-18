from .constants import (
    VALID_COUNTRIES,
    VALID_STATUSES,
    VALID_CATEGORIES,
    VALID_CARRIERS_BY_COUNTRY,
)


def clean(value):
    return str(value).strip() if value is not None else ""


def validate_record(row):
    errors = []

    country = clean(row.get("country"))
    carrier = clean(row.get("carrier"))
    tracking_number = clean(row.get("tracking_number"))
    category = clean(row.get("category"))
    description = clean(row.get("description"))
    status = clean(row.get("status"))
    email = clean(row.get("customer_email"))
    score = clean(row.get("satisfaction_score"))

    if country not in VALID_COUNTRIES:
        errors.append("invalid_country")

    if (
        carrier == ""
        or country not in VALID_CARRIERS_BY_COUNTRY
        or carrier not in VALID_CARRIERS_BY_COUNTRY.get(country, set())
    ):
        errors.append("invalid_carrier")

    if len(tracking_number) < 8:
        errors.append("invalid_tracking_number")

    if category not in VALID_CATEGORIES:
        errors.append("invalid_category")

    if len(description) < 5:
        errors.append("invalid_description")

    if "@" not in email:
        errors.append("invalid_email")

    if status not in VALID_STATUSES:
        errors.append("invalid_status")

    if status == "CLOSED" and score == "":
        errors.append("closed_no_score")

    if score != "":
        try:
            score_number = int(score)
            if score_number < 1 or score_number > 5:
                errors.append("score_out_of_range")
        except ValueError:
            errors.append("score_out_of_range")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }