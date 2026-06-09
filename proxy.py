"""
proxy.py — Layer 5 Flask Proxy for Amazon Video SEO Pipeline
============================================================
Security model:
  - API key loaded ONCE from .env at startup; never echoed to client
  - All user inputs sanitized before shell execution
  - No direct shell=True subprocess calls; arguments passed as lists
  - CORS restricted to localhost only
  - Input validation on all endpoints
  - Job state held server-side; client gets a job_id token only

Usage:
  python proxy.py
  (Set ANTHROPIC_API_KEY and PIPELINE_DIR in .env or environment)
"""

import os
import re
import sys
import uuid
import json
import shutil
import logging
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv()

API_KEY       = os.getenv("ANTHROPIC_API_KEY", "")
PIPELINE_DIR  = Path(os.getenv("PIPELINE_DIR", r"C:\Users\Baruch\Desktop\Video-seo-4LYRS"))
FFMPEG_DIR    = Path(os.getenv("FFMPEG_DIR",   r"C:\Users\Baruch\Desktop\ffmpeg-8.1.1-essentials_build\bin"))
OUTPUT_DIR    = PIPELINE_DIR / "outputs"
HISTORY_FILE  = PIPELINE_DIR / "run_history.json"
PORT          = int(os.getenv("PROXY_PORT", 5050))

# Runtime job store  {job_id: {status, progress, log, result_path, ...}}
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()

# ── App setup ─────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=str(PIPELINE_DIR), static_url_path="")

# CORS: only allow requests from localhost origins
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost",
    "http://localhost:5050",
    "http://127.0.0.1",
    "http://127.0.0.1:5050",
    "null",          # file:// origin
]}})

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PIPELINE_DIR / "proxy.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("proxy")

# ── Input Sanitization ────────────────────────────────────────────────────────

_SAFE_BRAND  = re.compile(r"^[A-Za-z0-9 _\-]{1,64}$")
_SAFE_URL    = re.compile(r"^https?://[^\s<>\"']+$")
_SAFE_ASIN   = re.compile(r"^[A-Z0-9]{10}$")
_MAX_NOTES   = 500

def sanitize_brand(name: str) -> str:
    name = name.strip()
    if not _SAFE_BRAND.match(name):
        raise ValueError(f"Brand name contains invalid characters: {name!r}")
    return name

def sanitize_url(url: str) -> str:
    url = url.strip()
    if not _SAFE_URL.match(url):
        raise ValueError(f"Invalid URL format: {url!r}")
    if len(url) > 2048:
        raise ValueError("URL too long (max 2048 chars)")
    return url

def sanitize_notes(notes: str) -> str:
    notes = notes.strip()[:_MAX_NOTES]
    # Strip anything that could inject into shell prompts
    notes = re.sub(r"[`$\\<>|;&]", "", notes)
    return notes

def safe_filename(brand: str) -> str:
    """Convert brand name to a safe filename prefix."""
    return re.sub(r"[^A-Za-z0-9_\-]", "_", brand).strip("_")

# ── History helpers ───────────────────────────────────────────────────────────

def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def save_history_entry(entry: dict):
    history = load_history()
    history.insert(0, entry)
    history = history[:200]  # keep last 200 runs
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")

# ── Job helpers ───────────────────────────────────────────────────────────────

def create_job(meta: dict) -> str:
    job_id = str(uuid.uuid4())
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id":         job_id,
            "status":     "queued",   # queued | running | done | error
            "progress":   0,          # 0-100
            "stage":      "",
            "log":        [],
            "result":     None,       # path to output xlsx
            "error":      None,
            "started_at": datetime.utcnow().isoformat(),
            "meta":       meta,
        }
    return job_id

def update_job(job_id: str, **kwargs):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(kwargs)

def append_log(job_id: str, line: str):
    ts = datetime.utcnow().strftime("%H:%M:%S")
    entry = f"[{ts}] {line}"
    log.info("[job %s] %s", job_id[:8], line)
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id]["log"].append(entry)

# ── Pipeline runner (background thread) ──────────────────────────────────────

