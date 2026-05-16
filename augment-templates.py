#!/usr/bin/env python3
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


MODEL = "google/gemini-2.5-flash"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_WORKERS = 5

SYSTEM_PROMPT = """你是一個 prompt template marker。我會給你一段 AI 生圖提示詞（中文），請你找出 3-6 個「使用者最可能想改」的關鍵詞（例如主題、產品、人物類型、城市、風格、顏色等），用 `{argument name="<簡短英文/中文鍵名>" default="<原文>"}` 包起來。

規則：
- 保留原始文字結構與標點，只是用 {argument} 把可變詞包起來
- name 用 2-8 字符的中文或英文 key（如「主題」「city」「product」）
- default 一定是原文中真實出現的詞
- 不要加新內容、不要改寫、不要中英翻譯
- 不要包過於通用的詞（如「請」「設計」「畫面」）
- 只回傳處理後的 prompt 文字，不要加任何說明、引號、markdown

範例輸入：「請幫我製作一張專業簡報封面，主題是新服務提案，使用簡潔排版、企業感配色與現代曲線設計。」
範例輸出：「請幫我製作一張專業簡報封面，主題是{argument name="主題" default="新服務提案"}，使用簡潔排版、{argument name="配色" default="企業感配色"}與{argument name="風格" default="現代曲線設計"}。」"""


def parse_args():
    parser = argparse.ArgumentParser(
        description="Augment prompts.json prompts with {argument} templates via OpenRouter Gemini Flash."
    )
    parser.add_argument(
        "--file",
        default="prompts.json",
        help="Path to prompts.json. Defaults to ./prompts.json.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print up to the first 5 augmented results without writing the file.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only call the model for the first N prompts that need augmentation.",
    )
    return parser.parse_args()


def should_skip(prompt):
    stripped = prompt.lstrip()
    if "{argument" in prompt or "【" in prompt:
        return "template"
    if stripped.startswith("{"):
        return "json"
    return None


def clean_model_text(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'", "「", "」"}:
        text = text[1:-1].strip()
    return text


def call_openrouter(prompt, api_key):
    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "gpt-image-2-prompts-template-augmenter",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        },
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    return clean_model_text(content)


def load_json(path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main():
    args = parse_args()
    if load_dotenv:
        load_dotenv()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY is not set.", file=sys.stderr)
        return 1

    path = Path(args.file)
    data = load_json(path)
    prompts = data.get("prompts", [])

    stats = {
        "total": len(prompts),
        "template_skip": 0,
        "json_skip": 0,
        "augmented": 0,
        "failed": 0,
    }

    targets = []
    for index, entry in enumerate(prompts):
        prompt = entry.get("prompt", "")
        skip_reason = should_skip(prompt)
        if skip_reason == "template":
            stats["template_skip"] += 1
            continue
        if skip_reason == "json":
            stats["json_skip"] += 1
            continue
        if args.limit is not None and len(targets) >= args.limit:
            continue
        targets.append((index, entry.get("id", f"index-{index}"), prompt))

    dry_run_outputs = []
    completed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(call_openrouter, prompt, api_key): (index, prompt_id, prompt)
            for index, prompt_id, prompt in targets
        }
        for future in as_completed(futures):
            index, prompt_id, original = futures[future]
            try:
                augmented_prompt = future.result()
                if "{argument" not in augmented_prompt:
                    raise ValueError("model response did not contain {argument")
                stats["augmented"] += 1
                if args.dry_run:
                    if len(dry_run_outputs) < 5:
                        dry_run_outputs.append((prompt_id, original, augmented_prompt))
                else:
                    prompts[index]["prompt"] = augmented_prompt
            except Exception as exc:
                stats["failed"] += 1
                print(f"ERROR {prompt_id}: {exc}", file=sys.stderr)
            finally:
                completed += 1
                if completed % 5 == 0:
                    print(f"progress: processed {completed}/{len(targets)} model calls")

    if args.dry_run:
        print("\nDRY RUN results (first 5):")
        for prompt_id, original, augmented_prompt in dry_run_outputs:
            print(f"\n[{prompt_id}]")
            print("before:", original)
            print("after: ", augmented_prompt)
    else:
        write_json(path, data)

    print("\nStats:")
    print(f"total: {stats['total']}")
    print(f"template skip: {stats['template_skip']}")
    print(f"JSON skip: {stats['json_skip']}")
    print(f"newly marked: {stats['augmented']}")
    print(f"failed: {stats['failed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
