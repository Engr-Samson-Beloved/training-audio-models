"""Dependency-free SVG plots for evaluation slices."""

from __future__ import annotations

import csv
import html
from pathlib import Path


def plot_metrics(metrics_path: str | Path, output_dir: str | Path) -> None:
    with Path(metrics_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    for dimension in ("noise_condition", "sentence_length", "accent_region", "gender"):
        values: dict[str, list[float]] = {}
        field = "sentence_length" if dimension == "sentence_length" else dimension
        for row in rows: values.setdefault(row.get(field, "unspecified"), []).append(float(row["wer"]))
        _bar_svg(out / f"wer_by_{dimension}.svg", f"WER by {dimension}",
                 {key: sum(vals) / len(vals) for key, vals in values.items()})


def _bar_svg(path: Path, title: str, values: dict[str, float]) -> None:
    width, height, margin = 720, 360, 70
    entries = sorted(values.items()) or [("none", 0.0)]
    maximum = max(1.0, *(value for _, value in entries))
    bar_width = (width - 2 * margin) / len(entries) * 0.65
    gap = (width - 2 * margin) / len(entries)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<text x="{width/2}" y="30" text-anchor="middle" font-family="sans-serif" font-size="18">{html.escape(title)}</text>',
             f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="black"/>']
    for idx, (label, value) in enumerate(entries):
        x = margin + idx * gap + (gap - bar_width) / 2
        h = value / maximum * (height - 2 * margin)
        y = height - margin - h
        parts.extend([f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{h:.1f}" fill="#2563eb"/>',
                      f'<text x="{x+bar_width/2:.1f}" y="{height-margin+18}" text-anchor="middle" font-family="sans-serif" font-size="11">{html.escape(label)}</text>',
                      f'<text x="{x+bar_width/2:.1f}" y="{max(48,y-5):.1f}" text-anchor="middle" font-family="sans-serif" font-size="11">{value:.3f}</text>'])
    parts.append('</svg>')
    path.write_text("\n".join(parts), encoding="utf-8")

