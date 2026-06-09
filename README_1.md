# 🎯 Amazon Video Intelligence Pipeline

Extract, transcribe, and analyze any Amazon product or Live video into a full competitive SEO intelligence report — automatically.

## What It Does

Paste any Amazon video URL → get a 6-tab Excel report with:
- Competitor hooks and ad copy to steal/beat
- Buyer language and keywords ranked by value  
- Ready-to-paste Amazon listing titles, bullets, backend keywords
- Competitor gaps and your exact opportunities
- Full timestamped transcript

**Cost per video: ~$0.01**

---

## Pipeline Overview

```
Amazon URL
    │
    ▼
Layer 1: Download (yt-dlp + ffmpeg)
    │  → downloads/<video_id>/video.mp4
    │  → downloads/<video_id>/audio.mp3
    ▼
Layer 2: Transcribe (OpenAI Whisper — free, local)
    │  → transcript.txt
    │  → transcript.srt (timestamped)
    │  → transcript.json (structured)
    ▼
Layer 3: Analyze (Claude API — ~$0.01/video)
    │  → analysis.json
    │  → analysis.txt (human readable)
    │  → listing_copy.txt
    ▼
Layer 4: Export (openpyxl)
    └  → intelligence_report_<date>.xlsx (6 tabs)
```

---

## Setup

### 1. Install dependencies

```bash
# Core tools (download yt-dlp.exe from GitHub releases for Windows)
pip install yt-dlp

# Transcription
pip install openai-whisper

# Analysis
pip install anthropic

# Export
pip install openpyxl
```

### 2. Install ffmpeg
- **Windows:** Download from https://www.gyan.dev/ffmpeg/builds/ → extract → add `bin` folder to PATH
- **Mac:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`

### 3. Get Anthropic API key
- Sign up at https://console.anthropic.com
- Create an API key
- Add $5 credits (covers ~500 videos)

---

## Usage

### Single video
```bash
# Step 1 — Download
python layer1_download.py "https://www.amazon.com/vdp/YOUR_VIDEO_ID"

# Step 2 — Transcribe
python layer2_transcribe.py <video_id>

# Step 3 — Analyze
python layer3_analyze.py <video_id> --api-key sk-ant-...

# Step 4 — Export to Excel
python layer4_export.py <video_id>
```

### Batch mode (multiple videos)
```bash
# Create urls.txt with one Amazon URL per line
python layer1_download.py urls.txt
python layer2_transcribe.py --batch
python layer3_analyze.py --batch --api-key sk-ant-...
python layer4_export.py --batch
```

### Audio only (faster, transcription focused)
```bash
python layer1_download.py "https://..." --audio-only
```

---

## Output Structure

```
downloads/
  <video_id>/
    video.mp4              # Full quality video
    audio.mp3              # Extracted mono 16kHz audio
    transcript.txt         # Clean full text
    transcript.srt         # Timestamped subtitles
    transcript.json        # Structured segments
    analysis.json          # Full Claude analysis
    analysis.txt           # Human readable report
    listing_copy.txt       # Ready-to-paste listing copy
    intelligence_report_<date>.xlsx   # 6-tab Excel report
    meta.json              # Pipeline state/metadata
```

---

## Excel Report Tabs

| Tab | Contents |
|-----|----------|
| Summary | Competitor score card, product overview, pipeline stats |
| Listing Copy | Title options + 5 bullets + backend keywords |
| Keywords | Buyer phrases ranked High/Medium/Low |
| Hooks & Ad Copy | Competitor hooks + 5 ad hooks to beat |
| Competitor Gaps | Their weaknesses + your exact opportunities |
| Raw Transcript | Full timestamped transcript |

---

## Supported URL Types

| Type | Example |
|------|---------|
| Amazon Live | `amazon.com/live/video/<id>` |
| Product Video | `amazon.com/vdp/<id>` |
| Sponsored Brand Video | Any Amazon video URL |

---

## Layer Details

### Layer 1 — Download (`layer1_download.py`)
- Auto-detects all available quality variants
- Always downloads highest quality
- Extracts audio as mono 16kHz MP3 (optimized for Whisper)
- Organizes output by video ID

### Layer 2 — Transcribe (`layer2_transcribe.py`)
- Runs OpenAI Whisper locally — **no API cost, no data sent externally**
- Default model: `base` (fast, good accuracy)
- Use `--model medium` for accented or fast speech
- Outputs txt, srt, and json formats

### Layer 3 — Analyze (`layer3_analyze.py`)
- Sends transcript to Claude API (claude-sonnet-4-5)
- Extracts: hooks, pain points, benefits, buyer language, gaps, ad hooks
- Generates: listing titles, 5 bullets, backend keywords
- Scores competitor listing on 3 dimensions
- Cost: ~$0.01 per video

### Layer 4 — Export (`layer4_export.py`)
- Builds formatted 6-tab Excel workbook
- Color coded by priority (green = high value, yellow = medium)
- Ready to open and act on immediately

---

## Use Cases

1. **Competitor research** — analyze every competitor's Amazon video
2. **Listing optimization** — steal exact buyer language for your copy
3. **Ad creative intelligence** — extract hooks to beat in your video ads
4. **UGC briefs** — feed transcripts into creator briefs
5. **Voice search optimization** — natural language phrases for Alexa/A10
6. **Batch monitoring** — run weekly on competitor videos to track changes

---

## Requirements

- Python 3.8+
- ffmpeg
- yt-dlp
- openai-whisper
- anthropic
- openpyxl

---

## Notes

- Keep your Anthropic API key secure — never commit it to git
- Use `--audio-only` flag to save disk space when you only need transcripts
- Whisper downloads model weights on first run (~150MB for base model)
- Some Amazon Live streams expire — download promptly after airing

---

## License

MIT — use freely, build on it, make money with it.
