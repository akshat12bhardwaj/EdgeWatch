"""Offline model comparison, leakage checks and bundling. Engineering evaluation, not the pre-registered E1-E9: D-01 and Option B stay open.

python -m ids.training dq-mqttset | mqttset | lab-tables | lab-select | lab-final
Labels: MQTTset labels are per file, as assigned by its authors, not verified ground truth. Lab labels come from the runner's schedule only.
"""
import argparse
import json
import os
import platform
import time
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.stats import ks_2samp
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from .alerts import AlertEngine
from .baselines import RateBaseline, RuleBaseline  # noqa: F401  (re-exported for lab-compare and tests)
from .features import EXTRACTOR_VERSION, FEATURE_IDS
from .pipeline import run as run_pipeline

DATA = Path(os.environ.get("EDGEWATCH_DATA", Path.home() / "edgewatch-data"))
RESULTS = Path(__file__).resolve().parents[2] / "results"
BENIGN = "benign"
W_NS = 5 * 10 ** 9
MQTTSET = {"capture_1w": BENIGN, "capture_flood": "flood", "capture_malariaDoS": "flood", "bruteforce": "bruteforce", "malformed": "malformed", "slowite": "lowrate"}
GRIDS = {
    "LR": [{"C": c} for c in (0.1, 1, 10)],
    "DT": [{"max_depth": d} for d in (4, 8, 12)],
    "RF": [{"n_estimators": n, "max_depth": d} for n in (25, 50, 100) for d in (8, 16)],
    "HGB": [{"max_iter": n, "learning_rate": r} for n in (100, 200) for r in (0.05, 0.1)],
}
ALL, NO_CONTEXT = list(FEATURE_IDS), [f for f in FEATURE_IDS if f not in ("F25", "F26")]
STATUS = "engineering evaluation; not an E1-E9 research result; D-01 open, Option B not approved"


def make_model(kind, params, seed):
    if kind == "LR":
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed, **params))
    if kind == "DT":
        return DecisionTreeClassifier(class_weight="balanced", random_state=seed, **params)
    if kind == "RF":
        return RandomForestClassifier(class_weight="balanced", random_state=seed, n_jobs=4, **params)
    if kind == "HGB":
        return HistGradientBoostingClassifier(class_weight="balanced", random_state=seed, **params)
    raise ValueError(kind)


def scores_of(model, X):
    """(score = 1 - P(benign), best attack class per row), the same rule as ids.detector."""
    proba = model.predict_proba(X)
    classes = np.array(model.classes_)
    benign = list(classes).index(BENIGN)
    score = 1 - proba[:, benign]
    masked = proba.copy()
    masked[:, benign] = -1
    return score, classes[masked.argmax(axis=1)]


def pick_tau(benign_scores, target_fpr=0.01):
    """Smallest threshold keeping validation benign FPR at or under the target (proposed default in the protocol)."""
    if not len(benign_scores):
        return 0.5
    top = np.sort(benign_scores)[::-1]
    allowed = int(np.floor(target_fpr * len(top)))
    return float(min(max(top[allowed] + 1e-9, 0.05), 0.999))


def predict_with_tau(score, attack, tau):
    return np.where(score >= tau, attack, BENIGN)


def evaluate(y, score, attack, tau):
    predicted = predict_with_tau(score, attack, tau)
    labels = sorted(set(y))
    binary, positive = y != BENIGN, predicted != BENIGN
    benign_total = int((~binary).sum())
    return {"macro_f1": float(f1_score(y, predicted, labels=labels, average="macro", zero_division=0)),
            "per_class_recall": {c: float(recall_score(y == c, predicted == c, zero_division=0)) for c in labels},
            "per_class_precision": {c: float(precision_score(y == c, predicted == c, zero_division=0)) for c in labels},
            "fpr": float((positive & ~binary).sum() / benign_total) if benign_total else None,
            "fp_windows": int((positive & ~binary).sum()), "benign_windows": benign_total, "attack_windows": int(binary.sum()),
            "binary_recall": float((positive & binary).sum() / binary.sum()) if binary.sum() else None,
            "binary_precision": float((positive & binary).sum() / positive.sum()) if positive.sum() else None,
            "pr_auc": float(average_precision_score(binary, score)) if binary.any() else None, "support": {k: int(v) for k, v in Counter(y).items()}}


def inference_cost(model, X, calls=2000):
    """Batch 1, median, on this development machine, for ranking only. Gateway figures need E3."""
    rows = X[np.random.RandomState(0).randint(0, len(X), calls)]
    times = []
    for row in rows:
        started = time.perf_counter_ns()
        model.predict_proba(row[None, :])
        times.append(time.perf_counter_ns() - started)
    return float(np.median(times) / 1000)


def model_size(model, tmp):
    joblib.dump(model, tmp, compress=3)
    size = os.path.getsize(tmp)
    os.remove(tmp)
    return size


def undersample(table, seed, benign_cap=50_000):
    benign = table[table.label == BENIGN]
    if len(benign) <= benign_cap:
        return table
    return pd.concat([benign.sample(benign_cap, random_state=seed), table[table.label != BENIGN]])


# MQTTset -----------------------------------------------------------------------------------------------------------------------

def load_mqttset():
    frames = []
    for capture, label in MQTTSET.items():
        frame = pd.read_parquet(DATA / "engineering" / "mqttset" / capture / "rows_w5.parquet")
        frame["capture"], frame["label"] = capture, label
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def s_time(table):
    """Per capture: first 60% of duration train, next 20% validation, last 20% test, with a gap of 2W between blocks (protocol section 3)."""
    parts = {"train": [], "val": [], "test": []}
    for _, frame in table.groupby("capture"):
        start, end = frame.window_start_ns.min(), frame.window_start_ns.max() + W_NS
        a, b = start + 0.6 * (end - start), start + 0.8 * (end - start)
        parts["train"].append(frame[frame.window_start_ns + W_NS <= a])
        parts["val"].append(frame[(frame.window_start_ns >= a + 2 * W_NS) & (frame.window_start_ns + W_NS <= b)])
        parts["test"].append(frame[frame.window_start_ns >= b + 2 * W_NS])
    return {k: pd.concat(v) for k, v in parts.items()}


