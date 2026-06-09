#!/usr/bin/env python3
"""
Amazon Video Pipeline -- Layer 3: Claude Analysis
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
MODEL = "claude-sonnet-4-5"

ANALYSIS_PROMPT = """You are an expert Amazon FBA listing optimizer and competitive intelligence analyst working for the brand {brand}.

Analyze this transcript from an Amazon product video and extract structured competitive intelligence.

TRANSCRIPT:
{transcript}

PRODUCT VIDEO URL: {url}
BRAND: {brand}
ADDITIONAL NOTES: {notes}

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
    "Ready to paste bullet point 1 -- benefit driven",
    "Ready to paste bullet point 2 -- feature with benefit",
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


def load_transcript(out_dir: Path) -> dict:
    json_path = out_dir / "transcript.json"
    txt_path  = out_dir / "transcript.txt"
    if json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8"))
    elif txt_path.exists():
        text = txt_path.read_text(encoding="utf-8")
        return {"full_text": text, "video_id": out_dir.name}
    return None


def call_claude(transcript_text: str, url: str, api_key: str, brand: str = "", notes: str = "") -> dict:
    try:
        import anthropic
    except ImportError:
        print("  [ERR] anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    prompt = ANALYSIS_PROMPT.format(
        transcript=transcript_text[:6000],
        url=url,
        brand=brand or "Unknown Brand",
        notes=notes or "None provided"
    )

    print(f"  [AI] Sending to Claude ({MODEL})...")
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
        print(f"  [WARN] JSON parse error: {e}")
        Path("debug.txt").write_text(raw, encoding='utf-8')
        return None


