#!/usr/bin/env python3
"""Static site generator for the Cosmos, AI & Philosophy dialogue blog."""

import html
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).parent.resolve()


def parse_frontmatter(text: str):
  meta = {}
  body = text
  if text.startswith('---\n'):
    parts = text.split('\n---\n', 1)
    if len(parts) == 2:
      raw_meta, body = parts[0][4:], parts[1]
      for line in raw_meta.splitlines():
        if ':' in line:
          k, v = line.split(':', 1)
          meta[k.strip()] = v.strip()
  return meta, body.strip()


def format_inline(text: str) -> str:
  # Protect inline math $...$
  math_tokens = []

  def save_math(m):
    math_tokens.append(m.group(0))
    return f'@@MATH_{len(math_tokens)-1}@@'

  text = re.sub(r'\$\$[\s\S]+?\$\$|\$[^$\n]+?\$', save_math, text)
  # Bold, italic, inline code, links
  text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
  text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
  text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
  text = re.sub(
      r'\[([^\]]+)\]\(([^)]+)\)',
      r'<a href="\2" target="_blank" rel="noopener">\1</a>',
      text,
  )

  for idx, token in enumerate(math_tokens):
    text = text.replace(f'@@MATH_{idx}@@', token)
  return text


def render_paragraphs(chunk: str) -> str:
  lines = chunk.strip().splitlines()
  out = []
  buf = []
  in_list = False

  def flush_buf():
    if buf:
      joined = ' '.join(buf).strip()
      if joined.startswith('$$') and joined.endswith('$$'):
        out.append(f'<div class="math-block">{joined}</div>')
      else:
        out.append(f'<p>{format_inline(joined)}</p>')
      buf.clear()

  for line in lines:
    stripped = line.strip()
    if not stripped:
      if in_list:
        out.append('</ul>')
        in_list = False
      flush_buf()
      continue
    if stripped.startswith('## '):
      if in_list:
        out.append('</ul>')
        in_list = False
      flush_buf()
      out.append(f'<h2>{format_inline(stripped[3:])}</h2>')
    elif stripped.startswith('### '):
      if in_list:
        out.append('</ul>')
        in_list = False
      flush_buf()
      out.append(f'<h3>{format_inline(stripped[4:])}</h3>')
    elif stripped.startswith('- ') or stripped.startswith('* '):
      flush_buf()
      if not in_list:
        out.append('<ul>')
        in_list = True
      out.append(f'<li>{format_inline(stripped[2:])}</li>')
    elif stripped.startswith('> '):
      if in_list:
        out.append('</ul>')
        in_list = False
      flush_buf()
      out.append(f'<blockquote><p>{format_inline(stripped[2:])}</p></blockquote>')
    else:
      buf.append(stripped)

  if in_list:
    out.append('</ul>')
  flush_buf()
  return '\n'.join(out)


def render_markdown(md_body: str, author_name: str):
  """Returns (site_html, portable_html_for_vocus_medium)."""
  pattern = re.compile(r':::(\w+)\n([\s\S]*?)\n:::', re.MULTILINE)
  pos = 0
  site_parts = []
  portable_parts = []

  for match in pattern.finditer(md_body):
    before = md_body[pos : match.start()]
    if before.strip():
      rendered_before = render_paragraphs(before)
      site_parts.append(rendered_before)
      portable_parts.append(rendered_before)

    role = match.group(1).lower()
    if role == 'html':
      site_parts.append(match.group(2))
      pos = match.end()
      continue
    content_html = render_paragraphs(match.group(2))
    if role == 'human':
      label = f'{html.escape(author_name)} 提問・思辨'
      site_parts.append(
          f'<section class="dialogue-turn dialogue-human">'
          f'<div class="speaker-label">✦ {label}</div>'
          f'<div class="dialogue-content">{content_html}</div>'
          f'</section>'
      )
      portable_parts.append(
          f'<blockquote><p><strong>🙋‍♂️ {html.escape(author_name)} 提問：</strong></p>'
          f'{content_html}</blockquote>'
      )
    else:
      label = 'AI 回應・推演'
      site_parts.append(
          f'<section class="dialogue-turn dialogue-ai">'
          f'<div class="speaker-label">◈ {label}</div>'
          f'<div class="dialogue-content">{content_html}</div>'
          f'</section>'
      )
      portable_parts.append(
          f'<blockquote><p><strong>🤖 AI 回應：</strong></p>{content_html}</blockquote>'
      )
    pos = match.end()

  tail = md_body[pos:]
  if tail.strip():
    rendered_tail = render_paragraphs(tail)
    site_parts.append(rendered_tail)
    portable_parts.append(rendered_tail)

  return '\n'.join(site_parts), '\n'.join(portable_parts)


