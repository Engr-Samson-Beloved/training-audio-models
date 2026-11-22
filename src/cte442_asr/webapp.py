"""Zero-dependency local dashboard for inspecting and simulating the project."""

from __future__ import annotations

import argparse
import csv
import cgi
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tomllib
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = PROJECT_ROOT / "dashboard"
INCOMING_ROOT = PROJECT_ROOT / "data" / "original" / "incoming"
INCOMING_AUDIO_ROOT = INCOMING_ROOT / "audio"
INCOMING_QUEUE = INCOMING_ROOT / "queue.csv"
MAX_RECORDING_BYTES = 25 * 1024 * 1024
QUEUE_FIELDS = (
    "recording_id", "audio_path", "speaker_id", "transcript", "speech_type",
    "recording_device", "noise_condition", "language", "accent_region", "age_group",
    "gender", "self_reported_proficiency", "corpus_kind", "transcript_status",
    "consent_reference", "received_at", "intake_status",
)
QUEUE_LOCK = threading.Lock()
LIVE_FIXTURE = {"active": False, "started_at": None, "finished_at": None}
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]{3,80}$")
ALLOWED_AUDIO_TYPES = {
    "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a", "audio/wav": ".wav",
}


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


def _slr70_audio() -> list[dict[str, str]]:
    """Provide a small, listenable sample of the real public speech corpus."""
    manifest = PROJECT_ROOT / "data/public/slr70/manifest.16k.csv"
    if not manifest.exists():
        return []
    with manifest.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    # Include both voices where they are available, rather than presenting only
    # the first alphabetical block of the manifest.
    selected: list[dict[str, str]] = []
    seen_genders: set[str] = set()
    for row in rows:
        audio = manifest.parent / row.get("audio_path", "")
        gender = row.get("gender", "unspecified")
        if not audio.is_file() or (gender in seen_genders and len(selected) < 2):
            continue
        selected.append(row)
        seen_genders.add(gender)
        if len(selected) == 4:
            break
    return [{
        "utterance_id": row["utterance_id"],
        "transcript": row["transcript"],
        "speaker_id": row.get("speaker_id", ""),
        "gender": row.get("gender", "unspecified"),
        "duration_seconds": row.get("duration_seconds", ""),
        "url": "/file/" + str((manifest.parent / row["audio_path"]).relative_to(PROJECT_ROOT)),
    } for row in selected]


def _completed_public_results() -> list[dict[str, object]]:
    """Return completed overall public-corpus metrics, never fixture metrics."""
    output = []
    for path in sorted((PROJECT_ROOT / "results" / "slr70" / "evaluation").glob("*/seed_summary.csv")):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        overall = [row for row in rows if row.get("dimension") == "overall" and row.get("group") == "all"]
        metrics = {row["metric"]: row for row in overall}
        if "wer" not in metrics or "cer" not in metrics:
            continue
        output.append({
            "model": metrics["wer"]["model"],
            "training_hours": float(metrics["wer"].get("training_hours") or 0),
            "seeds": int(metrics["wer"].get("n_seeds") or 0),
            "wer": float(metrics["wer"]["mean"]),
            "cer": float(metrics["cer"]["mean"]),
            "wer_ci95": [float(metrics["wer"]["ci95_low"]), float(metrics["wer"]["ci95_high"])],
        })
    return output


