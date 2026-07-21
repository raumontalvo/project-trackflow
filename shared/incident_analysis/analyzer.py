import csv
from collections import Counter

from .constants import VALID_CATEGORIES, VALID_STATUSES, VALID_COUNTRIES
from .validators import validate_record


def percentage(count, total):
    if total == 0:
        return 0.0
    return round((count / total) * 100, 1)


def analyze_csv(file_path):
    total_records = 0
    valid_records = []

    invalid_breakdown = Counter()
    category_breakdown = Counter()
    status_breakdown = Counter()
    country_breakdown = Counter()
    satisfaction_scores = Counter()

    with open(file_path, mode="r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        if not reader.fieldnames:
            raise ValueError("CSV file is empty or missing headers.")

        for row in reader:
            total_records += 1

            validation = validate_record(row)

            if not validation["valid"]:
                for error in set(validation["errors"]):
                    invalid_breakdown[error] += 1
                continue

            valid_records.append(row)

            category_breakdown[row["category"].strip()] += 1
            status_breakdown[row["status"].strip()] += 1
            country_breakdown[row["country"].strip()] += 1

            if row["status"].strip() == "CLOSED":
                score = row.get("satisfaction_score", "").strip()
                if score:
                    satisfaction_scores[int(score)] += 1

    valid_count = len(valid_records)
    invalid_count = total_records - valid_count
    scored_total = sum(satisfaction_scores.values())

    average_score = 0.0
    if scored_total > 0:
        total_score_value = sum(score * count for score, count in satisfaction_scores.items())
        average_score = round(total_score_value / scored_total, 2)

    return {
        "total_records": total_records,
        "valid_records": valid_count,
        "invalid_records": invalid_count,
        "invalid_breakdown": dict(invalid_breakdown),
        "category_breakdown": {
            category: {
                "count": category_breakdown.get(category, 0),
                "percentage": percentage(category_breakdown.get(category, 0), valid_count),
            }
            for category in [
                "LOST_PARCEL",
                "DELAYED_DELIVERY",
                "WRONG_ADDRESS",
                "RETURN_REQUEST",
                "DAMAGE",
            ]
        },
        "status_breakdown": {
            status: {
                "count": status_breakdown.get(status, 0),
                "percentage": percentage(status_breakdown.get(status, 0), valid_count),
            }
            for status in ["OPEN", "CLOSED", "DISCARDED"]
        },
        "country_breakdown": {
            country: {
                "count": country_breakdown.get(country, 0),
                "percentage": percentage(country_breakdown.get(country, 0), valid_count),
            }
            for country in ["US", "ES"]
        },
        "satisfaction": {
            "scored_incidents": scored_total,
            "closed_incidents": status_breakdown.get("CLOSED", 0),
            "average_score": average_score,
            "scores": {
                score: satisfaction_scores.get(score, 0)
                for score in [1, 2, 3, 4, 5]
            },
        },
    }