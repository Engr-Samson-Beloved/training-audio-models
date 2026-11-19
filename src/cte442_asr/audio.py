"""Audio inspection and dependency-free PCM WAV conversion."""

from __future__ import annotations

import array
import csv
import wave
from pathlib import Path

from .manifest import read_manifest, write_manifest


def inspect_wav(path: str | Path) -> dict[str, object]:
    path = Path(path)
    try:
        with wave.open(str(path), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return {
                "audio_path": str(path), "valid": True, "sample_rate": rate,
                "channels": wav.getnchannels(), "sample_width": wav.getsampwidth(),
                "frames": frames, "duration_seconds": frames / rate if rate else 0,
                "error": "",
            }
    except (wave.Error, EOFError, OSError) as exc:
        return {"audio_path": str(path), "valid": False, "sample_rate": "", "channels": "",
                "sample_width": "", "frames": "", "duration_seconds": "", "error": str(exc)}


def convert_wav_16k_mono(source: str | Path, destination: str | Path) -> None:
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(source), "rb") as inp:
        channels, width, rate = inp.getnchannels(), inp.getsampwidth(), inp.getframerate()
        data = inp.readframes(inp.getnframes())
    if width != 2 or channels not in {1, 2}:
        raise ValueError("stdlib converter supports 16-bit mono/stereo PCM WAV only; install audio extra for other formats")
    samples = array.array("h"); samples.frombytes(data)
    mono = [int((samples[i] + samples[i + 1]) / 2) for i in range(0, len(samples), 2)] if channels == 2 else list(samples)
    if rate != 16000 and mono:
        target_length = max(1, round(len(mono) * 16000 / rate))
        converted = []
        for index in range(target_length):
            position = index * rate / 16000
            left = min(int(position), len(mono) - 1); right = min(left + 1, len(mono) - 1)
            fraction = position - left
            converted.append(round(mono[left] * (1 - fraction) + mono[right] * fraction))
        mono = converted
    encoded = array.array("h", mono).tobytes()
    with wave.open(str(destination), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(encoded)


def validate_and_convert(manifest_path: str | Path, converted_dir: str | Path, report_path: str | Path,
                         converted_manifest: str | Path | None = None) -> int:
    manifest_path, converted_dir = Path(manifest_path), Path(converted_dir)
    rows = read_manifest(manifest_path)
    report: list[dict[str, object]] = []
    failures = 0
    for row in rows:
        raw = Path(row["audio_path"])
        source = raw if raw.is_absolute() else manifest_path.parent / raw
        info = inspect_wav(source)
        info["utterance_id"] = row["utterance_id"]
        info["manifest_duration_seconds"] = row["duration_seconds"]
        info["duration_delta_seconds"] = ""
        info["converted_path"] = ""
        if info["valid"]:
            info["duration_delta_seconds"] = abs(float(info["duration_seconds"]) - float(row["duration_seconds"]))
            destination = converted_dir / f"{row['utterance_id']}.wav"
            try:
                convert_wav_16k_mono(source, destination)
                info["converted_path"] = str(destination)
            except (ValueError, wave.Error, OSError) as exc:
                info["valid"], info["error"] = False, str(exc)
        if not info["valid"]:
            failures += 1
        report.append(info)
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["utterance_id", "audio_path", "valid", "sample_rate", "channels", "sample_width",
              "frames", "duration_seconds", "manifest_duration_seconds", "duration_delta_seconds",
              "converted_path", "error"]
    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(report)
    if converted_manifest and failures == 0:
        converted_manifest = Path(converted_manifest)
        rewritten = []
        for row, info in zip(rows, report):
            copy = dict(row)
            destination = Path(str(info["converted_path"]))
            try: copy["audio_path"] = str(destination.relative_to(converted_manifest.parent))
            except ValueError: copy["audio_path"] = str(destination.resolve())
            copy["duration_seconds"] = f"{float(info['duration_seconds']):.6f}"
            rewritten.append(copy)
        write_manifest(converted_manifest, rewritten)
    return failures

