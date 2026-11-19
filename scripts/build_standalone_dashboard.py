#!/usr/bin/env python3
"""Bundle the research console into one browser-openable HTML file."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dashboard"
OUTPUT = ROOT / "dist" / "standalone.html"


def main() -> None:
    html = (SOURCE / "index.html").read_text(encoding="utf-8")
    css = (SOURCE / "styles.css").read_text(encoding="utf-8")
    javascript = (SOURCE / "app.js").read_text(encoding="utf-8")
    status = json.loads((SOURCE / "status.json").read_text(encoding="utf-8"))
    # The standalone build omits audio/plot binaries; copy them beside the HTML in dist.
    status["plots"] = [path.removeprefix("/") for path in status["plots"]]
    for item in status["audio"]: item["url"] = item["url"].removeprefix("/")
    html = html.replace('<link rel="stylesheet" href="/styles.css">', f"<style>\n{css}\n</style>")
    embedded = f"<script>window.__STATIC_STATUS__={json.dumps(status, ensure_ascii=False)};</script>\n<script>\n{javascript}\n</script>"
    html = html.replace('<script src="/app.js"></script>', embedded)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__": main()

