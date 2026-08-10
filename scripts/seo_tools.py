#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://darawsheh.github.io"
ARTICLES_DIR = ROOT / "articles"
OG_DIR = ROOT / "assets" / "og"
INDEXNOW_KEY = "a89b01a4784870dc7fd5375a3d755561"

JSONLD_RE = re.compile(
    r'(<script\s+type="application/ld\+json">\s*)(\{.*?\})(\s*</script>)',
    re.DOTALL,
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_if_changed(path: Path, content: str) -> None:
    previous = read(path) if path.exists() else None
    if previous != content:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def meta_content(text: str, *, name: str | None = None, prop: str | None = None) -> str | None:
    attr = "name" if name else "property"
    value = name or prop
    if not value:
        return None
    match = re.search(
        rf'<meta\s+{attr}="{re.escape(value)}"\s+content="([^"]*)"\s*/?>',
        text,
        re.IGNORECASE,
    )
    return html.unescape(match.group(1)) if match else None


def canonical_url(text: str) -> str | None:
    match = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"\s*/?>', text, re.IGNORECASE)
    return match.group(1) if match else None


def first_jsonld(text: str, accepted_types: set[str]) -> dict | None:
    for match in JSONLD_RE.finditer(text):
        try:
            data = json.loads(match.group(2))
        except json.JSONDecodeError:
            continue
        if data.get("@type") in accepted_types:
            return data
    return None


def article_info(path: Path) -> dict:
    text = read(path)
    slug = path.parent.name
    title_match = re.search(r'<h1>(.*?)</h1>', text, re.DOTALL | re.IGNORECASE)
    if not title_match:
        raise ValueError(f"Missing h1 in {path.relative_to(ROOT)}")
    title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
    description = meta_content(text, name="description") or ""
    published = meta_content(text, prop="article:published_time") or ""
    article_json = first_jsonld(text, {"TechArticle", "Article", "BlogPosting"}) or {}
    modified = str(article_json.get("dateModified") or published)
    url = f"{BASE_URL}/articles/{slug}/"
    image = f"{BASE_URL}/assets/og/{slug}.png"
    return {
        "path": path,
        "slug": slug,
        "title": title,
        "description": description,
        "published": published,
        "modified": modified,
        "url": url,
        "image": image,
    }


def add_common_head_links(text: str) -> str:
    if 'rel="icon"' not in text:
        anchor = '  <meta name="theme-color" content="#111827">\n'
        text = text.replace(anchor, anchor + '  <link rel="icon" href="/favicon.svg" type="image/svg+xml">\n', 1)
    if 'rel="alternate" type="application/rss+xml"' not in text:
        anchor = re.search(r'(^\s*<link\s+rel="canonical"[^>]+>\s*$)', text, re.MULTILINE)
        rss = '  <link rel="alternate" type="application/rss+xml" title="Islam Darawsheh Articles" href="/feed.xml">'
        if anchor:
            text = text[: anchor.end()] + "\n" + rss + text[anchor.end() :]
    if 'property="og:site_name"' not in text and 'property="og:type"' in text:
        text = text.replace(
            re.search(r'^\s*<meta\s+property="og:type"[^>]+>\s*$', text, re.MULTILINE).group(0),
            lambda m: m.group(0) + '\n  <meta property="og:site_name" content="Islam Darawsheh">',
            1,
        )
    return text


def replace_article_jsonld(text: str, info: dict) -> str:
    replaced = False

    def repl(match: re.Match[str]) -> str:
        nonlocal replaced
        try:
            data = json.loads(match.group(2))
        except json.JSONDecodeError:
            return match.group(0)
        if replaced or data.get("@type") not in {"TechArticle", "Article", "BlogPosting"}:
            return match.group(0)
        data["@type"] = "BlogPosting"
        data["image"] = [info["image"]]
        data["isPartOf"] = {
            "@type": "Blog",
            "@id": f"{BASE_URL}/articles/",
            "name": "Islam Darawsheh Articles",
        }
        replaced = True
        return match.group(1) + json.dumps(data, ensure_ascii=False, indent=2) + match.group(3)

    return JSONLD_RE.sub(repl, text)


def breadcrumb_jsonld(info: dict) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Articles", "item": f"{BASE_URL}/articles/"},
            {"@type": "ListItem", "position": 3, "name": info["title"], "item": info["url"]},
        ],
    }
    return '  <script type="application/ld+json">\n' + json.dumps(data, ensure_ascii=False, indent=2) + "\n  </script>\n"


