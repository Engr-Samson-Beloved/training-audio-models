"""Zero-dependency local dashboard for inspecting and simulating the project."""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = PROJECT_ROOT / "dashboard"


def _manifest_summary(relative: str) -> dict[str, object]:
    path = PROJECT_ROOT / relative
    summary: dict[str, object] = {"path": relative, "ready": False, "utterances": 0,
                                  "speakers": 0, "hours": 0.0, "corpus_kind": ""}
    if not path.exists(): return summary
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    summary.update({"ready": bool(rows), "utterances": len(rows),
                    "speakers": len({row.get("speaker_id", "") for row in rows}),
                    "hours": round(sum(float(row.get("duration_seconds") or 0) for row in rows) / 3600, 3),
                    "corpus_kind": rows[0].get("corpus_kind", "") if rows else ""})
    return summary


def _experiments() -> list[dict[str, object]]:
    output = []
    for path in sorted((PROJECT_ROOT / "configs").glob("*.toml")):
        with path.open("rb") as handle: config = tomllib.load(handle)
        output.append({"file": path.name, "id": config.get("experiment_id"),
                       "model": config.get("model"), "mode": config.get("mode"),
                       "seeds": len(config.get("seeds", [])), "hours": config.get("hours", []),
                       "lm_rescoring": config.get("lm_rescoring", [])})
    return output


def _fixture_audio() -> list[dict[str, str]]:
    manifest = PROJECT_ROOT / "data/fixture/manifest.csv"
    if not manifest.exists(): return []
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))[:6]
    return [{"utterance_id": row["utterance_id"], "transcript": row["transcript"],
             "url": "/file/" + str((manifest.parent / row["audio_path"]).relative_to(PROJECT_ROOT))}
            for row in rows]


def project_status() -> dict[str, object]:
    plots = sorted((PROJECT_ROOT / "results/fixture_smoke/plots").glob("*.svg"))
    archives = {name: (PROJECT_ROOT / "data/public/slr70/raw" / name).exists()
                for name in ("en_ng_female.zip", "en_ng_male.zip")}
    return {
        "project": "Group 2 CTE 442 Speech Recognition Research",
        "warning": "Fixture and public data are development-only, never original-corpus findings.",
        "datasets": {
            "fixture": _manifest_summary("data/fixture/manifest.csv"),
            "slr70": _manifest_summary("data/public/slr70/manifest.16k.csv"),
            "original": _manifest_summary("data/original/manifest.16k.csv"),
        },
        "slr70_archives": archives,
        "experiments": _experiments(),
        "tools": {name: bool(shutil.which(name)) for name in ("python3.12", "ffmpeg", "sox")},
        "fixture_results_ready": (PROJECT_ROOT / "results/fixture_smoke/seed_summary.csv").exists(),
        "plots": ["/file/" + str(path.relative_to(PROJECT_ROOT)) for path in plots],
        "audio": _fixture_audio(),
    }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "CTE442Dashboard/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status": return self._json(project_status())
        if parsed.path.startswith("/file/"):
            return self._serve_path(PROJECT_ROOT / unquote(parsed.path.removeprefix("/file/")), PROJECT_ROOT)
        target = "index.html" if parsed.path in {"", "/"} else parsed.path.lstrip("/")
        return self._serve_path(WEB_ROOT / target, WEB_ROOT)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/run-fixture": return self.send_error(404)
        try:
            completed = subprocess.run([str(PROJECT_ROOT / "scripts/run_fixture.sh")], cwd=PROJECT_ROOT,
                                       text=True, capture_output=True, timeout=120, check=True,
                                       env={**os.environ, "PYTHONPATH": "src"})
            self._json({"ok": True, "output": completed.stdout[-4000:], "status": project_status()})
        except subprocess.CalledProcessError as exc:
            self._json({"ok": False, "output": (exc.stdout + exc.stderr)[-4000:]}, 500)
        except subprocess.TimeoutExpired:
            self._json({"ok": False, "output": "Fixture simulation exceeded 120 seconds."}, 500)

    def _serve_path(self, path: Path, allowed_root: Path) -> None:
        try: resolved = path.resolve(); resolved.relative_to(allowed_root.resolve())
        except (ValueError, OSError): return self.send_error(403)
        if not resolved.is_file(): return self.send_error(404)
        payload = resolved.read_bytes(); content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        self.send_response(200); self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(payload)

    def _json(self, value: object, status: int = 200) -> None:
        payload = json.dumps(value).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(payload)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[dashboard] {fmt % args}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Launch the local CTE 442 research dashboard")
    parser.add_argument("--host", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"CTE 442 dashboard: http://{args.host}:{args.port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__": main()

