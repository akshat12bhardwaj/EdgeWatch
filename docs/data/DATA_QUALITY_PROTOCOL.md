# Data Quality Protocol

**Why this exists:** dataset construction errors can change benchmark outcomes materially. Engelen et al. reconstructed or relabelled more than 20% of CICIDS2017 traces [R, P31]. Arp et al. list data snooping and spurious correlations among the common pitfalls [R, P30]. The MQTTset paper itself contains count inconsistencies [R, P08]. Run every check below **before** any model is trained on a dataset, and record the results in `results/data_quality/<dataset>.md`.

## 1. Provenance checks

| # | Check | Pass criterion |
|---|---|---|
| Q1 | Checksums recorded for every raw file | `data/MANIFEST.sha256` exists and verifies |
| Q2 | Source, URL, download date, and version recorded | Entry in `data/SOURCES.md` |
| Q3 | Licence/terms recorded | Entry in [DECISIONS.md](../DECISIONS.md) or an "unknown – academic use only, no redistribution" note |

## 2. Consistency checks

| # | Check | Pass criterion |
|---|---|---|
| Q4 | Packet counts per capture match the paper's tables (e.g., P08 Table 3) | Within 1%. If not, document the discrepancy rather than "fix" it silently |
| Q5 | Each attack capture contains traffic from the documented attacker IP | Attacker IP identified; if ambiguous, set `label_confidence = mixed` |
| Q6 | Attack captures also contain benign background traffic? | Quantify the benign packets inside attack captures. Label windows by **source**, not by file, when both are present |
| Q7 | Duplicate packets/rows | Report the duplicate rate. **Never** oversample before splitting (MQTTset's balancing replicated attack records [R]) |
| Q8 | Timestamps monotonic within each capture; capture durations plausible | Report gaps longer than 60 s |
| Q9 | tshark reports malformed or unknown frames | Report counts; expected for the `malformed` class only |

## 3. Shortcut (spurious correlation) checks

| # | Check | Method |
|---|---|---|
| Q10 | Can a model predict the label from **non-features**? | Train a DT on `source_key`, time-of-capture, and capture file length alone. If macro-F1 > 0.9, the dataset has identity/time shortcuts. Our features exclude these, but report the result |
| Q11 | Single-feature leakage | Train a depth-1 tree per feature. Any single feature with macro-F1 > 0.95 is inspected manually (it may be a legitimate signal, e.g., F11 for brute force, or an artefact) |
| Q12 | Testbed artefacts | Compare benign-feature distributions across datasets (KS test per feature). Large shifts on features such as packet length point to testbed-specific behaviour |

## 4. Labelling rules

1. Window label = the family of the attack whose **attacker source** produced the window, if the window lies inside a documented attack interval. Otherwise `benign`.
2. Windows from the attacker source that lie outside any attack interval are labelled `benign` only if the dataset documents that the attacker host also behaved benignly. Otherwise they are **dropped** and the count is reported.
3. Windows that straddle the start or end of an attack are marked `label_confidence = mixed` and excluded from test sets (they are reported in a sensitivity analysis).
4. For lab runs, labels come from `schedule.json` written by the experiment runner **before** the attack starts. Labels are never derived from model output.

## 5. Class imbalance

- Report the class distribution per dataset and per split.
- Handle imbalance **inside the training fold only**: class weights first, undersampling of benign second. Never oversample before splitting.
- Report metrics that are robust to imbalance (macro-F1, balanced accuracy, per-class recall, FPR).

## 6. Output

For each dataset, produce a one-page `results/data_quality/<dataset>.md` with: the Q1–Q12 outcomes, the class table, discrepancies found, and decisions taken. The data workstream lead (S2) and the ML lead (S3) both review it before M2.
