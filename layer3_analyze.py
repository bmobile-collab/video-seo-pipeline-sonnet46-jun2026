#!/usr/bin/env python3
"""
Amazon Video Pipeline — Layer 3: Claude Analysis
=================================================
Takes transcript.json from Layer 2
Sends to Claude API for deep competitive analysis
Outputs:
  analysis.json    — full structured analysis
  analysis.txt     — human readable report
  listing_copy.txt — ready to paste into Amazon listing
  meta.json        — updated with analysis status

Usage:
  python layer3_analyze.py <video_id>
  python layer3_analyze.py --batch

Setup:
  pip install anthropic
  Set your API key:
    Windows: setx ANTHROPIC_API_KEY "sk-ant-..."
    Or pass directly: python layer3_analyze.py <id> --api-key sk-ant-...

Get API key at: https://console.anthropic.com
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime

DOWNLOADS_DIR = Path("downloads")
MODEL = "claude-sonnet-4-5"

ANALYSIS_PROMPT = """You are an expert Amazon FBA listing optimizer and competitive intelligence analyst.

Analyze this transcript from an Amazon product video and extract structured competitive intelligence.

TRANSCRIPT:
{transcript}

PRODUCT VIDEO URL: {url}

Return ONLY valid JSON with this exact structure (no markdown, no preamble):
{{
  "product_summary": "One sentence describing the product",
  "target_audience": "Who this product is for",
  "hooks": [
    {{
      "text": "exact opening hook phrase",
      "timestamp_approx": "first 30 seconds",
      "type": "curiosity|pain|benefit|social_proof|question"
    }}
  ],
  "pain_points": [
    {{
      "phrase": "exact phrase from transcript",
      "pain": "what problem this addresses",
      "opportunity": "how you could use this"
    }}
  ],
  "benefits_claimed": [
    {{
      "phrase": "exact benefit phrase from transcript",
      "benefit_type": "functional|emotional|social",
      "strength": "strong|medium|weak"
    }}
  ],
  "buyer_language": [
    {{
      "phrase": "natural buyer phrase",
      "keyword_value": "high|medium|low",
      "use_in": "title|bullet|description|backend|all"
    }}
  ],
  "listing_title_suggestions": [
    "Full optimized title suggestion 1",
    "Full optimized title suggestion 2"
  ],
  "bullet_points": [
    "Ready to paste bullet point 1 — benefit driven",
    "Ready to paste bullet point 2 — feature with benefit",
    "Ready to paste bullet point 3",
    "Ready to paste bullet point 4",
    "Ready to paste bullet point 5"
  ],
  "backend_keywords": "space separated keywords not already in title or bullets",
  "competitor_gaps": [
    {{
      "gap": "what they failed to mention or do poorly",
      "your_opportunity": "how to exploit this in your listing or ads"
    }}
  ],
  "ad_hooks": [
    "Hook line for video ad 1",
    "Hook line for video ad 2",
    "Hook line for video ad 3"
  ],
  "overall_score": {{
    "listing_strength": 7,
    "hook_quality": 6,
    "keyword_density": 5,
    "notes": "brief assessment"
  }}
}}"""


def load_transcript(video_id: str) -> dict:
    json_path = DOWNLOADS_DIR / video_id / "transcript.json"
    txt_path = DOWNLOADS_DIR / video_id / "transcript.txt"

    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        return data
    elif txt_path.exists():
        text = txt_path.read_text(encoding="utf-8")
        return {"full_text": text, "video_id": video_id}
    else:
        return None


def call_claude(transcript_text: str, url: str, api_key: str) -> dict:
    try:
        import anthropic
    except ImportError:
        print("  ❌  anthropic package not installed")
        print("      Run: pip install anthropic")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    prompt = ANALYSIS_PROMPT.format(
        transcript=transcript_text[:6000],
        url=url
    )

    print(f"  🤖  Sending to Claude ({MODEL})...")
    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ⚠  JSON parse error: {e}")
        print(f"  Raw response saved to debug.txt")
        Path("debug.txt").write_text(raw)
        return None


def format_report(analysis: dict, video_id: str) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("AMAZON VIDEO COMPETITIVE ANALYSIS REPORT")
    lines.append(f"Video ID: {video_id}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)

    lines.append(f"\n📦 PRODUCT\n{analysis.get('product_summary', 'N/A')}")
    lines.append(f"\n👥 TARGET AUDIENCE\n{analysis.get('target_audience', 'N/A')}")

    score = analysis.get("overall_score", {})
    lines.append(f"\n📊 COMPETITOR SCORE")
    lines.append(f"  Listing Strength : {score.get('listing_strength', '?')}/10")
    lines.append(f"  Hook Quality     : {score.get('hook_quality', '?')}/10")
    lines.append(f"  Keyword Density  : {score.get('keyword_density', '?')}/10")
    lines.append(f"  Notes            : {score.get('notes', '')}")

    lines.append(f"\n🎣 HOOKS USED")
    for h in analysis.get("hooks", []):
        lines.append(f"  [{h.get('type', '').upper()}] \"{h.get('text', '')}\"")

    lines.append(f"\n😤 PAIN POINTS THEY HIT")
    for p in analysis.get("pain_points", []):
        lines.append(f"  • {p.get('pain', '')}")
        lines.append(f"    Phrase: \"{p.get('phrase', '')}\"")
        lines.append(f"    Your opportunity: {p.get('opportunity', '')}")

    lines.append(f"\n💰 HIGH VALUE BUYER PHRASES")
    for b in analysis.get("buyer_language", []):
        if b.get("keyword_value") == "high":
            lines.append(f"  ★ \"{b.get('phrase', '')}\" → use in: {b.get('use_in', '')}")
    for b in analysis.get("buyer_language", []):
        if b.get("keyword_value") == "medium":
            lines.append(f"  ◆ \"{b.get('phrase', '')}\" → use in: {b.get('use_in', '')}")

    lines.append(f"\n🚨 COMPETITOR GAPS (YOUR OPPORTUNITIES)")
    for g in analysis.get("competitor_gaps", []):
        lines.append(f"  GAP: {g.get('gap', '')}")
        lines.append(f"  ➜   {g.get('your_opportunity', '')}")
        lines.append("")

    lines.append(f"\n🎬 AD HOOKS TO STEAL/BEAT")
    for i, h in enumerate(analysis.get("ad_hooks", []), 1):
        lines.append(f"  {i}. {h}")

    lines.append("\n" + "=" * 60)
    lines.append("READY-TO-USE LISTING COPY")
    lines.append("=" * 60)

    lines.append(f"\n📝 TITLE OPTIONS")
    for i, t in enumerate(analysis.get("listing_title_suggestions", []), 1):
        lines.append(f"  {i}. {t}")

    lines.append(f"\n✅ BULLET POINTS")
    for b in analysis.get("bullet_points", []):
        lines.append(f"  • {b}")

    lines.append(f"\n🔑 BACKEND KEYWORDS")
    lines.append(f"  {analysis.get('backend_keywords', '')}")

    return "\n".join(lines)


def analyze(video_id: str, api_key: str) -> dict:
    out_dir = DOWNLOADS_DIR / video_id

    if not out_dir.exists():
        print(f"  ❌  Folder not found. Run layer1 and layer2 first.")
        return None

    print(f"\n{'='*55}")
    print(f"  Video ID : {video_id}")
    print(f"{'='*55}")

    transcript_data = load_transcript(video_id)
    if not transcript_data:
        print(f"  ❌  No transcript found. Run layer2_transcribe.py first.")
        return None

    full_text = transcript_data.get("full_text", "")
    word_count = transcript_data.get("word_count", len(full_text.split()))
    url = ""
    meta_path = out_dir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        url = meta.get("url", "")

    print(f"  📄  Transcript loaded: {word_count} words")

    analysis = call_claude(full_text, url, api_key)
    if not analysis:
        print(f"  ❌  Analysis failed")
        return None

    analysis_path = out_dir / "analysis.json"
    analysis_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    print(f"  ✅  analysis.json saved")

    report = format_report(analysis, video_id)
    report_path = out_dir / "analysis.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"  ✅  analysis.txt saved")

    bullets = analysis.get("bullet_points", [])
    titles = analysis.get("listing_title_suggestions", [])
    backend = analysis.get("backend_keywords", "")
    listing_lines = ["LISTING COPY — READY TO PASTE", "=" * 40, ""]
    listing_lines.append("TITLE OPTIONS:")
    for i, t in enumerate(titles, 1):
        listing_lines.append(f"{i}. {t}")
    listing_lines.append("\nBULLET POINTS:")
    for b in bullets:
        listing_lines.append(f"• {b}")
    listing_lines.append(f"\nBACKEND KEYWORDS:\n{backend}")
    listing_path = out_dir / "listing_copy.txt"
    listing_path.write_text("\n".join(listing_lines), encoding="utf-8")
    print(f"  ✅  listing_copy.txt saved")

    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        meta["analysis"] = {
            "status": "complete",
            "analyzed_at": datetime.utcnow().isoformat() + "Z",
            "model": MODEL,
            "files": {
                "analysis_json": str(analysis_path),
                "analysis_txt": str(report_path),
                "listing_copy": str(listing_path),
            }
        }
        meta["next_step"] = "layer4_export.py"
        meta_path.write_text(json.dumps(meta, indent=2))

    print(f"\n{'='*55}")
    print(report)
    print(f"\n  ✅  Layer 3 complete!")
    print(f"      Next: python layer4_export.py {video_id}")

    return analysis


def main():
    parser = argparse.ArgumentParser(description="Amazon Video Pipeline — Layer 3: Claude Analysis")
    parser.add_argument("video_id", nargs="?", help="Video ID from Layer 1/2 output")
    parser.add_argument("--api-key", help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    parser.add_argument("--batch", action="store_true", help="Analyze all transcribed but unanalyzed videos")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n  ❌  No API key found.")
        print("  Get one at: https://console.anthropic.com")
        print("  Then run:")
        print('    setx ANTHROPIC_API_KEY "sk-ant-..."')
        print("  Or pass directly:")
        print(f'    python layer3_analyze.py {args.video_id or "<video_id>"} --api-key sk-ant-...\n')
        sys.exit(1)

    if args.batch:
        if not DOWNLOADS_DIR.exists():
            print("  ❌  No downloads folder found.")
            return
        pending = []
        for folder in DOWNLOADS_DIR.iterdir():
            if folder.is_dir():
                has_transcript = (folder / "transcript.json").exists()
                has_analysis = (folder / "analysis.json").exists()
                if has_transcript and not has_analysis:
                    pending.append(folder.name)
        if not pending:
            print("  ✅  Nothing pending analysis.")
            return
        print(f"  📋  {len(pending)} video(s) to analyze")
        for i, vid_id in enumerate(pending, 1):
            print(f"\n  [{i}/{len(pending)}]")
            analyze(vid_id, api_key)
    elif args.video_id:
        analyze(args.video_id, api_key)
    else:
        parser.print_help()
        print("\n  Example:")
        print("    python layer3_analyze.py 0287b3106d634bd189057a96fc83101b --api-key sk-ant-...")


if __name__ == "__main__":
    main()
