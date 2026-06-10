# Amazon Video SEO Pipeline — Full Documentation

**Version:** Layer 5 (HTML5 UI + Flask Proxy)  
**Repo:** `bmobile-collab/video-seo-pipeline-sonnet46-jun2026`  
**Last Updated:** June 2026

---

## Overview

A fully local 5-layer pipeline that takes any Amazon product video URL, downloads it, transcribes the audio, analyzes it with Claude AI for competitive intelligence, and exports a color-coded Excel report — all controlled from a browser-based UI with no cloud dependency except the Anthropic API.

```
Amazon Video URL
       │
       ▼
 Layer 1: Download       yt-dlp + ffmpeg → video.mp4 + audio.mp3
       │
       ▼
 Layer 2: Transcribe     OpenAI Whisper (local) → transcript.json/.txt/.srt
       │
       ▼
 Layer 3: Analyze        Claude Sonnet API → analysis.json + listing_copy.txt
       │
       ▼
 Layer 4: Export         openpyxl → color-coded Excel report (6 tabs)
       │
       ▼
 Layer 5: UI + Proxy     Flask proxy + HTML5 browser UI
```

---

## File Structure

```
Video-seo-4LYRS/
├── layer1_download.py       # Download video + extract audio
├── layer2_transcribe.py     # Transcribe audio with Whisper
├── layer3_analyze.py        # Analyze transcript with Claude API
├── layer4_export.py         # Export Excel report
├── proxy.py                 # Flask proxy server (Layer 5 backend)
├── pipeline_ui.html         # Browser UI (Layer 5 frontend)
├── launch_pipeline.bat      # One-click launcher
├── .env                     # API key + paths (never committed to Git)
├── .gitignore               # Excludes .env, outputs/, downloads/
├── requirements.txt         # Python dependencies
├── run_history.json         # Auto-generated run log
├── proxy.log                # Proxy server log
└── outputs/                 # All pipeline outputs (auto-created)
    └── {Brand}_{date}_{time}/
        └── {video_id}/
            ├── video.mp4
            ├── audio.mp3
            ├── meta.json
            ├── transcript.txt
            ├── transcript.srt
            ├── transcript.json
            ├── analysis.json
            ├── analysis.txt
            ├── listing_copy.txt
            └── {Brand}_intelligence_report_{timestamp}.xlsx
```

---

## Setup

### Requirements

- Python 3.9+
- ffmpeg (bin folder path configured in `.env`)
- yt-dlp (included as `yt-dlp.exe` in pipeline folder)
- Anthropic API key

### Install Python Dependencies

```bash
pip install flask flask-cors python-dotenv anthropic openai-whisper openpyxl
```

### .env File

Create `.env` in the pipeline folder:

```
ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE
PIPELINE_DIR=C:\Users\Baruch\Desktop\Video-seo-4LYRS
FFMPEG_DIR=C:\Users\Baruch\Desktop\ffmpeg-8.1.1-essentials_build\bin
PROXY_PORT=5050
```

**Security note:** The `.env` file is listed in `.gitignore` and must never be committed to Git. GitHub's push protection will block the push if it detects an API key in any file.

### Launch

Double-click `launch_pipeline.bat`. It will:
1. Check Python is installed
2. Install required packages
3. Check for `.env` (creates a template if missing)
4. Add ffmpeg to PATH
5. Start `proxy.py` in a new console window
6. Open `http://127.0.0.1:5050` in the browser

---

## Layer 1 — Download (`layer1_download.py`)

**Purpose:** Download an Amazon product video and extract audio.

**How it works:**
1. Extracts a video ID from the Amazon URL using regex patterns
2. Runs `yt-dlp --list-formats` to detect available quality levels
3. Downloads the best available MP4
4. Runs `ffmpeg` to extract a 16kHz mono MP3 (optimized for Whisper)
5. Saves `meta.json` with URL, video ID, file paths, and timestamps

**Key change for Layer 5:** Accepts an optional second positional argument `output_dir`. When called by the proxy, files are saved into the proxy's `run_dir` instead of the default `downloads/` folder.

**Called by proxy as:**
```
python layer1_download.py <video_url> <run_dir>
```

**Output files:**
- `video.mp4` — full video
- `audio.mp3` — extracted audio (16kHz mono, ~1–3MB)
- `meta.json` — metadata and file paths

---

## Layer 2 — Transcribe (`layer2_transcribe.py`)

**Purpose:** Transcribe audio to text using OpenAI Whisper locally.

**How it works:**
1. Loads the Whisper model (downloads on first run, ~150MB for `base`)
2. Transcribes `audio.mp3` to text with timestamps
3. Outputs three formats: plain text, SRT subtitles, structured JSON

**Models available:** `tiny`, `base` (default), `small`, `medium`, `large`  
Larger models are more accurate but slower. `base` is recommended for most use cases.

