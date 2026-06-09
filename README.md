# Amazon Video SEO Intelligence Pipeline
**Model:** Claude Sonnet 4.5  
**Built:** June 2026  
**Repo:** https://github.com/bmobile-collab/video-seo-pipeline-sonnet46-jun2026  
**Owner:** bmobile-collab (Baruch / Lanaak)  
**Status:** Production-tested, Windows 10/11

---

## AGENT QUICK REFERENCE

```
SKILL NAME   : amazon-video-seo-pipeline
TRIGGER      : Any Amazon /vdp/ or /live/video/ URL + "analyze", "pipeline", "intel"
INPUT        : Amazon video URL (string)
OUTPUT       : intelligence_report_YYYYMMDD_HHMM.xlsx (6-tab Excel)
COST         : ~$0.02 per video (Claude API only, everything else free)
RUNTIME      : ~3 minutes per video on Windows
WORKING DIR  : C:\Users\Baruch\Desktop\Video-seo-4LYRS
SCRIPTS DIR  : Same as working dir
```

---

## WHAT THIS PIPELINE DOES

Takes any Amazon product video or Amazon Live video URL and produces a complete competitive SEO intelligence report in Excel format.

### Input → Output

```
Amazon Video URL
        ↓
[Layer 1] yt-dlp + ffmpeg → video.mp4 + audio.mp3
        ↓
[Layer 2] OpenAI Whisper (local, free) → transcript.txt + .srt + .json
        ↓
[Layer 3] Claude API (claude-sonnet-4-5) → analysis.json + listing_copy.txt
        ↓
[Layer 4] openpyxl → intelligence_report_YYYYMMDD_HHMM.xlsx
```

### Excel Output (6 tabs)

| Tab | Contents | Primary Use |
|-----|----------|-------------|
| Summary | Competitor score (1-10), product overview, stats | Quick assessment |
| Listing Copy | 2 titles + 5 bullets + backend keywords | Paste into Amazon Seller Central |
| Keywords | All buyer phrases ranked High/Medium/Low | PPC targeting, SEO |
| Hooks & Ad Copy | Competitor hooks + 5 ad hooks to beat | Video ad creative briefs |
| Competitor Gaps | Their weaknesses + your exact opportunities | Differentiation strategy |
| Raw Transcript | Full timestamped transcript | Deep research |

---

## ENVIRONMENT

### Machine
- OS: Windows 10 (Version 10.0.19045.6466)
- Python: 3.12.2 (64-bit)
- Location: `C:\Users\Baruch\`

### Working Directory
```
C:\Users\Baruch\Desktop\Video-seo-4LYRS\
```

### Required files in working directory
```
layer1_download.py      ← Pipeline Layer 1
layer2_transcribe.py    ← Pipeline Layer 2
layer3_analyze.py       ← Pipeline Layer 3
layer4_export.py        ← Pipeline Layer 4
run_pipeline.bat        ← Windows batch runner
yt-dlp.exe              ← MUST be in this folder (not just on PATH)
```

### Required external tools
```
ffmpeg.exe    → C:\Users\Baruch\Desktop\ffmpeg-8.1.1-essentials_build\bin\
ffprobe.exe   → C:\Users\Baruch\Desktop\ffmpeg-8.1.1-essentials_build\bin\
ffplay.exe    → C:\Users\Baruch\Desktop\ffmpeg-8.1.1-essentials_build\bin\
```

### Required Python packages
```bash
python -m pip install yt-dlp
python -m pip install openai-whisper
python -m pip install anthropic
python -m pip install openpyxl
```

### Required API keys
```
ANTHROPIC_API_KEY → Get at https://console.anthropic.com
                  → Current model: claude-sonnet-4-5
                  → Cost: $3.00/M input tokens, $15.00/M output tokens
                  → ~$0.018 per video analyzed
