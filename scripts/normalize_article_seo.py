#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://darawsheh.github.io"
PROFILE_URL = f"{BASE_URL}/islam-darawsheh/"
PROFILE_PERSON_ID = f"{PROFILE_URL}#person"
GITHUB_URL = "https://github.com/Darawsheh"
LINKEDIN_URL = "https://www.linkedin.com/in/darawsheh/"


def extract_meta(text: str, property_name: str) -> str:
    match = re.search(
        rf'<meta\s+property="{re.escape(property_name)}"\s+content="([^"]+)"',
        text,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"missing {property_name}")
    return html.unescape(match.group(1))


def insert_after(text: str, marker_pattern: str, addition: str) -> str:
    match = re.search(marker_pattern, text, re.IGNORECASE)
    if not match:
        raise ValueError(f"unable to find insertion marker: {marker_pattern}")
    return text[: match.end()] + addition + text[match.end() :]


def normalize_jsonld(text: str, canonical_url: str, image_url: str) -> str:
    match = re.search(
        r'<script\s+type="application/ld\+json">\s*(\{.*?\})\s*</script>',
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        raise ValueError("missing article JSON-LD")

    data = json.loads(match.group(1))
    data["@type"] = "BlogPosting"
    data["url"] = canonical_url
    data["image"] = [image_url]
    data["author"] = {
        "@id": PROFILE_PERSON_ID,
        "@type": "Person",
        "name": "Islam Darawsheh",
        "url": PROFILE_URL,
        "sameAs": [GITHUB_URL, LINKEDIN_URL],
    }
    data["isPartOf"] = {
        "@type": "Blog",
        "@id": f"{BASE_URL}/articles/",
        "name": "Islam Darawsheh Articles",
    }

    rendered = json.dumps(data, indent=2, ensure_ascii=False)
    rendered = "\n".join(f"  {line}" for line in rendered.splitlines())
    replacement = f'<script type="application/ld+json">\n{rendered}\n  </script>'
    return text[: match.start()] + replacement + text[match.end() :]


def normalize_article(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    slug = path.parent.name
    canonical_url = f"{BASE_URL}/articles/{slug}/"
    image_url = f"{BASE_URL}/assets/og/{slug}.svg"
    title = extract_meta(text, "og:title")

    image_path = ROOT / "assets" / "og" / f"{slug}.svg"
    if not image_path.exists():
        raise ValueError(f"missing social image: {image_path.relative_to(ROOT)}")

    if 'rel="icon" href="/favicon.svg"' not in text:
        text = insert_after(
            text,
            r'<meta\s+name="theme-color"\s+content="[^"]+">',
            '\n  <link rel="icon" href="/favicon.svg" type="image/svg+xml">',
        )

    if 'rel="alternate" type="application/rss+xml"' not in text:
        text = insert_after(
            text,
            rf'<link\s+rel="canonical"\s+href="{re.escape(canonical_url)}">',
            '\n  <link rel="alternate" type="application/rss+xml" title="Islam Darawsheh Articles" href="/feed.xml">',
        )

    if '<meta property="og:site_name" content="Islam Darawsheh">' not in text:
        text = insert_after(
            text,
            r'<meta\s+property="og:type"\s+content="article">',
            '\n  <meta property="og:site_name" content="Islam Darawsheh">',
        )

    if '<meta property="og:image"' not in text:
        text = insert_after(
            text,
            rf'<meta\s+property="og:url"\s+content="{re.escape(canonical_url)}">',
            f'\n  <meta property="og:image" content="{image_url}">\n  <meta property="og:image:alt" content="{html.escape(title, quote=True)}">',
        )

    text = re.sub(
        r'<meta\s+name="twitter:card"\s+content="[^"]+">',
        '<meta name="twitter:card" content="summary_large_image">',
        text,
        count=1,
        flags=re.IGNORECASE,
    )

    if '<meta name="twitter:image"' not in text:
        description_match = re.search(
            r'<meta\s+name="twitter:description"\s+content="[^"]+">',
            text,
            re.IGNORECASE,
        )
        if not description_match:
            raise ValueError("missing twitter:description")
        addition = (
            f'\n  <meta name="twitter:image" content="{image_url}">'
            f'\n  <meta name="twitter:image:alt" content="{html.escape(title, quote=True)}">'
        )
        text = text[: description_match.end()] + addition + text[description_match.end() :]

    text = normalize_jsonld(text, canonical_url, image_url)
    text = text.replace(
        '<a href="/#expertise">Expertise</a>',
        '<a href="/islam-darawsheh/">Profile</a>',
    )

    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if any article is not already normalized.",
    )
    args = parser.parse_args()

    article_pages = sorted((ROOT / "articles").glob("*/index.html"))
    changed: list[Path] = []

    for path in article_pages:
        try:
            normalized = normalize_article(path)
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"{path.relative_to(ROOT)}: {exc}", file=sys.stderr)
            return 1

        current = path.read_text(encoding="utf-8")
        if normalized != current:
            changed.append(path)
            if not args.check:
                path.write_text(normalized, encoding="utf-8")

    if args.check and changed:
        print("Article SEO normalization required:", file=sys.stderr)
        for path in changed:
            print(f" - {path.relative_to(ROOT)}", file=sys.stderr)
        return 1

    if changed:
        print(f"Normalized SEO metadata for {len(changed)} article(s).")
    else:
        print(f"Article SEO metadata is normalized for {len(article_pages)} article(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
