import csv
import math
import struct
import wave
from pathlib import Path

import pytest

from cte442_asr.datasets.original import import_original
from cte442_asr.datasets.slr70 import build_manifest
from cte442_asr.audio import validate_and_convert
from cte442_asr.evaluation import evaluate_files
from cte442_asr.manifest import read_manifest, validate_manifest, write_manifest
from cte442_asr.plots import plot_metrics
from cte442_asr.split import assert_disjoint, write_splits


def _wav(path: Path, frequency: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(48000)
        audio.writeframes(b"".join(struct.pack("<h", int(4000 * math.sin(2 * math.pi * frequency * i / 48000))) for i in range(4800)))


def test_slr70_layout_import_and_split(tmp_path: Path):
    root = tmp_path / "slr70"
    for gender_index, gender in enumerate(("female", "male")):
        folder = root / "extracted" / gender
        lines = []
        for speaker in range(3):
            for utterance in range(2):
                file_id = f"en_ng_{gender[0]}{speaker:02d}_{utterance:04d}"
                _wav(folder / f"{file_id}.wav", 200 + gender_index * 50 + speaker)
                lines.append(f"{file_id}\tpublic importer test sentence {utterance}\n")
        (folder / "line_index.tsv").write_text("".join(lines), encoding="utf-8")
    manifest = build_manifest(root, require_expected_count=False)
    rows = read_manifest(manifest)
    assert len(rows) == 12
    assert {row["corpus_kind"] for row in rows} == {"public"}
    assert {row["noise_condition"] for row in rows} == {"unspecified"}
    assert not validate_manifest(rows, manifest.parent)
    splits = root / "splits.csv"; write_splits(manifest, splits); assert_disjoint(splits)
    converted = root / "audio_16k"
    converted_manifest = root / "manifest.16k.csv"
    assert validate_and_convert(manifest, converted, root / "validation.csv", converted_manifest) == 0
    split_16k = root / "splits_16k.csv"; write_splits(converted_manifest, split_16k)
    split_rows = {}
    with split_16k.open(newline="", encoding="utf-8") as handle:
        split_rows = {row["utterance_id"]: row for row in csv.DictReader(handle)}
    predictions = root / "integration_predictions_NOT_ASR.csv"
    fields = ["utterance_id", "hypothesis", "model", "seed", "training_hours", "lm_rescoring",
              "inference_seconds", "model_size_bytes", "training_seconds"]
    converted_rows = read_manifest(converted_manifest)
    with predictions.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for seed in (11, 22, 33, 44, 55):
            for row in converted_rows:
                if split_rows[row["utterance_id"]]["split"] == "test":
                    writer.writerow({"utterance_id": row["utterance_id"], "hypothesis": "integration input",
                        "model": "slr70_layout_test_NOT_ASR", "seed": seed, "training_hours": 0,
                        "lm_rescoring": "false", "inference_seconds": 0, "model_size_bytes": 0,
                        "training_seconds": 0})
    results = root / "integration_results_NOT_DATASET_RESULTS"
    evaluate_files(converted_manifest, split_16k, predictions, results, bootstrap_samples=20)
    plot_metrics(results / "utterance_metrics.csv", results / "plots")
    with (results / "seed_summary.csv").open(newline="", encoding="utf-8") as handle:
        summaries = list(csv.DictReader(handle))
    assert summaries and {row["corpus_kind"] for row in summaries} == {"public"}


def test_original_ingress_rejects_public_manifest(tmp_path: Path):
    audio = tmp_path / "one.wav"; _wav(audio, 220)
    row = {"utterance_id": "one", "audio_path": str(audio), "speaker_id": "spk1",
           "transcript": "test", "speech_type": "prompted", "recording_device": "phone",
           "noise_condition": "quiet", "language": "en-NG", "accent_region": "unspecified",
           "age_group": "unspecified", "gender": "unspecified", "self_reported_proficiency": "unspecified",
           "corpus_kind": "public", "duration_seconds": "0.1", "transcript_status": "reviewed",
           "consent_reference": "https://example.invalid/license"}
    source = tmp_path / "source.csv"; write_manifest(source, [row])
    with pytest.raises(ValueError, match="corpus_kind=original"):
        import_original(source, tmp_path / "original.csv")

