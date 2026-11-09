"""Rule and rate baselines used by ids.training lab-compare: thresholds come only from the benign rows given to fit()."""
import numpy as np
import pandas as pd

from ids.features import FEATURE_IDS
from ids.training import RateBaseline, RuleBaseline

FEATURES = [f for f in FEATURE_IDS if f not in ("F25", "F26")]


def table(n=1000, seed=0):
    rng = np.random.RandomState(seed)
    frame = pd.DataFrame(rng.poisson(3, (n, len(FEATURES))).astype(float), columns=FEATURES)
    frame["label"] = "benign"
    return frame


def test_thresholds_come_from_benign_rows_only():
    dev = table()
    attack = dev.iloc[:5].copy()
    attack["F10"], attack["label"] = 10_000, "bruteforce"
    rule = RuleBaseline(FEATURES).fit(pd.concat([dev, attack]))
    assert rule.thresholds["F10"] == RuleBaseline(FEATURES).fit(dev).thresholds["F10"]


def test_rules_assign_the_class_of_the_first_rule_that_fires():
    rule = RuleBaseline(FEATURES).fit(table())
    rows = np.full((3, len(FEATURES)), 0.0)
    rows[0, FEATURES.index("F23")] = rows[0, FEATURES.index("F09")] = 1e6
    rows[1, FEATURES.index("F12")] = 1e6
    score, attack = rule.score(rows)
    assert list(score) == [1.0, 1.0, 0.0]
    assert list(attack[:2]) == ["malformed", "flood"]


def test_rate_baseline_uses_f01_only():
    rate = RateBaseline(FEATURES).fit(table())
    assert set(rate.thresholds) == {"F01"}
    rows = np.zeros((2, len(FEATURES)))
    rows[0, FEATURES.index("F01")] = 1e6
    rows[1, FEATURES.index("F10")] = 1e6
    assert list(rate.score(rows)[0]) == [1.0, 0.0]