def visible_breadcrumbs(info: dict) -> str:
    title = html.escape(info["title"])
    return (
        '      <nav class="breadcrumbs" aria-label="Breadcrumb">\n'
        '        <a href="/">Home</a><span aria-hidden="true">›</span>\n'
        '        <a href="/articles/">Articles</a><span aria-hidden="true">›</span>\n'
        f'        <span aria-current="page">{title}</span>\n'
        '      </nav>\n'
    )


def related_section(current: dict, all_infos: list[dict]) -> str:
    related = [item for item in all_infos if item["slug"] != current["slug"]][:3]
    if not related:
        return ""
    items = []
    for item in related:
        items.append(
            '          <li>'
            f'<a href="/articles/{html.escape(item["slug"])}/">{html.escape(item["title"])}</a>'
            f'<span>{html.escape(item["description"])}</span>'
            '</li>'
        )
    return (
        '      <section class="related-articles" aria-labelledby="related-articles-title">\n'
        '        <p class="eyebrow">Continue reading</p>\n'
        '        <h2 id="related-articles-title">Related articles</h2>\n'
        '        <ul>\n' + "\n".join(items) + '\n        </ul>\n'
        '      </section>\n\n'
    )


def upgrade_article(info: dict, all_infos: list[dict]) -> None:
    path = info["path"]
    text = add_common_head_links(read(path))

    if 'property="og:image"' not in text:
        og = (
            f'  <meta property="og:image" content="{info["image"]}">\n'
            '  <meta property="og:image:width" content="1200">\n'
            '  <meta property="og:image:height" content="675">\n'
            f'  <meta property="og:image:alt" content="{html.escape(info["title"], quote=True)}">\n'
        )
        match = re.search(r'(^\s*<meta\s+property="og:url"[^>]+>\s*$)', text, re.MULTILINE)
        if match:
            text = text[: match.end()] + "\n" + og.rstrip("\n") + text[match.end() :]

    text = text.replace('<meta name="twitter:card" content="summary">', '<meta name="twitter:card" content="summary_large_image">')
    if 'name="twitter:image"' not in text:
        twitter = (
            f'  <meta name="twitter:image" content="{info["image"]}">\n'
            f'  <meta name="twitter:image:alt" content="{html.escape(info["title"], quote=True)}">'
        )
        match = re.search(r'(^\s*<meta\s+name="twitter:description"[^>]+>\s*$)', text, re.MULTILINE)
        if match:
            text = text[: match.end()] + "\n" + twitter + text[match.end() :]

    text = replace_article_jsonld(text, info)

    if '"@type": "BreadcrumbList"' not in text:
        text = text.replace('</head>', breadcrumb_jsonld(info) + '</head>', 1)

    if 'class="breadcrumbs"' not in text:
        text = text.replace(
            '    <article class="article shell">\n',
            '    <article class="article shell">\n' + visible_breadcrumbs(info),
            1,
        )

    if 'class="related-articles"' not in text:
        related = related_section(info, all_infos)
        if related:
            if '      <section class="comments"' in text:
                text = text.replace('      <section class="comments"', related + '      <section class="comments"', 1)
            elif '      <footer class="article-footer">' in text:
                text = text.replace('      <footer class="article-footer">', related + '      <footer class="article-footer">', 1)

    write_if_changed(path, text)