def s_rand(table, seed):
    train, rest = train_test_split(table, test_size=0.3, stratify=table.label, random_state=seed)
    val, test = train_test_split(rest, test_size=0.5, stratify=rest.label, random_state=seed)
    return {"train": train, "val": val, "test": test}


def fit_select(kind, split, features, seed):
    """Grid on validation only, by macro-F1 at its own tau. Test is scored once, after selection."""
    train = undersample(split["train"], seed)
    best = None
    for params in GRIDS[kind]:
        model = make_model(kind, params, seed).fit(train[features].values, train.label.values)
        score, attack = scores_of(model, split["val"][features].values)
        y = split["val"].label.values
        tau = pick_tau(score[y == BENIGN])
        macro = evaluate(y, score, attack, tau)["macro_f1"]
        if best is None or macro > best[0]:
            best = (macro, params, model, tau)
    return best


def mqttset_experiment(seeds=range(5)):
    # F-59 is open: lowrate has one row and cannot be split, so it is left out here and that choice is reported, not decided.
    table = load_mqttset()
    table = table[table.label != "lowrate"]
    out = []
    for split_name in ("S-rand", "S-time"):
        for feature_name, features in (("all_26", ALL), ("without_F25_F26", NO_CONTEXT)):
            for kind in GRIDS:
                for seed in seeds:
                    split = s_time(table) if split_name == "S-time" else s_rand(table, seed)
                    started = time.perf_counter()
                    val_macro, params, model, tau = fit_select(kind, split, features, seed)
                    score, attack = scores_of(model, split["test"][features].values)
                    metrics = evaluate(split["test"].label.values, score, attack, tau)
                    out.append({"split": split_name, "features": feature_name, "model": kind, "seed": seed, "params": params, "tau": tau, "val_macro_f1": val_macro, "train_select_s": time.perf_counter() - started, **metrics})
                    print(split_name, feature_name, kind, seed, round(metrics["macro_f1"], 4), round(metrics["fpr"], 5), flush=True)
    write_result("ENG-M1", {"status": STATUS, "dataset": "MQTTset", "labels": "author per-file labels, not verified ground truth (F-54)", "classes_excluded": {"lowrate": "1 row, cannot be split (F-59 undecided)"},
                            "benign_undersampled_train_cap": 50000, "threshold": "score = 1 - P(benign); tau on validation, benign FPR at most 1%; no refit (F-06 undecided)", "runs": out})


def dq_mqttset():
    table = load_mqttset()
    binary = (table.label != BENIGN).values
    out = {"status": STATUS, "class_rows": {k: int(v) for k, v in table.label.value_counts().items()},
           "capture_rows": {k: int(v) for k, v in table.capture.value_counts().items()}}
    # Q10: identity and time alone
    identity = pd.DataFrame({"source": pd.factorize(table.source_key)[0], "time": table.window_start_ns, "capture_rows": table.groupby("capture").source_key.transform("size")})
    keep = table.label != "lowrate"
    split = train_test_split(identity[keep], table.label[keep], test_size=0.3, stratify=table.label[keep], random_state=0)
    q10 = DecisionTreeClassifier(class_weight="balanced", random_state=0, max_depth=8).fit(split[0], split[2])
    out["Q10_macro_f1_identity_time_only"] = float(f1_score(split[3], q10.predict(split[1]), average="macro"))
    # Q11: each feature alone
    q11 = {}
    for name in FEATURE_IDS:
        tree = DecisionTreeClassifier(max_depth=1, class_weight="balanced", random_state=0).fit(table[[name]].values[keep], binary[keep])
        q11[name] = float(f1_score(binary[keep], tree.predict(table[[name]].values[keep]), average="macro"))
    out["Q11_binary_macro_f1_single_feature_stump"] = q11
    out["Q11_above_0_95"] = [k for k, v in q11.items() if v > 0.95]
    out["F26_values"] = {label: sorted(map(float, set(frame.F26))) for label, frame in table.groupby("label")}
    out["F23_nonzero_rows"] = int((table.F23 > 0).sum())
    out["constant_features"] = [f for f in FEATURE_IDS if table[f].nunique() == 1]
    # Leave-one-capture-out for flood, the only family present in two captures: the one cross-environment check inside MQTTset.
    loco = {}
    for held, kept in (("capture_flood", "capture_malariaDoS"), ("capture_malariaDoS", "capture_flood")):
        train = undersample(table[(table.capture != held) & keep], 0)
        model = make_model("RF", {"n_estimators": 50, "max_depth": 16}, 0).fit(train[ALL].values, train.label.values)
        tested = table[table.capture == held]
        score, attack = scores_of(model, tested[ALL].values)
        loco[held] = {"windows": len(tested), "flagged_as_attack_at_0_5": float((score >= 0.5).mean()), "predicted_flood_at_0_5": float(((score >= 0.5) & (attack == "flood")).mean()), "predicted_classes": {k: int(v) for k, v in Counter(predict_with_tau(score, attack, 0.5)).items()}}
    out["flood_leave_one_capture_out"] = loco
    # Exact-duplicate feature rows between train and test: the near-copy leakage a random split allows.
    def duplicates(split):
        train = set(map(tuple, split["train"][ALL].values))
        test = split["test"][ALL].values
        return {label: float(np.mean([tuple(r) in train for r in test[split["test"].label.values == label]])) for label in sorted(set(split["test"].label))}
    out["test_rows_with_exact_copy_in_train"] = {"S-rand": duplicates(s_rand(table[keep], 0)), "S-time": duplicates(s_time(table[keep]))}
    write_result("DQ-MQTTSET", out)
    print(json.dumps({k: v for k, v in out.items() if k != "Q11_binary_macro_f1_single_feature_stump"}, indent=1))