```

---

## SESSION SETUP (REQUIRED EVERY NEW CMD WINDOW)

```cmd
cd C:\Users\Baruch\Desktop\Video-seo-4LYRS
set PATH=%PATH%;C:\Users\Baruch\Desktop\ffmpeg-8.1.1-essentials_build\bin
```

⚠️ **CRITICAL:** ffmpeg PATH resets every time you close cmd. Must run `set PATH=...` every new session or ffmpeg will not be found.

---

## SUPPORTED URL FORMATS

### Format 1 — Product Video (VDP) ← MOST COMMON
```
https://www.amazon.com/vdp/<video_id>?aci=amzn1.vse.video.<video_id>&product=<ASIN>&ref=<ref>
```
Example:
```
https://www.amazon.com/vdp/07458b53ff3540d29d77d28a0414739b?aci=amzn1.vse.video.07458b53ff3540d29d77d28a0414739b&product=B08CV69V9G&ref=cm_sw_cp_r_ib_dt_qmNWd03mrt6pW
```

### Format 2 — Amazon Live Video
```
https://www.amazon.com/live/video/<video_id>
```
Example:
```
https://www.amazon.com/live/video/0a5e8afd2ecc46bab7e555fb9813c1cc
```

### How to get video URLs from Amazon product pages
1. Go to any Amazon product page in Chrome
2. Press F12 → Network tab
3. Type `m3u8` in the filter box
4. Scroll to the video section on the page and press play
5. A request appears → right click → Copy URL
6. That URL works directly with yt-dlp and this pipeline

---

## VIDEO ID EXTRACTION

The pipeline extracts a `video_id` from the URL automatically using these patterns:

| Pattern | Example match |
|---------|--------------|
| `/live/video/([a-f0-9]+)` | `0a5e8afd2ecc46bab7e555fb9813c1cc` |
| `/vdp/([a-f0-9]+)` | `07458b53ff3540d29d77d28a0414739b` |
| `aci=amzn1.vse.video.([a-f0-9]+)` | `07458b53ff3540d29d77d28a0414739b` |
| MD5 hash fallback | If none match |

The `video_id` becomes the folder name under `downloads/` and is used for all subsequent layers.

---

## LAYER 1 — DOWNLOAD

### Script
```
layer1_download.py
```

### Command
```cmd
python layer1_download.py "AMAZON_VIDEO_URL"
```

### What it does
1. Extracts video_id from URL
2. Creates `downloads/<video_id>/` folder
3. Runs `yt-dlp --list-formats` to detect all quality variants
4. Downloads highest quality (always picks highest TBR/bitrate)
5. Extracts mono 16kHz MP3 audio using ffmpeg (optimized for Whisper)
6. Saves `meta.json` with pipeline state

### Output files
```
downloads/<video_id>/
  video.mp4       ← Full quality video (1080p when available)
  audio.mp3       ← Mono 16kHz audio extracted for Whisper
  meta.json       ← URL, formats, timestamps, pipeline state
```

### Quality variants (typical Amazon video)
```
ID    RES         SIZE      BITRATE   ← ALWAYS PICK HIGHEST ID
690   640x360     ~6.9MB    691k
1229  854x480     ~12.3MB   1229k
2240  1280x720    ~22.4MB   2240k
3703  1920x1080   ~37.1MB   3703k    ← Layer 1 picks this automatically
```

### Flags
```cmd
python layer1_download.py "URL"                  # Standard
python layer1_download.py "URL" --audio-only     # Delete video after audio extraction
python layer1_download.py urls.txt               # Batch mode (one URL per line)
```

### Error → Fix table

| Error message | Root cause | Fix |
|---------------|-----------|-----|
| `FileNotFoundError: yt-dlp` | yt-dlp.exe not in working directory | `copy C:\Users\Baruch\Downloads\yt-dlp.exe C:\Users\Baruch\Desktop\Video-seo-4LYRS\` |
| `FileNotFoundError: ffmpeg` | ffmpeg not in PATH | Run `set PATH=%PATH%;C:\Users\Baruch\Desktop\ffmpeg-8.1.1-essentials_build\bin` |
| `Could not detect formats` | yt-dlp output format changed | Script falls back to 'best' — still works |
| `already been downloaded` | File exists from previous run | Add `--force-overwrites` to yt-dlp command inside script |
| Low quality / audio sync issues | ffmpeg not being used | Ensure ffmpeg is on PATH, use `--downloader ffmpeg --hls-use-mpegts` |
| `'pip' is not recognized` | Python not on PATH | Use `python -m pip install` instead |

---

## LAYER 2 — TRANSCRIBE

### Script
```
layer2_transcribe.py
```

### Command
```cmd
python layer2_transcribe.py <video_id>
```

### What it does
1. Loads `downloads/<video_id>/audio.mp3`
2. Runs OpenAI Whisper locally (no internet, no cost)
3. Outputs transcript in 3 formats
4. Updates `meta.json` with transcription status

### Output files
```
downloads/<video_id>/
  transcript.txt    ← Clean full text, no timestamps
  transcript.srt    ← Timestamped subtitles format
  transcript.json   ← Structured segments with start/end times
