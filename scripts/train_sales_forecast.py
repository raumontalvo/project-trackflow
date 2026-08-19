from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score


RANDOM_STATE = 42
DATA_PATH = Path("data/raw/trackflow_sales.csv")
MODEL_PATH = Path("models/trackflow_sales_random_forest.joblib")
FIGURE_PATH = Path("reports/figures/trackflow_sales_forecast.png")
METRICS_PATH = Path("reports/trackflow_sales_metrics.json")

FEATURE_COLUMNS = [
    "year",
    "month_number",
    "time_index",
    "month_sin",
    "month_cos",
]


def load_and_prepare_data(path: Path = DATA_PATH) -> pd.DataFrame:
    """Load and validate TrackFlow's monthly consolidated revenue data."""
    df = pd.read_csv(path)

    required_columns = {
        "month",
        "revenue_eur",
        "shipments_processed",
        "avg_revenue_per_shipment_eur",
        "market",
    }
    missing_columns = required_columns.difference(df.columns)

    if missing_columns:
        raise ValueError(
            f"Dataset is missing required columns: {sorted(missing_columns)}"
        )

    df["month"] = pd.to_datetime(df["month"], errors="raise")
    df["market"] = df["market"].astype(str).str.lower().str.strip()
    df = df[df["market"] == "consolidated"].copy()
    df = df.sort_values("month").reset_index(drop=True)

    if df.empty:
        raise ValueError("No consolidated rows were found in the dataset.")

    if df.isna().any().any():
        raise ValueError("Dataset contains missing values.")

    if (df["revenue_eur"] <= 0).any():
        raise ValueError("All revenue_eur values must be positive.")

    expected_months = pd.date_range(
        start="2016-01-01",
        end="2025-12-01",
        freq="MS",
    )

    if len(df) != 120:
        raise ValueError(
            f"Expected 120 consolidated monthly rows, but found {len(df)}."
        )

    if not df["month"].reset_index(drop=True).equals(
        pd.Series(expected_months, name="month")
    ):
        raise ValueError(
            "The dataset must contain every month from 2016-01 through 2025-12."
        )

    df["year"] = df["month"].dt.year
    df["month_number"] = df["month"].dt.month
    df["time_index"] = np.arange(len(df))
    df["month_sin"] = np.sin(2 * np.pi * df["month_number"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month_number"] / 12)

    return df


def split_train_test(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use the first 8 years for training and the final 2 years for testing."""
    train_df = df[df["month"] < "2024-01-01"].copy()
    test_df = df[df["month"] >= "2024-01-01"].copy()

    if len(train_df) != 96:
        raise ValueError(
            f"Expected 96 training rows, but found {len(train_df)}."
        )

    if len(test_df) != 24:
        raise ValueError(
            f"Expected 24 test rows, but found {len(test_df)}."
        )

    if train_df["month"].max() >= test_df["month"].min():
        raise ValueError("Training and test periods overlap.")

    return train_df, test_df


def population_stability_index(
    expected: np.ndarray,
    actual: np.ndarray,
    bins: int = 10,
) -> float:
    """
    Calculate PSI between training and test revenue distributions.

    Values below 0.10 usually suggest little distribution shift.
    Values from 0.10 to 0.25 suggest moderate shift.
    Values above 0.25 suggest substantial shift.
    """
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)

    breakpoints = np.unique(
        np.quantile(expected, np.linspace(0, 1, bins + 1))
    )

    if len(breakpoints) < 3:
        return 0.0

    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf

    expected_counts, _ = np.histogram(expected, bins=breakpoints)
    actual_counts, _ = np.histogram(actual, bins=breakpoints)

    expected_percent = expected_counts / len(expected)
    actual_percent = actual_counts / len(actual)

    epsilon = 1e-6
    expected_percent = np.clip(expected_percent, epsilon, None)
    actual_percent = np.clip(actual_percent, epsilon, None)

    psi = np.sum(
        (actual_percent - expected_percent)
        * np.log(actual_percent / expected_percent)
    )

    return float(psi)


def normalized_gini(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> float:
    """
    Calculate normalized Gini for regression ranking quality.

    A score near 1 means predicted rankings closely match actual rankings.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    def gini(actual: np.ndarray, predicted: np.ndarray) -> float:
        order = np.lexsort((np.arange(len(predicted)), -predicted))
        sorted_actual = actual[order]

        total_actual = sorted_actual.sum()
        if total_actual == 0:
            return 0.0

        cumulative_actual = np.cumsum(sorted_actual)
        gini_sum = cumulative_actual.sum() / total_actual
        gini_sum -= (len(actual) + 1) / 2

        return gini_sum / len(actual)

    perfect_gini = gini(y_true, y_true)

    if perfect_gini == 0:
        return 0.0

    return float(gini(y_true, y_pred) / perfect_gini)


def prediction_interval(
    model: RandomForestRegressor,
    x_test: pd.DataFrame,
    lower_percentile: float = 10,
    upper_percentile: float = 90,
) -> tuple[np.ndarray, np.ndarray]:
    """Create a variability range using predictions from individual trees."""
    x_test_values = x_test.to_numpy()
    tree_predictions = np.array(
        [tree.predict(x_test_values) for tree in model.estimators_]
    )

    lower = np.percentile(
        tree_predictions,
        lower_percentile,
        axis=0,
    )
    upper = np.percentile(
        tree_predictions,
        upper_percentile,
        axis=0,
    )

    return lower, upper


def create_forecast_plot(
    test_df: pd.DataFrame,
    predictions: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    output_path: Path = FIGURE_PATH,
) -> None:
    """Save actual revenue, forecast, and variability range."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(12, 6))
    plt.plot(
        test_df["month"],
        test_df["revenue_eur"],
        marker="o",
        label="Actual revenue",
    )
    plt.plot(
        test_df["month"],
        predictions,
        marker="o",
        label="Predicted revenue",
    )
    plt.fill_between(
        test_df["month"],
        lower,
        upper,
        alpha=0.25,
        label="10th–90th percentile variability range",
    )

    plt.title("TrackFlow Sales Forecast: Actual vs Predicted Revenue")
    plt.xlabel("Month")
    plt.ylabel("Revenue (EUR)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def train_and_evaluate() -> dict[str, float]:
    """Train, evaluate, save, and visualize the TrackFlow forecast model."""
    df = load_and_prepare_data()
    train_df, test_df = split_train_test(df)

    x_train = train_df[FEATURE_COLUMNS]
    y_train = train_df["revenue_eur"]

    x_test = test_df[FEATURE_COLUMNS]
    y_test = test_df["revenue_eur"]

    model = RandomForestRegressor(
        n_estimators=500,
        max_depth=None,
        min_samples_leaf=1,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    model.fit(x_train, y_train)
    predictions = model.predict(x_test)

    mse = mean_squared_error(y_test, predictions)
    rmse = float(np.sqrt(mse))
    mean_monthly_revenue = float(y_test.mean())
    rmse_percentage = (rmse / mean_monthly_revenue) * 100
    psi = population_stability_index(
        y_train.to_numpy(),
        y_test.to_numpy(),
    )
    gini = normalized_gini(
        y_test.to_numpy(),
        predictions,
    )

    # The assignment requests a "K2 Score" but does not define it.
    # We report standard R² as the regression goodness-of-fit score.
    r2 = r2_score(y_test, predictions)

    lower, upper = prediction_interval(model, x_test)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(
        {
            "model": model,
            "features": FEATURE_COLUMNS,
            "random_state": RANDOM_STATE,
            "train_period": [
                str(train_df["month"].min().date()),
                str(train_df["month"].max().date()),
            ],
            "test_period": [
                str(test_df["month"].min().date()),
                str(test_df["month"].max().date()),
            ],
        },
        MODEL_PATH,
    )

    create_forecast_plot(
        test_df=test_df,
        predictions=predictions,
        lower=lower,
        upper=upper,
    )

    metrics = {
        "mse_eur_squared": float(mse),
        "rmse_eur": rmse,
        "rmse_percentage_of_average_monthly_revenue": float(
            rmse_percentage
        ),
        "psi": float(psi),
        "normalized_gini": float(gini),
        "r2_score": float(r2),
        "assignment_k2_note": (
            "The assignment requests K2 Score but does not define it; "
            "standard R² is reported instead."
        ),
        "average_test_monthly_revenue_eur": mean_monthly_revenue,
        "training_rows": len(train_df),
        "test_rows": len(test_df),
    }

    with METRICS_PATH.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)

    return metrics


if __name__ == "__main__":
    results = train_and_evaluate()

    print("\nTrackFlow sales forecasting results")
    print("=" * 40)
    print(f"MSE: €{results['mse_eur_squared']:,.2f}²")
    print(f"RMSE: €{results['rmse_eur']:,.2f}")
    print(
        "RMSE as % of average monthly revenue: "
        f"{results['rmse_percentage_of_average_monthly_revenue']:.2f}%"
    )
    print(f"PSI: {results['psi']:.4f}")
    print(f"Normalized Gini: {results['normalized_gini']:.4f}")
    print(f"R² score: {results['r2_score']:.4f}")
    print(
        "K2 note: the assignment does not define K2, "
        "so standard R² is reported."
    )
    print(f"\nModel saved to: {MODEL_PATH}")
    print(f"Metrics saved to: {METRICS_PATH}")
    print(f"Forecast chart saved to: {FIGURE_PATH}")
