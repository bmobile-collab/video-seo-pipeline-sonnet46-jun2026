#!/usr/bin/env python3
"""
Amazon Video Pipeline — Layer 2: Transcription
===============================================
Takes audio.mp3 from Layer 1 output folder
Runs OpenAI Whisper locally (free, no API key needed)
Outputs:
  transcript.txt     — clean full text
  transcript.srt     — timestamped subtitles
  transcript.json    — structured segments with timestamps
  meta.json          — updated with transcription status

Usage:
  python layer2_transcribe.py <video_id>
  python layer2_transcribe.py <video_id> --model medium
  python layer2_transcribe.py --batch          (transcribes all pending)

Models (tradeoff: speed vs accuracy):
  tiny    — fastest, good enough for clear speech
  base    — good balance (recommended default)
  small   — better accuracy, slower
  medium  — best for accented/fast speech
  large   — most accurate, slowest

Install Whisper first (one time):
  pip install openai-whisper

On Windows if pip not found:
  python -m pip install openai-whisper
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

DOWNLOADS_DIR = Path("downloads")
DEFAULT_MODEL = "base"


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(segments: list) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_timestamp(seg["start"])
        end = format_timestamp(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def transcribe(video_id: str, model_name: str = DEFAULT_MODEL) -> dict:
    out_dir = DOWNLOADS_DIR / video_id

    if not out_dir.exists():
        print(f"  ❌  Folder not found: {out_dir}")
        print(f"      Run layer1_download.py first")
        return None

    audio_path = out_dir / "audio.mp3"
    if not audio_path.exists():
        print(f"  ❌  audio.mp3 not found in {out_dir}")
        print(f"      Run layer1_download.py first")
        return None

    meta_path = out_dir / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}

    print(f"\n{'='*55}")
    print(f"  Video ID : {video_id}")
    print(f"  Audio    : {audio_path}")
    print(f"  Model    : {model_name}")
    print(f"{'='*55}")

    try:
        import whisper
    except ImportError:
        print("\n  ❌  Whisper not installed.")
        print("  Run: pip install openai-whisper")
        print("  Then re-run this script\n")
        sys.exit(1)

    print(f"  🔄  Loading Whisper model '{model_name}'...")
    print(f"      (First run downloads the model — ~150MB for 'base')")
    model = whisper.load_model(model_name)

    print(f"  🎙  Transcribing...")
    result = model.transcribe(
        str(audio_path),
        language="en",
        task="transcribe",
        verbose=False,
        fp16=False,
    )

    full_text = result["text"].strip()
    segments = result["segments"]

    txt_path = out_dir / "transcript.txt"
    txt_path.write_text(full_text, encoding="utf-8")
    print(f"  ✅  transcript.txt saved ({len(full_text)} chars)")

    srt_content = segments_to_srt(segments)
    srt_path = out_dir / "transcript.srt"
    srt_path.write_text(srt_content, encoding="utf-8")
    print(f"  ✅  transcript.srt saved ({len(segments)} segments)")

    structured = {
        "video_id": video_id,
        "transcribed_at": datetime.utcnow().isoformat() + "Z",
        "model": model_name,
        "language": result.get("language", "en"),
        "duration_seconds": segments[-1]["end"] if segments else 0,
        "word_count": len(full_text.split()),
        "full_text": full_text,
        "segments": [
            {
                "id": s["id"],
                "start": round(s["start"], 2),
                "end": round(s["end"], 2),
                "text": s["text"].strip(),
                "duration": round(s["end"] - s["start"], 2),
            }
            for s in segments
        ],
    }

    json_path = out_dir / "transcript.json"
    json_path.write_text(json.dumps(structured, indent=2), encoding="utf-8")
    print(f"  ✅  transcript.json saved")

    meta["transcription"] = {
        "status": "complete",
        "model": model_name,
        "transcribed_at": structured["transcribed_at"],
        "word_count": structured["word_count"],
        "duration_seconds": structured["duration_seconds"],
        "files": {
            "txt": str(txt_path),
            "srt": str(srt_path),
            "json": str(json_path),
        }
    }
    meta["next_step"] = "layer3_analyze.py"
    meta_path.write_text(json.dumps(meta, indent=2))

    print(f"\n  📊  Stats:")
    print(f"      Words      : {structured['word_count']}")
    print(f"      Duration   : {structured['duration_seconds']:.1f}s")
    print(f"      Segments   : {len(segments)}")
    print(f"\n  ✅  Layer 2 complete")
    print(f"      Next: python layer3_analyze.py {video_id}")

    print(f"\n  📄  Transcript preview:")
    print(f"  {'─'*50}")
    preview = full_text[:500] + ("..." if len(full_text) > 500 else "")
    print(f"  {preview}")
    print(f"  {'─'*50}")

    return structured


def batch_transcribe(model_name: str = DEFAULT_MODEL):
    if not DOWNLOADS_DIR.exists():
        print("  ❌  No downloads folder found. Run layer1 first.")
        return

    pending = []
    for folder in DOWNLOADS_DIR.iterdir():
        if folder.is_dir():
            audio = folder / "audio.mp3"
            transcript = folder / "transcript.txt"
            if audio.exists() and not transcript.exists():
                pending.append(folder.name)

    if not pending:
        print("  ✅  No pending transcriptions found.")
        print("      (All downloaded videos already transcribed)")
        return

    print(f"  📋  Found {len(pending)} pending transcription(s)")
    for i, vid_id in enumerate(pending, 1):
        print(f"\n  [{i}/{len(pending)}]")
        transcribe(vid_id, model_name)


def main():
    parser = argparse.ArgumentParser(description="Amazon Video Pipeline — Layer 2: Transcription")
    parser.add_argument("video_id", nargs="?", help="Video ID from Layer 1 output folder name")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Whisper model size (default: base)")
    parser.add_argument("--batch", action="store_true",
                        help="Transcribe all pending (downloaded but not transcribed)")
    args = parser.parse_args()

    if args.batch:
        batch_transcribe(args.model)
    elif args.video_id:
        transcribe(args.video_id, args.model)
    else:
        parser.print_help()
        print("\n  Example:")
        print("    python layer2_transcribe.py 0287b3106d634bd189057a96fc83101b")
        print("    python layer2_transcribe.py 0287b3106d634bd189057a96fc83101b --model medium")
        print("    python layer2_transcribe.py --batch")


if __name__ == "__main__":
    main()