```

### transcript.json structure
```json
{
  "video_id": "07458b53ff3540d29d77d28a0414739b",
  "transcribed_at": "2026-06-09T13:36:00Z",
  "model": "base",
  "language": "en",
  "duration_seconds": 80.6,
  "word_count": 213,
  "full_text": "Hi, this is Doreen with WTI...",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 3.5,
      "text": "Hi, this is Doreen with WTI.",
      "duration": 3.5
    }
  ]
}
```

### Model selection
```cmd
python layer2_transcribe.py <video_id>                  # base (default, fast)
python layer2_transcribe.py <video_id> --model tiny     # fastest, lower accuracy
python layer2_transcribe.py <video_id> --model small    # better accuracy
python layer2_transcribe.py <video_id> --model medium   # best for accents/fast speech
python layer2_transcribe.py <video_id> --model large    # most accurate, slowest
```

### Batch mode
```cmd
python layer2_transcribe.py --batch    # Transcribes all downloaded but not yet transcribed
```

### First run note
Whisper downloads model weights on first use:
- `base` model: ~150MB download, cached after first run
- Subsequent runs use cached model — no re-download

### Error → Fix table

| Error message | Root cause | Fix |
|---------------|-----------|-----|
| `whisper not installed` | Package missing | `python -m pip install openai-whisper` |
| `audio.mp3 not found` | Layer 1 didn't complete | Run layer1 first |
| Wrong/garbled words | Background music, fast speech | Use `--model medium` or `--model large` |
| Slow transcription | Large model on CPU | Use `--model base` for speed |
| Missing first 3 seconds | HLS segment sync issue without ffmpeg | Ensure ffmpeg is on PATH during Layer 1 |

---

## LAYER 3 — ANALYZE

### Script
```
layer3_analyze.py
```

### Command
```cmd
python layer3_analyze.py <video_id> --api-key sk-ant-YOUR_KEY_HERE
```

⚠️ **CRITICAL:** There must be a space between `--api-key` and the key value. No space = "unrecognized arguments" error.

### What it does
1. Loads `downloads/<video_id>/transcript.json`
2. Sends transcript + analysis prompt to Claude API (claude-sonnet-4-5)
3. Parses structured JSON response
4. Saves analysis in 3 formats
5. Updates `meta.json`

### Output files
```
downloads/<video_id>/
  analysis.json       ← Full structured JSON (agent-consumable)
  analysis.txt        ← Human-readable formatted report
  listing_copy.txt    ← Title options + bullets + backend keywords