def upgrade_home() -> None:
    path = ROOT / "index.html"
    text = add_common_head_links(read(path))
    if '"@type": "WebSite"' not in text:
        website = {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "name": "Islam Darawsheh",
            "alternateName": ["Islam Aldarawsheh", "darawsheh.github.io"],
            "url": f"{BASE_URL}/",
        }
        block = '  <script type="application/ld+json">\n' + json.dumps(website, ensure_ascii=False, indent=2) + "\n  </script>\n"
        text = text.replace('</head>', block + '</head>', 1)
    write_if_changed(path, text)


def upgrade_articles_index(infos: list[dict]) -> None:
    path = ARTICLES_DIR / "index.html"
    text = add_common_head_links(read(path))
    if '"@type": "Blog"' not in text:
        blog = {
            "@context": "https://schema.org",
            "@type": "Blog",
            "name": "Islam Darawsheh Articles",
            "url": f"{BASE_URL}/articles/",
            "author": {"@type": "Person", "name": "Islam Darawsheh", "url": f"{BASE_URL}/"},
            "blogPost": [
                {
                    "@type": "BlogPosting",
                    "headline": item["title"],
                    "url": item["url"],
                    "datePublished": item["published"],
                    "image": item["image"],
                }
                for item in infos
            ],
        }
        block = '  <script type="application/ld+json">\n' + json.dumps(blog, ensure_ascii=False, indent=2) + "\n  </script>\n"
        text = text.replace('</head>', block + '</head>', 1)
    write_if_changed(path, text)


def upgrade_article_css() -> None:
    path = ROOT / "assets" / "article.css"
    text = read(path)
    marker = "/* SEO navigation additions */"
    if marker in text:
        return
    addition = r'''

/* SEO navigation additions */
.breadcrumbs {
  display: flex;
  flex-wrap: wrap;
  gap: .45rem;
  align-items: center;
  margin: 0 0 1.5rem;
  font-size: .9rem;
}

.breadcrumbs a {
  text-decoration: none;
}

.related-articles {
  margin-top: 3rem;
  padding-top: 2rem;
  border-top: 1px solid currentColor;
}

.related-articles ul {
  list-style: none;
  margin: 1rem 0 0;
  padding: 0;
  display: grid;
  gap: 1rem;
}

.related-articles li {
  display: grid;
  gap: .3rem;
}

.related-articles li > a {
  font-weight: 700;
}

.related-articles li > span {
  opacity: .78;
}
'''
    write_if_changed(path, text.rstrip() + addition + "\n")


def generate_sitemap(infos: list[dict]) -> None:
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    urlset = ET.Element("{http://www.sitemaps.org/schemas/sitemap/0.9}urlset")
    entries = [
        (f"{BASE_URL}/", max((x["modified"] for x in infos), default="")),
        (f"{BASE_URL}/articles/", max((x["modified"] for x in infos), default="")),
    ] + [(x["url"], x["modified"]) for x in infos]
    for loc, lastmod in entries:
        url = ET.SubElement(urlset, "{http://www.sitemaps.org/schemas/sitemap/0.9}url")
        ET.SubElement(url, "{http://www.sitemaps.org/schemas/sitemap/0.9}loc").text = loc
        if lastmod:
            ET.SubElement(url, "{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod").text = lastmod
    tree = ET.ElementTree(urlset)
    ET.indent(tree, space="  ")
    output = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(urlset, encoding="unicode") + "\n"
    write_if_changed(ROOT / "sitemap.xml", output)


def generate_feed(infos: list[dict]) -> None:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Islam Darawsheh Articles"
    ET.SubElement(channel, "link").text = f"{BASE_URL}/articles/"
    ET.SubElement(channel, "description").text = "Practical articles on software architecture, enterprise .NET, secure systems, and maintainable software design."
    ET.SubElement(channel, "language").text = "en"
    for item in infos:
        node = ET.SubElement(channel, "item")
        ET.SubElement(node, "title").text = item["title"]
        ET.SubElement(node, "link").text = item["url"]
        ET.SubElement(node, "guid", {"isPermaLink": "true"}).text = item["url"]
        ET.SubElement(node, "description").text = item["description"]
        try:
            dt = datetime.fromisoformat(item["published"]).replace(tzinfo=timezone.utc)
            ET.SubElement(node, "pubDate").text = format_datetime(dt, usegmt=True)
        except ValueError:
            pass
    ET.indent(rss, space="  ")
    output = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode") + "\n"
    write_if_changed(ROOT / "feed.xml", output)


