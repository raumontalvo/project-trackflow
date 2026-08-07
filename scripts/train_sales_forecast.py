from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import TimeSeriesSplit


RANDOM_STATE = 42

DATA_PATH = Path("data/raw/trackflow_sales.csv")
MODEL_PATH = Path("models/trackflow_sales_random_forest.joblib")

FIGURE_PATH = Path("reports/figures/trackflow_sales_forecast.png")
METRICS_PATH = Path("reports/trackflow_sales_metrics.json")

EVALUATION_DIR = Path("data/eval")
LEARNING_CURVE_PATH = EVALUATION_DIR / "learning_curve.png"
EVALUATION_REPORT_PATH = EVALUATION_DIR / "evaluation_report.md"
CV_RESULTS_PATH = EVALUATION_DIR / "cross_validation_results.json"

FEATURE_COLUMNS = [
    "year",
    "month_number",
    "time_index",
    "month_sin",
    "month_cos",
]

TARGET_COLUMN = "revenue_eur"


def create_model() -> RandomForestRegressor:
    """Create the tuned TrackFlow Random Forest regression model."""
    return RandomForestRegressor(
        n_estimators=500,
        max_depth=None,
        min_samples_leaf=1,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )


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

    if (df[TARGET_COLUMN] <= 0).any():
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
            "The dataset must contain every month from "
            "2016-01 through 2025-12."
        )

    # Time-derived features available before forecasting the target month.
    df["year"] = df["month"].dt.year
    df["month_number"] = df["month"].dt.month
    df["time_index"] = np.arange(len(df))

    # Cyclical features preserve the relationship between December and January.
    df["month_sin"] = np.sin(
        2 * np.pi * df["month_number"] / 12
    )
    df["month_cos"] = np.cos(
        2 * np.pi * df["month_number"] / 12
    )

    return df