def format_report(analysis: dict, video_id: str) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("AMAZON VIDEO COMPETITIVE ANALYSIS REPORT")
    lines.append(f"Video ID: {video_id}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)
    lines.append(f"\nPRODUCT\n{analysis.get('product_summary', 'N/A')}")
    lines.append(f"\nTARGET AUDIENCE\n{analysis.get('target_audience', 'N/A')}")

    score = analysis.get("overall_score", {})
    lines.append(f"\nCOMPETITOR SCORE")
    lines.append(f"  Listing Strength : {score.get('listing_strength', '?')}/10")
    lines.append(f"  Hook Quality     : {score.get('hook_quality', '?')}/10")
    lines.append(f"  Keyword Density  : {score.get('keyword_density', '?')}/10")
    lines.append(f"  Notes            : {score.get('notes', '')}")

    lines.append(f"\nHOOKS USED")
    for h in analysis.get("hooks", []):
        lines.append(f"  [{h.get('type','').upper()}] \"{h.get('text','')}\"")

    lines.append(f"\nPAIN POINTS")
    for p in analysis.get("pain_points", []):
        lines.append(f"  - {p.get('pain','')}")
        lines.append(f"    Phrase: \"{p.get('phrase','')}\"")
        lines.append(f"    Opportunity: {p.get('opportunity','')}")

    lines.append(f"\nHIGH VALUE BUYER PHRASES")
    for b in analysis.get("buyer_language", []):
        if b.get("keyword_value") == "high":
            lines.append(f"  * \"{b.get('phrase','')}\" -> use in: {b.get('use_in','')}")

    lines.append(f"\nCOMPETITOR GAPS")
    for g in analysis.get("competitor_gaps", []):
        lines.append(f"  GAP: {g.get('gap','')}")
        lines.append(f"  ->  {g.get('your_opportunity','')}")

    lines.append(f"\nAD HOOKS")
    for i, h in enumerate(analysis.get("ad_hooks", []), 1):
        lines.append(f"  {i}. {h}")

    lines.append("\n" + "=" * 60)
    lines.append("LISTING COPY")
    lines.append("=" * 60)
    lines.append(f"\nTITLE OPTIONS")
    for i, t in enumerate(analysis.get("listing_title_suggestions", []), 1):
        lines.append(f"  {i}. {t}")
    lines.append(f"\nBULLET POINTS")
    for b in analysis.get("bullet_points", []):
        lines.append(f"  - {b}")
    lines.append(f"\nBACKEND KEYWORDS\n  {analysis.get('backend_keywords', '')}")

    return "\n".join(lines)


def analyze(out_dir: Path, api_key: str, brand: str = "", notes: str = "", product_url: str = "") -> dict:
    if not out_dir.exists():
        print(f"  [ERR] Folder not found: {out_dir}")
        return None

    print(f"\n{'='*55}")
    print(f"  Run dir : {out_dir}")
    print(f"  Brand   : {brand or 'Not specified'}")
    print(f"{'='*55}")

    transcript_data = load_transcript(out_dir)
    if not transcript_data:
        print(f"  [ERR] No transcript found. Run layer2 first.")
        return None

    full_text  = transcript_data.get("full_text", "")
    word_count = transcript_data.get("word_count", len(full_text.split()))
    print(f"  [FILE] Transcript loaded: {word_count} words")

    # Get URL from meta or use product_url arg
    url = product_url
    meta_path = out_dir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        url = url or meta.get("url", "")
    else:
        meta = {}

    analysis = call_claude(full_text, url, api_key, brand=brand, notes=notes)
    if not analysis:
        print(f"  [ERR] Analysis failed")
        return None

    analysis_path = out_dir / "analysis.json"
    analysis_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    print(f"  [OK] analysis.json saved")

    report = format_report(analysis, out_dir.name)
    report_path = out_dir / "analysis.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"  [OK] analysis.txt saved")

    bullets  = analysis.get("bullet_points", [])
    titles   = analysis.get("listing_title_suggestions", [])
    backend  = analysis.get("backend_keywords", "")
    listing_lines = ["LISTING COPY -- READY TO PASTE", "=" * 40, "", "TITLE OPTIONS:"]
    for i, t in enumerate(titles, 1):
        listing_lines.append(f"{i}. {t}")
    listing_lines.append("\nBULLET POINTS:")
    for b in bullets:
        listing_lines.append(f"- {b}")
    listing_lines.append(f"\nBACKEND KEYWORDS:\n{backend}")
    listing_path = out_dir / "listing_copy.txt"
    listing_path.write_text("\n".join(listing_lines), encoding="utf-8")
    print(f"  [OK] listing_copy.txt saved")

    meta["analysis"] = {
        "status": "complete",
        "analyzed_at": datetime.utcnow().isoformat() + "Z",
        "model": MODEL,
        "brand": brand,
        "files": {
            "analysis_json": str(analysis_path),
            "analysis_txt":  str(report_path),
            "listing_copy":  str(listing_path),
        }
    }
    meta["next_step"] = "layer4_export.py"
    meta_path.write_text(json.dumps(meta, indent=2), encoding='utf-8')

    print(f"\n  [OK] Layer 3 complete!")
    return analysis


def main():
    parser = argparse.ArgumentParser(description="Amazon Video Pipeline -- Layer 3")
    parser.add_argument("run_dir",     nargs="?", help="Full path to run directory (from proxy) or video_id")
    parser.add_argument("brand",       nargs="?", default="", help="Brand name")
    parser.add_argument("product_url", nargs="?", default="", help="Amazon product URL")
    parser.add_argument("notes",       nargs="?", default="", help="Additional notes")
    parser.add_argument("--api-key",   help="Anthropic API key")
    parser.add_argument("--batch",     action="store_true")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n  [ERR] No API key. Set ANTHROPIC_API_KEY or pass --api-key\n")
        sys.exit(1)

    if args.batch:
        if not DOWNLOADS_DIR.exists():
            print("  [ERR] No downloads folder.")
            return
        pending = [
            f for f in DOWNLOADS_DIR.iterdir()
            if f.is_dir() and (f / "transcript.json").exists() and not (f / "analysis.json").exists()
        ]
        if not pending:
            print("  [OK] Nothing pending.")
            return
        for i, folder in enumerate(pending, 1):
            print(f"\n  [{i}/{len(pending)}]")
            analyze(folder, api_key)
    elif args.run_dir:
        p = Path(args.run_dir)
        # Accept full absolute path from proxy OR bare video_id
        if not p.is_absolute():
            p = DOWNLOADS_DIR / args.run_dir
        analyze(p, api_key, brand=args.brand, notes=args.notes, product_url=args.product_url)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
