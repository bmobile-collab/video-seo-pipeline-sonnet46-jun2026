#!/usr/bin/env python3
"""
Amazon Video Pipeline -- Layer 1: Download + Audio Extraction
"""

import subprocess
import sys
import os
import io
import json
import re
import argparse
from datetime import datetime
from pathlib import Path

# Force UTF-8 output so Windows cp1252 never chokes on our print statements
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

OUTPUT_DIR = Path("downloads")


def sanitize_id(url: str) -> str:
    patterns = [
        r"/live/video/([a-f0-9]+)",
        r"/vdp/([a-f0-9]+)",
        r"aci=amzn1\.vse\.video\.([a-f0-9]+)",
        r"video/([a-f0-9]{20,})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)[:32]
    import hashlib
    return hashlib.md5(url.encode()).hexdigest()[:16]


def get_formats(url: str) -> list:
    cmd = ["yt-dlp", "--list-formats", "--no-warnings", url]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    lines = result.stdout.splitlines()
    formats = []
    for line in lines:
        m = re.match(r"^(\d+)\s+mp4\s+(\d+x\d+)\s+(\d+)\s+~?([\d.]+\w+)\s+(\d+)k", line)
        if m:
            formats.append({
                "id": m.group(1),
                "resolution": m.group(2),
                "fps": int(m.group(3)),
                "filesize": m.group(4),
                "tbr": int(m.group(5)),
            })
    formats.sort(key=lambda x: x["tbr"], reverse=True)
    return formats


def best_format_id(formats: list) -> str:
    if not formats:
        return "best"
    return formats[0]["id"]


def download_video(url: str, out_dir: Path, fmt_id: str) -> Path:
    out_path = out_dir / "video.mp4"
    cmd = [
        "yt-dlp",
        "--downloader", "ffmpeg",
        "--hls-use-mpegts",
        "-f", fmt_id,
        "--force-overwrites",
        "--no-warnings",
        "-o", str(out_path),
        url,
    ]
    print(f"  [DL] Downloading format {fmt_id}...")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode != 0:
        print(f"  [WARN] yt-dlp error: {result.stderr[:300]}")
        return None
    return out_path


def extract_audio(video_path: Path, out_dir: Path) -> Path:
    audio_path = out_dir / "audio.mp3"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        "-b:a", "64k",
        str(audio_path),
        "-loglevel", "error",
    ]
    print(f"  [AUDIO] Extracting audio...")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode != 0:
        print(f"  [WARN] ffmpeg error: {result.stderr[:300]}")
        return None
    return audio_path


def save_meta(out_dir: Path, url: str, video_id: str, formats: list, video_path: Path, audio_path: Path):
    meta = {
        "video_id": video_id,
        "url": url,
        "downloaded_at": datetime.utcnow().isoformat() + "Z",
        "formats_available": formats,
        "selected_format": formats[0] if formats else None,
        "files": {
            "video": str(video_path) if video_path else None,
            "audio": str(audio_path) if audio_path else None,
        },
        "status": "complete",
        "next_step": "layer2_transcribe.py"
    }
    meta_path = out_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding='utf-8')
    return meta


def process_url(url: str, audio_only: bool = False) -> dict:
    url = url.strip()
    if not url:
        return None

    print(f"\n{'='*55}")
    print(f"  URL: {url[:80]}")
    print(f"{'='*55}")

    video_id = sanitize_id(url)
    out_dir = OUTPUT_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"  [DIR] Output folder: {out_dir}")

    print(f"  [SCAN] Detecting available formats...")
    formats = get_formats(url)
    if formats:
        print(f"  [OK] Found {len(formats)} formats -- best: {formats[0]['resolution']} @ {formats[0]['tbr']}kbps")
    else:
        print(f"  [WARN] Could not detect formats, trying 'best'")

    fmt_id = best_format_id(formats)
    video_path = download_video(url, out_dir, fmt_id)
    if not video_path or not video_path.exists():
        print(f"  [ERR] Download failed")
        return {"status": "failed", "video_id": video_id, "url": url}

    size_mb = video_path.stat().st_size / 1024 / 1024
    print(f"  [OK] Video saved: {size_mb:.1f} MB")

    audio_path = extract_audio(video_path, out_dir)
    if audio_path and audio_path.exists():
        audio_mb = audio_path.stat().st_size / 1024 / 1024
        print(f"  [OK] Audio saved: {audio_mb:.2f} MB")
    else:
        print(f"  [WARN] Audio extraction failed")

    if audio_only and video_path.exists():
        video_path.unlink()
        print(f"  [DEL] Video removed (audio-only mode)")
        video_path = None

    meta = save_meta(out_dir, url, video_id, formats, video_path, audio_path)
    print(f"  [OK] Meta saved -- ready for Layer 2 transcription")
    return meta


def main():
    parser = argparse.ArgumentParser(description="Amazon Video Pipeline -- Layer 1")
    parser.add_argument("input", help="Amazon URL or path to .txt file with URLs")
    parser.add_argument("output_dir", nargs="?", default=None, help="Output directory (used by Layer 5 proxy)")
    parser.add_argument("--audio-only", action="store_true", help="Delete video after audio extraction")
    args = parser.parse_args()

    global OUTPUT_DIR
    if args.output_dir:
        OUTPUT_DIR = Path(args.output_dir)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.input.endswith(".txt") and os.path.isfile(args.input):
        urls = Path(args.input).read_text(encoding='utf-8').splitlines()
        urls = [u for u in urls if u.strip() and not u.startswith("#")]
        print(f"[LIST] Batch mode -- {len(urls)} URLs found")
        results = []
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}]")
            result = process_url(url, args.audio_only)
            results.append(result)
        summary = OUTPUT_DIR / "batch_summary.json"
        summary.write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(f"\n[OK] Batch complete. Summary -> {summary}")
    else:
        result = process_url(args.input, args.audio_only)
        if result and result.get("status") != "failed":
            print(f"\n[OK] Layer 1 complete for {result['video_id']}")
            print(f"    Next: python layer2_transcribe.py {result['video_id']}")
        else:
            print(f"\n[ERR] Layer 1 failed")
            sys.exit(1)


if __name__ == "__main__":
    main()
