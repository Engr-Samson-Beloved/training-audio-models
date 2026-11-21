from __future__ import annotations

import csv

from cte442_asr import webapp


class Form:
    def __init__(self, values: dict[str, str]): self.values = values
    def getfirst(self, name: str, default: str = "") -> str: return self.values.get(name, default)


def test_recording_intake_queues_review_only(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, "INCOMING_ROOT", tmp_path / "incoming")
    monkeypatch.setattr(webapp, "INCOMING_AUDIO_ROOT", tmp_path / "incoming" / "audio")
    monkeypatch.setattr(webapp, "INCOMING_QUEUE", tmp_path / "incoming" / "queue.csv")
    form = Form({
        "consent_ack": "yes", "speaker_id": "g2_speaker_014", "consent_reference": "consent_014",
        "transcript": "the quick brown fox", "speech_type": "prompted", "noise_condition": "quiet",
        "language": "en", "accent_region": "",
    })
    result = webapp.save_recording(form, "audio/webm", b"non-personal-test-bytes")
    assert result["status"] == "pending_review"
    with webapp.INCOMING_QUEUE.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["corpus_kind"] == "original"
    assert rows[0]["transcript_status"] == "unreviewed"
    assert rows[0]["accent_region"] == "unspecified"
    assert not (tmp_path / "incoming" / "manifest.csv").exists()


def test_recording_intake_requires_consent():
    form = Form({"speaker_id": "g2_speaker_014", "consent_reference": "consent_014", "transcript": "hello"})
    try:
        webapp._recording_row(form, "audio/webm", b"test")
    except ValueError as exc:
        assert "consent" in str(exc).lower()
    else:
        raise AssertionError("Expected consent validation to fail")