def upgrade() -> None:
    article_paths = sorted(ARTICLES_DIR.glob("*/index.html"))
    infos = [article_info(path) for path in article_paths]
    infos.sort(key=lambda x: (x["published"], x["slug"]), reverse=True)
    upgrade_home()
    upgrade_articles_index(infos)
    for info in infos:
        upgrade_article(info, infos)
    upgrade_article_css()
    # Re-read after upgrades so modified metadata reflects final JSON-LD.
    infos = [article_info(path) for path in article_paths]
    infos.sort(key=lambda x: (x["published"], x["slug"]), reverse=True)
    generate_sitemap(infos)
    generate_feed(infos)


def validate() -> list[str]:
    errors: list[str] = []
    article_paths = sorted(ARTICLES_DIR.glob("*/index.html"))
    infos = [article_info(path) for path in article_paths]
    sitemap_text = read(ROOT / "sitemap.xml") if (ROOT / "sitemap.xml").exists() else ""

    for common in [ROOT / "index.html", ARTICLES_DIR / "index.html", *article_paths]:
        text = read(common)
        rel = common.relative_to(ROOT)
        if 'rel="icon" href="/favicon.svg"' not in text:
            errors.append(f"{rel}: missing favicon link")
        if 'rel="alternate" type="application/rss+xml"' not in text:
            errors.append(f"{rel}: missing RSS link")
        robots = meta_content(text, name="robots")
        if robots and "noindex" in robots.lower():
            errors.append(f"{rel}: noindex is set")

    home = read(ROOT / "index.html")
    if '"@type": "WebSite"' not in home:
        errors.append("index.html: missing WebSite structured data")

    article_index = read(ARTICLES_DIR / "index.html")
    if '"@type": "Blog"' not in article_index:
        errors.append("articles/index.html: missing Blog structured data")

    for info in infos:
        path = info["path"]
        text = read(path)
        rel = path.relative_to(ROOT)
        if canonical_url(text) != info["url"]:
            errors.append(f"{rel}: canonical URL mismatch")
        if not info["description"]:
            errors.append(f"{rel}: missing meta description")
        if meta_content(text, name="robots") != "index,follow":
            errors.append(f"{rel}: robots should be index,follow")
        if '"@type": "BlogPosting"' not in text:
            errors.append(f"{rel}: missing BlogPosting structured data")
        if '"@type": "BreadcrumbList"' not in text:
            errors.append(f"{rel}: missing BreadcrumbList structured data")
        if 'property="og:image"' not in text:
            errors.append(f"{rel}: missing og:image")
        if 'name="twitter:image"' not in text:
            errors.append(f"{rel}: missing twitter:image")
        if 'class="related-articles"' not in text and len(infos) > 1:
            errors.append(f"{rel}: missing related article links")
        if info["url"] not in sitemap_text:
            errors.append(f"{rel}: missing from sitemap.xml")
        if not (OG_DIR / f'{info["slug"]}.png').exists():
            errors.append(f"{rel}: missing assets/og/{info['slug']}.png")

    if not (ROOT / "feed.xml").exists():
        errors.append("feed.xml: missing RSS feed")
    if not (ROOT / "favicon.svg").exists():
        errors.append("favicon.svg: missing favicon asset")
    key_path = ROOT / f"{INDEXNOW_KEY}.txt"
    if not key_path.exists() or read(key_path).strip() != INDEXNOW_KEY:
        errors.append("IndexNow verification key file missing or invalid")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply or validate static-site SEO conventions.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--apply", action="store_true", help="Apply idempotent SEO upgrades and regenerate indexes.")
    group.add_argument("--validate", action="store_true", help="Validate SEO/indexing requirements.")
    args = parser.parse_args()

    if args.apply:
        upgrade()

    errors = validate()
    if errors:
        print("SEO validation failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("SEO validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