def split_train_test(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use the first eight years for training and final two years for testing."""
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


def get_time_series_split(
    n_splits: int = 5,
) -> TimeSeriesSplit:
    """
    Return the time-aware cross-validation strategy.

    TimeSeriesSplit uses expanding training windows and never shuffles data.
    """
    if n_splits < 2:
        raise ValueError("Time-series cross-validation requires at least 2 folds.")

    return TimeSeriesSplit(n_splits=n_splits)


def validate_time_series_indices(
    train_indices: np.ndarray,
    validation_indices: np.ndarray,
) -> None:
    """Ensure no future validation observation appears in a training fold."""
    if len(train_indices) == 0 or len(validation_indices) == 0:
        raise ValueError("Training and validation indices cannot be empty.")

    if train_indices.max() >= validation_indices.min():
        raise ValueError(
            "Temporal leakage detected: training observations must occur "
            "before validation observations."
        )


def calculate_regression_metrics(
    y_true: pd.Series | np.ndarray,
    predictions: np.ndarray,
) -> dict[str, float]:
    """Calculate MAE, MSE, RMSE, and R² for regression predictions."""
    mse = mean_squared_error(y_true, predictions)

    return {
        "mae_eur": float(mean_absolute_error(y_true, predictions)),
        "mse_eur_squared": float(mse),
        "rmse_eur": float(np.sqrt(mse)),
        "r2_score": float(r2_score(y_true, predictions)),
    }


def run_time_series_cross_validation(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    n_splits: int = 5,
) -> dict[str, Any]:
    """
    Evaluate model stability with expanding-window time-series validation.

    Returns every fold result and the mean and standard deviation for
    training and validation MAE and RMSE.
    """
    splitter = get_time_series_split(n_splits=n_splits)

    fold_results: list[dict[str, Any]] = []

    for fold_number, (
        fold_train_indices,
        fold_validation_indices,
    ) in enumerate(splitter.split(x_train), start=1):
        validate_time_series_indices(
            fold_train_indices,
            fold_validation_indices,
        )

        fold_x_train = x_train.iloc[fold_train_indices]
        fold_y_train = y_train.iloc[fold_train_indices]

        fold_x_validation = x_train.iloc[fold_validation_indices]
        fold_y_validation = y_train.iloc[fold_validation_indices]

        fold_model = create_model()
        fold_model.fit(fold_x_train, fold_y_train)

        training_predictions = fold_model.predict(fold_x_train)
        validation_predictions = fold_model.predict(fold_x_validation)

        training_mae = mean_absolute_error(
            fold_y_train,
            training_predictions,
        )
        training_rmse = np.sqrt(
            mean_squared_error(
                fold_y_train,
                training_predictions,
            )
        )

        validation_mae = mean_absolute_error(
            fold_y_validation,
            validation_predictions,
        )
        validation_rmse = np.sqrt(
            mean_squared_error(
                fold_y_validation,
                validation_predictions,
            )
        )

        fold_results.append(
            {
                "fold": fold_number,
                "training_rows": int(len(fold_train_indices)),
                "validation_rows": int(len(fold_validation_indices)),
                "training_start_index": int(fold_train_indices.min()),
                "training_end_index": int(fold_train_indices.max()),
                "validation_start_index": int(
                    fold_validation_indices.min()
                ),
                "validation_end_index": int(
                    fold_validation_indices.max()
                ),
                "training_mae_eur": float(training_mae),
                "validation_mae_eur": float(validation_mae),
                "training_rmse_eur": float(training_rmse),
                "validation_rmse_eur": float(validation_rmse),
            }
        )

    training_mae_values = np.array(
        [row["training_mae_eur"] for row in fold_results]
    )
    validation_mae_values = np.array(
        [row["validation_mae_eur"] for row in fold_results]
    )
    training_rmse_values = np.array(
        [row["training_rmse_eur"] for row in fold_results]
    )
    validation_rmse_values = np.array(
        [row["validation_rmse_eur"] for row in fold_results]
    )

    return {
        "n_splits": n_splits,
        "folds": fold_results,
        "summary": {
            "training_mae_mean_eur": float(training_mae_values.mean()),
            "training_mae_std_eur": float(
                training_mae_values.std(ddof=1)
            ),
            "validation_mae_mean_eur": float(
                validation_mae_values.mean()
            ),
            "validation_mae_std_eur": float(
                validation_mae_values.std(ddof=1)
            ),
            "training_rmse_mean_eur": float(
                training_rmse_values.mean()
            ),
            "training_rmse_std_eur": float(
                training_rmse_values.std(ddof=1)
            ),
            "validation_rmse_mean_eur": float(
                validation_rmse_values.mean()
            ),
            "validation_rmse_std_eur": float(
                validation_rmse_values.std(ddof=1)
            ),
        },
    }


def create_learning_curve(
    cross_validation_results: dict[str, Any],
    output_path: Path = LEARNING_CURVE_PATH,
) -> None:
    """
    Create a time-aware learning curve from expanding CV training windows.

    The x-axis is the number of chronological training observations. The
    y-axis shows training and validation RMSE.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    folds = cross_validation_results["folds"]

    training_sizes = [
        fold["training_rows"]
        for fold in folds
    ]
    training_rmse = [
        fold["training_rmse_eur"]
        for fold in folds
    ]
    validation_rmse = [
        fold["validation_rmse_eur"]
        for fold in folds
    ]

    plt.figure(figsize=(10, 6))

    plt.plot(
        training_sizes,
        training_rmse,
        marker="o",
        linewidth=2,
        label="Training RMSE",
    )

    plt.plot(
        training_sizes,
        validation_rmse,
        marker="o",
        linewidth=2,
        label="Validation RMSE",
    )

    plt.title("TrackFlow Time-Aware Learning Curve")
    plt.xlabel("Chronological training observations")
    plt.ylabel("RMSE (EUR)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def diagnose_fit(
    cross_validation_results: dict[str, Any],
    average_training_revenue: float,
) -> dict[str, Any]:
    """
    Diagnose underfitting, overfitting, or reasonable fit using the
    time-aware cross-validation learning-curve results.
    """
    summary = cross_validation_results["summary"]

    training_rmse = summary["training_rmse_mean_eur"]
    validation_rmse = summary["validation_rmse_mean_eur"]
    validation_rmse_std = summary["validation_rmse_std_eur"]

    training_error_ratio = training_rmse / average_training_revenue
    validation_error_ratio = validation_rmse / average_training_revenue

    gap_eur = validation_rmse - training_rmse
    gap_ratio = gap_eur / average_training_revenue

    validation_to_training_ratio = (
        validation_rmse / training_rmse
        if training_rmse > 0
        else float("inf")
    )

    instability_ratio = (
        validation_rmse_std / validation_rmse
        if validation_rmse > 0
        else 0.0
    )

    if (
        training_error_ratio >= 0.15
        and validation_error_ratio >= 0.15
        and validation_to_training_ratio < 1.5
    ):
        diagnosis = "underfitting"
        explanation = (
            "Training and validation RMSE are both high and relatively close. "
            "The model is unable to capture the revenue pattern even on its "
            "training folds."
        )
        recommendation = (
            "Increase useful predictive signal by adding leakage-safe lag "
            "features, specifically revenue_lag_1, revenue_lag_12, and a "
            "rolling 12-month revenue mean. Re-evaluate them with the same "
            "five-fold TimeSeriesSplit before promotion."
        )

    elif (
        validation_to_training_ratio >= 2.0
        or gap_ratio >= 0.05
    ):
        diagnosis = "moderate overfitting with unstable validation performance"
        explanation = (
            "Training RMSE remains much lower than validation RMSE across the "
            "expanding chronological folds. Validation RMSE is more than "
            f"{validation_to_training_ratio:.1f} times training RMSE, and its "
            "variation between folds is substantial. This indicates that the "
            "unrestricted Random Forest is fitting historical detail that "
            "does not generalize reliably to later months."
        )
        recommendation = (
            "Regularize the Random Forest by changing max_depth from None to "
            "8 and min_samples_leaf from 1 to 3. Then rerun the identical "
            "five-fold TimeSeriesSplit and only accept the change if mean "
            "validation RMSE and its standard deviation decrease."
        )

    else:
        diagnosis = "reasonably well fitted"
        explanation = (
            "Training and validation errors are close, remain low relative "
            "to average monthly revenue, and are reasonably stable across "
            "chronological folds."
        )
        recommendation = (
            "Keep the current model configuration and monitor time-aware "
            "validation RMSE as new complete months become available."
        )

    return {
        "diagnosis": diagnosis,
        "explanation": explanation,
        "recommendation": recommendation,
        "training_rmse_percentage_of_average_revenue": float(
            training_error_ratio * 100
        ),
        "validation_rmse_percentage_of_average_revenue": float(
            validation_error_ratio * 100
        ),
        "rmse_gap_eur": float(gap_eur),
        "rmse_gap_percentage_of_average_revenue": float(
            gap_ratio * 100
        ),
        "validation_to_training_rmse_ratio": float(
            validation_to_training_ratio
        ),
        "validation_instability_ratio": float(instability_ratio),
    }
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
        np.quantile(
            expected,
            np.linspace(0, 1, bins + 1),
        )
    )

    if len(breakpoints) < 3:
        return 0.0

    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf

    expected_counts, _ = np.histogram(
        expected,
        bins=breakpoints,
    )
    actual_counts, _ = np.histogram(
        actual,
        bins=breakpoints,
    )

    expected_percent = expected_counts / len(expected)
    actual_percent = actual_counts / len(actual)

    epsilon = 1e-6

    expected_percent = np.clip(
        expected_percent,
        epsilon,
        None,
    )
    actual_percent = np.clip(
        actual_percent,
        epsilon,
        None,
    )

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

    def gini(
        actual: np.ndarray,
        predicted: np.ndarray,
    ) -> float:
        order = np.lexsort(
            (
                np.arange(len(predicted)),
                -predicted,
            )
        )

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

    return float(
        gini(y_true, y_pred) / perfect_gini
    )


