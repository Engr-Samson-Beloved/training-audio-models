"""Fine-tuning-hour and ablation study plan generation."""

from __future__ import annotations

import csv
import itertools
import json
from pathlib import Path

from .manifest import read_manifest
from .split import nested_hour_subsets, read_splits, split_fingerprint
from .training import load_config


def build_study_plan(config_path: str | Path, manifest_path: str | Path, splits_path: str | Path,
                     output_dir: str | Path) -> Path:
    config = load_config(config_path); rows = read_manifest(manifest_path); splits = read_splits(splits_path)
    hours = [float(value) for value in config.get("hours", [0])]
    seeds = [int(value) for value in config.get("seeds", [11])]
    rescoring = config.get("lm_rescoring", [False])
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    subset_files: dict[tuple[int, float], str] = {}
    if any(hours):
        for seed in seeds:
            subsets = nested_hour_subsets(rows, splits, hours, seed)
            for hour, utterance_ids in subsets.items():
                path = out / f"train_{hour:g}h_seed{seed}.txt"
                path.write_text("\n".join(utterance_ids) + "\n", encoding="utf-8")
                subset_files[(seed, hour)] = str(path)
    plan = []
    for seed, hour, lm in itertools.product(seeds, hours, rescoring):
        plan.append({"experiment_id": config["experiment_id"], "model": config["model"],
            "mode": config["mode"], "seed": seed, "hours": hour, "lm_rescoring": bool(lm),
            "train_subset": subset_files.get((seed, hour), "all_train"),
            "split_fingerprint": split_fingerprint(splits_path)})
    plan_path = out / "study_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return plan_path


def rescore_nbest(input_path: str | Path, output_path: str | Path, lm_weight: float = 0.3) -> None:
    """Apply supplied LM log-scores to n-best acoustic candidates (no score fabrication)."""
    with Path(input_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"utterance_id", "hypothesis", "model", "seed", "training_hours", "lm_rescoring",
                "inference_seconds", "model_size_bytes", "training_seconds",
                "acoustic_logprob", "lm_logprob", "rank"}
    if not rows or required - set(rows[0]): raise ValueError(f"n-best CSV needs {sorted(required)}")
    best: dict[str, tuple[float, dict[str, str]]] = {}
    for row in rows:
        score = float(row["acoustic_logprob"]) + lm_weight * float(row["lm_logprob"])
        if row["utterance_id"] not in best or score > best[row["utterance_id"]][0]: best[row["utterance_id"]] = (score, row)
    output = Path(output_path); output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) + ["rescored_logprob", "lm_weight"]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for _, (score, row) in sorted(best.items()):
            writer.writerow({**row, "lm_rescoring": "true", "rescored_logprob": score,
                             "lm_weight": lm_weight})

