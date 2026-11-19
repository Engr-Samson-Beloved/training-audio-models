"""Deterministic speaker-disjoint splitting and nested hour subsets."""

from __future__ import annotations

import csv
import hashlib
import random
from collections import defaultdict
from pathlib import Path

from .manifest import read_manifest


def speaker_split(rows: list[dict[str, str]], seed: int = 442, train_ratio: float = 0.7,
                  dev_ratio: float = 0.15) -> dict[str, str]:
    speakers = sorted({row["speaker_id"] for row in rows})
    if len(speakers) < 3:
        raise ValueError("At least 3 speakers are required for speaker-disjoint train/dev/test")
    rng = random.Random(seed); rng.shuffle(speakers)
    n = len(speakers)
    n_train = max(1, min(n - 2, round(n * train_ratio)))
    n_dev = max(1, min(n - n_train - 1, round(n * dev_ratio)))
    assignment = {speaker: "train" for speaker in speakers[:n_train]}
    assignment.update({speaker: "dev" for speaker in speakers[n_train:n_train + n_dev]})
    assignment.update({speaker: "test" for speaker in speakers[n_train + n_dev:]})
    return assignment


def write_splits(manifest_path: str | Path, output: str | Path, seed: int = 442) -> None:
    rows = read_manifest(manifest_path)
    assignment = speaker_split(rows, seed)
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["utterance_id", "speaker_id", "split", "split_seed"])
        writer.writeheader()
        for row in rows:
            writer.writerow({"utterance_id": row["utterance_id"], "speaker_id": row["speaker_id"],
                             "split": assignment[row["speaker_id"]], "split_seed": seed})
    assert_disjoint(output)


def read_splits(path: str | Path) -> dict[str, dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return {row["utterance_id"]: row for row in csv.DictReader(handle)}


def assert_disjoint(path: str | Path) -> None:
    by_split: dict[str, set[str]] = defaultdict(set)
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle): by_split[row["split"]].add(row["speaker_id"])
    names = sorted(by_split)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            overlap = by_split[left] & by_split[right]
            if overlap: raise ValueError(f"Speaker leakage between {left}/{right}: {sorted(overlap)}")


def split_fingerprint(path: str | Path) -> str:
    rows = read_splits(path)
    payload = "\n".join(f"{uid},{row['speaker_id']},{row['split']}" for uid, row in sorted(rows.items()))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def nested_hour_subsets(rows: list[dict[str, str]], split_rows: dict[str, dict[str, str]],
                        hours: list[float], seed: int) -> dict[float, list[str]]:
    """Select one deterministic shuffled train order; prefixes make subsets nested."""
    train = [row for row in rows if split_rows[row["utterance_id"]]["split"] == "train"]
    rng = random.Random(seed)
    by_speaker: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in train: by_speaker[row["speaker_id"]].append(row)
    speakers = sorted(by_speaker); rng.shuffle(speakers)
    for speaker in speakers: rng.shuffle(by_speaker[speaker])
    # Round-robin speakers so every nested prefix has broad speaker coverage.
    train = []
    while any(by_speaker.values()):
        for speaker in speakers:
            if by_speaker[speaker]: train.append(by_speaker[speaker].pop())
    result: dict[float, list[str]] = {}
    for target in sorted(hours):
        picked, seconds = [], 0.0
        for row in train:
            if seconds >= target * 3600: break
            picked.append(row["utterance_id"]); seconds += float(row["duration_seconds"])
        if seconds + 1e-9 < target * 3600:
            raise ValueError(f"Training split has {seconds/3600:.2f} h, below requested {target:g} h")
        result[target] = picked
    return result

