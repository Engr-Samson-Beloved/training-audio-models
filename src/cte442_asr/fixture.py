"""Generate a clearly labelled non-speech fixture for pipeline smoke tests."""

from __future__ import annotations

import csv
import math
import struct
import wave
from pathlib import Path

from .manifest import write_manifest
from .split import read_splits


NOTICE = "SYNTHETIC NON-SPEECH FIXTURE — NEVER REPORT AS ASR OR ORIGINAL-CORPUS RESULTS"


def make_fixture(root: str | Path = "data/fixture") -> Path:
    root = Path(root); audio_dir = root / "audio"; audio_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    transcripts = ["fixture alpha", "fixture beta signal"]
    for speaker_index in range(9):
        speaker = f"fixture_spk_{speaker_index:02d}"
        for utterance_index, transcript in enumerate(transcripts):
            uid = f"fx_{speaker_index:02d}_{utterance_index:02d}"
            duration = 0.35 + 0.05 * utterance_index
            filename = f"{uid}.wav"
            _tone(audio_dir / filename, 8000 if utterance_index == 0 else 22050, duration,
                  220 + 15 * speaker_index)
            rows.append({"utterance_id": uid, "audio_path": f"audio/{filename}",
                "speaker_id": speaker, "transcript": transcript,
                "speech_type": "prompted" if utterance_index == 0 else "free",
                "recording_device": "synthetic_wave_generator",
                "noise_condition": "quiet" if speaker_index % 2 == 0 else "noisy",
                "language": "fixture-not-a-language", "accent_region": "not_applicable",
                "age_group": "not_applicable", "gender": "not_applicable",
                "self_reported_proficiency": "not_applicable", "corpus_kind": "fixture",
                "duration_seconds": f"{duration:.3f}", "transcript_status": "adjudicated",
                "consent_reference": "not_applicable_synthetic_fixture"})
    manifest = root / "manifest.csv"; write_manifest(manifest, rows)
    (root / "FIXTURE_NOTICE.txt").write_text(NOTICE + "\n", encoding="utf-8")
    return manifest


def _tone(path: Path, sample_rate: int, seconds: float, frequency: float) -> None:
    frames = int(sample_rate * seconds)
    payload = bytearray()
    for index in range(frames):
        sample = int(9000 * math.sin(2 * math.pi * frequency * index / sample_rate))
        payload.extend(struct.pack("<h", sample))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(sample_rate); wav.writeframes(payload)


def smoke_predictions(manifest_path: str | Path, splits_path: str | Path, output: str | Path) -> None:
    from .manifest import read_manifest
    rows, splits = read_manifest(manifest_path), read_splits(splits_path)
    fields = ["utterance_id", "hypothesis", "model", "seed", "training_hours", "lm_rescoring",
              "inference_seconds", "model_size_bytes", "training_seconds"]
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for seed in (11, 22, 33, 44, 55):
            for idx, row in enumerate(rows):
                if splits[row["utterance_id"]]["split"] != "test": continue
                words = row["transcript"].split()
                # Deterministic fake hypotheses test edit accounting only; no model/audio is used.
                hypothesis = " ".join(words[:-1]) if (idx + seed) % 3 == 0 else row["transcript"]
                writer.writerow({"utterance_id": row["utterance_id"], "hypothesis": hypothesis,
                    "model": "fixture_plumbing_input_NOT_ASR", "seed": seed,
                    "training_hours": "0",
                    "lm_rescoring": "false", "inference_seconds": "0",
                    "model_size_bytes": "0", "training_seconds": "0"})

