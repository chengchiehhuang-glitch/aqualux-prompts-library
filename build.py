#!/usr/bin/env python3
"""Build static index.html from prompts.json (Muji / Kenya Hara aesthetic)."""
import json, html, re
from pathlib import Path

ROOT = Path(__file__).parent
DATA = json.loads((ROOT / 'prompts.json').read_text())

# Chinese numerals for chapter markers (1-indexed)
HAN_NUM = ['壹', '貳', '參', '肆', '伍', '陸', '柒', '捌', '玖', '拾', '拾壹', '拾貳']


def esc(s: str) -> str:
    return html.escape(s or '', quote=True)


def render_prompt_card(p: dict, idx: int) -> str:
    tags_html = ''
    if p.get('tags'):
        chips = ''.join(f'<span class="tag">{esc(t)}</span>' for t in p['tags'][:5])
        tags_html = f'<div class="tags">{chips}</div>'

    desc_html = f'<p class="desc">{esc(p["description"])}</p>' if p.get('description') else ''
    src_label = '· bnext' if 'bnext' in (p.get('source', '') or '').lower() else ''

    # Preview image (only if generated)
    pid = p.get('id', '')
    preview_html = ''
    if pid and (ROOT / 'previews' / f'{pid}.webp').exists():
        preview_html = f'''<div class="preview">
      <img src="previews/{pid}.webp" alt="{esc(p['title'])} · 示範圖" loading="lazy" width="600" height="600">
      <div class="preview-caption">示範圖 · GPT Image 2 生成</div>
    </div>'''

    # Encode prompt for data-attribute (will be read by JS, not displayed via HTML)
    prompt_for_attr = html.escape(p['prompt'], quote=True)

    return f'''<article class="entry" data-cat="{esc(p['category_en'])}" data-search="{esc((p['title'] + ' ' + (p.get('description', '') or '') + ' ' + ' '.join(p.get('tags', []))).lower())}">
  <div class="num">{idx:03d}</div>
  <div class="body">
    <h3 class="entry-title">{esc(p['title'])} <span class="src">{src_label}</span></h3>
    {desc_html}
    {preview_html}
    <pre class="prompt-body">{esc(p['prompt'])}</pre>
    {tags_html}
    <div class="actions">
      <button class="copy-btn" data-prompt="{prompt_for_attr}" aria-label="複製提示詞">複製 ↗</button>
    </div>
  </div>
</article>'''


def render_chapter(cat: dict, prompts: list, han_idx: int) -> str:
    cards = '\n'.join(render_prompt_card(p, i + 1) for i, p in enumerate(prompts))
    han = HAN_NUM[han_idx] if han_idx < len(HAN_NUM) else str(han_idx)
    return f'''<section class="chapter" id="cat-{cat['id']}" data-cat="{cat['id']}">
  <header class="chapter-head">
    <div class="chapter-han">{han}</div>
    <div class="chapter-title">
      <div class="zh">{esc(cat['zh'])}</div>
      <div class="en">{esc(cat['en'])} <span class="count">· {cat['count']}</span></div>
    </div>
  </header>
  <div class="entries">
    {cards}
  </div>
</section>'''


def render_nav(categories: list) -> str:
    items = [f'<a href="#top" class="nav-link active" data-cat="all">全部 · {DATA["meta"]["totalPrompts"]}</a>']
    for cat in categories:
        items.append(f'<a href="#cat-{cat["id"]}" class="nav-link" data-cat="{cat["id"]}">{esc(cat["zh"])} <span class="nav-count">{cat["count"]}</span></a>')
    return '\n'.join(items)


# Group prompts by category in display order
prompts_by_cat = {}
for p in DATA['prompts']:
    prompts_by_cat.setdefault(p['category_en'], []).append(p)

chapters_html = '\n'.join(
    render_chapter(cat, prompts_by_cat.get(cat['id'], []), i)
    for i, cat in enumerate(DATA['categories'])
)

# Read template and substitute
TEMPLATE = (ROOT / 'template.html').read_text()
out = (TEMPLATE
       .replace('{{TOTAL}}', str(DATA['meta']['totalPrompts']))
       .replace('{{NAV}}', render_nav(DATA['categories']))
       .replace('{{CHAPTERS}}', chapters_html)
       .replace('{{UPDATED}}', DATA['meta']['lastUpdated'])
       )

(ROOT / 'index.html').write_text(out)
print(f"Built index.html ({(ROOT / 'index.html').stat().st_size / 1024:.1f} KB)")
print(f"  Chapters: {len(DATA['categories'])}")
print(f"  Prompts: {DATA['meta']['totalPrompts']}")