# Lab ---------------------------------------------------------------------------------------------------------------------------

LAB_RUNS = {"ep_s0": 18840, "ep_s1": 18841, "ep_s2": 18842}
BENIGN_RUNS = {"ben_steady_sensors": 18851, "ben_bursty_publishers": 18852, "ben_qos_heavy": 18853, "ben_retained_churn": 18854, "ben_reconnect_storm": 18855, "ben_new_device": 18856}
BENIGN_CAMPAIGN = "campaign1"  # 30-minute scenarios, never used to train or select
FAMILY_CLASS = {"flood_connect": "flood", "flood_publish": "flood", "lowrate": "lowrate", "malformed": "malformed", "bruteforce": "bruteforce"}


def campaign_dir(campaign):
    return DATA / "lab" / campaign


def label_lab(table, manifest, window_s=5):
    """DATA_QUALITY_PROTOCOL section 4. Attack label only inside the interval from that source; straddling is mixed; attacker windows outside are dropped."""
    labels, episodes = [], []
    attack_by_source = {}
    for mark in manifest["episodes"]:
        attack_by_source.setdefault(mark["source"], []).append(mark)
    dropped = 0
    for row in table.itertuples():
        marks = attack_by_source.get(row.source_key)
        if not marks:
            labels.append(BENIGN)
            episodes.append(None)
            continue
        start, end = row.window_start_ns / 1e9, row.window_start_ns / 1e9 + window_s
        label, episode = "drop", None
        for mark in marks:
            if start >= mark["start_epoch"] and end <= mark["end_epoch"]:
                label, episode = FAMILY_CLASS[mark["family"]], mark["episode"]
            elif start < mark["end_epoch"] and mark["start_epoch"] < end:
                label, episode = "mixed", mark["episode"]
        dropped += label == "drop"
        labels.append(label)
        episodes.append(episode)
    table["label"], table["episode"] = labels, episodes
    return table, dropped


def lab_tables(campaign):
    reports = {}
    for name, port in RUN_PORTS.get(campaign, LAB_RUNS if campaign != BENIGN_CAMPAIGN else {**LAB_RUNS, **BENIGN_RUNS}).items():
        folder = campaign_dir(campaign) / name
        reports[name] = run_pipeline(folder / "capture.pcap", folder / "tables", 5, port, raw_sources=True)  # invented loopback addresses only
        print(name, reports[name]["rows"], reports[name]["decoder"]["frames"], reports[name]["decoder"]["malformed_frames"], flush=True)
    return reports


def load_lab_run(campaign, name, window_s=5):
    folder = campaign_dir(campaign) / name
    manifest = json.loads((folder / "manifest.json").read_text())
    table = pd.read_parquet(folder / "tables" / f"rows_w{window_s}.parquet")
    table, dropped = label_lab(table, manifest, window_s)
    table["run"] = name
    table["group"] = np.where(table.episode.notna(), f"{campaign}/{name}-ep" + table.episode.astype(str), f"{campaign}/{name}-" + table.source_key)
    return table, manifest, dropped


def alert_level(table, score, attack, tau, marks, k=2, window_s=5):
    """Replays rows through the real AlertEngine. Reports alert precision, episodes detected, and time-to-detect by family."""
    order = np.lexsort((table.window_start_ns.values, table.source_key.values))
    rows = table.iloc[order]
    engine = AlertEngine(tau, k=k, window_s=window_s)
    alerts = []
    w = window_s
    features = rows[ALL].values
    for i, row in enumerate(rows.itertuples()):
        _, emitted = engine.observe(row.source_key, row.window_start_ns, str(i), features[i], attack[order][i], float(score[order][i]))
        alerts += [a for a in emitted if not a["update"] and a["kind"] == "model"]
    detected, ttd = set(), {}
    false_alerts = 0
    for alert in alerts:
        mark = next((m for m in marks if m["source"] == alert["source_key"] and alert["start_ns"] / 1e9 < m["end_epoch"] + w and m["start_epoch"] - w < alert["last_window_ns"] / 1e9 + w), None)
        if mark is None:
            false_alerts += 1
        elif mark["episode"] not in detected:
            detected.add(mark["episode"])
            # Open time is when the k-th window closes.
            ttd.setdefault(mark["family"], []).append(alert["last_window_ns"] / 1e9 + w - mark["start_epoch"])
    by_family = {}
    for family in sorted({m["family"] for m in marks}):
        episodes = [m for m in marks if m["family"] == family]
        by_family[family] = {"episodes": len(episodes), "detected": sum(m["episode"] in detected for m in episodes),
                             "ttd_median_s": float(np.median(ttd[family])) if ttd.get(family) else None, "ttd_max_s": float(np.max(ttd[family])) if ttd.get(family) else None}
    return {"alerts": len(alerts), "false_alerts": false_alerts, "alert_precision": (len(alerts) - false_alerts) / len(alerts) if alerts else None, "episodes_total": len(marks), "episodes_detected": len(detected), "by_family": by_family}


