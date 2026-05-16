#!/usr/bin/env python3
"""Generate preview images for prompts via gpt-image-2.

Run with the shared openai venv:
  ~/.config/openai/venv/bin/python generate-previews.py [--all|--featured]

Strategy:
- Pick 30 representative prompts across all 11 categories (--featured default)
  OR generate for all 176 (--all).
- For each: call gpt-image-2 low quality 1024x1024
- Resize → WebP 600x600 (~60KB)
- Save to previews/<id>.webp
- Skip if file already exists (incremental safe re-run)
"""
import argparse
import base64
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, BadRequestError, APIError, RateLimitError
from PIL import Image

ROOT = Path(__file__).parent
load_dotenv(Path.home() / ".config" / "openai" / ".env")
client = OpenAI()

PREVIEWS_DIR = ROOT / "previews"
PREVIEWS_DIR.mkdir(exist_ok=True)

# 30 featured IDs spread across categories + viral hits
FEATURED_IDS = {
    # avatar (3)
    "p001", "p003", "p005",
    # social (3)
    "p021", "p024", "p030",
    # product-marketing (3)
    "p056", "p060", "p068",
    # ecommerce (3)
    "p076", "p081", "p092",
    # youtube-thumbnail (3)
    "p096", "p101", "p110",
    # comic-storyboard (3)
    "p115", "p123", "p133",
    # infographic (3)
    "p138", "p145", "p150",
    # lifestyle (3) — bnext, include 編織小人
    "p159", "p162", "p166",
    # photo-transform (3) — Y2K, 衝破, 極道
    "p169", "p173", "p177",  # adjust as needed
    # creative-meme (2)
    "p180", "p182",
    # featured (1)
    "p183",
}


def clean_prompt(raw: str) -> str:
    """Process raw prompt for gpt-image-2:
    - If JSON-as-prompt: extract `description`/`subject`/`instruction` or fall back to title
    - Replace {argument name="X" default="Y"} → Y
    """
    s = raw.strip()
    # Replace template variables: {argument name="X" default="Y"} → Y
    s = re.sub(r'\{argument\s+name="[^"]+"\s+default="([^"]+)"\}', r'\1', s)

    # If looks like JSON, try to flatten into a brief description
    if s.startswith("{"):
        try:
            data = json.loads(s)
            # Try common keys for a generation-friendly summary
            parts = []
            for key in ("type", "description", "instruction", "subject"):
                v = data.get(key)
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, dict):
                    desc = v.get("description") if isinstance(v.get("description"), str) else None
                    if desc:
                        parts.append(desc)
            if "style" in data and isinstance(data["style"], (str, dict)):
                style_s = data["style"] if isinstance(data["style"], str) else json.dumps(data["style"], ensure_ascii=False)
                parts.append(f"風格: {style_s[:200]}")
            if parts:
                s = " · ".join(parts)[:1800]
        except json.JSONDecodeError:
            pass

    # Truncate to safe length (gpt-image-2 ~4000 char limit, leave buffer)
    return s[:3500]


def generate_one(item: dict) -> tuple[str, str | None, str | None]:
    """Returns (id, output_path or None, error or None)."""
    pid = item["id"]
    out_path = PREVIEWS_DIR / f"{pid}.webp"
    if out_path.exists():
        return (pid, str(out_path), "skipped (exists)")

    prompt_text = clean_prompt(item["prompt"])
    if not prompt_text or len(prompt_text) < 10:
        # Fall back to title + description if prompt is too thin after cleaning
        prompt_text = f"{item['title']}. {item.get('description', '')}"

    try:
        resp = client.images.generate(
            model="gpt-image-2",
            prompt=prompt_text,
            quality="low",
            size="1024x1024",
            n=1,
        )
        b64 = resp.data[0].b64_json
        png_bytes = base64.b64decode(b64)
        img = Image.open(BytesIO(png_bytes)).convert("RGB")
        img = img.resize((600, 600), Image.LANCZOS)
        img.save(out_path, "WEBP", quality=78, method=6)
        return (pid, str(out_path), None)
    except (BadRequestError, APIError, RateLimitError) as e:
        return (pid, None, f"{type(e).__name__}: {str(e)[:200]}")
    except Exception as e:
        return (pid, None, f"{type(e).__name__}: {str(e)[:200]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="Generate for all 176 (default: 30 featured)")
    ap.add_argument("--workers", type=int, default=4, help="Parallel workers (default 4)")
    ap.add_argument("--limit", type=int, help="Only process first N items (debug)")
    args = ap.parse_args()

    data = json.loads((ROOT / "prompts.json").read_text())
    prompts = data["prompts"]

    if args.all:
        targets = prompts
    else:
        targets = [p for p in prompts if p["id"] in FEATURED_IDS]
        if not targets:
            # Fallback: pick first 3 of each category
            from collections import defaultdict
            by_cat = defaultdict(list)
            for p in prompts:
                by_cat[p["category_en"]].append(p)
            targets = []
            for cat, items in by_cat.items():
                targets.extend(items[:3])
            targets = targets[:30]

    if args.limit:
        targets = targets[:args.limit]

    print(f"Generating {len(targets)} previews with {args.workers} workers...")
    print(f"Estimated cost: ${len(targets) * 0.02:.2f} USD")
    print()

    t0 = time.time()
    done = 0
    errors = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(generate_one, item): item for item in targets}
        for fut in as_completed(futures):
            item = futures[fut]
            pid, path, err = fut.result()
            done += 1
            if err and "skipped" not in err:
                errors.append((pid, item['title'], err))
                print(f"  [{done}/{len(targets)}] ✗ {pid} {item['title'][:30]}  ERROR: {err[:80]}")
            elif err == "skipped (exists)":
                print(f"  [{done}/{len(targets)}] ↻ {pid} {item['title'][:30]}  (exists)")
            else:
                size_kb = Path(path).stat().st_size / 1024
                print(f"  [{done}/{len(targets)}] ✓ {pid} {item['title'][:30]}  ({size_kb:.0f} KB)")

    elapsed = time.time() - t0
    print(f"\nFinished in {elapsed:.1f}s. {len(errors)} errors.")
    if errors:
        print("\nErrors:")
        for pid, title, err in errors:
            print(f"  {pid} {title[:40]}: {err[:120]}")


if __name__ == "__main__":
    main()