def prediction_interval(
    model: RandomForestRegressor,
    x_test: pd.DataFrame,
    lower_percentile: float = 10,
    upper_percentile: float = 90,
) -> tuple[np.ndarray, np.ndarray]:
    """Create a variability range using predictions from individual trees."""
    x_test_values = x_test.to_numpy()

    tree_predictions = np.array(
        [
            tree.predict(x_test_values)
            for tree in model.estimators_
        ]
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
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    plt.figure(figsize=(12, 6))

    plt.plot(
        test_df["month"],
        test_df[TARGET_COLUMN],
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

    plt.title(
        "TrackFlow Sales Forecast: Actual vs Predicted Revenue"
    )
    plt.xlabel("Month")
    plt.ylabel("Revenue (EUR)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def create_evaluation_report(
    cross_validation_results: dict[str, Any],
    fit_diagnosis: dict[str, Any],
    final_metrics: dict[str, float],
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    output_path: Path = EVALUATION_REPORT_PATH,
) -> None:
    """Write the formal TrackFlow technical evaluation report."""
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary = cross_validation_results["summary"]

    report = f"""# TrackFlow Sales Forecast Model Evaluation

## Executive conclusion

The TrackFlow Random Forest model is diagnosed as **{fit_diagnosis["diagnosis"]}**.

{fit_diagnosis["explanation"]}

## Data and evaluation design

- Target variable: `revenue_eur`
- Training period: {train_df["month"].min().strftime("%Y-%m")} through {train_df["month"].max().strftime("%Y-%m")}
- Final test period: {test_df["month"].min().strftime("%Y-%m")} through {test_df["month"].max().strftime("%Y-%m")}
- Training observations: {len(train_df)}
- Final test observations: {len(test_df)}
- Cross-validation strategy: `TimeSeriesSplit(n_splits=5)`
- Data shuffling: none
- Temporal leakage rule: the final training index must be earlier than the first validation index in every fold

The final two years remain outside cross-validation and are used only as the final holdout test set.

## Time-aware cross-validation results

### Mean absolute error

- Training MAE: €{summary["training_mae_mean_eur"]:,.2f} ± €{summary["training_mae_std_eur"]:,.2f}
- Validation MAE: €{summary["validation_mae_mean_eur"]:,.2f} ± €{summary["validation_mae_std_eur"]:,.2f}

### Root mean squared error

- Training RMSE: €{summary["training_rmse_mean_eur"]:,.2f} ± €{summary["training_rmse_std_eur"]:,.2f}
- Validation RMSE: €{summary["validation_rmse_mean_eur"]:,.2f} ± €{summary["validation_rmse_std_eur"]:,.2f}

The average training RMSE represents {fit_diagnosis["training_rmse_percentage_of_average_revenue"]:.2f}% of average training revenue. The average validation RMSE represents {fit_diagnosis["validation_rmse_percentage_of_average_revenue"]:.2f}% of average training revenue.

The mean validation-to-training RMSE gap is €{fit_diagnosis["rmse_gap_eur"]:,.2f}, or {fit_diagnosis["rmse_gap_percentage_of_average_revenue"]:.2f}% of average training revenue.

## Learning-curve interpretation

The learning curve is saved at:

`data/eval/learning_curve.png`

It plots training and validation RMSE as the chronological training window expands. The diagnosis is based on both the absolute error levels and the gap between the two curves.

## Final holdout-test performance

- MAE: €{final_metrics["mae_eur"]:,.2f}
- MSE: €{final_metrics["mse_eur_squared"]:,.2f} EUR²
- RMSE: €{final_metrics["rmse_eur"]:,.2f}
- RMSE as percentage of average test revenue: {final_metrics["rmse_percentage_of_average_monthly_revenue"]:.2f}%
- PSI: {final_metrics["psi"]:.4f}
- Normalized Gini: {final_metrics["normalized_gini"]:.4f}
- R²: {final_metrics["r2_score"]:.4f}

## Metric selection

**RMSE is the primary business metric.**

TrackFlow experiences sharp November and December revenue peaks caused by Black Friday and holiday shipping. A large forecasting error during one of these months can create disproportionate warehouse-capacity, staffing, and carrier-planning problems. RMSE penalizes large errors more heavily than MAE and therefore reflects this risk.

MAE is retained as a secondary metric because it communicates the model's typical monthly forecasting error directly in euros.

## Corrective action

{fit_diagnosis["recommendation"]}

This recommendation is specific to the observed learning-curve and cross-validation pattern. It should be evaluated using the same chronological folds before any model is promoted to staging.
"""

    output_path.write_text(
        report,
        encoding="utf-8",
    )


def save_cross_validation_results(
    cross_validation_results: dict[str, Any],
    output_path: Path = CV_RESULTS_PATH,
) -> None:
    """Save detailed cross-validation results as JSON."""
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            cross_validation_results,
            file,
            indent=2,
        )


def train_and_evaluate() -> dict[str, Any]:
    """Train, evaluate, save, and visualize the TrackFlow forecast model."""
    df = load_and_prepare_data()
    train_df, test_df = split_train_test(df)

    x_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN]

    x_test = test_df[FEATURE_COLUMNS]
    y_test = test_df[TARGET_COLUMN]

    # Evaluate stability using only the original training period.
    cross_validation_results = run_time_series_cross_validation(
        x_train=x_train,
        y_train=y_train,
        n_splits=5,
    )

    create_learning_curve(
        cross_validation_results
    )

    average_training_revenue = float(
        y_train.mean()
    )

    fit_diagnosis = diagnose_fit(
        cross_validation_results=cross_validation_results,
        average_training_revenue=average_training_revenue,
    )

    save_cross_validation_results(
        cross_validation_results
    )

    # Train the final model using all eight training years.
    model = create_model()
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)

    final_metrics = calculate_regression_metrics(
        y_true=y_test,
        predictions=predictions,
    )

    mean_monthly_revenue = float(
        y_test.mean()
    )

    rmse_percentage = (
        final_metrics["rmse_eur"]
        / mean_monthly_revenue
    ) * 100

    psi = population_stability_index(
        y_train.to_numpy(),
        y_test.to_numpy(),
    )

    gini = normalized_gini(
        y_test.to_numpy(),
        predictions,
    )

    lower, upper = prediction_interval(
        model,
        x_test,
    )

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    METRICS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(
        {
            "model": model,
            "features": FEATURE_COLUMNS,
            "random_state": RANDOM_STATE,
            "train_period": [
                str(
                    train_df["month"].min().date()
                ),
                str(
                    train_df["month"].max().date()
                ),
            ],
            "test_period": [
                str(
                    test_df["month"].min().date()
                ),
                str(
                    test_df["month"].max().date()
                ),
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

    metrics: dict[str, Any] = {
        "mae_eur": final_metrics["mae_eur"],
        "mse_eur_squared": final_metrics["mse_eur_squared"],
        "rmse_eur": final_metrics["rmse_eur"],
        "rmse_percentage_of_average_monthly_revenue": float(
            rmse_percentage
        ),
        "psi": float(psi),
        "normalized_gini": float(gini),
        "r2_score": final_metrics["r2_score"],
        "assignment_k2_note": (
            "The assignment requests K2 Score but does not define it; "
            "standard R² is reported instead."
        ),
        "average_test_monthly_revenue_eur": mean_monthly_revenue,
        "average_training_monthly_revenue_eur": average_training_revenue,
        "training_rows": len(train_df),
        "test_rows": len(test_df),
        "cross_validation": cross_validation_results,
        "fit_diagnosis": fit_diagnosis,
    }

    with METRICS_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metrics,
            file,
            indent=2,
        )

    create_evaluation_report(
        cross_validation_results=cross_validation_results,
        fit_diagnosis=fit_diagnosis,
        final_metrics={
            "mae_eur": final_metrics["mae_eur"],
            "mse_eur_squared": final_metrics["mse_eur_squared"],
            "rmse_eur": final_metrics["rmse_eur"],
            "rmse_percentage_of_average_monthly_revenue": float(
                rmse_percentage
            ),
            "psi": float(psi),
            "normalized_gini": float(gini),
            "r2_score": final_metrics["r2_score"],
        },
        train_df=train_df,
        test_df=test_df,
    )

    return metrics


if __name__ == "__main__":
    results = train_and_evaluate()

    cv_summary = results["cross_validation"]["summary"]
    diagnosis = results["fit_diagnosis"]

    print("\nTrackFlow sales forecasting results")
    print("=" * 50)

    print("\nFinal 2024–2025 holdout test")
    print("-" * 50)
    print(f"MAE: €{results['mae_eur']:,.2f}")
    print(f"MSE: €{results['mse_eur_squared']:,.2f} EUR²")
    print(f"RMSE: €{results['rmse_eur']:,.2f}")
    print(
        "RMSE as % of average monthly revenue: "
        f"{results['rmse_percentage_of_average_monthly_revenue']:.2f}%"
    )
    print(f"PSI: {results['psi']:.4f}")
    print(
        "Normalized Gini: "
        f"{results['normalized_gini']:.4f}"
    )
    print(f"R² score: {results['r2_score']:.4f}")

    print("\nFive-fold time-series cross-validation")
    print("-" * 50)
    print(
        "Validation MAE: "
        f"€{cv_summary['validation_mae_mean_eur']:,.2f} "
        f"± €{cv_summary['validation_mae_std_eur']:,.2f}"
    )
    print(
        "Validation RMSE: "
        f"€{cv_summary['validation_rmse_mean_eur']:,.2f} "
        f"± €{cv_summary['validation_rmse_std_eur']:,.2f}"
    )

    print("\nTechnical diagnosis")
    print("-" * 50)
    print(
        f"Diagnosis: {diagnosis['diagnosis']}"
    )
    print(
        f"Recommendation: {diagnosis['recommendation']}"
    )

    print("\nSaved outputs")
    print("-" * 50)
    print(f"Model: {MODEL_PATH}")
    print(f"Metrics: {METRICS_PATH}")
    print(f"Forecast chart: {FIGURE_PATH}")
    print(f"Learning curve: {LEARNING_CURVE_PATH}")
    print(f"Cross-validation results: {CV_RESULTS_PATH}")
    print(f"Evaluation report: {EVALUATION_REPORT_PATH}")