# Dev runs per campaign. campaign3 adds attacks among heavy clients and a heavy benign run to what campaign2 gave. Its test run was never used by any model.
DEV_RUNS = {"campaign3": [("campaign2", "ep_s0"), ("campaign2", "ep_s1"), ("campaign3", "ep_s1"), ("campaign3", "ben_heavy_train")],
            "campaign4": [("campaign2", "ep_s0"), ("campaign2", "ep_s1"), ("campaign3", "ep_s1"), ("campaign3", "ben_heavy_train"), ("campaign4", "ep_s1")],
            "campaign5": [("campaign2", "ep_s0"), ("campaign2", "ep_s1"), ("campaign3", "ep_s1"), ("campaign3", "ben_heavy_train"), ("campaign4", "ep_s1"), ("campaign5", "ep_s1"), ("campaign5", "ben_heavy_train2")],
            "campaign6": [("campaign2", "ep_s0"), ("campaign2", "ep_s1"), ("campaign3", "ep_s1"), ("campaign3", "ben_heavy_train"), ("campaign4", "ep_s1"), ("campaign5", "ep_s1"), ("campaign5", "ben_heavy_train2"), ("campaign6", "ep_s1"), ("campaign6", "ben_hold_train")]}
RUN_PORTS = {"campaign3": {"ep_s1": 18841, "ep_s2": 18842, "ben_heavy_train": 18847, "ben_heavy_test": 18846}, "campaign4": {"ep_s1": 18841, "ep_s2": 18842, "ben_heavy_test": 18846}, "campaign5": {"ep_s1": 18841, "ep_s2": 18842, "ben_heavy_train2": 18847, "ben_heavy_test2": 18846}, "campaign6": {"ep_s1": 18841, "ep_s2": 18842, "ben_hold_train": 18847, "ben_hold_test": 18846}}


def dev_runs(campaign):
    return DEV_RUNS.get(campaign, [(campaign, "ep_s0"), (campaign, "ep_s1")])


def group_folds(groups, seed, k=5):
    unique = sorted(set(groups))
    np.random.RandomState(seed).shuffle(unique)
    assignment = {g: i % k for i, g in enumerate(unique)}
    return np.array([assignment[g] for g in groups])


def lab_select(campaign, seed=0):
    """S-episode: group 5-fold over attack episodes and benign sources, on runs ep_s0 and ep_s1 only. ep_s2 and the benign runs stay untouched."""
    dev = pd.concat([load_lab_run(c, r)[0] for c, r in dev_runs(campaign)], ignore_index=True)
    dev = dev[~dev.label.isin(("mixed", "drop"))]
    folds = group_folds(dev.group.values, seed)
    out = []
    for feature_name, features in (("all_26", ALL), ("without_F25_F26", NO_CONTEXT)):
        for kind, grid in GRIDS.items():
            for params in grid:
                macros, fprs = [], []
                started = time.perf_counter()
                for fold in range(5):
                    train, val = dev[folds != fold], dev[folds == fold]
                    model = make_model(kind, params, seed).fit(train[features].values, train.label.values)
                    score, attack = scores_of(model, val[features].values)
                    tau = pick_tau(score[val.label.values == BENIGN])
                    m = evaluate(val.label.values, score, attack, tau)
                    macros.append(m["macro_f1"])
                    fprs.append(m["fpr"])
                final = make_model(kind, params, seed).fit(dev[features].values, dev.label.values)
                if hasattr(final, "n_jobs"):
                    final.n_jobs = 1  # as deployed, so the cost ranking is not distorted by a worker pool
                out.append({"features": feature_name, "model": kind, "params": params, "cv_macro_f1_mean": float(np.mean(macros)), "cv_macro_f1_std": float(np.std(macros)), "cv_fpr_mean": float(np.mean(fprs)),
                            "inference_us_batch1": inference_cost(final, dev[features].values), "model_bytes": model_size(final, RESULTS / f".tmp-{os.getpid()}.joblib"), "fit_s": (time.perf_counter() - started) / 6})
                print(feature_name, kind, params, round(out[-1]["cv_macro_f1_mean"], 4), round(out[-1]["cv_fpr_mean"], 4), round(out[-1]["inference_us_batch1"]), out[-1]["model_bytes"], flush=True)
    write_result("ENG-L1-select", {"status": STATUS, "protocol": "S-episode style group 5-fold on lab dev runs only", "dev_rows": {k: int(v) for k, v in dev.label.value_counts().items()}, "dev_groups": int(dev.group.nunique()), "candidates": out})


