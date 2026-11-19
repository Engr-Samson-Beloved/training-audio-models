"""Manifest schema, loading, and validation."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FIELDS = (
    "utterance_id", "audio_path", "speaker_id", "transcript", "speech_type",
    "recording_device", "noise_condition", "language", "accent_region", "age_group",
    "gender", "self_reported_proficiency", "corpus_kind", "duration_seconds",
    "transcript_status", "consent_reference",
)
ENUMS = {
    "speech_type": {"prompted", "free"},
    "noise_condition": {"quiet", "noisy", "unspecified"},
    "corpus_kind": {"fixture", "public", "original"},
    "transcript_status": {"unreviewed", "reviewed", "adjudicated"},
}


@dataclass(frozen=True)
class ManifestIssue:
    row: int
    field: str
    message: str


def read_manifest(path: str | Path) -> list[dict[str, str]]:
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = set(REQUIRED_FIELDS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Manifest missing columns: {sorted(missing)}")
        return [dict(row) for row in reader]


def write_manifest(path: str | Path, rows: list[dict[str, object]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(REQUIRED_FIELDS)
    extras = sorted({key for row in rows for key in row} - set(fields))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields + extras)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields + extras})


def validate_manifest(rows: list[dict[str, str]], base_dir: str | Path | None = None) -> list[ManifestIssue]:
    issues: list[ManifestIssue] = []
    seen: set[str] = set()
    kinds: set[str] = set()
    base = Path(base_dir) if base_dir else None
    for number, row in enumerate(rows, start=2):
        for field in REQUIRED_FIELDS:
            if field not in row or (not row[field].strip() and field not in {"consent_reference"}):
                issues.append(ManifestIssue(number, field, "required value is empty"))
        uid = row.get("utterance_id", "")
        if uid in seen:
            issues.append(ManifestIssue(number, "utterance_id", "duplicate"))
        seen.add(uid)
        for field, allowed in ENUMS.items():
            if row.get(field) not in allowed:
                issues.append(ManifestIssue(number, field, f"must be one of {sorted(allowed)}"))
        kind = row.get("corpus_kind", "")
        kinds.add(kind)
        if kind == "original" and not row.get("consent_reference", "").strip():
            issues.append(ManifestIssue(number, "consent_reference", "required for original corpus"))
        try:
            if float(row.get("duration_seconds", "")) <= 0:
                raise ValueError
        except ValueError:
            issues.append(ManifestIssue(number, "duration_seconds", "must be a positive number"))
        if base:
            audio = Path(row.get("audio_path", ""))
            resolved = audio if audio.is_absolute() else base / audio
            if not resolved.exists():
                issues.append(ManifestIssue(number, "audio_path", f"not found: {resolved}"))
    if len(kinds - {""}) > 1:
        issues.append(ManifestIssue(0, "corpus_kind", "a manifest cannot mix corpus kinds"))
    return issues


def assert_research_manifest(rows: list[dict[str, str]]) -> None:
    """Prevent fixture/public data from being silently treated as original results."""
    kinds = {row["corpus_kind"] for row in rows}
    if kinds != {"original"}:
        raise ValueError(f"Research result command requires corpus_kind=original; found {sorted(kinds)}")