def head_html(
    title: str,
    description: str,
    css_path: str,
    canonical_url: str = '',
    og_image: str = '',
) -> str:
  canon_tag = (
      f'<link rel="canonical" href="{html.escape(canonical_url)}">'
      if canonical_url
      else ''
  )
  og_img_tag = (
      f'<meta property="og:image" content="{html.escape(og_image)}">'
      if og_image
      else ''
  )
  return f"""<!DOCTYPE html>
<html lang="zh-Hant" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description)}">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{html.escape(description)}">
  <meta property="og:type" content="article">
  {og_img_tag}
  {canon_tag}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Iansui&family=LXGW+WenKai+TC:wght@400;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
  <link rel="stylesheet" href="{css_path}">
  <script>
    (function() {{
      const saved = localStorage.getItem('cosmos_theme') || 'dark';
      document.documentElement.setAttribute('data-theme', saved);
    }})();
  </script>
</head>"""


def header_nav(site_cfg: dict, home_href: str, is_home: bool = False) -> str:
  if is_home:
    return ''
  return f"""<header class="site-header">
  <div class="header-inner">
    <a href="{home_href}" class="icon-btn" id="nav-home-link">← 返回所有文章</a>
    <div class="header-actions">
      <button type="button" class="icon-btn" id="theme-toggle-btn" aria-label="切換深淺色主題">
        <span id="theme-toggle-label">切換日／夜視角</span>
      </button>
    </div>
  </div>
</header>"""


def theme_script() -> str:
  return """<script>
  const themeBtn = document.getElementById('theme-toggle-btn');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('cosmos_theme', next);
    });
  }
</script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.body, {delimiters: [{left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}]});"></script>"""


