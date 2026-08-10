#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://darawsheh.github.io"
PROFILE_URL = f"{BASE_URL}/islam-darawsheh/"
PROFILE_PERSON_ID = f"{PROFILE_URL}#person"
INDEXNOW_KEY = "a89b01a4784870dc7fd5375a3d755561"


def has_jsonld_type(text: str, expected: str) -> bool:
    """Check for a JSON-LD @type without trying to parse nested script objects."""
    return bool(
        re.search(
            rf'<script\s+type="application/ld\+json">.*?"@type"\s*:\s*"{re.escape(expected)}".*?</script>',
            text,
            re.DOTALL | re.IGNORECASE,
        )
    )


def meta(text: str, key: str, attr: str = "name") -> str | None:
    match = re.search(rf'<meta\s+{attr}="{re.escape(key)}"\s+content="([^"]*)"', text, re.IGNORECASE)
    return match.group(1) if match else None


def canonical(text: str) -> str | None:
    match = re.search(r'<link\s+rel="canonical"\s+href="([^"]+)"', text, re.IGNORECASE)
    return match.group(1) if match else None


def main() -> int:
    errors: list[str] = []
    sitemap_path = ROOT / "sitemap.xml"
    sitemap = sitemap_path.read_text(encoding="utf-8") if sitemap_path.exists() else ""
    script = (ROOT / "assets" / "script.js").read_text(encoding="utf-8")
    article_css = (ROOT / "assets" / "article.css").read_text(encoding="utf-8")

    home_path = ROOT / "index.html"
    profile_path = ROOT / "islam-darawsheh" / "index.html"
    article_index_path = ROOT / "articles" / "index.html"
    article_pages = sorted((ROOT / "articles").glob("*/index.html"))

    home = home_path.read_text(encoding="utf-8")
    if not has_jsonld_type(home, "WebSite"):
        errors.append("index.html: missing WebSite structured data")
    if 'rel="icon" href="/favicon.svg"' not in home:
        errors.append("index.html: missing favicon link")
    if 'rel="alternate" type="application/rss+xml"' not in home:
        errors.append("index.html: missing RSS discovery link")
    if meta(home, "robots") != "index,follow":
        errors.append("index.html: robots should be index,follow")
    if PROFILE_URL not in home or PROFILE_PERSON_ID not in home:
        errors.append("index.html: missing canonical author-profile entity references")
    if "<h1>Islam Darawsheh</h1>" not in home:
        errors.append("index.html: primary H1 should identify Islam Darawsheh")

    if not profile_path.exists():
        errors.append("islam-darawsheh/index.html: missing author profile page")
    else:
        profile = profile_path.read_text(encoding="utf-8")
        if canonical(profile) != PROFILE_URL:
            errors.append("islam-darawsheh/index.html: canonical URL mismatch")
        if meta(profile, "robots") != "index,follow":
            errors.append("islam-darawsheh/index.html: robots should be index,follow")
        if not has_jsonld_type(profile, "ProfilePage"):
            errors.append("islam-darawsheh/index.html: missing ProfilePage structured data")
        if PROFILE_PERSON_ID not in profile:
            errors.append("islam-darawsheh/index.html: missing stable Person @id")
        if "https://github.com/Darawsheh" not in profile or "https://www.linkedin.com/in/darawsheh/" not in profile:
            errors.append("islam-darawsheh/index.html: missing public sameAs profiles")
        if PROFILE_URL not in sitemap:
            errors.append("islam-darawsheh/index.html: missing from sitemap.xml")

    article_index = article_index_path.read_text(encoding="utf-8")
    if not has_jsonld_type(article_index, "Blog"):
        errors.append("articles/index.html: missing Blog structured data")
    if 'rel="alternate" type="application/rss+xml"' not in article_index:
        errors.append("articles/index.html: missing RSS discovery link")
    if PROFILE_URL not in article_index or PROFILE_PERSON_ID not in article_index:
        errors.append("articles/index.html: blog author is not linked to the profile entity")

    enhancer_tokens = [
        "BlogPosting",
        "BreadcrumbList",
        "og:image",
        "twitter:image",
        "summary_large_image",
        "related-articles",
        "breadcrumbs",
    ]
    for token in enhancer_tokens:
        if token not in script:
            errors.append(f"assets/script.js: missing rendered SEO behavior for {token}")

    if ".breadcrumbs" not in article_css or ".related-articles" not in article_css:
        errors.append("assets/article.css: missing breadcrumb/related article styling")

    allowed_source_article_types = ("TechArticle", "Article", "BlogPosting")
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
        if not any(has_jsonld_type(text, item_type) for item_type in allowed_source_article_types):
            errors.append(f"{rel}: missing source article structured data")
        if expected_url not in sitemap:
            errors.append(f"{rel}: missing from sitemap.xml")
        if slug not in script:
            errors.append(f"assets/script.js: article registry missing {slug}")
        if not (ROOT / "assets" / "og" / f"{slug}.svg").exists():
            errors.append(f"assets/og/{slug}.svg: missing article search image")

    if not sitemap_path.exists():
        errors.append("sitemap.xml: missing sitemap")
    if not (ROOT / "feed.xml").exists():
        errors.append("feed.xml: missing RSS feed")
    if not (ROOT / "favicon.svg").exists():
        errors.append("favicon.svg: missing favicon")

    robots_path = ROOT / "robots.txt"
    if not robots_path.exists():
        errors.append("robots.txt: missing")
    else:
        robots = robots_path.read_text(encoding="utf-8")
        if "Sitemap: https://darawsheh.github.io/sitemap.xml" not in robots:
            errors.append("robots.txt: sitemap directive missing")

    key_file = ROOT / f"{INDEXNOW_KEY}.txt"
    if not key_file.exists() or key_file.read_text(encoding="utf-8").strip() != INDEXNOW_KEY:
        errors.append("IndexNow verification key is missing or invalid")

    if errors:
        print("SEO validation failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print(f"SEO validation passed for profile plus {len(article_pages)} article(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
