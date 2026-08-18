import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.api.database import incidents_table

CATEGORY_MAP = {
    "LOST_PARCEL": "lost_parcel",
    "FAILED_DELIVERY": "delivery_failure",
    "INVENTORY_MISMATCH": "inventory_discrepancy",
    "CARRIER_DELAY": "carrier_issue",
    "RETURN_REQUEST": "returns_issue",
    "WAREHOUSE_DAMAGE": "warehouse_incident",
    "SYSTEM_OUTAGE": "system_failure",
    "CUSTOMER_COMPLAINT": "client_complaint",
    "OTHER": "other",
}

STATUS_MAP = {
    "OPEN": "open",
    "IN_PROGRESS": "in_progress",
    "RESOLVED": "resolved",
    "DISCARDED": "discarded",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def main():
    csv_path = ROOT / "scripts" / "incidents-trackflow.csv"

    inserted = 0
    skipped = 0
    invalid = []

    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    existing_keys = {
        incident.get("seed_duplicate_key")
        for incident in incidents_table.all()
        if incident.get("seed_duplicate_key")
    }

    for index, row in enumerate(rows, start=2):
        incident_id = (row.get("incident_id") or "").strip()
        description = (row.get("description") or "").strip()
        old_category = (row.get("category") or "").strip()
        old_status = (row.get("status") or "").strip()
        created_at = (row.get("date") or now_iso()).strip()
        tracking_number = (row.get("tracking_number") or "").strip()
        carrier = (row.get("carrier") or "").strip()

        category = CATEGORY_MAP.get(old_category)
        status = STATUS_MAP.get(old_status)

        if not description:
            invalid.append((index, "description", "Missing required field"))
            skipped += 1
            continue

        if not category:
            invalid.append((index, "category", old_category))
            skipped += 1
            continue

        if not status:
            invalid.append((index, "status", old_status))
            skipped += 1
            continue

        title_parts = [old_category.replace("_", " ").title()]
        if tracking_number:
            title_parts.append(tracking_number)
        if carrier:
            title_parts.append(carrier)

        title = " — ".join(title_parts)

        duplicate_key = incident_id or f"{title}|{created_at}"

        if duplicate_key in existing_keys:
            skipped += 1
            continue

        incidents_table.insert(
            {
                "title": title,
                "description": description,
                "category": category,
                "status": status,
                "origin": "customer",
                "branch": "central",
                "created_at": created_at,
                "updated_at": now_iso(),
                "seed_duplicate_key": duplicate_key,
            }
        )

        existing_keys.add(duplicate_key)
        inserted += 1

    print(f"Inserted: {inserted}")
    print(f"Skipped: {skipped}")

    if invalid:
        print("Invalid records:")
        for row_number, field, value in invalid:
            print(f"- row {row_number}: {field} -> {value}")


if __name__ == "__main__":
    main()
