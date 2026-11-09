"""Rule and rate baselines (SG-05). numpy only, so the API can replay them without the offline stack."""
import numpy as np

BENIGN = "benign"


class RuleBaseline:
    """Hand-written per-class rules. Each threshold is a high quantile of dev benign windows, so no test data sets it."""
    RULES = (("malformed", "F23"), ("bruteforce", "F10"), ("lowrate", "F22"), ("flood", "F09"), ("flood", "F12"))

    def __init__(self, features, quantile=0.999):
        self.features, self.quantile, self.thresholds = list(features), quantile, {}

    def fit(self, table):
        benign = table[table.label == BENIGN]
        self.thresholds = {f: float(benign[f].quantile(self.quantile)) for _, f in self.RULES}
        return self

    @classmethod
    def from_thresholds(cls, features, thresholds):
        rule = cls(features)
        missing = {f for _, f in cls.RULES} - set(thresholds)
        if missing:
            raise ValueError(f"thresholds missing for {sorted(missing)}")
        rule.thresholds = {f: float(thresholds[f]) for _, f in cls.RULES}
        return rule

    def score(self, X):
        score, attack = np.zeros(len(X)), np.full(len(X), "flood", dtype=object)
        for cls, f in reversed(self.RULES):  # the first rule in RULES wins when several fire
            fired = X[:, self.features.index(f)] > self.thresholds[f]
            score[fired], attack[fired] = 1.0, cls
        return score, attack


class RateBaseline(RuleBaseline):
    """One feature, packets to the broker per window (F01): the simplest rate detector. Persistence comes from the shared k=2 alert policy."""
    RULES = (("flood", "F01"),)
