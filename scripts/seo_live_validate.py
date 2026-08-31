#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from seo_validate import (
    BASE_URL,
    INDEXNOW_KEY,
    ROOT,
    Page,
    PageParser,
    parse_feed,
    parse_sitemap,
)

USER_AGENT = "Darawsheh-SEO-Live-Validator/2.0"


def fetch(url: str) -> tuple[str, str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        content_type = response.headers.get_content_type()
        charset = response.headers.get_content_charset() or "utf-8"
        return response.geturl(), content_type, response.read().decode(charset)


def parse_html(url: str, text: str) -> Page:
    page = Page(Path(url))
    parser = PageParser(page)
    parser.feed(text)
    parser.close()
    return page


def validate_page(url: str, root: Path) -> list[str]:
    errors: list[str] = []
    try:
        final_url, content_type, body = fetch(url)
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
        return [f"{url}: request failed: {exc}"]
    if final_url != url:
        errors.append(f"{url}: redirected to {final_url}")
    if content_type != "text/html":
        return errors + [f"{url}: expected text/html, received {content_type}"]
    page = parse_html(url, body)
    if page.canonical_values() != [url]:
        errors.append(f"{url}: deployed canonical mismatch")
    if page.value("robots") != "index,follow":
        errors.append(f"{url}: deployed robots mismatch")
    local_path = root / (
        "index.html"
        if url == f"{BASE_URL}/"
        else url.removeprefix(f"{BASE_URL}/") + "index.html"
    )
    local_page = parse_html(url, local_path.read_text(encoding="utf-8"))
    if page.title != local_page.title:
        errors.append(f"{url}: deployed title is stale or different")
    return errors


def validate_once(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    local_sitemap = parse_sitemap(root, errors)
    local_feed = parse_feed(root, errors)
    with ThreadPoolExecutor(max_workers=6) as executor:
        for page_errors in executor.map(
            lambda url: validate_page(url, root), sorted(local_sitemap)
        ):
            errors.extend(page_errors)

    try:
        _, _, deployed_sitemap = fetch(f"{BASE_URL}/sitemap.xml")
        deployed_root = ET.fromstring(deployed_sitemap)
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        deployed_urls = {
            (node.text or "").strip()
            for node in deployed_root.findall("s:url/s:loc", namespace)
        }
        if deployed_urls != set(local_sitemap):
            errors.append("deployed sitemap.xml does not match the repository")
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, ET.ParseError) as exc:
        errors.append(f"deployed sitemap.xml failed validation: {exc}")

    try:
        _, _, deployed_feed = fetch(f"{BASE_URL}/feed.xml")
        deployed_root = ET.fromstring(deployed_feed)
        deployed_links = {
            (node.text or "").strip()
            for node in deployed_root.findall("channel/item/link")
        }
        if deployed_links != set(local_feed):
            errors.append("deployed feed.xml does not match the repository")
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, ET.ParseError) as exc:
        errors.append(f"deployed feed.xml failed validation: {exc}")

    try:
        _, content_type, body = fetch(f"{BASE_URL}/robots.txt")
        if content_type != "text/plain" or f"Sitemap: {BASE_URL}/sitemap.xml" not in body:
            errors.append("deployed robots.txt is missing the canonical sitemap directive")
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
        errors.append(f"deployed robots.txt failed validation: {exc}")

    try:
        _, _, body = fetch(f"{BASE_URL}/{INDEXNOW_KEY}.txt")
        if body.strip() != INDEXNOW_KEY:
            errors.append("deployed IndexNow key is invalid")
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
        errors.append(f"deployed IndexNow key failed validation: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, default=8)
    parser.add_argument("--delay", type=int, default=15)
    args = parser.parse_args()

    errors: list[str] = []
    for attempt in range(1, args.attempts + 1):
        errors = validate_once()
        if not errors:
            print("Live SEO validation passed for all deployed sitemap URLs.")
            return 0
        print(
            f"Live validation attempt {attempt}/{args.attempts} found "
            f"{len(errors)} issue(s)."
        )
        if attempt < args.attempts:
            time.sleep(args.delay)

    print("Live SEO validation failed after deployment retries:")
    for error in errors:
        print(f" - {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
