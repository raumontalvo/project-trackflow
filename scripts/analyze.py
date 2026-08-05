import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.incident_analysis.analyzer import analyze_csv
from shared.incident_analysis.exporter import export_results_to_csv


def print_report(results, source_file):
    print("=" * 60)
    print("TRACKFLOW — INCIDENT REPORT ANALYSIS")
    print(f"Source file: {source_file}")
    print("=" * 60)

    print()
    print(f"TOTAL RECORDS IN FILE .......... {results['total_records']}")
    print(f"  ├─ Valid records .............. {results['valid_records']}")
    print(f"  └─ Invalid / incomplete ....... {results['invalid_records']}")

    print()
    print("INVALID RECORDS BREAKDOWN")

    invalid_labels = {
        "invalid_tracking_number": "Invalid tracking number",
        "invalid_carrier": "Carrier/country mismatch",
        "invalid_category": "Invalid or missing category",
        "invalid_email": "Invalid or missing email",
        "closed_no_score": "Closed incident, no score",
    }

    for key, label in invalid_labels.items():
        count = results["invalid_breakdown"].get(key, 0)
        print(f"  ├─ {label:<30} {count}")

    print()
    print("BREAKDOWN BY CATEGORY (valid records)")

    for category, data in results["category_breakdown"].items():
        print(f"  ├─ {category:<25} {data['count']:>3} ({data['percentage']}%)")

    print()
    print("BREAKDOWN BY STATUS (valid records)")

    for status, data in results["status_breakdown"].items():
        print(f"  ├─ {status:<25} {data['count']:>3} ({data['percentage']}%)")

    print()
    print("BREAKDOWN BY COUNTRY (valid records)")

    for country, data in results["country_breakdown"].items():
        print(f"  ├─ {country:<25} {data['count']:>3} ({data['percentage']}%)")

    print()
    print("SATISFACTION INDEX (closed incidents)")

    satisfaction = results["satisfaction"]

    print(
        f"  Scored incidents: {satisfaction['scored_incidents']} "
        f"of {satisfaction['closed_incidents']}"
    )
    print(f"  Average score: {satisfaction['average_score']:.2f} / 5.00")

    score_labels = {
        1: "Very dissatisfied",
        2: "Dissatisfied",
        3: "Neutral",
        4: "Satisfied",
        5: "Very satisfied",
    }

    for score, count in satisfaction["scores"].items():
        print(f"  ├─ Score {score} ({score_labels[score]}) .... {count}")

    print()
    print("=" * 60)


def main():
    if len(sys.argv) != 2:
        print("Usage:")
        print("python scripts/analyze.py scripts/incidents-trackflow.csv")
        sys.exit(1)

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)

    try:
        results = analyze_csv(file_path)
    except Exception as error:
        print(f"Error analyzing file: {error}")
        sys.exit(1)

    print_report(results, os.path.basename(file_path))

    export_choice = input("Export results to CSV? [y / n]: ").strip().lower()

    if export_choice == "y":
        output_file = export_results_to_csv(results)
        print(f"Results exported to {output_file}")


if __name__ == "__main__":
    main()