#!/usr/bin/env python3
"""
Amazon Video Pipeline -- Layer 2: Transcription
"""

import sys
import os
import io
import json
import argparse
from pathlib import Path
from datetime import datetime

# Force UTF-8 output so Windows cp1252 never chokes
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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
        print(f"  [ERR] Folder not found: {out_dir}")
        return None

    audio_path = out_dir / "audio.mp3"
    if not audio_path.exists():
        print(f"  [ERR] audio.mp3 not found in {out_dir}")
        return None

    meta_path = out_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}

    print(f"\n{'='*55}")
    print(f"  Video ID : {video_id}")
    print(f"  Audio    : {audio_path}")
    print(f"  Model    : {model_name}")
    print(f"{'='*55}")

    try:
        import whisper
    except ImportError:
        print("\n  [ERR] Whisper not installed. Run: pip install openai-whisper\n")
        sys.exit(1)

    print(f"  [LOAD] Loading Whisper model '{model_name}'...")
    print(f"         (First run downloads the model -- ~150MB for 'base')")
    model = whisper.load_model(model_name)

    print(f"  [MIC] Transcribing...")
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
    print(f"  [OK] transcript.txt saved ({len(full_text)} chars)")

    srt_content = segments_to_srt(segments)
    srt_path = out_dir / "transcript.srt"
    srt_path.write_text(srt_content, encoding="utf-8")
    print(f"  [OK] transcript.srt saved ({len(segments)} segments)")

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
    print(f"  [OK] transcript.json saved")

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
    meta_path.write_text(json.dumps(meta, indent=2), encoding='utf-8')

    print(f"\n  [STATS]")
    print(f"      Words    : {structured['word_count']}")
    print(f"      Duration : {structured['duration_seconds']:.1f}s")
    print(f"      Segments : {len(segments)}")
    print(f"\n  [OK] Layer 2 complete")

    preview = full_text[:500] + ("..." if len(full_text) > 500 else "")
    print(f"\n  Transcript preview:\n  {'-'*50}\n  {preview}\n  {'-'*50}")

    return structured


def batch_transcribe(model_name: str = DEFAULT_MODEL):
    if not DOWNLOADS_DIR.exists():
        print("  [ERR] No downloads folder found.")
        return
    pending = []
    for folder in DOWNLOADS_DIR.iterdir():
        if folder.is_dir():
            audio = folder / "audio.mp3"
            transcript = folder / "transcript.txt"
            if audio.exists() and not transcript.exists():
                pending.append(folder.name)
    if not pending:
        print("  [OK] No pending transcriptions found.")
        return
    print(f"  [LIST] Found {len(pending)} pending transcription(s)")
    for i, vid_id in enumerate(pending, 1):
        print(f"\n  [{i}/{len(pending)}]")
        transcribe(vid_id, model_name)


def main():
    parser = argparse.ArgumentParser(description="Amazon Video Pipeline -- Layer 2")
    parser.add_argument("video_id", nargs="?", help="Video ID or full path to run directory")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--batch", action="store_true")
    args = parser.parse_args()

    if args.batch:
        batch_transcribe(args.model)
    elif args.video_id:
        # Accept full path from proxy (e.g. C:\...\outputs\Lanaak_20260609_130400)
        p = Path(args.video_id)
        if p.is_absolute() or (p.exists() and p.is_dir()):
            global DOWNLOADS_DIR
            DOWNLOADS_DIR = p.parent
            transcribe(p.name, args.model)
        else:
            transcribe(args.video_id, args.model)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