def _run_pipeline(job_id: str, brand: str, product_url: str, video_url: str, notes: str):
    """Execute layers 1-4 in sequence, streaming log lines into the job store."""
    try:
        update_job(job_id, status="running", stage="Downloading video")
        append_log(job_id, f"Starting pipeline for brand: {brand}")
        append_log(job_id, f"Video URL: {video_url}")

        brand_slug = safe_filename(brand)
        run_id     = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        run_label  = f"{brand_slug}_{run_id}"
        run_dir    = OUTPUT_DIR / run_label
        run_dir.mkdir(parents=True, exist_ok=True)

        # Build environment — inject API key + ffmpeg path
        env = os.environ.copy()
        env["ANTHROPIC_API_KEY"] = API_KEY
        env["PATH"] = str(FFMPEG_DIR) + os.pathsep + env.get("PATH", "")

        python = sys.executable

        # ── Layer 1: Download ────────────────────────────────────────────────
        append_log(job_id, "Layer 1 → Downloading video…")
        update_job(job_id, progress=5, stage="Layer 1: Download")
        dl_script = PIPELINE_DIR / "layer1_download.py"
        result = subprocess.run(
            [python, str(dl_script), video_url, str(run_dir)],
            capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=300,
        )
        _relay_output(job_id, result)
        if result.returncode != 0:
            raise RuntimeError(f"Layer 1 failed (exit {result.returncode})")
        update_job(job_id, progress=25)

        # ── Layer 2: Transcribe ──────────────────────────────────────────────
        append_log(job_id, "Layer 2 -> Transcribing audio...")
        update_job(job_id, progress=30, stage="Layer 2: Transcribe")
        tr_script = PIPELINE_DIR / "layer2_transcribe.py"
        result = subprocess.run(
            [python, str(tr_script), str(run_dir)],
            capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=600,
        )
        _relay_output(job_id, result)
        if result.returncode != 0:
            raise RuntimeError(f"Layer 2 failed (exit {result.returncode})")
        update_job(job_id, progress=55)

        # ── Layer 3: Analyze ─────────────────────────────────────────────────
        append_log(job_id, "Layer 3 -> Analyzing with Claude...")
        update_job(job_id, progress=60, stage="Layer 3: Claude Analysis")
        an_script = PIPELINE_DIR / "layer3_analyze.py"
        result = subprocess.run(
            [python, str(an_script), str(run_dir), brand, product_url, notes],
            capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=300,
        )
        _relay_output(job_id, result)
        if result.returncode != 0:
            raise RuntimeError(f"Layer 3 failed (exit {result.returncode})")
        update_job(job_id, progress=80)

        # ── Layer 4: Export ──────────────────────────────────────────────────
        append_log(job_id, "Layer 4 -> Exporting Excel...")
        update_job(job_id, progress=85, stage="Layer 4: Excel Export")
        ex_script = PIPELINE_DIR / "layer4_export.py"
        result = subprocess.run(
            [python, str(ex_script), str(run_dir), brand_slug],
            capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=120,
        )
        _relay_output(job_id, result)
        if result.returncode != 0:
            raise RuntimeError(f"Layer 4 failed (exit {result.returncode})")

        # Find the output xlsx
        xlsx_files = list(run_dir.glob("*.xlsx"))
        result_path = str(xlsx_files[0]) if xlsx_files else None

        update_job(job_id, progress=100, status="done", stage="Complete",
                   result=result_path)
        append_log(job_id, f"✓ Pipeline complete → {result_path}")

        # Persist to history
        save_history_entry({
            "job_id":      job_id,
            "brand":       brand,
            "video_url":   video_url,
            "product_url": product_url,
            "run_label":   run_label,
            "result":      result_path,
            "status":      "done",
            "finished_at": datetime.utcnow().isoformat(),
        })

    except Exception as exc:
        err_msg = str(exc)
        update_job(job_id, status="error", stage="Error", error=err_msg)
        append_log(job_id, f"✗ ERROR: {err_msg}")
        save_history_entry({
            "job_id":      job_id,
            "brand":       brand,
            "video_url":   video_url,
            "product_url": product_url,
            "run_label":   run_label if "run_label" in dir() else "n/a",
            "result":      None,
            "status":      "error",
            "error":       err_msg,
            "finished_at": datetime.utcnow().isoformat(),
        })


def _relay_output(job_id: str, result: subprocess.CompletedProcess):
    """Forward stdout/stderr lines from a subprocess into the job log."""
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if line:
            append_log(job_id, line)
    for line in (result.stderr or "").splitlines():
        line = line.strip()
        if line:
            append_log(job_id, f"[stderr] {line}")

# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.route("/api/ping", methods=["GET"])
def ping():
    """Health check — also confirms API key is loaded (without revealing it)."""
    return jsonify({
        "ok":            True,
        "api_key_loaded": bool(API_KEY),
        "pipeline_dir":  str(PIPELINE_DIR),
        "version":       "5.0.0",
    })