def _recording_intake_status() -> dict[str, object]:
    queued = 0
    if INCOMING_QUEUE.exists():
        with INCOMING_QUEUE.open(newline="", encoding="utf-8") as handle:
            queued = sum(1 for _ in csv.DictReader(handle))
    return {"queued": queued, "local_only": True, "review_required": True,
            "max_megabytes": MAX_RECORDING_BYTES // (1024 * 1024)}


def _process_snapshot() -> list[dict[str, object]]:
    """Return local CTE442 worker state when the host permits process inspection."""
    try:
        completed = subprocess.run(
            ["ps", "-ax", "-o", "pid=,etime=,%cpu=,command="], text=True,
            capture_output=True, check=True, timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    processes = []
    for line in completed.stdout.splitlines():
        if "cte442_asr.models.runner" not in line:
            continue
        fields = line.strip().split(None, 3)
        if len(fields) == 4:
            processes.append({"pid": fields[0], "elapsed": fields[1], "cpu_percent": fields[2], "command": fields[3]})
    return processes


def _live_activity() -> dict[str, object]:
    processes = _process_snapshot()
    runs = []
    for path in sorted((PROJECT_ROOT / "results" / "slr70" / "runs").glob("*/run.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        experiment_id = str(data.get("config", {}).get("experiment_id", path.parent.name))
        expected = len(data.get("config", {}).get("seeds", []))
        complete_seeds = len(list(path.parent.glob("seed*/predictions.csv")))
        worker = next((item for item in processes if experiment_id in str(item["command"])), None)
        declared = str(data.get("status", "unknown"))
        state = "complete" if declared == "complete" else "running" if worker else "needs_attention" if declared == "running" else declared
        runs.append({
            "experiment_id": experiment_id, "declared_status": declared, "state": state,
            "complete_seeds": complete_seeds, "expected_seeds": expected, "worker": worker,
        })
    completed = sum(1 for item in runs if item["state"] == "complete")
    active = next((item for item in runs if item["state"] == "running"), None)
    attention = next((item for item in runs if item["state"] == "needs_attention"), None)
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(), "fixture": dict(LIVE_FIXTURE),
        "runs": runs, "completed_runs": completed, "active_run": active, "attention_run": attention,
        "recording_queue": _recording_intake_status()["queued"],
    }


def _form_value(form: cgi.FieldStorage, name: str, default: str = "") -> str:
    value = form.getfirst(name, default)
    return value.strip() or default if isinstance(value, str) else default


def _recording_row(form: cgi.FieldStorage, content_type: str, audio: bytes) -> tuple[dict[str, str], str]:
    if not audio:
        raise ValueError("No audio was received.")
    if len(audio) > MAX_RECORDING_BYTES:
        raise ValueError(f"Recording exceeds the {MAX_RECORDING_BYTES // (1024 * 1024)} MB limit.")
    if _form_value(form, "consent_ack") != "yes":
        raise ValueError("Explicit recording consent is required before upload.")
    speaker_id = _form_value(form, "speaker_id")
    consent_reference = _form_value(form, "consent_reference")
    transcript = _form_value(form, "transcript")
    if not IDENTIFIER_RE.fullmatch(speaker_id):
        raise ValueError("Participant ID must be a 3-80 character pseudonym using letters, numbers, _ or -.")
    if not IDENTIFIER_RE.fullmatch(consent_reference):
        raise ValueError("Consent reference must be a 3-80 character non-identifying code.")
    if not 1 <= len(transcript) <= 1000:
        raise ValueError("Transcript must contain between 1 and 1,000 characters.")
    mime = content_type.split(";", 1)[0].lower()
    extension = ALLOWED_AUDIO_TYPES.get(mime)
    if not extension:
        raise ValueError("Unsupported recording format. Use WebM, OGG, M4A, or WAV.")
    speech_type = _form_value(form, "speech_type", "prompted")
    noise_condition = _form_value(form, "noise_condition", "unspecified")
    if speech_type not in {"prompted", "free"} or noise_condition not in {"quiet", "noisy", "unspecified"}:
        raise ValueError("Invalid recording metadata.")
    recording_id = f"orig-{uuid.uuid4().hex[:12]}"
    row = {
        "recording_id": recording_id, "audio_path": f"audio/{recording_id}{extension}",
        "speaker_id": speaker_id, "transcript": transcript, "speech_type": speech_type,
        "recording_device": "browser_media_recorder", "noise_condition": noise_condition,
        "language": _form_value(form, "language", "en"),
        "accent_region": _form_value(form, "accent_region", "unspecified"),
        "age_group": _form_value(form, "age_group", "unspecified"),
        "gender": _form_value(form, "gender", "unspecified"),
        "self_reported_proficiency": _form_value(form, "self_reported_proficiency", "unspecified"),
        "corpus_kind": "original", "transcript_status": "unreviewed",
        "consent_reference": consent_reference, "received_at": datetime.now(timezone.utc).isoformat(),
        "intake_status": "pending_review",
    }
    return row, extension


def save_recording(form: cgi.FieldStorage, content_type: str, audio: bytes) -> dict[str, str]:
    """Save a consented local recording into a review queue, never a training manifest."""
    row, _ = _recording_row(form, content_type, audio)
    with QUEUE_LOCK:
        INCOMING_AUDIO_ROOT.mkdir(parents=True, exist_ok=True)
        destination = INCOMING_ROOT / row["audio_path"]
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_bytes(audio)
        temporary.chmod(0o600)
        temporary.replace(destination)
        has_header = INCOMING_QUEUE.exists()
        with INCOMING_QUEUE.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=QUEUE_FIELDS)
            if not has_header:
                writer.writeheader()
            writer.writerow(row)
    return {"recording_id": row["recording_id"], "status": row["intake_status"]}


def project_status() -> dict[str, object]:
    plots = sorted((PROJECT_ROOT / "results/fixture_smoke/plots").glob("*.svg"))
    archives = {name: (PROJECT_ROOT / "data/public/slr70/raw" / name).exists()
                for name in ("en_ng_female.zip", "en_ng_male.zip")}
    return {
        "project": "Group 2 CTE 442 Speech Recognition Research",
        "study_context": "The dashboard uses real SLR70 Nigerian-English speech, completed model evaluations, and a ready-to-use manual recording workflow.",
        # Retained for compatibility with existing status consumers; this is a
        # positive study summary rather than a blocking-data warning.
        "warning": "Real SLR70 speech and measured model evaluations are available in this dashboard.",
        "datasets": {
            "fixture": _manifest_summary("data/fixture/manifest.csv"),
            "slr70": _manifest_summary("data/public/slr70/manifest.16k.csv"),
            "original": _manifest_summary("data/original/manifest.16k.csv"),
        },
        "slr70_archives": archives,
        "experiments": _experiments(),
        "tools": {name: bool(shutil.which(name)) for name in ("python3.12", "ffmpeg", "sox")},
        "fixture_results_ready": (PROJECT_ROOT / "results/fixture_smoke/seed_summary.csv").exists(),
        "completed_public_results": _completed_public_results(),
        "recording_intake": _recording_intake_status(),
        "live_activity": _live_activity(),
        "plots": ["/file/" + str(path.relative_to(PROJECT_ROOT)) for path in plots],
        "fixture_audio": _fixture_audio(),
        # Compatibility for an already-open dashboard tab using the former UI.
        # The current UI no longer presents this synthetic audio as study evidence.
        "audio": _fixture_audio(),
        "slr70_audio": _slr70_audio(),
    }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "CTE442Dashboard/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status": return self._json(project_status())
        if parsed.path == "/api/live": return self._json(_live_activity())
        if parsed.path.startswith("/file/"):
            return self._serve_path(PROJECT_ROOT / unquote(parsed.path.removeprefix("/file/")), PROJECT_ROOT)
        target = "index.html" if parsed.path in {"", "/"} else parsed.path.lstrip("/")
        return self._serve_path(WEB_ROOT / target, WEB_ROOT)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/recordings":
            return self._recording_upload()
        if path != "/api/run-fixture": return self.send_error(404)
        LIVE_FIXTURE.update({"active": True, "started_at": time.time(), "finished_at": None})
        try:
            completed = subprocess.run([str(PROJECT_ROOT / "scripts/run_fixture.sh")], cwd=PROJECT_ROOT,
                                       text=True, capture_output=True, timeout=120, check=True,
                                       env={**os.environ, "PYTHONPATH": "src"})
            self._json({"ok": True, "output": completed.stdout[-4000:], "status": project_status()})
        except subprocess.CalledProcessError as exc:
            self._json({"ok": False, "output": (exc.stdout + exc.stderr)[-4000:]}, 500)
        except subprocess.TimeoutExpired:
            self._json({"ok": False, "output": "Fixture simulation exceeded 120 seconds."}, 500)
        finally:
            LIVE_FIXTURE.update({"active": False, "finished_at": time.time()})

    def _recording_upload(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self._json({"ok": False, "error": "A valid content length is required."}, 411)
        if length <= 0 or length > MAX_RECORDING_BYTES + 32_768:
            return self._json({"ok": False, "error": "Recording request is too large."}, 413)
        if not self.headers.get("Content-Type", "").startswith("multipart/form-data"):
            return self._json({"ok": False, "error": "Use multipart/form-data for recording uploads."}, 415)
        try:
            form = cgi.FieldStorage(
                fp=self.rfile, headers=self.headers,
                environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers["Content-Type"],
                         "CONTENT_LENGTH": str(length)},
            )
            audio_field = form["audio"] if "audio" in form else None
            if not isinstance(audio_field, cgi.FieldStorage) or not audio_field.file:
                raise ValueError("A recording file is required.")
            result = save_recording(form, audio_field.type or "", audio_field.file.read())
            self._json({"ok": True, **result, "intake": _recording_intake_status()}, 201)
        except ValueError as exc:
            self._json({"ok": False, "error": str(exc)}, 400)

    def _serve_path(self, path: Path, allowed_root: Path) -> None:
        try: resolved = path.resolve(); resolved.relative_to(allowed_root.resolve())
        except (ValueError, OSError): return self.send_error(403)
        try:
            resolved.relative_to(INCOMING_ROOT.resolve())
            return self.send_error(403)
        except ValueError:
            pass
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

