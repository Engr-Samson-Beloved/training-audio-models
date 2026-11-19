"""Inference helpers and runtime/model-size measurement."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Callable

from .manifest import read_manifest
from .split import read_splits


def directory_size(path: str | Path | int) -> int:
    if isinstance(path, int): return path
    path = Path(path)
    return path.stat().st_size if path.is_file() else sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def run_inference(manifest_path: str | Path, splits_path: str | Path, transcribe: Callable[[Path], str],
                  model: str, seed: int, artifact: str | Path | int, output: str | Path,
                  training_seconds: float = 0.0, lm_rescoring: bool = False,
                  training_hours: float = 0.0) -> None:
    rows, splits = read_manifest(manifest_path), read_splits(splits_path)
    fields = ["utterance_id", "hypothesis", "model", "seed", "training_hours", "lm_rescoring",
              "inference_seconds", "model_size_bytes", "training_seconds"]
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for row in rows:
            if splits[row["utterance_id"]]["split"] != "test": continue
            audio = Path(row["audio_path"])
            if not audio.is_absolute(): audio = Path(manifest_path).parent / audio
            started = time.perf_counter(); hypothesis = transcribe(audio); elapsed = time.perf_counter() - started
            writer.writerow({"utterance_id": row["utterance_id"], "hypothesis": hypothesis,
                "model": model, "seed": seed, "lm_rescoring": str(lm_rescoring).lower(),
                "training_hours": training_hours,
                "inference_seconds": elapsed, "model_size_bytes": directory_size(artifact),
                "training_seconds": training_seconds})

