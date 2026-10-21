# Data Dictionary

This file defines every table the project produces. Feature definitions live in [FEATURE_SPECIFICATION.md](../architecture/FEATURE_SPECIFICATION.md), and event schemas in [DATA_FLOW.md](../architecture/DATA_FLOW.md#3-event-contract). This file covers the **on-disk tables** only.

## 1. `fields_<capture>.tsv` (tshark export, intermediate)

One row per packet. Columns are exactly the field list in FEATURE_SPECIFICATION §1, in that order. Empty values are kept as empty strings. Not stored long-term.

## 2. `windows.parquet` (feature table)

| Column | Type | Description |
|---|---|---|
| `dataset` | str | `mqttset`, `mqtt_iot_ids2020`, `ciciomt2024`, `lab` |
| `capture_id` | str | Source PCAP file name (or lab `run_id`) |
| `episode_id` | str | Attack episode identifier (contiguous attack interval), or `benign-<n>` |
| `window_start` | float | Epoch seconds |
| `source_key` | str | Hash of source IP (salted per dataset). **Not a feature** |
| `F01` … `F26` | float | Features |
| `label_raw` | str | Dataset's own label |
| `label_family` | str | Harmonised family ([DATASET_SELECTION.md §3](DATASET_SELECTION.md#3-label-harmonisation-for-cross-dataset-tests-e2)) |
| `label_binary` | int | 0 benign / 1 attack |
| `label_confidence` | str | `file`, `ip+time`, or `mixed` (how the label was inferred; see DATA_QUALITY_PROTOCOL) |
| `extractor_version` | str | e.g. `fx-0.1` |

## 3. `splits/<split_name>.json`

`{ "split": "time_blocked", "seed": 0, "train": [episode_ids...], "val": [...], "test": [...], "gap_s": 10 }`

Splits are defined over **episodes and time ranges**, never over individual rows (see [EVALUATION_PROTOCOL.md](../experiments/EVALUATION_PROTOCOL.md#3-splits)).

## 4. `results/<exp_id>/metrics.json`

| Key | Description |
|---|---|
| `exp_id`, `model`, `split`, `dataset_train`, `dataset_test`, `seed` | Identity |
| `macro_f1`, `balanced_accuracy`, `fpr`, `per_class` {class: {precision, recall, f1, support}} | Quality |
| `ci95` | Bootstrap intervals (episode-level resampling) |
| `train_time_s`, `model_size_bytes`, `inference_us_per_window` (laptop) | Cost (offline) |
| `git_commit`, `env` {python, sklearn, numpy, os, cpu} | Reproducibility |

## 5. `results/<run_id>/` (lab run)

| File | Content |
|---|---|
| `manifest.json` | Operator, start/end, scenario file hash, allow-list hash, device, versions |
| `schedule.json` | Ground-truth attack intervals `[{family, start, end, source_key}]` |
| `events.jsonl` | All events (window, alert, resource, topology, run_marker) |
| `resource.csv` | 1 Hz resource samples |
| `stage_latency.csv` | Per-window stage latencies |
| `capture_stats.json` | tshark packets received / dropped |

## 6. Model card `model_card.json`

`model_id`, `estimator`, `hyperparameters`, `feature_order`, `extractor_version`, `train_data` (dataset, split, row counts, SHA-256 of the feature table), `threshold`, `sklearn_version`, `seed`, `created_at`, `metrics_ref`.