def build_site():
  site_cfg = json.loads((ROOT / 'site.json').read_text(encoding='utf-8'))
  posts_dir = ROOT / 'posts'
  posts = []

  for md_file in sorted(posts_dir.glob('*.md'), reverse=True):
    slug = md_file.stem
    raw = md_file.read_text(encoding='utf-8')
    meta, body = parse_frontmatter(raw)
    title = meta.get('title', slug)
    date = meta.get('date', '')
    category = meta.get('category', '生命科學')
    categories = [c.strip() for c in category.split(',') if c.strip()]
    tags = [t.strip() for t in meta.get('tags', '').split(',') if t.strip()]
    summary = meta.get('summary', '')
    image = meta.get('image', '').strip().lstrip('/')

    site_html, portable_html = render_markdown(body, site_cfg['author'])
    post_url = f"{site_cfg['base_url'].rstrip('/')}/posts/{slug}/"
    og_image_url = (
        f"{site_cfg['base_url'].rstrip('/')}/{image}" if image else ''
    )

    post_data = {
        'slug': slug,
        'title': title,
        'date': date,
        'category': category,
        'categories': categories,
        'tags': tags,
        'summary': summary,
        'image': image,
        'site_html': site_html,
        'portable_html': portable_html,
        'url': post_url,
    }
    posts.append(post_data)

    # Write individual post page: posts/<slug>/index.html
    out_dir = posts_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    tags_html = ''.join(f'<span class="tag-badge">#{html.escape(t)}</span>' for t in tags)
    hero_img_html = (
        f'<figure class="article-hero-figure">'
        f'<img src="../../{html.escape(image)}" alt="{html.escape(title)}" class="article-hero-img" loading="eager">'
        f'</figure>'
        if image
        else ''
    )

    cats_meta_html = '<span>·</span>'.join(
        f'<span class="post-category">{html.escape(c)}</span>' for c in categories
    )
    article_page = f"""{head_html(f"{title} | {site_cfg['title']}", summary, "../../assets/index.css", post_url, og_image_url)}
<body>
  {header_nav(site_cfg, "../../index.html")}
  <main class="main-container">
    <article>
      <header class="article-header">
        <div class="post-meta">
          {cats_meta_html}
          <span>·</span>
          <time datetime="{html.escape(date)}">{html.escape(date)}</time>
          <span>·</span>
          <span>作者：{html.escape(site_cfg['author'])}</span>
          <span>·</span>
          <span>觀看人次：<span id="article-view-count">—</span></span>
        </div>
        <h1 class="article-title">{html.escape(title)}</h1>
        <p class="article-subtitle">{html.escape(summary)}</p>
      </header>
      {hero_img_html}
      <div class="article-body" id="article-content">
        {site_html}
      </div>

      <footer style="margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid var(--border-subtle); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
        <div class="post-tags">{tags_html}</div>
        <a href="../../index.html" class="icon-btn" id="back-to-home-btn">← 返回所有文章</a>
      </footer>
    </article>
  </main>
  <footer class="site-footer">
    <p>© {html.escape(site_cfg['author'])} · {html.escape(site_cfg['title'])} · Hosted on GitHub Pages</p>
  </footer>
  {theme_script()}
  <script>
    (async function() {{
      const el = document.getElementById('article-view-count');
      if (!el) return;
      try {{
        const res = await fetch('https://events.vercount.one/api/v2/log', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ url: '{html.escape(post_url)}' }})
        }});
        if (res.ok) {{
          const json = await res.json();
          const pv = json?.data?.page_pv ?? json?.page_pv;
          if (pv !== undefined) el.textContent = Number(pv).toLocaleString();
        }}
      }} catch (e) {{}}
    }})();
  </script>
</body>
</html>"""
    (out_dir / 'index.html').write_text(article_page, encoding='utf-8')

  # Build Home Page (index.html)
  cat_buttons = []
  for idx, cat in enumerate(site_cfg.get('categories', ['全部'])):
    active_cls = 'active' if idx == 0 else ''
    cat_buttons.append(
        f'<button type="button" class="cat-tab {active_cls}" data-cat="{html.escape(cat)}" id="cat-btn-{idx}">{html.escape(cat)}</button>'
    )

  cards_html = []
  for p in posts:
    tags_badges = ''.join(f'<span class="tag-badge">#{html.escape(t)}</span>' for t in p['tags'])
    cover_html = (
        f'<div class="post-card-cover">'
        f'<img src="{html.escape(p["image"])}" alt="{html.escape(p["title"])}" class="post-card-img" loading="lazy">'
        f'</div>'
        if p.get('image')
        else ''
    )
    card_cats_html = '<span>·</span>'.join(
        f'<span class="post-category">{html.escape(c)}</span>'
        for c in p['categories']
    )
    cards_html.append(f"""<article class="post-card" data-category="{html.escape(','.join(p['categories']))}" data-tags="{html.escape(','.join(p['tags']))}" data-search="{html.escape((p['title'] + ' ' + p['summary'] + ' ' + ' '.join(p['tags'])).lower())}">
      <div class="post-meta">
        {card_cats_html}
        <span>·</span>
        <time datetime="{html.escape(p['date'])}">{html.escape(p['date'])}</time>
        <span>·</span>
        <span>觀看人次：<span class="card-view-count" data-post-url="{html.escape(p['url'])}">—</span></span>
      </div>
      <a href="posts/{p['slug']}/index.html" id="post-link-{p['slug']}">
        {cover_html}
        <h2 class="post-card-title">{html.escape(p['title'])}</h2>
        <p class="post-summary">{html.escape(p['summary'])}</p>
      </a>
      <div class="post-tags">{tags_badges}</div>
    </article>""")

  hero_en = (
      f'<span class="hero-title-en">{html.escape(site_cfg.get("title_en", ""))}</span>'
      if site_cfg.get('title_en')
      else ''
  )
  index_page = f"""{head_html(f"{site_cfg['title']} {site_cfg.get('title_en', '')} — {site_cfg['subtitle']}", site_cfg['subtitle'], "assets/index.css", site_cfg['base_url'])}
<body>
  {header_nav(site_cfg, "index.html", is_home=True)}
  <section class="hero-section">
    <span class="hero-eyebrow">COSMOS · ARTIFICIAL INTELLIGENCE · LIFE SCIENCES</span>
    <h1 class="hero-title">{html.escape(site_cfg['title'])}{hero_en}</h1>
    <p class="hero-subtitle">{html.escape(site_cfg['subtitle'])}</p>
  </section>

  <section class="filter-bar" aria-label="文章分類與搜尋">
    <div class="category-tabs" id="category-tabs">
      {''.join(cat_buttons)}
    </div>
    <input type="search" class="search-input" id="post-search-input" placeholder="搜尋議題、關鍵字..." aria-label="搜尋文章">
  </section>

  <main class="main-container" id="posts-list">
    {''.join(cards_html)}
  </main>

  <footer class="site-footer">
    <p>© {html.escape(site_cfg['author'])} · {html.escape(site_cfg['title'])} · 公開免費發表，歡迎引用與延伸思辨 · <button type="button" id="theme-toggle-btn" style="background:none;border:none;color:var(--text-muted);text-decoration:underline;cursor:pointer;font-family:inherit;font-size:inherit;">切換日／夜視角</button></p>
  </footer>
  {theme_script()}
  <script>
    const tabs = document.querySelectorAll('.cat-tab');
    const searchInput = document.getElementById('post-search-input');
    const cards = document.querySelectorAll('.post-card');
    let activeCat = '全部';

    function filterPosts() {{
      const q = (searchInput.value || '').trim().toLowerCase();
      cards.forEach(card => {{
        const cats = (card.dataset.category || '').split(',');
        const tags = (card.dataset.tags || '').split(',');
        const catMatch = activeCat === '全部' || cats.includes(activeCat) || tags.includes(activeCat);
        const searchMatch = !q || card.dataset.search.includes(q);
        card.style.display = (catMatch && searchMatch) ? '' : 'none';
      }});
    }}

    tabs.forEach(tab => {{
      tab.addEventListener('click', () => {{
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        activeCat = tab.dataset.cat;
        filterPosts();
      }});
    }});

    if (searchInput) {{
      searchInput.addEventListener('input', filterPosts);
    }}

    document.querySelectorAll('.card-view-count').forEach(async (el) => {{
      const targetUrl = el.dataset.postUrl;
      if (!targetUrl) return;
      try {{
        const res = await fetch('https://events.vercount.one/api/v2/log?url=' + encodeURIComponent(targetUrl));
        if (res.ok) {{
          const json = await res.json();
          const pv = json?.data?.page_pv ?? json?.page_pv;
          if (pv !== undefined) el.textContent = Number(pv).toLocaleString();
        }}
      }} catch (e) {{}}
    }});
  </script>
</body>
</html>"""
  (ROOT / 'index.html').write_text(index_page, encoding='utf-8')
  print(f'Successfully built {len(posts)} post(s) -> index.html')


if __name__ == '__main__':
  build_site()