def lab_final(campaign, kind, params, features, model_id, seed=0):
    """Fit on dev runs, tau from out-of-fold benign scores, then score held-out ep_s2 and benign runs once. Never retune after this."""
    features = ALL if features == "all_26" else NO_CONTEXT
    dev_full = pd.concat([load_lab_run(c, r)[0] for c, r in dev_runs(campaign)], ignore_index=True)
    dev = dev_full[~dev_full.label.isin(("mixed", "drop"))]
    folds = group_folds(dev.group.values, seed)
    oof = np.zeros(len(dev))
    for fold in range(5):
        model = make_model(kind, params, seed).fit(dev[features].values[folds != fold], dev.label.values[folds != fold])
        oof[folds == fold] = scores_of(model, dev[features].values[folds == fold])[0]
    tau = pick_tau(oof[dev.label.values == BENIGN])
    model = make_model(kind, params, seed).fit(dev[features].values, dev.label.values)
    if hasattr(model, "n_jobs"):
        model.n_jobs = 1  # one window at a time on a gateway; a worker pool would only add latency
    test_full, manifest, dropped = load_lab_run(campaign, "ep_s2")
    test = test_full[~test_full.label.isin(("mixed", "drop"))]
    score, attack = scores_of(model, test[features].values)
    held_out = evaluate(test.label.values, score, attack, tau)
    # Mixed windows are excluded from window metrics, but the alert path sees every row, as it would live.
    score_all, attack_all = scores_of(model, test_full[features].values)
    alerts = alert_level(test_full, score_all, attack_all, tau, manifest["episodes"])
    boot = episode_bootstrap(test, score, attack, tau)
    benign_results = {}
    for name in BENIGN_RUNS:
        table, m, _ = load_lab_run(BENIGN_CAMPAIGN, name)
        s, a = scores_of(model, table[features].values)
        hours = m["seconds"] / 3600
        level = alert_level(table, s, a, tau, [])
        benign_results[name] = {"windows": len(table), "fp_windows": int((s >= tau).sum()), "fpr": float((s >= tau).mean()), "false_alerts": level["alerts"], "false_alerts_per_hour": level["alerts"] / hours, "hours": hours}
    medians = {f: float(dev[dev.label == BENIGN][f].median()) for f in features}
    bundle = DATA / "models" / model_id
    bundle.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, bundle / "model.joblib", compress=3)
    card = {"model_id": model_id, "kind": kind, "params": params, "extractor_version": EXTRACTOR_VERSION, "feature_ids": features, "tau": tau, "classes": list(map(str, model.classes_)), "k": 2,
            "sklearn_version": sklearn.__version__, "python": platform.python_version(), "benign_medians": medians, "trained_on": "lab runs " + ", ".join(f"{c}/{r}" for c, r in dev_runs(campaign)) + " (Windows loopback, simulated clients)", "status": STATUS,
            "not_for": "RQ1 or any claim about real traffic", "f23_signal": "decoder structural flag, adapter-defined; retrain if the F23 decision changes it", "score_label": "model score, uncalibrated"}
    (bundle / "model_card.json").write_text(json.dumps(card, indent=1))
    write_result("ENG-L2-final", {"status": STATUS, "model_card": card, "model_bytes": os.path.getsize(bundle / "model.joblib"), "held_out_run": "ep_s2", "window_metrics": held_out, "alert_metrics": alerts, "macro_f1_95ci_episode_bootstrap": boot, "mixed_or_dropped_windows": {"mixed": int((test_full.label == "mixed").sum()), "dropped": dropped},
                                  "benign_scenarios_never_used_for_tuning": benign_results, "inference_us_batch1": inference_cost(model, test[features].values)})
    print(json.dumps({"tau": tau, "held_out": held_out, "alerts": alerts, "ci": boot, "benign": benign_results}, indent=1))
    calibration(model, test, features)
    return model


def calibration(model, test, features):
    """MODEL_EVALUATION section 3: the UI may only say 'confidence' if expected calibration error is 0.05 or less."""
    score = scores_of(model, test[features].values)[0]
    y = (test.label.values != BENIGN).astype(float)
    bins = np.minimum((score * 10).astype(int), 9)
    ece = sum((bins == b).mean() * abs(y[bins == b].mean() - score[bins == b].mean()) for b in range(10) if (bins == b).any())
    write_result("ENG-L2-calibration", {"status": STATUS, "ece": float(ece), "brier": float(((score - y) ** 2).mean()), "ui_label": "confidence" if ece <= 0.05 else "model score"})


def episode_bootstrap(test, score, attack, tau, n=1000, seed=0):
    rng = np.random.RandomState(seed)
    groups = test.group.values
    unique = sorted(set(groups))
    indices = {g: np.where(groups == g)[0] for g in unique}
    y = test.label.values
    predicted = predict_with_tau(score, attack, tau)
    values = []
    for _ in range(n):
        chosen = np.concatenate([indices[unique[i]] for i in rng.randint(0, len(unique), len(unique))])
        values.append(f1_score(y[chosen], predicted[chosen], average="macro", zero_division=0))
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]


def lab_stealth(campaign, model_id, run_name="stealth", port=18843, result="ENG-L3-stealth"):
    """Low-rate variants the model never saw, scored once with the frozen model and tau. No retuning follows from this."""
    folder = campaign_dir(campaign) / run_name
    run_pipeline(folder / "capture.pcap", folder / "tables", 5, port, raw_sources=True)
    card = json.loads((DATA / "models" / model_id / "model_card.json").read_text())
    model = joblib.load(DATA / "models" / model_id / "model.joblib")
    full, manifest, _ = load_lab_run(campaign, run_name)
    table = full[~full.label.isin(("mixed", "drop"))]
    features, tau = card["feature_ids"], card["tau"]
    score, attack = scores_of(model, table[features].values)
    score_all, attack_all = scores_of(model, full[features].values)
    body = {"status": STATUS, "model_id": model_id, "attack_rates": "far below the training rates; see lab.run.STEALTH", "window_metrics": evaluate(table.label.values, score, attack, tau),
            "alert_metrics": alert_level(full, score_all, attack_all, tau, manifest["episodes"])}
    write_result(result, body)
    print(json.dumps(body, indent=1))


def lab_benign_check(campaign, name, port, model_id):
    """One frozen model on one benign run. Windows flagged and alerts raised, per source, with the source's profile."""
    folder = campaign_dir(campaign) / name
    run_pipeline(folder / "capture.pcap", folder / "tables", 5, port, raw_sources=True)
    card = json.loads((DATA / "models" / model_id / "model_card.json").read_text())
    model = joblib.load(DATA / "models" / model_id / "model.joblib")
    table, manifest, _ = load_lab_run(campaign, name)
    score, attack = scores_of(model, table[card["feature_ids"]].values)
    level = alert_level(table, score, attack, card["tau"], [])
    hours = manifest["seconds"] / 3600
    profiles = manifest["benign_sources"]
    by_profile = {}
    for profile in sorted(set(profiles.values())):
        rows = table.source_key.isin([s for s, p in profiles.items() if p == profile]).values
        by_profile[profile] = {"windows": int(rows.sum()), "flagged": int((score[rows] >= card["tau"]).sum())}
    body = {"status": STATUS, "model_id": model_id, "run": f"{campaign}/{name}", "windows": len(table), "fp_windows": int((score >= card["tau"]).sum()), "fpr": float((score >= card["tau"]).mean()), "false_alerts": level["alerts"], "false_alerts_per_hour": level["alerts"] / hours, "by_profile": by_profile}
    write_result(f"ENG-B1-{model_id}-{name}", body)
    print(json.dumps(body, indent=1))


