import csv
from pathlib import Path

from cte442_asr.audio import inspect_wav, validate_and_convert
from cte442_asr.evaluation import evaluate_files
from cte442_asr.fixture import make_fixture, smoke_predictions
from cte442_asr.plots import plot_metrics
from cte442_asr.split import write_splits
from cte442_asr.webapp import project_status


def test_complete_fixture_pipeline(tmp_path: Path):
    root = tmp_path / "fixture"
    manifest = make_fixture(root)
    converted = root / "audio_16k"
    converted_manifest = converted / "manifest.csv"
    assert validate_and_convert(manifest, converted, root / "validation.csv", converted_manifest) == 0
    with converted_manifest.open(newline="", encoding="utf-8") as handle:
        converted_rows = list(csv.DictReader(handle))
    assert all(inspect_wav(converted / row["audio_path"])["sample_rate"] == 16000 for row in converted_rows)
    splits = root / "splits.csv"; write_splits(manifest, splits)
    predictions = root / "predictions.csv"; smoke_predictions(manifest, splits, predictions)
    results = tmp_path / "results"
    evaluate_files(manifest, splits, predictions, results, bootstrap_samples=20)
    plot_metrics(results / "utterance_metrics.csv", results / "plots")
    assert (results / "seed_summary.csv").exists()
    assert len(list((results / "plots").glob("*.svg"))) == 4


def test_dashboard_status_is_provenance_separated():
    status = project_status()
    assert set(status["datasets"]) == {"fixture", "slr70", "original"}
    assert status["datasets"]["fixture"]["corpus_kind"] == "fixture"
    assert status["warning"]

