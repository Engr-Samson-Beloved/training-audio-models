"""Terminal transcription-review queue."""

from __future__ import annotations

from pathlib import Path

from .manifest import read_manifest, write_manifest


def review_manifest(source: str | Path, output: str | Path) -> None:
    rows = read_manifest(source)
    print("Transcription review. Enter accepts; type replacement; :q saves and quits.")
    for row in rows:
        if row["transcript_status"] == "adjudicated":
            continue
        print(f"\n{row['utterance_id']} | {row['speaker_id']} | {row['audio_path']}")
        print(f"Current: {row['transcript']}")
        answer = input("Reviewed transcript> ").strip()
        if answer == ":q":
            break
        if answer:
            row["transcript"] = answer
        row["transcript_status"] = "reviewed"
    write_manifest(output, rows)

