from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "train_sales_forecast.py"
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "trackflow_sales.csv"

spec = spec_from_file_location("train_sales_forecast", SCRIPT_PATH)

if spec is None or spec.loader is None:
    raise ImportError(f"Could not load forecasting script from {SCRIPT_PATH}")

forecast_module = module_from_spec(spec)
spec.loader.exec_module(forecast_module)


def test_sales_data_uses_first_8_years_for_training_and_last_2_for_test():
    df = forecast_module.load_and_prepare_data(DATA_PATH)
    train_df, test_df = forecast_module.split_train_test(df)

    assert len(train_df) == 96
    assert len(test_df) == 24

    assert train_df["month"].min().strftime("%Y-%m") == "2016-01"
    assert train_df["month"].max().strftime("%Y-%m") == "2023-12"

    assert test_df["month"].min().strftime("%Y-%m") == "2024-01"
    assert test_df["month"].max().strftime("%Y-%m") == "2025-12"

    assert train_df["month"].max() < test_df["month"].min()
    assert set(train_df.index).isdisjoint(set(test_df.index))
