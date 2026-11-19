"""WER/CER, slices, paired bootstrap intervals, and seed summaries."""

from __future__ import annotations

import csv
import math
import random
import re
import statistics
import itertools
import unicodedata
from collections import defaultdict
from pathlib import Path

from .manifest import read_manifest
from .split import read_splits


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def edit_counts(reference: list[str], hypothesis: list[str]) -> tuple[int, int, int, int]:
    """Return substitutions, deletions, insertions, and reference length."""
    n, m = len(reference), len(hypothesis)
    dp = [[(0, 0, 0, 0)] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1): dp[i][0] = (i, 0, i, 0)
    for j in range(1, m + 1): dp[0][j] = (j, 0, 0, j)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if reference[i - 1] == hypothesis[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                candidates = [
                    (dp[i - 1][j - 1][0] + 1, dp[i - 1][j - 1][1] + 1,
                     dp[i - 1][j - 1][2], dp[i - 1][j - 1][3]),
                    (dp[i - 1][j][0] + 1, dp[i - 1][j][1], dp[i - 1][j][2] + 1,
                     dp[i - 1][j][3]),
                    (dp[i][j - 1][0] + 1, dp[i][j - 1][1], dp[i][j - 1][2],
                     dp[i][j - 1][3] + 1),
                ]
                dp[i][j] = min(candidates)
    _, substitutions, deletions, insertions = dp[n][m]
    return substitutions, deletions, insertions, n


def score(reference: str, hypothesis: str, unit: str = "word") -> dict[str, float | int]:
    ref, hyp = normalize_text(reference), normalize_text(hypothesis)
    ref_tokens = ref.split() if unit == "word" else list(ref.replace(" ", ""))
    hyp_tokens = hyp.split() if unit == "word" else list(hyp.replace(" ", ""))
    s, d, i, n = edit_counts(ref_tokens, hyp_tokens)
    return {"substitutions": s, "deletions": d, "insertions": i, "reference_units": n,
            "error_rate": (s + d + i) / n if n else (0.0 if not hyp_tokens else 1.0)}


def sentence_length_bucket(transcript: str) -> str:
    length = len(normalize_text(transcript).split())
    return "short_1_5" if length <= 5 else "medium_6_12" if length <= 12 else "long_13_plus"


def _prediction_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"utterance_id", "hypothesis", "model", "seed", "training_hours", "lm_rescoring",
                "inference_seconds", "model_size_bytes", "training_seconds"}
    missing = required - set(rows[0] if rows else [])
    if missing: raise ValueError(f"Predictions missing fields: {sorted(missing)}")
    return rows


def evaluate_files(manifest_path: str | Path, splits_path: str | Path, predictions_path: str | Path,
                   output_dir: str | Path, bootstrap_samples: int = 2000, seed: int = 442) -> None:
    manifest = {row["utterance_id"]: row for row in read_manifest(manifest_path)}
    splits = read_splits(splits_path)
    predictions = _prediction_rows(predictions_path)
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    utterances: list[dict[str, object]] = []
    for pred in predictions:
        uid = pred["utterance_id"]
        if uid not in manifest or uid not in splits: raise ValueError(f"Unknown utterance: {uid}")
        if splits[uid]["split"] != "test": continue
        row = manifest[uid]
        wer, cer = score(row["transcript"], pred["hypothesis"]), score(row["transcript"], pred["hypothesis"], "char")
        utterances.append({**pred, "speaker_id": row["speaker_id"], "reference": row["transcript"],
            "corpus_kind": row["corpus_kind"], "noise_condition": row["noise_condition"],
            "accent_region": row["accent_region"] or "unspecified", "age_group": row["age_group"] or "unspecified",
            "gender": row["gender"] or "unspecified", "speech_type": row["speech_type"],
            "self_reported_proficiency": row["self_reported_proficiency"] or "unspecified",
            "sentence_length": sentence_length_bucket(row["transcript"]),
            "wer_errors": wer["substitutions"] + wer["deletions"] + wer["insertions"],
            "wer_reference": wer["reference_units"], "wer": wer["error_rate"],
            "cer_errors": cer["substitutions"] + cer["deletions"] + cer["insertions"],
            "cer_reference": cer["reference_units"], "cer": cer["error_rate"]})
    _write_csv(out / "utterance_metrics.csv", utterances)
    slices = summarize_slices(utterances)
    _write_csv(out / "slice_metrics.csv", slices)
    intervals = bootstrap_intervals(utterances, bootstrap_samples, seed)
    _write_csv(out / "bootstrap_intervals.csv", intervals)
    comparisons = paired_model_intervals(utterances, bootstrap_samples, seed)
    if comparisons: _write_csv(out / "paired_model_intervals.csv", comparisons)
    _write_csv(out / "seed_summary.csv", summarize_seeds(slices))