**Key change for Layer 5:** Accepts a full directory path from the proxy (not just a bare video ID). Detects whether the argument is an absolute path and adjusts accordingly.

**Called by proxy as:**
```
python layer2_transcribe.py <full_path_to_video_dir>
```

**Output files:**
- `transcript.txt` — clean full text
- `transcript.srt` — timestamped subtitles
- `transcript.json` — structured segments with start/end times, word count, duration

---

## Layer 3 — Analyze (`layer3_analyze.py`)

**Purpose:** Send the transcript to Claude Sonnet for competitive intelligence analysis.

**How it works:**
1. Loads transcript from `transcript.json`
2. Builds a prompt injecting the transcript, brand name, product URL, and notes
3. Calls `claude-sonnet-4-5` with `max_tokens=8000`
4. Parses the JSON response (with robust fallback handling for malformed JSON)
5. Saves structured analysis and human-readable report

**Prompt design:** Claude is instructed to act as an Amazon FBA listing optimizer working for the specified brand. Brand name is injected so analysis is framed from a competitive intelligence perspective — what can Lanaak (or any brand) learn from this competitor video.

**JSON parsing:** Claude's response is extracted by finding the first `{` and last `}` in the output, then attempting `json.loads()`. If that fails, trailing commas are removed and parsing is retried. Raw output is saved to `debug.txt` if both attempts fail.

**Called by proxy as:**
```
python layer3_analyze.py <full_path_to_video_dir> <brand> <product_url> <notes>
```

**Output files:**
- `analysis.json` — full structured analysis
- `analysis.txt` — human-readable competitive report
- `listing_copy.txt` — ready-to-paste Amazon listing copy

**Analysis JSON structure:**
```json
{
  "product_summary": "...",
  "target_audience": "...",
  "hooks": [...],
  "pain_points": [...],
  "benefits_claimed": [...],
  "buyer_language": [...],
  "listing_title_suggestions": [...],
  "bullet_points": [...],
  "backend_keywords": "...",
  "competitor_gaps": [...],
  "ad_hooks": [...],
  "overall_score": {
    "listing_strength": 7,
    "hook_quality": 6,
    "keyword_density": 5,
    "notes": "..."
  }
}
```

---

## Layer 4 — Export (`layer4_export.py`)

**Purpose:** Generate a color-coded Excel report from the analysis.

**How it works:**
1. Loads `analysis.json` and `transcript.json`
2. Builds a 6-tab Excel workbook using `openpyxl`
3. Applies color coding, borders, and formatting throughout
4. Saves the file named `{brand_slug}_intelligence_report_{timestamp}.xlsx`

**Excel tabs:**

| Tab | Contents |
|-----|----------|
| Summary | Product overview, competitor score card, pipeline stats |
| Listing Copy | Title suggestions, bullet points, backend keywords |
| Keywords | Buyer language sorted by value (high/medium/low), benefits claimed |
| Hooks & Ad Copy | Hooks competitor used, ad hooks to steal/beat |
| Competitor Gaps | Weaknesses identified, your counter-opportunities |
| Raw Transcript | Full transcript with timestamps |

**Color scheme:**
- Dark blue headers
- Green = high-value / positive
- Orange = gaps and pain points
- Yellow = backend keywords
- Light gray = alternating rows

**Called by proxy as:**
```
python layer4_export.py <full_path_to_video_dir> <brand_slug>
```

---

## Layer 5 — UI + Proxy

### `proxy.py` — Flask Backend

**Purpose:** Secure local proxy that sits between the browser UI and the pipeline scripts. The API key never touches the browser.

**Security model:**
- API key loaded once at startup from `.env` — never sent to client
- All user inputs sanitized before any subprocess call:
  - `sanitize_brand()` — regex whitelist, 64-char max
  - `sanitize_url()` — URL format check, 2048-char cap
  - `sanitize_notes()` — 500-char max, shell metacharacters stripped
- All subprocesses use list-form arguments (never `shell=True`)
- Job IDs validated as UUIDs before lookup — prevents path traversal
- `/api/open-output` validates paths are inside `outputs/` before opening
- CORS restricted to `127.0.0.1` and `localhost` only
- All subprocess calls use `encoding='utf-8', errors='replace'` to prevent Windows cp1252 encoding crashes

**Job system:**
- Each pipeline run gets a UUID job ID
- Job state (status, progress, log lines) stored server-side in memory
- Browser polls `/api/status/{job_id}` every 1.5 seconds
- Pipeline runs in a background thread — UI stays responsive

**Path resolution:**
Layer 1 creates a video-ID subfolder inside `run_dir`. After Layer 1 completes, the proxy detects that subfolder and passes it to Layers 2, 3, and 4:
```python
subfolders = [d for d in run_dir.iterdir() if d.is_dir()]
video_dir = subfolders[0] if subfolders else run_dir
```