def lab_transfer(campaign):
    """How does a MQTTset-trained model do on lab traffic? Descriptive. Proposed E10 is not approved; this is not that experiment."""
    table = load_mqttset()
    table = table[table.label != "lowrate"]
    test_full, manifest, _ = load_lab_run(campaign, "ep_s2")
    test = test_full[~test_full.label.isin(("mixed", "drop"))]
    out = {}
    for feature_name, features in (("all_26", ALL), ("without_F25_F26", NO_CONTEXT)):
        split = s_time(table)
        tr = undersample(split["train"], 0)
        model = make_model("RF", {"n_estimators": 50, "max_depth": 16}, 0).fit(tr[features].values, tr.label.values)
        val_score = scores_of(model, split["val"][features].values)[0]
        tau = pick_tau(val_score[split["val"].label.values == BENIGN])
        score, attack = scores_of(model, test[features].values)
        out[feature_name] = evaluate(np.where(test.label.values == "lowrate", "lowrate", test.label.values), score, attack, tau)
        out[feature_name]["tau"] = tau
    benign_lab = pd.concat([load_lab_run(BENIGN_CAMPAIGN, r)[0] for r in BENIGN_RUNS])
    benign_mqttset = table[table.label == BENIGN]
    ks = {f: float(ks_2samp(benign_lab[f].values, benign_mqttset[f].sample(100000, random_state=0).values).statistic) for f in FEATURE_IDS}
    write_result("ENG-X1-transfer", {"status": STATUS, "note": "trained on MQTTset S-time train (RF, fixed params), tested on lab ep_s2; lowrate has no training class", "results": out, "Q12_ks_benign_lab_vs_mqttset": ks})
    print(json.dumps(out, indent=1))


# Model comparison (SG-05) ------------------------------------------------------------------------------------------------------

def _timed_us(fn, X, calls=2000):
    rows = X[np.random.RandomState(0).randint(0, len(X), calls)]
    times = []
    for row in rows:
        started = time.perf_counter_ns()
        fn(row[None, :])
        times.append(time.perf_counter_ns() - started)
    return float(np.median(times) / 1000)


def _load_peak_kib(path):
    import tracemalloc
    tracemalloc.start()
    joblib.load(path)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return peak / 1024


