"""Alert policy from docs/ml/MODEL_EVALUATION.md section 5. Passive: it only ever produces records.

A prediction is never called a confirmed attack. States are normal, suspicious (one window at or above tau), and alert (k in a row).
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .features import FEATURE_IDS

F24 = FEATURE_IDS.index("F24")
HIGH_CLASSES = ("flood", "malformed")
NORMAL, SUSPICIOUS, ALERT = "normal", "suspicious", "alert"


@dataclass
class _SourceState:
    streak: int = 0
    streak_windows: list = field(default_factory=list)
    streak_class: Optional[str] = None
    open_alert: Optional[dict] = None
    last_alert_ns: dict = field(default_factory=dict)  # class -> time of its last alert, for suppression
    last_rule_ns: Optional[int] = None
    last_ns: int = 0  # newest window seen, for prune()


def severity(predicted_class, score, duration_s=0):
    if predicted_class in HIGH_CLASSES and score >= 0.9 or duration_s > 60:
        return "high"
    return "medium"


class AlertEngine:
    """Feed one scored window at a time. Returns the state and any alerts opened or updated by it."""

    def __init__(self, tau, k=2, suppress_s=60, window_s=5, explain=None, clock=time.time):
        if k < 1 or not 0 <= tau <= 1:
            raise ValueError("k must be at least 1 and tau within 0 to 1")
        self.tau, self.k, self.suppress_ns, self.window_ns = tau, k, suppress_s * 10 ** 9, window_s * 10 ** 9
        self.clock = clock
        self.explain = explain  # (features, predicted class) -> evidence list; called only when an alert opens
        self.sources: dict[str, _SourceState] = {}

    def observe(self, source_key, window_start_ns, window_id, features, predicted_class, score):
        state = self.sources.setdefault(source_key, _SourceState())
        state.last_ns = max(state.last_ns, window_start_ns)
        emitted = []
        rule = self._rule(state, source_key, window_start_ns, window_id, features)
        if rule:
            emitted.append(rule)
        # A gap in rows breaks a streak: "consecutive" means adjacent windows from this source.
        adjacent = state.streak_windows and window_start_ns - state.streak_windows[-1][0] == self.window_ns
        if not adjacent:
            state.streak, state.streak_windows, state.streak_class = 0, [], None
            state.open_alert = None
        if predicted_class is None or score is None or score < self.tau:
            state.streak, state.streak_windows, state.streak_class = 0, [], None
            state.open_alert = None
            return NORMAL, emitted
        state.streak += 1
        state.streak_windows.append((window_start_ns, window_id))
        state.streak_class = predicted_class
        if state.open_alert is not None:
            alert = state.open_alert
            alert["last_window_ns"] = window_start_ns
            alert["window_ids"].append(window_id)
            alert["score"] = max(alert["score"], score)
            alert["duration_s"] = (window_start_ns + self.window_ns - alert["start_ns"]) / 1e9
            alert["severity"] = severity(alert["predicted_class"], alert["score"], alert["duration_s"])
            emitted.append({**alert, "window_ids": list(alert["window_ids"]), "update": True})
            return ALERT, emitted
        if state.streak < self.k:
            return SUSPICIOUS, emitted
        last = state.last_alert_ns.get(predicted_class)
        if last is not None and window_start_ns - last < self.suppress_ns:
            return ALERT, emitted  # still an alert state for this source, but no duplicate record
        state.last_alert_ns[predicted_class] = window_start_ns
        start_ns = state.streak_windows[-self.k][0]
        duration = (window_start_ns + self.window_ns - start_ns) / 1e9
        alert = {"alert_id": uuid.uuid4().hex, "source_key": source_key, "kind": "model", "predicted_class": predicted_class, "score": score,
                 "severity": severity(predicted_class, score, duration), "start_ns": start_ns, "last_window_ns": window_start_ns, "duration_s": duration,
                 "window_ids": [w for _, w in state.streak_windows[-self.k:]], "evidence": self.explain(features, predicted_class) if self.explain else [], "first_seen": self.clock(), "update": False}
        state.open_alert = alert
        emitted.append({**alert, "window_ids": list(alert["window_ids"])})  # a copy: later windows keep changing the open one
        return ALERT, emitted

    def prune(self, now_window_ns):
        """Forget sources idle for longer than suppression plus one window. Exact: their streak is already broken
        by the gap and every suppression timer has expired, so a returning source is treated identically."""
        horizon = now_window_ns - self.suppress_ns - self.window_ns
        for key in [k for k, s in self.sources.items() if s.last_ns < horizon]:
            del self.sources[key]

    def _rule(self, state, source_key, window_start_ns, window_id, features):
        """T6 has no training data, so it is a low-severity indicator (F24), never a model prediction."""
        if features[F24] <= 0:
            return None
        if state.last_rule_ns is not None and window_start_ns - state.last_rule_ns < self.suppress_ns:
            return None
        state.last_rule_ns = window_start_ns
        return {"alert_id": uuid.uuid4().hex, "source_key": source_key, "kind": "rule", "predicted_class": "wildcard_subscribe", "score": None, "severity": "low",
                "start_ns": window_start_ns, "last_window_ns": window_start_ns, "duration_s": self.window_ns / 1e9, "window_ids": [window_id],
                "evidence": [{"feature": "F24", "value": features[F24], "baseline_p50": None, "contribution": None}], "first_seen": self.clock(), "update": False}


def ground_truth_status(alert, schedule, window_ns):
    """Compares with the runner's schedule only when one exists. Without a schedule a prediction stays unverified."""
    if schedule is None:
        return "unverified_prediction"
    for entry in schedule:
        if entry["source_key"] == alert["source_key"] and alert["start_ns"] < entry["end_ns"] and entry["start_ns"] < alert["last_window_ns"] + window_ns:
            return "matches_scheduled_attack"
    return "no_scheduled_attack"