```

### analysis.json full structure
```json
{
  "product_summary": "One sentence product description",
  "target_audience": "Who this is for",
  "hooks": [
    {
      "text": "exact hook phrase from video",
      "timestamp_approx": "first 30 seconds",
      "type": "curiosity|pain|benefit|social_proof|question"
    }
  ],
  "pain_points": [
    {
      "phrase": "exact phrase from transcript",
      "pain": "what problem this addresses",
      "opportunity": "how Lanaak can exploit this"
    }
  ],
  "benefits_claimed": [
    {
      "phrase": "exact benefit phrase",
      "benefit_type": "functional|emotional|social",
      "strength": "strong|medium|weak"
    }
  ],
  "buyer_language": [
    {
      "phrase": "natural buyer phrase",
      "keyword_value": "high|medium|low",
      "use_in": "title|bullet|description|backend|all"
    }
  ],
  "listing_title_suggestions": [
    "Full optimized Amazon title option 1",
    "Full optimized Amazon title option 2"
  ],
  "bullet_points": [
    "Bullet 1 — benefit driven",
    "Bullet 2 — feature with benefit",
    "Bullet 3",
    "Bullet 4",
    "Bullet 5"
  ],
  "backend_keywords": "space separated keywords not in title or bullets",
  "competitor_gaps": [
    {
      "gap": "what competitor failed to mention",
      "your_opportunity": "how Lanaak exploits this"
    }
  ],
  "ad_hooks": [
    "Hook line for video ad 1",
    "Hook line for video ad 2",
    "Hook line for video ad 3"
  ],
  "overall_score": {
    "listing_strength": 7,
    "hook_quality": 6,
    "keyword_density": 5,
    "notes": "brief competitive assessment"
  }
}
```

### Batch mode
```cmd
python layer3_analyze.py --batch --api-key sk-ant-YOUR_KEY
```

### API key management
- Get key: https://console.anthropic.com → API Keys
- Add credits: https://console.anthropic.com/billing (minimum $5)
- NEVER paste API key in chat, email, or screenshots
- If key is exposed: immediately revoke at console.anthropic.com and generate new key

### Error → Fix table

| Error message | Root cause | Fix |
|---------------|-----------|-----|
| `unrecognized arguments: --api-keysk-ant-...` | No space before key | Add space: `--api-key sk-ant-...` |
| `authentication_error 401` | Invalid or revoked API key | Generate new key at console.anthropic.com |
| `credit balance too low` | Zero Anthropic account balance | Add $5 at console.anthropic.com/billing |
| `model deprecated` | Old model string in script | Change MODEL in script to `claude-sonnet-4-5` |
| `transcript.json not found` | Layer 2 didn't complete | Run layer2 first |
| `JSON parse error` | Claude response malformed | Check debug.txt, rerun usually fixes it |
| `No API key found` | Key not passed and not in env | Pass `--api-key sk-ant-...` explicitly |

---

## LAYER 4 — EXPORT

### Script
```
layer4_export.py
```

### Command
```cmd
python layer4_export.py <video_id>
```

### What it does
1. Loads `analysis.json` + `transcript.json` + `meta.json`
2. Builds formatted 6-tab Excel workbook using openpyxl
3. Applies color coding by value/priority
4. Saves timestamped Excel file

### Output file
```
downloads/<video_id>/
  intelligence_report_YYYYMMDD_HHMM.xlsx    ← Final deliverable
```

### Color coding system
| Color | Meaning |
|-------|---------|
| 🟢 Green background | High value opportunities |
| 🟡 Yellow background | Medium value / backend keywords |
| 🔴 Orange background | Competitor weaknesses |
| 🔵 Blue header | Section headers |
| ⬜ Light gray | Alternating row styling |

### Batch mode
```cmd
python layer4_export.py --batch    # Exports all analyzed videos
```

### Idempotent — safe to rerun
Layer 4 only reads existing files. If computer shuts off mid-run, simply rerun:
```cmd
python layer4_export.py <video_id>
```

### Error → Fix table

| Error message | Root cause | Fix |
|---------------|-----------|-----|
| `analysis.json not found` | Layer 3 incomplete | Run layer3 first |
| `openpyxl not installed` | Package missing | `python -m pip install openpyxl` |
| No .xlsx file after run | Computer shut off | Rerun layer4 — safe and idempotent |

---

## COMPLETE PIPELINE — COPY-PASTE SEQUENCES

### Single video
```cmd
REM === SETUP (run every new cmd session) ===
cd C:\Users\Baruch\Desktop\Video-seo-4LYRS
set PATH=%PATH%;C:\Users\Baruch\Desktop\ffmpeg-8.1.1-essentials_build\bin

REM === LAYER 1: DOWNLOAD ===
python layer1_download.py "PASTE_AMAZON_VIDEO_URL_HERE"

REM === LAYER 2: TRANSCRIBE (replace VIDEO_ID with actual ID from Layer 1 output) ===
python layer2_transcribe.py VIDEO_ID_HERE

REM === LAYER 3: ANALYZE (replace with your current API key) ===
python layer3_analyze.py VIDEO_ID_HERE --api-key sk-ant-YOUR_KEY_HERE

REM === LAYER 4: EXPORT ===
python layer4_export.py VIDEO_ID_HERE

REM === RESULT ===
REM Open: downloads\VIDEO_ID_HERE\intelligence_report_*.xlsx
```

### Batch (multiple videos)
```cmd
REM Create urls.txt with one Amazon video URL per line, then:

cd C:\Users\Baruch\Desktop\Video-seo-4LYRS
set PATH=%PATH%;C:\Users\Baruch\Desktop\ffmpeg-8.1.1-essentials_build\bin