def lab_compare(campaign="campaign6", frozen="ew-dt12-lab-v6", seed=0):
    """Frozen tree vs LR, RF, rule and rate baselines on identical held-out runs, all thresholds from dev data only.
    Post-freeze comparison: its outcome does not change the deployed model, so the held-out runs are not used for tuning."""
    from sklearn.metrics import confusion_matrix
    card = json.loads((DATA / "models" / frozen / "model_card.json").read_text())
    features = card["feature_ids"]
    dev_full = pd.concat([load_lab_run(c, r)[0] for c, r in dev_runs(campaign)], ignore_index=True)
    dev = dev_full[~dev_full.label.isin(("mixed", "drop"))]
    folds = group_folds(dev.group.values, seed)
    select = json.loads((RESULTS / "ENG-L1-select" / "metrics.json").read_text())
    best = {k: max((c for c in select["candidates"] if c["model"] == k and c["features"] == "without_F25_F26"), key=lambda c: c["cv_macro_f1_mean"])["params"] for k in ("LR", "RF")}
    scratch = []
    frozen_path = DATA / "models" / frozen / "model.joblib"
    frozen_model = joblib.load(frozen_path)
    candidates = {f"DT {frozen} (frozen, deployed)": (lambda X, m=frozen_model: scores_of(m, X), card["tau"], frozen_path, "frozen bundle, not refitted")}
    for kind in ("LR", "RF"):
        oof = np.zeros(len(dev))
        for fold in range(5):
            m = make_model(kind, best[kind], seed).fit(dev[features].values[folds != fold], dev.label.values[folds != fold])
            oof[folds == fold] = scores_of(m, dev[features].values[folds == fold])[0]
        model = make_model(kind, best[kind], seed).fit(dev[features].values, dev.label.values)
        if hasattr(model, "n_jobs"):
            model.n_jobs = 1
        path = RESULTS / f".tmp-{kind}-{os.getpid()}.joblib"
        joblib.dump(model, path, compress=3)
        scratch.append(path)
        candidates[f"{kind} {best[kind]}"] = (lambda X, m=model: scores_of(m, X), pick_tau(oof[dev.label.values == BENIGN]), path, "params from ENG-L1-select, tau from out-of-fold dev benign scores")
    for name, rule in (("rule baseline (dev benign q0.999)", RuleBaseline(features).fit(dev)), ("rate baseline F01 (dev benign q0.999)", RateBaseline(features).fit(dev))):
        path = RESULTS / f".tmp-rule{len(scratch)}-{os.getpid()}.joblib"
        joblib.dump(rule.thresholds, path)
        scratch.append(path)
        candidates[name] = (rule.score, 0.5, path, {"thresholds": rule.thresholds})
    test_full, manifest, _ = load_lab_run(campaign, "ep_s2")
    test = test_full[~test_full.label.isin(("mixed", "drop"))]
    benign_runs = [(BENIGN_CAMPAIGN, r) for r in BENIGN_RUNS] + [("campaign5", "ben_heavy_test2"), ("campaign6", "ben_hold_test")]
    if (campaign_dir("campaign7") / "ben_smart_home" / "tables" / "rows_w5.parquet").exists():
        benign_runs.append(("campaign7", "ben_smart_home"))
    benign_tables = [load_lab_run(c, r)[:2] for c, r in benign_runs]
    stealth_full, stealth_manifest, _ = load_lab_run(BENIGN_CAMPAIGN, "stealth")
    labels = sorted(set(test.label))
    out = {}
    for name, (fn, tau, path, note) in candidates.items():
        score, attack = fn(test[features].values)
        window = evaluate(test.label.values, score, attack, tau)
        window["confusion_matrix"] = {"labels": labels, "rows_true_cols_predicted": confusion_matrix(test.label.values, predict_with_tau(score, attack, tau), labels=labels).tolist()}
        s_all, a_all = fn(test_full[features].values)
        alerts = alert_level(test_full, s_all, a_all, tau, manifest["episodes"])
        per_run, hours = {}, 0.0
        for (c, r), (table, m) in zip(benign_runs, benign_tables):
            s, a = fn(table[features].values)
            per_run[f"{c}/{r}"] = {"windows": len(table), "fp_windows": int((s >= tau).sum()), "false_alerts": alert_level(table, s, a, tau, [])["alerts"]}
            hours += m["seconds"] / 3600
        totals = {k: sum(v[k] for v in per_run.values()) for k in ("windows", "fp_windows", "false_alerts")}
        s_st, a_st = fn(stealth_full[features].values)
        stealth = alert_level(stealth_full, s_st, a_st, tau, stealth_manifest["episodes"])
        out[name] = {"note": note, "tau": tau, "window_metrics": window, "macro_f1_95ci_episode_bootstrap": episode_bootstrap(test, score, attack, tau), "alert_metrics": alerts,
                     "benign_runs": {**totals, "fpr": totals["fp_windows"] / totals["windows"], "hours": hours, "false_alerts_per_hour": totals["false_alerts"] / hours, "per_run": per_run},
                     "stealth_run_untrained_rates": {k: stealth[k] for k in ("episodes_detected", "episodes_total", "by_family")},
                     "inference_us_batch1": _timed_us(fn, test[features].values), "model_bytes": os.path.getsize(path), "load_peak_kib": _load_peak_kib(path)}
        print(name, round(window["macro_f1"], 4), alerts["episodes_detected"], "/", alerts["episodes_total"], "false/h", round(totals["false_alerts"] / hours, 3), flush=True)
    for path in scratch:
        path.unlink(missing_ok=True)
    write_result("ENG-C1-compare", {"status": STATUS, "protocol": "same dev runs, features, alert policy (k=2, 60 s suppression) and held-out runs for every candidate; thresholds from dev only; post-freeze, no candidate or threshold changed after scoring",
                                    "dev_runs": [f"{c}/{r}" for c, r in dev_runs(campaign)], "held_out_run": f"{campaign}/ep_s2", "benign_runs": [f"{c}/{r}" for c, r in benign_runs], "features": features,
                                    "caveat": "one held-out run with 30 episodes; overlapping CIs mean no candidate is shown better than another", "candidates": out})


