"""Config validation, run planning, provenance, and backend dispatch."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
import tomllib
from pathlib import Path

from .manifest import read_manifest, validate_manifest
from .split import assert_disjoint, split_fingerprint

SUPPORTED = {"mfcc_gmm_hmm", "cnn_bilstm_ctc", "wav2vec2", "whisper_small"}


def load_config(path: str | Path) -> dict[str, object]:
    with Path(path).open("rb") as handle: config = tomllib.load(handle)
    missing = {"experiment_id", "model", "mode", "seeds"} - set(config)
    if missing: raise ValueError(f"Config missing: {sorted(missing)}")
    if config["model"] not in SUPPORTED: raise ValueError(f"Unknown model: {config['model']}")
    if config["mode"] not in {"train", "fine_tune", "zero_shot"}: raise ValueError("Invalid mode")
    return config


def prepare_run(config_path: str | Path, manifest_path: str | Path, splits_path: str | Path,
                output_dir: str | Path, execute: bool = False) -> Path:
    config = load_config(config_path); rows = read_manifest(manifest_path)
    issues = validate_manifest(rows, Path(manifest_path).parent)
    if issues: raise ValueError(f"Manifest has {len(issues)} issue(s); first: {issues[0]}")
    assert_disjoint(splits_path)
    run_dir = Path(output_dir) / str(config["experiment_id"]); run_dir.mkdir(parents=True, exist_ok=True)
    record = {"status": "planned" if not execute else "running", "config": config,
              "manifest": str(manifest_path), "splits": str(splits_path),
              "split_fingerprint": split_fingerprint(splits_path), "python": sys.version,
              "platform": platform.platform(), "started_unix": time.time(),
              "corpus_kind": sorted({row["corpus_kind"] for row in rows})}
    record_path = run_dir / "run.json"; record_path.write_text(json.dumps(record, indent=2) + "\n")
    if execute:
        command = [sys.executable, "-m", "cte442_asr.models.runner", "--config", str(config_path),
                   "--manifest", str(manifest_path), "--splits", str(splits_path), "--output", str(run_dir)]
        started = time.perf_counter()
        try:
            subprocess.run(command, check=True)
            record["status"] = "complete"
        except subprocess.CalledProcessError as exc:
            record["status"] = "failed"; record["return_code"] = exc.returncode
            raise
        finally:
            record["training_seconds"] = time.perf_counter() - started
            record["finished_unix"] = time.time()
            record_path.write_text(json.dumps(record, indent=2) + "\n")
    return record_path

