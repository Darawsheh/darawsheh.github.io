#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://darawsheh.github.io"
INDEXNOW_KEY = "a89b01a4784870dc7fd5375a3d755561"
JSONLD_RE = re.compile(r'<script\s+type="application/ld\+json">\s*(\{.*?\})\s*</script>', re.DOTALL)


def has_jsonld_type(text: str, expected: str) -> bool:
    for match in JSONLD_RE.finditer(text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if data.get("@type") == expected:
            return True
    return False


def meta(text: str, key: str, attr: str = "name") -> str | None:
    match = re.search(rf'<meta\s+{attr}="{re.escape(key)}"\s+content="([^"]*)"', text, re.IGNORECASE)
    return match.group(1) if match else None


def canonical(text: str) -> str | None:
    match = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', text, re.IGNORECASE)
    return match.group(1) if match else None


def main() -> int:
    errors: list[str] = []
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8") if (ROOT / "sitemap.xml").exists() else ""

    common_pages = [ROOT / "index.html", ROOT / "articles" / "index.html"]
    article_pages = sorted((ROOT / "articles").glob("*/index.html"))

    for page in [*common_pages, *article_pages]:
        text = page.read_text(encoding="utf-8")
        rel = page.relative_to(ROOT)
        if 'rel="icon" href="/favicon.svg"' not in text:
            errors.append(f"{rel}: missing favicon link")
        if 'rel="alternate" type="application/rss+xml"' not in text:
            errors.append(f"{rel}: missing RSS discovery link")
        robots = meta(text, "robots")
        if robots and "noindex" in robots.lower():
            errors.append(f"{rel}: noindex is set")

    home = (ROOT / "index.html").read_text(encoding="utf-8")
    if not has_jsonld_type(home, "WebSite"):
        errors.append("index.html: missing WebSite structured data")

    article_index = (ROOT / "articles" / "index.html").read_text(encoding="utf-8")
    if not has_jsonld_type(article_index, "Blog"):
        errors.append("articles/index.html: missing Blog structured data")

    for page in article_pages:
        text = page.read_text(encoding="utf-8")
        slug = page.parent.name
        rel = page.relative_to(ROOT)
        expected_url = f"{BASE_URL}/articles/{slug}/"
        if canonical(text) != expected_url:
            errors.append(f"{rel}: canonical URL mismatch")
        if not meta(text, "description"):
            errors.append(f"{rel}: missing meta description")
        if meta(text, "robots") != "index,follow":
            errors.append(f"{rel}: robots should be index,follow")
        if not has_jsonld_type(text, "BlogPosting"):
            errors.append(f"{rel}: missing BlogPosting structured data")
        if not has_jsonld_type(text, "BreadcrumbList"):
            errors.append(f"{rel}: missing BreadcrumbList structured data")
        if 'property="og:image"' not in text:
            errors.append(f"{rel}: missing og:image")
        if 'name="twitter:image"' not in text or 'name="twitter:card" content="summary_large_image"' not in text:
            errors.append(f"{rel}: incomplete Twitter/X large-image metadata")
        if 'class="breadcrumbs"' not in text:
            errors.append(f"{rel}: missing visible breadcrumbs")
        if len(article_pages) > 1 and 'class="related-articles"' not in text:
            errors.append(f"{rel}: missing related article links")
        if expected_url not in sitemap:
            errors.append(f"{rel}: missing from sitemap.xml")
        if not (ROOT / "assets" / "og" / f"{slug}.png").exists():
            errors.append(f"assets/og/{slug}.png: missing social/search image")

    if not (ROOT / "feed.xml").exists():
        errors.append("feed.xml: missing RSS feed")
    if not (ROOT / "favicon.svg").exists():
        errors.append("favicon.svg: missing favicon")
    key_file = ROOT / f"{INDEXNOW_KEY}.txt"
    if not key_file.exists() or key_file.read_text(encoding="utf-8").strip() != INDEXNOW_KEY:
        errors.append("IndexNow verification key is missing or invalid")

    if errors:
        print("SEO validation failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print(f"SEO validation passed for {len(article_pages)} article(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
