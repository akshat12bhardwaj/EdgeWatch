"""Alert policy, event store, and detector refusal tests."""
import json
import sqlite3

import pytest

from ids import FEATURE_IDS
from ids.alerts import ALERT, NORMAL, SUSPICIOUS, AlertEngine, ground_truth_status, severity
from ids.detector import Detector, ModelRefused
from ids.store import EventStore, connect

W = 5 * 10 ** 9
ZERO = (0.0,) * 26


def feed(engine, scores, source="s", cls="flood", start=0, features=ZERO):
    return [engine.observe(source, start + i * W, f"w{i}", features, cls, s) for i, s in enumerate(scores)]


def test_one_window_is_suspicious_and_k_windows_open_one_alert():
    results = feed(AlertEngine(0.5), [0.1, 0.9, 0.9, 0.9])
    assert [r[0] for r in results] == [NORMAL, SUSPICIOUS, ALERT, ALERT]
    opened = [a for _, emitted in results for a in emitted if not a["update"]]
    assert len(opened) == 1 and opened[0]["window_ids"] == ["w1", "w2"] and opened[0]["start_ns"] == W


def test_open_alert_updates_instead_of_duplicating():
    results = feed(AlertEngine(0.5), [0.9, 0.9, 0.95])
    update = results[2][1][0]
    assert update["update"] and update["alert_id"] == results[1][1][0]["alert_id"] and update["window_ids"] == ["w0", "w1", "w2"] and update["score"] == 0.95


def test_repeat_within_suppression_is_silent_and_after_it_alerts_again():
    engine = AlertEngine(0.5, suppress_s=60)
    first = feed(engine, [0.9, 0.9])
    feed(engine, [0.1], start=2 * W)
    again = feed(engine, [0.9, 0.9], start=3 * W)
    assert again[1][0] == ALERT and again[1][1] == []
    later = feed(engine, [0.9, 0.9], start=30 * W)
    assert later[1][1] and later[1][1][0]["alert_id"] != first[1][1][0]["alert_id"]


def test_suppression_is_per_class_and_per_source():
    engine = AlertEngine(0.5)
    feed(engine, [0.9, 0.9])
    other_source = feed(engine, [0.9, 0.9], source="t")
    other_class = feed(engine, [0.9, 0.9], cls="bruteforce", start=10 * W)
    assert other_source[1][1] and other_class[1][1]


def test_a_gap_in_rows_breaks_consecutive_windows():
    engine = AlertEngine(0.5)
    feed(engine, [0.9])
    state, emitted = engine.observe("s", 2 * W, "x", ZERO, "flood", 0.9)
    assert state == SUSPICIOUS and not emitted


def test_missing_model_output_is_normal_and_never_alerts():
    assert AlertEngine(0.5).observe("s", 0, "w", ZERO, None, None) == (NORMAL, [])


def test_severity_follows_the_policy():
    assert severity("flood", 0.95) == "high" and severity("malformed", 0.9) == "high"
    assert severity("flood", 0.8) == "medium" and severity("bruteforce", 0.99) == "medium" and severity("bruteforce", 0.6, 61) == "high"


def test_wildcard_rule_is_low_severity_suppressed_and_not_a_model_prediction():
    features = list(ZERO)
    features[FEATURE_IDS.index("F24")] = 1.0
    engine = AlertEngine(0.5)
    _, first = engine.observe("s", 0, "a", features, "flood", 0.1)
    _, second = engine.observe("s", W, "b", features, "flood", 0.1)
    assert first[0]["severity"] == "low" and first[0]["kind"] == "rule" and first[0]["score"] is None and second == []


def test_explain_runs_only_when_an_alert_opens():
    calls = []
    engine = AlertEngine(0.5, explain=lambda f, c: calls.append(c) or [{"feature": "F01"}])
    results = feed(engine, [0.9, 0.9, 0.9])
    assert calls == ["flood"] and results[1][1][0]["evidence"] == [{"feature": "F01"}]


def test_invalid_engine_settings_are_refused():
    for args in ((2,), (0.5, 0)):
        with pytest.raises(ValueError):
            AlertEngine(*args)


def test_ground_truth_status_needs_a_schedule_and_matches_by_source_and_time():
    alert = {"source_key": "s", "start_ns": 10 * W, "last_window_ns": 12 * W}
    assert ground_truth_status(alert, None, W) == "unverified_prediction"
    assert ground_truth_status(alert, [{"source_key": "s", "start_ns": 9 * W, "end_ns": 11 * W}], W) == "matches_scheduled_attack"
    assert ground_truth_status(alert, [{"source_key": "t", "start_ns": 9 * W, "end_ns": 11 * W}], W) == "no_scheduled_attack"
    assert ground_truth_status(alert, [{"source_key": "s", "start_ns": 20 * W, "end_ns": 21 * W}], W) == "no_scheduled_attack"


def test_store_sets_provenance_on_every_event_and_persists_across_reopen(tmp_path):
    path = tmp_path / "e.sqlite"
    store = EventStore(path, "run1", "replay")
    event = store.write("window", 1.0, {"source_key": "s"})
    assert event["provenance"] == "replay" and event["schema_version"] == "1.0"
    store.write("alert", 2.0, {"alert_id": "a", "source_key": "s", "severity": "high"})
    store.db.close()
    db = connect(path, read_only=True)
    assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2 and db.execute("SELECT severity FROM alerts").fetchone()[0] == "high"
    assert json.loads(db.execute("SELECT body FROM events WHERE event_type='window'").fetchone()[0])["provenance"] == "replay"
    db.close()


