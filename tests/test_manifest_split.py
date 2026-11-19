from pathlib import Path

import pytest

from cte442_asr.fixture import make_fixture
from cte442_asr.manifest import read_manifest, validate_manifest
from cte442_asr.split import assert_disjoint, read_splits, speaker_split, write_splits


def test_fixture_manifest_and_speaker_split(tmp_path: Path):
    manifest = make_fixture(tmp_path / "fixture")
    rows = read_manifest(manifest)
    assert not validate_manifest(rows, manifest.parent)
    assignment = speaker_split(rows, seed=442)
    assert set(assignment.values()) == {"train", "dev", "test"}
    split_path = tmp_path / "splits.csv"
    write_splits(manifest, split_path, seed=442)
    assert_disjoint(split_path)
    splits = read_splits(split_path)
    per_speaker = {}
    for item in splits.values():
        per_speaker.setdefault(item["speaker_id"], set()).add(item["split"])
    assert all(len(values) == 1 for values in per_speaker.values())


def test_original_requires_consent_reference(tmp_path: Path):
    manifest = make_fixture(tmp_path / "fixture")
    rows = read_manifest(manifest)
    rows[0]["corpus_kind"] = "original"
    rows[0]["consent_reference"] = ""
    issues = validate_manifest(rows)
    assert any(issue.field == "consent_reference" for issue in issues)
    assert any("mix" in issue.message for issue in issues)


def test_too_few_speakers_rejected(tmp_path: Path):
    rows = [{"speaker_id": "one"}, {"speaker_id": "two"}]
    with pytest.raises(ValueError, match="At least 3"):
        speaker_split(rows)