def summarize_slices(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output = []
    dimensions = [("overall", None), ("speaker_group:accent_region", "accent_region"),
                  ("speaker_group:age_group", "age_group"), ("speaker_group:gender", "gender"),
                  ("speaker_group:self_reported_proficiency", "self_reported_proficiency"),
                  ("noise_condition", "noise_condition"), ("sentence_length", "sentence_length")]
    run_keys = ("corpus_kind", "model", "seed", "training_hours", "lm_rescoring")
    for dimension, field in dimensions:
        groups: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            groups[tuple(row[k] for k in run_keys) + ((row[field] if field else "all"),)].append(row)
        for key, items in groups.items():
            result = {k: value for k, value in zip(run_keys, key[:5])}
            result.update({"dimension": dimension, "group": key[5], "utterances": len(items),
                "speakers": len({item["speaker_id"] for item in items})})
            for metric in ("wer", "cer"):
                errors = sum(int(item[f"{metric}_errors"]) for item in items)
                units = sum(int(item[f"{metric}_reference"]) for item in items)
                result[metric] = errors / units if units else 0.0
            result["inference_seconds"] = sum(float(item["inference_seconds"]) for item in items)
            result["model_size_bytes"] = max(int(item["model_size_bytes"]) for item in items)
            result["training_seconds"] = max(float(item["training_seconds"]) for item in items)
            output.append(result)
    return output


def bootstrap_intervals(rows: list[dict[str, object]], samples: int, seed: int) -> list[dict[str, object]]:
    """Cluster bootstrap test speakers for each run; preserves within-speaker dependence."""
    result = []
    runs: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows: runs[(row["corpus_kind"], row["model"], row["seed"], row["training_hours"], row["lm_rescoring"])].append(row)
    for run, items in runs.items():
        by_speaker: dict[object, list[dict[str, object]]] = defaultdict(list)
        for item in items: by_speaker[item["speaker_id"]].append(item)
        speakers = sorted(by_speaker, key=str)
        rng = random.Random(f"{seed}:{run}")
        for metric in ("wer", "cer"):
            values = []
            for _ in range(samples):
                sampled = [rng.choice(speakers) for _ in speakers]
                picked = [row for speaker in sampled for row in by_speaker[speaker]]
                errors = sum(int(row[f"{metric}_errors"]) for row in picked)
                units = sum(int(row[f"{metric}_reference"]) for row in picked)
                values.append(errors / units if units else 0.0)
            values.sort()
            lo = values[max(0, int(0.025 * samples) - 1)] if values else math.nan
            hi = values[min(len(values) - 1, int(0.975 * samples))] if values else math.nan
            result.append({"corpus_kind": run[0], "model": run[1], "seed": run[2], "training_hours": run[3], "lm_rescoring": run[4], "metric": metric,
                           "method": "speaker_cluster_bootstrap", "samples": samples, "ci_low": lo, "ci_high": hi})
    return result


def paired_model_intervals(rows: list[dict[str, object]], samples: int, seed: int) -> list[dict[str, object]]:
    """Paired cluster bootstrap differences (model A minus B) on identical speakers."""
    grouped: dict[tuple[object, object, object, object], dict[object, list[dict[str, object]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows: grouped[(row["corpus_kind"], row["seed"], row["training_hours"], row["lm_rescoring"])][row["model"]].append(row)
    output = []
    for (corpus_kind, run_seed, training_hours, lm), models in grouped.items():
        for model_a, model_b in itertools.combinations(sorted(models, key=str), 2):
            by_a, by_b = defaultdict(list), defaultdict(list)
            for row in models[model_a]: by_a[row["speaker_id"]].append(row)
            for row in models[model_b]: by_b[row["speaker_id"]].append(row)
            speakers = sorted(set(by_a) & set(by_b), key=str)
            if not speakers: continue
            rng = random.Random(f"paired:{seed}:{run_seed}:{lm}:{model_a}:{model_b}")
            for metric in ("wer", "cer"):
                differences = []
                for _ in range(samples):
                    picked = [rng.choice(speakers) for _ in speakers]
                    rates = []
                    for lookup in (by_a, by_b):
                        selected = [row for speaker in picked for row in lookup[speaker]]
                        errors = sum(int(row[f"{metric}_errors"]) for row in selected)
                        units = sum(int(row[f"{metric}_reference"]) for row in selected)
                        rates.append(errors / units if units else 0.0)
                    differences.append(rates[0] - rates[1])
                differences.sort()
                output.append({"corpus_kind": corpus_kind, "model_a": model_a, "model_b": model_b, "seed": run_seed,
                    "training_hours": training_hours,
                    "lm_rescoring": lm, "metric": metric, "difference": "model_a_minus_model_b",
                    "samples": samples, "speakers": len(speakers),
                    "ci_low": differences[max(0, int(0.025 * samples) - 1)],
                    "ci_high": differences[min(len(differences) - 1, int(0.975 * samples))]})
    return output


def summarize_seeds(slice_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in slice_rows:
        groups[(row["corpus_kind"], row["model"], row["training_hours"], row["lm_rescoring"], row["dimension"], row["group"])].append(row)
    output = []
    # two-sided 95% t critical values for df 1..4; normal approximation thereafter.
    critical = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776}
    for key, items in groups.items():
        for metric in ("wer", "cer", "inference_seconds", "training_seconds"):
            values = [float(item[metric]) for item in items]
            mean = statistics.mean(values); sd = statistics.stdev(values) if len(values) > 1 else 0.0
            margin = (critical.get(len(values) - 1, 1.96) * sd / math.sqrt(len(values))) if len(values) > 1 else 0.0
            output.append({"corpus_kind": key[0], "model": key[1], "training_hours": key[2], "lm_rescoring": key[3], "dimension": key[4], "group": key[5],
                           "metric": metric, "n_seeds": len(values), "mean": mean, "sample_sd": sd,
                           "ci95_low": mean - margin, "ci95_high": mean + margin})
    return output


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows: raise ValueError(f"No evaluable test predictions for {path}")
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)