@app.route("/api/run", methods=["POST"])
def run_pipeline():
    """
    Start a new pipeline run.
    Body JSON: { brand, product_url, video_url, notes }
    Returns: { job_id }
    """
    data = request.get_json(force=True, silent=True) or {}
    try:
        brand       = sanitize_brand(data.get("brand", ""))
        video_url   = sanitize_url(data.get("video_url", ""))
        product_url = sanitize_url(data.get("product_url", "")) if data.get("product_url") else ""
        notes       = sanitize_notes(data.get("notes", ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if not API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY not set on server"}), 500

    meta    = dict(brand=brand, video_url=video_url, product_url=product_url, notes=notes)
    job_id  = create_job(meta)

    thread  = threading.Thread(
        target=_run_pipeline,
        args=(job_id, brand, product_url, video_url, notes),
        daemon=True,
    )
    thread.start()

    log.info("Queued job %s for brand=%r", job_id[:8], brand)
    return jsonify({"job_id": job_id}), 202


@app.route("/api/status/<job_id>", methods=["GET"])
def job_status(job_id: str):
    """Poll job state.  Returns full log + progress."""
    # Validate job_id is a UUID to prevent path traversal
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({"error": "Invalid job ID"}), 400

    with JOBS_LOCK:
        job = JOBS.get(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    return jsonify({
        "id":       job["id"],
        "status":   job["status"],
        "progress": job["progress"],
        "stage":    job["stage"],
        "log":      job["log"],
        "result":   job["result"],
        "error":    job["error"],
        "meta":     job["meta"],
    })


@app.route("/api/history", methods=["GET"])
def get_history():
    """Return run history (last 200 entries)."""
    return jsonify(load_history())


@app.route("/api/open-output", methods=["POST"])
def open_output():
    """
    Open a result file in Explorer (Windows only).
    Body JSON: { path }  — validated to be inside OUTPUT_DIR.
    """
    data = request.get_json(force=True, silent=True) or {}
    raw_path = data.get("path", "")
    try:
        target = Path(raw_path).resolve()
        output_root = OUTPUT_DIR.resolve()
        # Must be inside the output directory
        target.relative_to(output_root)
    except (ValueError, Exception):
        return jsonify({"error": "Invalid path"}), 400

    if not target.exists():
        return jsonify({"error": "File not found"}), 404

    try:
        subprocess.Popen(["explorer", "/select,", str(target)])
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/config", methods=["GET"])
def get_config():
    """Return non-sensitive config for the UI."""
    return jsonify({
        "pipeline_dir": str(PIPELINE_DIR),
        "output_dir":   str(OUTPUT_DIR),
        "ffmpeg_dir":   str(FFMPEG_DIR),
        "api_key_set":  bool(API_KEY),
    })


@app.route("/api/config", methods=["POST"])
def save_config():
    """
    Update runtime paths (writes to .env in pipeline dir).
    Body JSON: { pipeline_dir?, ffmpeg_dir? }
    Does NOT accept api_key changes via API for security.
    """
    global PIPELINE_DIR, FFMPEG_DIR, OUTPUT_DIR, HISTORY_FILE
    data = request.get_json(force=True, silent=True) or {}

    updates = {}
    if "pipeline_dir" in data:
        p = Path(data["pipeline_dir"])
        if not p.exists():
            return jsonify({"error": f"pipeline_dir does not exist: {p}"}), 400
        updates["PIPELINE_DIR"] = str(p)
        PIPELINE_DIR = p
        OUTPUT_DIR   = p / "outputs"
        HISTORY_FILE = p / "run_history.json"

    if "ffmpeg_dir" in data:
        f = Path(data["ffmpeg_dir"])
        if not (f / "ffmpeg.exe").exists():
            return jsonify({"error": f"ffmpeg.exe not found in {f}"}), 400
        updates["FFMPEG_DIR"] = str(f)
        FFMPEG_DIR = f

    # Persist updates to .env
    env_path = PIPELINE_DIR / ".env"
    existing = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()
    existing.update(updates)
    lines = [f"{k}={v}" for k, v in existing.items()]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return jsonify({"ok": True, "updated": list(updates.keys())})


# ── Static file serving (pipeline_ui.html) ───────────────────────────────────

@app.route("/")
def serve_ui():
    return send_from_directory(str(PIPELINE_DIR), "pipeline_ui.html")


# ── Startup ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  Amazon Video SEO Pipeline — Layer 5 Proxy")
    print(f"  Pipeline dir : {PIPELINE_DIR}")
    print(f"  Output dir   : {OUTPUT_DIR}")
    print(f"  API key set  : {'YES ✓' if API_KEY else 'NO ✗  (set ANTHROPIC_API_KEY in .env)'}")
    print(f"  Listening on : http://localhost:{PORT}")
    print("=" * 60)

    if not API_KEY:
        print("\n⚠  WARNING: ANTHROPIC_API_KEY is not set.")
        print("   Add it to .env in the pipeline directory and restart.\n")

    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
