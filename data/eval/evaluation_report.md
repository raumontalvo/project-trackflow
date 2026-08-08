# TrackFlow Sales Forecast Model Evaluation

## Executive conclusion

The TrackFlow Random Forest model is diagnosed as **moderate overfitting with unstable validation performance**.

Training RMSE remains much lower than validation RMSE across the expanding chronological folds. Validation RMSE is more than 4.1 times training RMSE, and its variation between folds is substantial. This indicates that the unrestricted Random Forest is fitting historical detail that does not generalize reliably to later months.

## Data and evaluation design

- Target variable: `revenue_eur`
- Training period: 2016-01 through 2023-12
- Final test period: 2024-01 through 2025-12
- Training observations: 96
- Final test observations: 24
- Cross-validation strategy: `TimeSeriesSplit(n_splits=5)`
- Data shuffling: none
- Temporal leakage rule: the final training index must be earlier than the first validation index in every fold

The final two years remain outside cross-validation and are used only as the final holdout test set.

## Time-aware cross-validation results

### Mean absolute error

- Training MAE: €15,245.81 ± €2,397.02
- Validation MAE: €66,111.64 ± €27,610.94

### Root mean squared error

- Training RMSE: €19,360.97 ± €3,388.60
- Validation RMSE: €79,196.30 ± €29,460.65

The average training RMSE represents 1.98% of average training revenue. The average validation RMSE represents 8.12% of average training revenue.

The mean validation-to-training RMSE gap is €59,835.33, or 6.13% of average training revenue.

## Learning-curve interpretation

The learning curve is saved at:

`data/eval/learning_curve.png`

It plots training and validation RMSE as the chronological training window expands. The diagnosis is based on both the absolute error levels and the gap between the two curves.

## Final holdout-test performance

- MAE: €93,074.33
- MSE: €13,748,377,032.89 EUR²
- RMSE: €117,253.47
- RMSE as percentage of average test revenue: 9.03%
- PSI: 9.3133
- Normalized Gini: 0.6458
- R²: 0.5303

## Metric selection

**RMSE is the primary business metric.**

TrackFlow experiences sharp November and December revenue peaks caused by Black Friday and holiday shipping. A large forecasting error during one of these months can create disproportionate warehouse-capacity, staffing, and carrier-planning problems. RMSE penalizes large errors more heavily than MAE and therefore reflects this risk.

MAE is retained as a secondary metric because it communicates the model's typical monthly forecasting error directly in euros.

## Corrective action

Regularize the Random Forest by changing max_depth from None to 8 and min_samples_leaf from 1 to 3. Then rerun the identical five-fold TimeSeriesSplit and only accept the change if mean validation RMSE and its standard deviation decrease.

This recommendation is specific to the observed learning-curve and cross-validation pattern. It should be evaluated using the same chronological folds before any model is promoted to staging.