**API endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ping` | Health check, confirms API key is loaded |
| POST | `/api/run` | Start a pipeline run, returns `job_id` |
| GET | `/api/status/{job_id}` | Poll job state, progress, and log |
| GET | `/api/history` | Return last 200 runs |
| POST | `/api/clear-history` | Wipe `run_history.json` |
| GET | `/api/config` | Return current paths |
| POST | `/api/config` | Update pipeline/ffmpeg paths |
| POST | `/api/open-output` | Open output folder in Windows Explorer |
| GET | `/` | Serve `pipeline_ui.html` |

### `pipeline_ui.html` — Browser Frontend

**Purpose:** Single-file HTML5 UI with 5 screens, no external dependencies.

**Screens:**

| Screen | Purpose |
|--------|---------|
| Setup | Configure paths, verify proxy connection, clear history |
| New Run | Enter brand name, video URL, product URL, notes |
| Progress | Live log stream, layer indicator pills, progress bar |
| Results | Run summary, output file link, full log |
| History | All previous runs with folder links |

**Key features:**
- Light/clean theme — white cards on soft gray background
- Layer indicator pills animate through ① → ④ as pipeline progresses
- Live log polls every 1.5s and auto-scrolls
- "Open in Explorer" button calls `/api/open-output` to highlight the file
- "Clear All History" wipes server-side history
- "Reset Browser State" clears form and cached job state
- Proxy health check runs on load and every 30 seconds

---

## Running the Pipeline Manually (Without UI)

Each layer can be run standalone from the command line:

```bash
# Layer 1
python layer1_download.py "https://www.amazon.com/vdp/..."

# Layer 2
python layer2_transcribe.py <video_id>
python layer2_transcribe.py <video_id> --model medium

# Layer 3
python layer3_analyze.py <video_id>

# Layer 4
python layer4_export.py <video_id>

# Batch mode (all layers have --batch flag)
python layer2_transcribe.py --batch
python layer3_analyze.py --batch
python layer4_export.py --batch
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `unrecognized arguments: C:\...\outputs\...` | Old layer file | Replace with updated version that accepts `output_dir` arg |
| `UnicodeEncodeError: 'charmap' codec` | Emoji in print statement on Windows cp1252 | All layers now force `sys.stdout` to UTF-8 on startup |
| `audio.mp3 not found` | Proxy passing wrong directory to Layer 2 | Fixed: proxy now detects video-ID subfolder after Layer 1 |
| `JSON parse error` from Layer 3 | Claude response truncated or had extra text | Fixed: robust JSON extraction + trailing comma removal + max_tokens=8000 |
| `503 Service Unavailable` on download | Amazon video URL expired | Copy a fresh URL from the product page and retry immediately |
| `GitHub push blocked: secret detected` | API key in `.env` was committed | Remove `.env` from tracking, add to `.gitignore`, rotate API key |
| Proxy shows old behavior after file update | Old process still running | Close "Video SEO Proxy" console window completely, relaunch |

---

## Git Workflow

```bash
cd C:\Users\Baruch\Desktop\Video-seo-4LYRS

# Push updates
git add .
git commit -m "Your message"
git push origin master:main

# If push is rejected due to unrelated histories
git pull origin main --allow-unrelated-histories
git push origin master:main --force
```

**Important:** Never commit `.env`. If you accidentally do, rotate your API key immediately at console.anthropic.com and remove the file from tracking:
```bash
git rm --cached .env
echo .env >> .gitignore
git add .gitignore
git commit -m "Remove .env"
git push origin master:main --force
```

---

## Dependencies

```
flask              # Proxy web server
flask-cors         # CORS headers for local browser access
python-dotenv      # Load .env file
anthropic          # Claude API client
openai-whisper     # Local audio transcription
openpyxl           # Excel file generation
yt-dlp             # Video downloader
ffmpeg             # Audio extraction (external binary)
```

---

## Architecture Diagram

```
Browser (pipeline_ui.html)
        │  HTTP (localhost only)
        ▼
proxy.py (Flask, port 5050)
        │  subprocess (list args, UTF-8)
        ├──▶ layer1_download.py  ──▶ yt-dlp + ffmpeg
        ├──▶ layer2_transcribe.py ──▶ Whisper (local)
        ├──▶ layer3_analyze.py  ──▶ Anthropic API
        └──▶ layer4_export.py  ──▶ openpyxl
                                        │
                                        ▼
                              outputs/{Brand}_{date}/{video_id}/
                                  ├── video.mp4
                                  ├── audio.mp3
                                  ├── transcript.*
                                  ├── analysis.*
                                  └── {Brand}_intelligence_report.xlsx
```