def test_body_cannot_override_provenance_with_a_wrong_stored_column(tmp_path):
    store = EventStore(tmp_path / "e.sqlite", "r", "replay")
    event = store.write("window", 1.0, {"source_key": "s"})
    row = store.db.execute("SELECT provenance FROM events").fetchone()
    store.db.close()
    assert row[0] == event["provenance"] == "replay"


def test_unknown_provenance_and_event_type_are_refused(tmp_path):
    with pytest.raises(ValueError):
        EventStore(tmp_path / "a.sqlite", "r", "demo")
    store = EventStore(tmp_path / "b.sqlite", "r", "live")
    with pytest.raises(ValueError):
        store.write("nonsense", 1.0, {})
    store.db.close()


def test_alert_update_replaces_its_row(tmp_path):
    store = EventStore(tmp_path / "e.sqlite", "r", "live")
    store.write("alert", 1.0, {"alert_id": "a", "source_key": "s", "severity": "medium"})
    store.write("alert", 2.0, {"alert_id": "a", "source_key": "s", "severity": "high"})
    rows = [tuple(r) for r in store.db.execute("SELECT alert_id, severity FROM alerts")]
    store.db.close()
    assert rows == [("a", "high")]


def test_database_failure_is_counted_and_does_not_raise(tmp_path):
    store = EventStore(tmp_path / "e.sqlite", "r", "live")
    store.db.close()
    assert store.write("window", 1.0, {"source_key": "s"}) is None and store.write_errors == 1
    assert store.control("enabled", "true") == "true" and store.write_errors == 2


def test_retention_prunes_events_but_not_alerts(tmp_path):
    store = EventStore(tmp_path / "e.sqlite", "r", "live", max_events=10)
    store.write("alert", 0.0, {"alert_id": "a", "source_key": "s", "severity": "low"})
    for i in range(50):
        store.write("window", float(i), {"source_key": "s"})
    store.prune()
    assert store.db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 10 and store.db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 1
    store.db.close()


def bundle(tmp_path, **card_changes):
    import joblib
    import numpy as np
    import sklearn
    from sklearn.ensemble import RandomForestClassifier
    X = np.random.RandomState(0).rand(60, 26)
    y = np.array(["benign", "flood", "bruteforce"] * 20)
    X[y == "flood", 0] += 10
    model = RandomForestClassifier(n_estimators=5, random_state=0).fit(X, y)
    joblib.dump(model, tmp_path / "model.joblib")
    card = {"model_id": "m", "extractor_version": "fx-0.1", "feature_ids": list(FEATURE_IDS), "tau": 0.5, "classes": list(model.classes_),
            "sklearn_version": sklearn.__version__, "benign_medians": {f: 0.5 for f in FEATURE_IDS}, **card_changes}
    (tmp_path / "model_card.json").write_text(json.dumps(card))
    return tmp_path


def test_detector_scores_and_explains_without_claiming_proof(tmp_path):
    detector = Detector(bundle(tmp_path))
    features = [0.5] * 26
    features[0] = 11.0
    predicted, score = detector.score(features)
    assert predicted == "flood" and score > 0.5
    evidence = detector.explain(features, predicted)
    assert len(evidence) == 5 and evidence[0]["feature"] == "F01" and evidence[0]["baseline_p50"] == 0.5


def test_detector_scores_low_on_benign_like_input(tmp_path):
    assert Detector(bundle(tmp_path)).score([0.5] * 26)[1] < 1


@pytest.mark.parametrize("changes, reason", [
    ({"extractor_version": "fx-0.2"}, "extractor"),
    ({"sklearn_version": "0.0"}, "scikit-learn"),
    ({"feature_ids": ["F99"]}, "feature"),
])
def test_detector_refuses_mismatches(tmp_path, changes, reason):
    with pytest.raises(ModelRefused, match=reason):
        Detector(bundle(tmp_path, **changes))


def test_detector_refuses_missing_and_corrupt_bundles(tmp_path):
    with pytest.raises(ModelRefused, match="missing"):
        Detector(tmp_path / "nothing")
    (tmp_path / "model.joblib").write_bytes(b"not a model")
    (tmp_path / "model_card.json").write_text(json.dumps({"model_id": "m", "extractor_version": "fx-0.1", "feature_ids": list(FEATURE_IDS), "tau": 0.5, "classes": [], "sklearn_version": __import__("sklearn").__version__}))
    with pytest.raises(ModelRefused, match="could not be loaded"):
        Detector(tmp_path)


def test_prune_forgets_idle_sources_without_changing_later_decisions():
    def run(prune):
        engine = AlertEngine(0.5, k=2, suppress_s=60, window_s=5)
        out = []
        for i in range(3):
            out.append(engine.observe("old", i * W, f"w{i}", ZERO, "flood", 0.9)[0])
        for i in range(3, 40):  # another source keeps windows flowing while "old" is idle
            if prune:
                engine.prune(i * W)
            engine.observe(f"churn{i}", i * W, f"c{i}", ZERO, None, None)
        sizes = len(engine.sources)
        for i in range(40, 43):
            out.append(engine.observe("old", i * W, f"x{i}", ZERO, "flood", 0.9)[0])
        return out, sizes
    kept, kept_size = run(False)
    pruned, pruned_size = run(True)
    assert kept == pruned
    assert pruned_size < kept_size
