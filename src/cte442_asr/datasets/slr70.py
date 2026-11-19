"""OpenSLR SLR70 Nigerian-English public-development dataset importer."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import urllib.request
import wave
import zipfile
from collections import Counter
from pathlib import Path

from ..manifest import write_manifest

RESOURCE_URL = "https://www.openslr.org/70/"
BASE_URL = "https://www.openslr.org/resources/70"
LICENSE_NAME = "CC BY-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
EXPECTED_UTTERANCES = 3359

# SHA-256 values published in the Hugging Face OpenSLR dataset metadata.
ARCHIVES = {
    "female": {
        "filename": "en_ng_female.zip",
        "bytes": 759_856_787,
        "sha256": "e840afea824c9075db8c7d574e993837c6a4861fd0ff0275c4cc223aa00a785c",
    },
    "male": {
        "filename": "en_ng_male.zip",
        "bytes": 454_098_409,
        "sha256": "f619d09d5ffdf0d4044ef1d57585eeaa50c0cbf08844782a9dd08f56ea9e567f",
    },
}
METADATA_FILES = ("about.html", "LICENSE", "checksum.md5", "line_index_female.tsv", "line_index_male.tsv")


def download_slr70(root: str | Path, base_url: str = BASE_URL) -> None:
    """Download one file at a time and verify archive size/SHA-256.

    Existing valid files are reused. Partial downloads use a `.part` suffix, so an
    interrupted transfer cannot be mistaken for a complete archive.
    """
    root = Path(root); raw = root / "raw"; raw.mkdir(parents=True, exist_ok=True)
    for filename in METADATA_FILES:
        _download(f"{base_url}/{filename}", raw / filename)
    for spec in ARCHIVES.values():
        destination = raw / str(spec["filename"])
        if destination.exists() and _sha256(destination) == spec["sha256"]:
            continue
        if destination.exists():
            destination.replace(destination.with_suffix(destination.suffix + ".invalid"))
        _download(f"{base_url}/{spec['filename']}", destination)
        if destination.stat().st_size != spec["bytes"]:
            raise ValueError(f"Unexpected size for {destination.name}: {destination.stat().st_size}")
        digest = _sha256(destination)
        if digest != spec["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {destination.name}: {digest}")


def _download(url: str, destination: Path) -> None:
    if destination.exists(): return
    partial = destination.with_suffix(destination.suffix + ".part")
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": "CTE442-SLR70-import/1.0"}
    if offset: headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            resumed = offset and getattr(response, "status", 200) == 206
            mode = "ab" if resumed else "wb"
            with partial.open(mode) as handle:
                shutil.copyfileobj(response, handle, length=1024 * 1024)
        partial.replace(destination)
    except Exception:
        # Keep the partial file for diagnosis; restart is safe and explicit.
        raise


def extract_slr70(root: str | Path) -> None:
    root = Path(root); extracted = root / "extracted"; extracted.mkdir(parents=True, exist_ok=True)
    for gender, spec in ARCHIVES.items():
        archive = root / "raw" / str(spec["filename"])
        if not archive.exists(): raise FileNotFoundError(f"Missing archive: {archive}")
        if _sha256(archive) != spec["sha256"]: raise ValueError(f"SHA-256 mismatch: {archive}")
        destination = extracted / gender; destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                target = (destination / member.filename).resolve()
                if destination.resolve() not in target.parents and target != destination.resolve():
                    raise ValueError(f"Unsafe ZIP member: {member.filename}")
            bundle.extractall(destination)


def build_manifest(root: str | Path, output: str | Path | None = None,
                   limit: int | None = None, require_expected_count: bool = True) -> Path:
    """Build the public manifest from extracted archives without inferring metadata."""
    root = Path(root); extracted = root / "extracted"
    output = Path(output) if output else root / "manifest.csv"
    rows: list[dict[str, object]] = []
    for gender in ("female", "male"):
        gender_root = extracted / gender
        indexes = sorted(gender_root.rglob("line_index.tsv"))
        if len(indexes) != 1:
            raise ValueError(f"Expected exactly one line_index.tsv under {gender_root}; found {len(indexes)}")
        audio_by_stem = {path.stem: path for path in gender_root.rglob("*.wav")}
        for file_id, transcript in _read_line_index(indexes[0]):
            audio = audio_by_stem.get(file_id)
            if audio is None: raise ValueError(f"Missing WAV for {gender}/{file_id}")
            duration = _wav_duration(audio)
            speaker = _speaker_id(file_id, gender)
            rows.append({
                "utterance_id": f"slr70_{file_id}", "audio_path": str(audio.relative_to(output.parent)),
                "speaker_id": speaker, "transcript": transcript, "speech_type": "prompted",
                "recording_device": "unspecified_by_slr70", "noise_condition": "unspecified",
                "language": "en-NG", "accent_region": "unspecified_by_utterance",
                "age_group": "unspecified", "gender": gender,
                "self_reported_proficiency": "unspecified", "corpus_kind": "public",
                "duration_seconds": f"{duration:.6f}", "transcript_status": "reviewed",
                "consent_reference": LICENSE_URL, "dataset_id": "OpenSLR SLR70",
                "source_url": RESOURCE_URL, "source_file_id": file_id,
                "license": LICENSE_NAME, "public_development_only": "true",
            })
            if limit and len(rows) >= limit: break
        if limit and len(rows) >= limit: break
    if not rows: raise ValueError(f"No indexed WAV files found under {extracted}")
    _validate_speaker_derivation(rows)
    if require_expected_count and limit is None and len(rows) != EXPECTED_UTTERANCES:
        raise ValueError(f"Expected {EXPECTED_UTTERANCES} SLR70 utterances; found {len(rows)}")
    write_manifest(output, rows)
    _write_import_report(root, rows, output)
    return output


def import_slr70(root: str | Path, download: bool = True, extract: bool = True,
                 limit: int | None = None, require_expected_count: bool = True) -> Path:
    if download: download_slr70(root)
    if extract: extract_slr70(root)
    return build_manifest(root, limit=limit, require_expected_count=require_expected_count)


def _read_line_index(path: Path):
    with path.open(encoding="utf-8-sig") as handle:
        for number, line in enumerate(handle, 1):
            # Mirrors the normalization used by the published Hugging Face loader.
            normalized = re.sub(r"\t[^\t]*\t", "\t", line.strip())
            fields = re.split(r"\t\t?", normalized, maxsplit=1)
            if len(fields) != 2 or not fields[0] or not fields[1]:
                raise ValueError(f"Malformed index row {path}:{number}")
            yield fields[0], fields[1]


def _speaker_id(file_id: str, gender: str) -> str:
    """SLR70 IDs end in an utterance number; the preceding prefix is the speaker key."""
    if "_" not in file_id: raise ValueError(f"Cannot derive speaker from SLR70 file ID: {file_id}")
    prefix, utterance = file_id.rsplit("_", 1)
    if not utterance.isdigit(): raise ValueError(f"SLR70 file ID lacks numeric utterance suffix: {file_id}")
    return f"slr70_{gender}_{prefix}"


def _validate_speaker_derivation(rows: list[dict[str, object]]) -> None:
    counts = Counter(str(row["speaker_id"]) for row in rows)
    singletons = sum(count == 1 for count in counts.values())
    if len(rows) >= 20 and singletons / len(counts) > 0.5:
        raise ValueError("Derived mostly one-utterance speakers; inspect SLR70 filename parsing")


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        if not audio.getframerate(): raise ValueError(f"Zero sample rate: {path}")
        return audio.getnframes() / audio.getframerate()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def _write_import_report(root: Path, rows: list[dict[str, object]], manifest: Path) -> None:
    speakers = Counter(str(row["gender"]) for row in rows)
    report = {
        "dataset_id": "OpenSLR SLR70", "corpus_kind": "public",
        "use": "development only; not original-corpus results", "resource_url": RESOURCE_URL,
        "license": LICENSE_NAME, "manifest": str(manifest), "utterances": len(rows),
        "speakers": len({row["speaker_id"] for row in rows}), "utterances_by_gender": dict(speakers),
        "duration_hours": sum(float(row["duration_seconds"]) for row in rows) / 3600,
    }
    (root / "import_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

