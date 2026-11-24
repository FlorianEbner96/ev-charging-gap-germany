"""Expected number of charging points per district, and how well each model predicts it.

Three models are compared with cross validation:
- a baseline: every district gets BEV divided by the national ratio of BEV per charging point
- linear regression on logs (the main model)
- gradient boosting (the comparison model)

The gap of a district is its actual number of charging points compared with the expected number.
The expected number always comes from a model that did not see that district (out of fold).
"""

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer

from ev_gap import config
from ev_gap.pipeline import load_districts

BASELINE = "Baseline ratio"
LINEAR = "Linear regression on logs"
BOOSTING = "Gradient boosting"
GAPS_FILE = config.PROCESSED_DIR / "gaps.csv"


class RatioBaseline(RegressorMixin, BaseEstimator):
    """Expected points = BEV / (BEV per charging point of the training districts).

    The ratio is a number learned from the data. It is computed in fit(), from the training
    districts only, so a test district never influences its own expected value.
    """

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.bev_per_point_ = X["bev"].sum() / y.sum()
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return X["bev"].to_numpy() / self.bev_per_point_


def log_target(regressor) -> TransformedTargetRegressor:
    """Fit on log(points), predict points. A percentage view of the data."""
    return TransformedTargetRegressor(regressor=regressor, func=np.log, inverse_func=np.exp)


def make_models(seed: int = 0) -> dict:
    return {
        BASELINE: RatioBaseline(),
        LINEAR: log_target(make_pipeline(FunctionTransformer(np.log), LinearRegression())),
        BOOSTING: log_target(
            GradientBoostingRegressor(
                n_estimators=200, learning_rate=0.05, max_depth=2, subsample=0.8, random_state=seed
            )
        ),
    }


def score(actual: np.ndarray, expected: np.ndarray) -> dict:
    """Three views of the error. Smaller is better for all of them."""
    actual, expected = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    return {
        "mae_points": np.mean(np.abs(expected - actual)),
        "median_error_pct": np.median(np.abs(expected - actual) / actual) * 100,
        "log_rmse": np.sqrt(np.mean(np.log(expected / actual) ** 2)),
    }


def state_of(districts: pd.DataFrame) -> pd.Series:
    """The first two digits of the district key are the federal state."""
    return districts["key"].str[:2]


def cross_validate(districts: pd.DataFrame, models: dict, splitter, groups=None):
    """Fit every model on the training districts of each fold and predict the held-out districts.

    Returns (out_of_fold, per_fold):
    - out_of_fold: one expected value per district and model, from a model that did not see it
    - per_fold: the error scores of every model in every fold
    """
    X, y = districts[config.FEATURE_COLUMNS], districts[config.TARGET]
    out_of_fold = pd.DataFrame(np.nan, index=districts.index, columns=list(models))
    rows = []
    for fold, (train, test) in enumerate(splitter.split(X, y, groups)):
        for name, model in models.items():
            fitted = clone(model).fit(X.iloc[train], y.iloc[train])
            expected = fitted.predict(X.iloc[test])
            out_of_fold.iloc[test, out_of_fold.columns.get_loc(name)] = expected
            rows.append({"model": name, "fold": fold, **score(y.iloc[test], expected)})
    return out_of_fold, pd.DataFrame(rows)


def summarise(per_fold: pd.DataFrame) -> pd.DataFrame:
    """Mean and standard deviation of every score over the folds."""
    return per_fold.drop(columns="fold").groupby("model").agg(["mean", "std"]).round(3)


def random_folds(n_splits: int = 5, seed: int = 42) -> KFold:
    return KFold(n_splits=n_splits, shuffle=True, random_state=seed)


def add_gap(districts: pd.DataFrame, expected: pd.Series) -> pd.DataFrame:
    """gap_pct: percent above (positive) or below (negative) the expected number of charging points."""
    actual = districts[config.TARGET]
    return pd.DataFrame({
        "gap_pct": (actual - expected) / expected * 100,
        "missing_points": expected - actual,
    })


def build_gap_table(districts: pd.DataFrame, out_of_fold: pd.DataFrame) -> pd.DataFrame:
    table = districts[["key", "name", "bev", "population", config.TARGET]].copy()
    for model in out_of_fold:
        short = {BASELINE: "baseline", LINEAR: "linear", BOOSTING: "boosting"}[model]
        table[f"expected_{short}"] = out_of_fold[model]
        gap = add_gap(districts, out_of_fold[model])
        table[f"gap_pct_{short}"] = gap["gap_pct"]
        table[f"missing_points_{short}"] = gap["missing_points"]
    return table


def run(target=GAPS_FILE) -> pd.DataFrame:
    districts = load_districts()
    models = make_models()

    print("Random 5-fold cross validation")
    out_of_fold, per_fold = cross_validate(districts, models, random_folds())
    print(summarise(per_fold).to_string())

    print("\nCross validation by federal state (whole states are held out)")
    _, per_fold_state = cross_validate(districts, models, GroupKFold(n_splits=5), groups=state_of(districts))
    print(summarise(per_fold_state).to_string())

    gaps = build_gap_table(districts, out_of_fold)
    target.parent.mkdir(parents=True, exist_ok=True)
    gaps.to_csv(target, index=False)
    print(f"\n{len(gaps)} districts written to {target}")
    return gaps


if __name__ == "__main__":
    run()
