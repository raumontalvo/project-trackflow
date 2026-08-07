from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "train_sales_forecast.py"

spec = spec_from_file_location("train_sales_forecast", SCRIPT_PATH)

if spec is None or spec.loader is None:
    raise ImportError(
        f"Could not load forecasting script from {SCRIPT_PATH}"
    )

forecast_module = module_from_spec(spec)
spec.loader.exec_module(forecast_module)


def test_time_series_split_never_uses_future_data_for_training():
    observations = np.arange(96)
    splitter = forecast_module.get_time_series_split(n_splits=5)

    folds_checked = 0

    for train_indices, validation_indices in splitter.split(observations):
        assert len(train_indices) > 0
        assert len(validation_indices) > 0

        assert train_indices.max() < validation_indices.min()
        assert set(train_indices).isdisjoint(set(validation_indices))

        folds_checked += 1

    assert folds_checked == 5