def lab_splits(campaign="campaign6", seeds=range(5)):
    """RQ1 analogue on lab data (engineering, not E1): one protocol, three ways to split the same dev runs.
    S-rand shuffles windows; S-episode keeps each attack episode and benign source on one side; S-run holds out whole runs.
    The held-out run ep_s2 and the benign test runs are not read."""
    dev = pd.concat([load_lab_run(c, r)[0].assign(run_key=f"{c}/{r}") for c, r in dev_runs(campaign)], ignore_index=True)
    dev = dev[~dev.label.isin(("mixed", "drop"))].reset_index(drop=True)
    features, out = NO_CONTEXT, []
    run_keys = sorted(dev.run_key.unique())
    attack_runs = [r for r in run_keys if dev[dev.run_key == r].label.ne(BENIGN).any()]
    for seed in seeds:
        rng = np.random.RandomState(seed)
        groups = sorted(dev.group.unique())
        rng.shuffle(groups)
        held_groups = set(groups[: len(groups) // 5])
        held_run = attack_runs[seed % len(attack_runs)]
        splits = {"S-rand": rng.rand(len(dev)) < 0.2, "S-episode": dev.group.isin(held_groups).values, "S-run": (dev.run_key == held_run).values}
        for name, test_mask in splits.items():
            train, test = dev[~test_mask], dev[test_mask]
            for kind, params in (("DT", {"max_depth": 12}), ("RF", {"n_estimators": 25, "max_depth": 16})):
                model = make_model(kind, params, seed).fit(train[features].values, train.label.values)
                score, attack = scores_of(model, test[features].values)
                tau = pick_tau(scores_of(model, train[features].values)[0][train.label.values == BENIGN])
                m = evaluate(test.label.values, score, attack, tau)
                out.append({"split": name, "model": kind, "seed": seed, "held_out_run": held_run if name == "S-run" else None, "macro_f1": m["macro_f1"], "fpr": m["fpr"], "binary_recall": m["binary_recall"], "support": m["support"]})
                print(name, kind, seed, round(m["macro_f1"], 4), flush=True)
    summary = {}
    for name in ("S-rand", "S-episode", "S-run"):
        for kind in ("DT", "RF"):
            values = [r["macro_f1"] for r in out if r["split"] == name and r["model"] == kind]
            summary[f"{name} {kind}"] = {"mean": float(np.mean(values)), "std": float(np.std(values)), "min": float(np.min(values)), "n_seeds": len(values)}
    write_result("ENG-R1-lab-splits", {"status": STATUS, "question": "RQ1 analogue: how much does the split change the score on the same lab data?", "dev_runs": run_keys, "features": features,
                                       "note": "tau from training benign scores (in-sample), the same for every split, so differences come from the split. Lab traffic from one generator; not E1, not MQTTset, not a test of H1.",
                                       "summary": summary, "runs": out})


def lab_windows(campaign="campaign6", windows=(1, 5, 10), seed=0):
    """E9 analogue (engineering, not E9): window-size sensitivity on dev runs only, with S-episode group 5-fold.
    Each window size gets its own tables, its own out-of-fold tau, and alert-level replay with k = 2, so time to detect is
    comparable. The held-out run ep_s2 and the benign test runs are not read, and nothing here changes the deployed model."""
    out = {}
    for w in windows:
        tables = []
        for c, r in dev_runs(campaign):
            folder = campaign_dir(c) / r
            if not (folder / "tables" / f"rows_w{w}.parquet").exists():
                run_pipeline(folder / "capture.pcap", folder / "tables", w, _port(c, r), raw_sources=True)
            table, manifest, _ = load_lab_run(c, r, w)
            tables.append((table, manifest))
        dev = pd.concat([t for t, _ in tables], ignore_index=True)
        clean = dev[~dev.label.isin(("mixed", "drop"))].reset_index(drop=True)
        folds = group_folds(clean.group.values, seed)
        oof_score, oof_attack = np.zeros(len(clean)), np.empty(len(clean), dtype=object)
        for fold in range(5):
            m = make_model("DT", {"max_depth": 12}, seed).fit(clean[NO_CONTEXT].values[folds != fold], clean.label.values[folds != fold])
            oof_score[folds == fold], oof_attack[folds == fold] = scores_of(m, clean[NO_CONTEXT].values[folds == fold])
        tau = pick_tau(oof_score[clean.label.values == BENIGN])
        window = evaluate(clean.label.values, oof_score, oof_attack, tau)
        # Alert replay per run with a model fitted without that run's groups would need nested folds; this uses the fold models' out-of-fold scores.
        clean["score"], clean["attack"] = oof_score, oof_attack
        detected = total = 0
        ttd = []
        for (table, manifest), (c, r) in zip(tables, dev_runs(campaign)):
            part = clean[clean.group.str.startswith(f"{c}/{r}-")]  # run names repeat across campaigns; groups are qualified
            level = alert_level(part, part.score.values, part.attack.values, tau, manifest["episodes"], window_s=w)
            detected += level["episodes_detected"]
            total += level["episodes_total"]
            ttd += [v["ttd_median_s"] for v in level["by_family"].values() if v["ttd_median_s"] is not None]
        out[f"W={w}s"] = {"windows": len(clean), "attack_windows": int((clean.label != BENIGN).sum()), "tau": tau, "oof_macro_f1": window["macro_f1"], "oof_fpr": window["fpr"],
                          "oof_binary_recall": window["binary_recall"], "episodes_alerted": detected, "episodes_total": total,
                          "median_of_family_median_ttd_s": float(np.median(ttd)) if ttd else None, "minimum_ttd_bound_s": 2 * w}
        print(w, out[f"W={w}s"], flush=True)
    write_result("ENG-W1-window-size", {"status": STATUS, "question": "E9 analogue: how do 1, 5 and 10 s windows trade detection quality against delay on the same lab dev runs?",
                                         "protocol": "DT depth 12, features without F25/F26, S-episode group 5-fold out-of-fold scores, tau at 1% dev benign FPR, k = 2; dev runs only",
                                         "results": out, "note": "Lab traffic from one generator; not E9. Episode counts include only episodes whose windows were not all mixed or dropped."})


def _port(campaign, run):
    return RUN_PORTS.get(campaign, {}).get(run) or {**LAB_RUNS, **BENIGN_RUNS}[run]


def write_result(experiment, body):
    folder = RESULTS / experiment
    folder.mkdir(parents=True, exist_ok=True)
    body = {"experiment": experiment, "run_date": time.strftime("%Y-%m-%d"), "device": f"development laptop ({platform.processor()}), not a gateway", "extractor_version": EXTRACTOR_VERSION, "sklearn_version": sklearn.__version__, **body}
    (folder / "metrics.json").write_text(json.dumps(body, indent=1))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("dq-mqttset", "mqttset", "lab-tables", "lab-select", "lab-final", "lab-transfer", "lab-stealth", "lab-benign", "lab-compare", "lab-splits", "lab-windows"))
    parser.add_argument("--campaign", default="campaign1")
    parser.add_argument("--kind")
    parser.add_argument("--params", type=json.loads)
    parser.add_argument("--features", default="all_26")
    parser.add_argument("--model-id")
    parser.add_argument("--port", type=int, default=18843)
    parser.add_argument("--run")
    args = parser.parse_args()
    if args.command == "dq-mqttset":
        dq_mqttset()
    elif args.command == "mqttset":
        mqttset_experiment()
    elif args.command == "lab-tables":
        lab_tables(args.campaign)
    elif args.command == "lab-select":
        lab_select(args.campaign)
    elif args.command == "lab-transfer":
        lab_transfer(args.campaign)
    elif args.command == "lab-windows":
        lab_windows(args.campaign)
    elif args.command == "lab-splits":
        lab_splits(args.campaign)
    elif args.command == "lab-compare":
        lab_compare(args.campaign)
    elif args.command == "lab-benign":
        lab_benign_check(args.campaign, args.run, args.port, args.model_id)
    elif args.command == "lab-stealth":
        lab_stealth(args.campaign, args.model_id, port=args.port)
    else:
        lab_final(args.campaign, args.kind, args.params, args.features, args.model_id)


if __name__ == "__main__":
    main()
