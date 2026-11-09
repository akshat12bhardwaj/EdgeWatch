"""Loads a versioned model bundle and scores one window at a time. Refuses any mismatch (ADR-11) instead of guessing."""
import json
from pathlib import Path

from .features import EXTRACTOR_VERSION, FEATURE_IDS

BENIGN = "benign"


class ModelRefused(RuntimeError):
    """The model bundle cannot be used safely. The IDS keeps running without inference when this happens."""


def _tree_contributions(model, x, class_index):
    """Decision-path contribution per feature (MODEL_EVALUATION section 6), summed over trees, for the predicted class."""
    trees = getattr(model, "estimators_", None)
    trees = [model] if trees is None else list(trees)
    contributions = [0.0] * len(x)
    for tree in trees:
        t = tree.tree_
        node = 0
        value = t.value[node][0] / t.value[node][0].sum()
        while t.children_left[node] != -1:
            feature = t.feature[node]
            node = t.children_left[node] if x[feature] <= t.threshold[node] else t.children_right[node]
            child = t.value[node][0] / t.value[node][0].sum()
            contributions[feature] += child[class_index] - value[class_index]
            value = child
    return [c / len(trees) for c in contributions]


class Detector:
    def __init__(self, bundle_dir):
        bundle_dir = Path(bundle_dir)
        card_path, model_path = bundle_dir / "model_card.json", bundle_dir / "model.joblib"
        if not card_path.exists() or not model_path.exists():
            raise ModelRefused("model bundle is missing")
        try:
            self.card = json.loads(card_path.read_text())
            import joblib
            import sklearn
            for key in ("model_id", "extractor_version", "feature_ids", "tau", "classes", "sklearn_version"):
                if key not in self.card:
                    raise ModelRefused(f"model card has no {key}")
            if self.card["extractor_version"] != EXTRACTOR_VERSION:
                raise ModelRefused("model was trained on another extractor version")
            if not set(self.card["feature_ids"]) <= set(FEATURE_IDS):  # columns are then looked up by name, so order cannot go wrong
                raise ModelRefused("model feature list does not match the extractor")
            if self.card["sklearn_version"] != sklearn.__version__:
                raise ModelRefused("model was saved by another scikit-learn version")
            self.model = joblib.load(model_path)
        except ModelRefused:
            raise
        except Exception as error:  # a corrupt file can raise almost anything from unpickling
            raise ModelRefused(f"model bundle could not be loaded: {type(error).__name__}") from None
        self.columns = [FEATURE_IDS.index(f) for f in self.card["feature_ids"]]
        self.classes = list(self.model.classes_)
        if BENIGN not in self.classes:
            raise ModelRefused("model has no benign class")
        self.benign_index = self.classes.index(BENIGN)
        self.tau = float(self.card["tau"])
        self.medians = self.card.get("benign_medians", {})

    @property
    def model_id(self):
        return self.card["model_id"]

    def score(self, features):
        """(best attack class, score) where score = 1 - P(benign), or ('benign', score) when no attack class outranks it."""
        import numpy as np
        x = np.asarray([[features[i] for i in self.columns]], dtype=float)
        probabilities = self.model.predict_proba(x)[0]
        score = float(1 - probabilities[self.benign_index])
        attack = max((i for i in range(len(self.classes)) if i != self.benign_index), key=lambda i: probabilities[i])
        return self.classes[attack], score

    def explain(self, features, predicted_class, top=5):
        """Top features by what the model weighted. It is not proof of an attack."""
        x = [features[i] for i in self.columns]
        estimator = self.model.steps[-1][1] if hasattr(self.model, "steps") else self.model
        index = self.classes.index(predicted_class)
        if hasattr(estimator, "tree_") or (hasattr(estimator, "estimators_") and hasattr(getattr(estimator, "estimators_")[0], "tree_")):
            contributions = _tree_contributions(estimator, x, index)
        elif hasattr(estimator, "coef_"):
            scaled = self.model[:-1].transform([x])[0] if hasattr(self.model, "steps") else x
            row = estimator.coef_[index if estimator.coef_.shape[0] > 1 else 0]
            contributions = [float(c * v) for c, v in zip(row, scaled)]
        else:  # boosting: score drop when one feature is set to its benign median
            base = self.score(features)[1]
            contributions = []
            for position, i in enumerate(self.columns):
                changed = list(features)
                changed[i] = self.medians.get(FEATURE_IDS[i], 0.0)
                contributions.append(base - self.score(changed)[1])
        order = sorted(range(len(x)), key=lambda i: abs(contributions[i]), reverse=True)[:top]
        return [{"feature": self.card["feature_ids"][i], "value": x[i], "baseline_p50": self.medians.get(self.card["feature_ids"][i]), "contribution": round(contributions[i], 4)} for i in order]
