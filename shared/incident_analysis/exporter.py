import csv


def export_results_to_csv(results, output_file="results.csv"):
    rows = [
        ["metric", "value"],
        ["total_records", results["total_records"]],
        ["valid_records", results["valid_records"]],
        ["invalid_records", results["invalid_records"]],
    ]

    for key, value in results["invalid_breakdown"].items():
        rows.append([f"invalid_{key}", value])

    for category, data in results["category_breakdown"].items():
        rows.append([f"category_{category}", data["count"]])

    for status, data in results["status_breakdown"].items():
        rows.append([f"status_{status}", data["count"]])

    for country, data in results["country_breakdown"].items():
        rows.append([f"country_{country}", data["count"]])

    rows.append(
        [
            "average_satisfaction_score",
            results["satisfaction"]["average_score"],
        ]
    )

    for score, count in results["satisfaction"]["scores"].items():
        rows.append([f"score_{score}", count])

    with open(output_file, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows(rows)

    return output_file