"""Strict ingress for the future consent-cleared original corpus."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..manifest import assert_research_manifest, read_manifest, validate_manifest


def import_original(source_manifest: str | Path, destination: str | Path = "data/original/manifest.csv") -> Path:
    source, destination = Path(source_manifest), Path(destination)
    rows = read_manifest(source)
    assert_research_manifest(rows)
    issues = validate_manifest(rows, source.parent)
    if issues: raise ValueError(f"Original manifest has {len(issues)} issue(s); first: {issues[0]}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination

