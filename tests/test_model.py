import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import GroupKFold

from ev_gap import config
from ev_gap.model import (
    BASELINE, BOOSTING, LINEAR, RatioBaseline, add_gap, cross_validate, make_models,
    random_folds, score, state_of,
)


@pytest.fixture
def districts() -> pd.DataFrame:
    """60 made-up districts in 6 states. Points follow a known power law of BEV and population."""
    rng = np.random.default_rng(0)
    n = 60
    bev = rng.integers(500, 20_000, n).astype(float)
    population = rng.integers(40_000, 600_000, n).astype(float)
    area = rng.integers(100, 3000, n).astype(float)
    points = 0.4 * bev**0.5 * population**0.5 / 30 * np.exp(rng.normal(0, 0.1, n))
    return pd.DataFrame({
        "key": [f"{i % 6 + 1:02d}{i:03d}" for i in range(n)],
        "name": [f"District {i}" for i in range(n)],
        "bev": bev,
        "population": population,
        "density": population / area,
        "charging_points": points.round().clip(min=1).astype(int),
    })


def test_baseline_learns_its_ratio_from_the_training_districts_only(districts):
    train, test = districts.iloc[:40], districts.iloc[40:]
    baseline = RatioBaseline().fit(train[config.FEATURE_COLUMNS], train[config.TARGET])
    assert baseline.bev_per_point_ == pytest.approx(train["bev"].sum() / train["charging_points"].sum())

    # changing the test districts must not change the predictions
    changed = test.assign(charging_points=test["charging_points"] * 10)
    again = RatioBaseline().fit(train[config.FEATURE_COLUMNS], train[config.TARGET])
    assert again.predict(changed[config.FEATURE_COLUMNS]).tolist() == baseline.predict(test[config.FEATURE_COLUMNS]).tolist()


def test_linear_model_on_logs_finds_a_known_power_law(districts):
    X, y = districts[config.FEATURE_COLUMNS], districts[config.TARGET]
    model = make_models()[LINEAR].fit(X, y)
    typical_error = np.median(np.abs(model.predict(X) - y) / y)
    assert typical_error < 0.15


def test_models_never_predict_negative_points(districts):
    X, y = districts[config.FEATURE_COLUMNS], districts[config.TARGET]
    for model in make_models().values():
        assert (model.fit(X, y).predict(X) > 0).all()


def test_every_district_gets_one_out_of_fold_prediction(districts):
    out_of_fold, per_fold = cross_validate(districts, make_models(), random_folds())
    assert out_of_fold.notna().all().all()
    assert set(out_of_fold.columns) == {BASELINE, LINEAR, BOOSTING}
    assert len(per_fold) == 5 * 3  # 5 folds, 3 models


def test_a_district_does_not_influence_its_own_expected_value(districts):
    """If the target of one district is changed, its own out-of-fold prediction must stay the same."""
    models = {LINEAR: make_models()[LINEAR], BASELINE: make_models()[BASELINE]}
    before, _ = cross_validate(districts, models, random_folds())
    changed = districts.copy()
    changed.loc[7, "charging_points"] = 100_000
    after, _ = cross_validate(changed, models, random_folds())
    assert after.loc[7].tolist() == pytest.approx(before.loc[7].tolist())


def test_folds_by_state_keep_whole_states_together(districts):
    states = state_of(districts)
    for train, test in GroupKFold(n_splits=3).split(districts, groups=states):
        assert not set(states.iloc[train]) & set(states.iloc[test])


def test_gap_is_negative_when_a_district_has_fewer_points_than_expected():
    districts = pd.DataFrame({"charging_points": [80, 150]})
    gap = add_gap(districts, pd.Series([100.0, 100.0]))
    assert gap["gap_pct"].tolist() == [-20.0, 50.0]
    assert gap["missing_points"].tolist() == [20.0, -50.0]


def test_score_is_zero_for_a_perfect_prediction():
    perfect = score([100, 200, 300], [100, 200, 300])
    assert perfect == {"mae_points": 0.0, "median_error_pct": 0.0, "log_rmse": 0.0}