python layer1_download.py urls.txt
python layer2_transcribe.py --batch
python layer3_analyze.py --batch --api-key sk-ant-YOUR_KEY_HERE
python layer4_export.py --batch
```

---

## OUTPUT FILE STRUCTURE

```
C:\Users\Baruch\Desktop\Video-seo-4LYRS\
│
├── layer1_download.py
├── layer2_transcribe.py
├── layer3_analyze.py
├── layer4_export.py
├── run_pipeline.bat
├── yt-dlp.exe                          ← Must be here
│
└── downloads\
    └── <video_id>\                     ← One folder per video
        ├── video.mp4                   ← 1080p video
        ├── audio.mp3                   ← Whisper-ready audio
        ├── transcript.txt              ← Clean text
        ├── transcript.srt              ← Timestamped
        ├── transcript.json             ← Structured segments
        ├── analysis.json               ← Claude analysis (agent-consumable)
        ├── analysis.txt                ← Human readable report
        ├── listing_copy.txt            ← Ready-to-paste Amazon copy
        ├── intelligence_report_*.xlsx  ← FINAL DELIVERABLE
        └── meta.json                   ← Pipeline state tracker
```

---

## AGENT DECISION TREE

```
RECEIVE: Amazon video URL
    │
    ├─► Is URL format /vdp/ or /live/video/?
    │       YES → proceed
    │       NO  → ask user: "Please share the video URL from the Amazon product page"
    │
    ▼
RUN SETUP:
    cd C:\Users\Baruch\Desktop\Video-seo-4LYRS
    set PATH=%PATH%;C:\Users\Baruch\Desktop\ffmpeg-8.1.1-essentials_build\bin
    │
    ▼
LAYER 1: python layer1_download.py "URL"
    │
    ├─► Success? Check for downloads/<video_id>/audio.mp3
    │       YES → proceed to Layer 2
    │       NO, yt-dlp not found → copy yt-dlp.exe to working directory
    │       NO, ffmpeg not found → set PATH for ffmpeg
    │       NO, other error → run yt-dlp --list-formats "URL" manually, check output
    │
    ▼
LAYER 2: python layer2_transcribe.py <video_id>
    │
    ├─► Success? Check for downloads/<video_id>/transcript.json
    │       YES → proceed to Layer 3
    │       NO, whisper missing → python -m pip install openai-whisper
    │       NO, poor quality → rerun with --model medium
    │
    ▼
LAYER 3: python layer3_analyze.py <video_id> --api-key <key>
    │
    ├─► Success? Check for downloads/<video_id>/analysis.json
    │       YES → proceed to Layer 4
    │       NO, spacing error → ensure space: --api-key sk-ant-...
    │       NO, auth error 401 → generate new key at console.anthropic.com
    │       NO, credit error → add $5 at console.anthropic.com/billing
    │       NO, model deprecated → update MODEL = "claude-sonnet-4-5" in script
    │
    ▼
LAYER 4: python layer4_export.py <video_id>
    │
    ├─► Success? Check for downloads/<video_id>/intelligence_report_*.xlsx
    │       YES → PIPELINE COMPLETE
    │       NO → safe to rerun layer4 (idempotent)
    │
    ▼
DELIVER: Open intelligence_report_*.xlsx
```

---

## LANAAK-SPECIFIC CONTEXT

### Brand
- **Name:** Lanaak
- **Product:** Kids beginner fishing kits
- **Website:** myfirstfishingkit.com
- **Amazon:** Multiple ASINs (backpack line, classic line)
- **Core ASIN:** B074RP1VHS (Kids Fishing Pole + Tackle Box)
- **Target age:** 5-10 years
- **Key differentiator:** Complete kit, beginner-friendly, "first fishing kit"

### Competitor priority list (run pipeline in this order)

| Priority | Brand | Why | ASIN to target |
|----------|-------|-----|----------------|
| 1 | PLUSINNO | #1 BSR, most videos, biggest threat | B08CV69V9G (confirmed video) |
| 2 | ODDSPRO | Pink/girls angle — Lanaak vulnerability | Search Amazon for videos |
| 3 | WIDDEN | Age 5-18 targeting overlaps Lanaak | Search Amazon for videos |
| 4 | Play22 | 40-piece bundle — volume competitor | Search Amazon for videos |
| 5 | Lanaak own listing | Analyze own language for gaps | B074RP1VHS |

### What to extract for Lanaak specifically

From **Competitor Gaps tab:**
→ What pain points do they miss? That's your ad angle.

From **Keywords tab (High value only):**
→ Phrases not in your current title/bullets = immediate listing update

From **Hooks & Ad Copy tab:**
→ Ad hooks to beat in your Sponsored Brands video campaign

From **Listing Copy tab:**
→ Compare their bullets to yours — steal their strongest language and improve it

### Key Lanaak intel from first run (PLUSINNO, June 9 2026)
- Competitor hook: *"are they bugging you to go fishing but you don't want to spend a ton of money"*
- Pain point: Parents who feel pressured/unprepared for fishing
- Gap identified: No CTA or price/value justification
- Opportunity: Own the "complete kit, no experience needed, affordable" angle

---

## COST BREAKDOWN

### Per video (current pricing June 2026)
| Component | Tool | Cost |
|-----------|------|------|
| Download | yt-dlp (free) | $0.00 |
| Audio extraction | ffmpeg (free) | $0.00 |
| Transcription | Whisper local (free) | $0.00 |
| Claude input (~1,100 tokens) | Sonnet 4.5 @ $3/M | $0.0033 |
| Claude output (~1,000 tokens) | Sonnet 4.5 @ $15/M | $0.015 |
| Excel export | openpyxl (free) | $0.00 |
| **TOTAL** | | **~$0.018** |

### Scale projections
| Volume | Monthly cost |
|--------|-------------|
| 5 videos/week | ~$0.40/month |
| 50 videos/week | ~$4.00/month |
| 500 videos/week | ~$40.00/month |
| 5,000 videos/week | ~$400/month |

### Cost optimization
| Method | Savings | How |
|--------|---------|-----|
| Switch to Haiku 4.5 | 66% cheaper | Change MODEL in layer3_analyze.py to `claude-haiku-4-5` |
| Batch API | 50% off | Queue 10+ videos |
| Prompt caching | 90% off input | Cache system prompt (advanced) |
| Audio only mode | Saves disk space | Add `--audio-only` flag |

**$5 Anthropic credit = ~250 videos at standard rate, ~750 with Haiku 4.5**

---

## KNOWN ISSUES LOG (RL TRAINING DATA)

### Session: June 9, 2026 — First production run

**Video:** PLUSINNO Kids Fishing Pole Amazon Live  
**Video ID:** `07458b53ff3540d29d77d28a0414739b`  
**Result:** ✅ Full pipeline completed successfully

| # | Error | Layer | Root Cause | Fix Applied |
|---|-------|-------|-----------|-------------|
| 1 | ASIN B09JW55B7X had no video | Pre-L1 | Product page had no video attached | Switched to VDP URL format |
| 2 | FileNotFoundError yt-dlp | L1 | yt-dlp.exe not in working directory | Copied yt-dlp.exe to Video-seo-4LYRS folder |
| 3 | unrecognized arguments --api-keysk-ant | L3 | No space between flag and value | Added space: `--api-key sk-ant-...` |
| 4 | authentication_error 401 | L3 | Exposed API key was revoked | Generated new key at console.anthropic.com |
| 5 | credit balance too low | L3 | Zero balance | Added $5 at billing page |
| 6 | Layer 4 incomplete | L4 | Computer shut off mid-run | Reran layer4 — completed in 10 seconds |
| 7 | layer1_download.py not found | L1 | Scripts not in working directory | Downloaded all .py files to Video-seo-4LYRS |
| 8 | Python shell opened instead of cmd | Setup | Clicked Python app not cmd.exe | Win+R → cmd → Enter |
| 9 | model deprecated warning | L3 | Old model string `claude-sonnet-4-20250514` | Updated to `claude-sonnet-4-5` |

---

## VERSION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | June 9, 2026 | Initial 4-layer pipeline, Windows-tested, first Lanaak run complete |

---

## LINKS

- **Anthropic Console:** https://console.anthropic.com
- **yt-dlp releases:** https://github.com/yt-dlp/yt-dlp/releases/latest
- **ffmpeg download:** https://www.gyan.dev/ffmpeg/builds/
- **Lanaak Amazon:** https://www.amazon.com/Lanaak-Kids-Fishing-Pole-Tackle/dp/B074RP1VHS
- **Lanaak website:** https://myfirstfishingkit.com
