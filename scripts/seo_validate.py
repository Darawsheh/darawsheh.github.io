#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://darawsheh.github.io"
PROFILE_URL = f"{BASE_URL}/islam-darawsheh/"
PROFILE_PERSON_ID = f"{PROFILE_URL}#person"
INDEXNOW_KEY = "a89b01a4784870dc7fd5375a3d755561"
SITEMAP_NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@dataclass
class Page:
    path: Path
    lang: str = ""
    title_parts: list[str] = field(default_factory=list)
    metas: dict[tuple[str, str], list[str]] = field(default_factory=lambda: defaultdict(list))
    links: list[dict[str, str]] = field(default_factory=list)
    references: list[tuple[str, str]] = field(default_factory=list)
    headings: list[list[str]] = field(default_factory=list)
    jsonld_raw: list[str] = field(default_factory=list)
    _in_title: bool = False
    _in_h1: bool = False
    _in_jsonld: bool = False
    _jsonld_parts: list[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())

    @property
    def h1s(self) -> list[str]:
        return [" ".join("".join(parts).split()) for parts in self.headings]

    def values(self, key: str, attr: str = "name") -> list[str]:
        return self.metas.get((attr.lower(), key.lower()), [])

    def value(self, key: str, attr: str = "name") -> str | None:
        values = self.values(key, attr)
        return values[0] if values else None

    def canonical_values(self) -> list[str]:
        return [
            link.get("href", "")
            for link in self.links
            if "canonical" in link.get("rel", "").lower().split()
        ]


class PageParser(HTMLParser):
    def __init__(self, page: Page) -> None:
        super().__init__(convert_charrefs=True)
        self.page = page

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        if tag == "html":
            self.page.lang = data.get("lang", "")
        elif tag == "title":
            self.page._in_title = True
        elif tag == "h1":
            self.page._in_h1 = True
            self.page.headings.append([])
        elif tag == "meta":
            for attr in ("name", "property", "http-equiv"):
                if data.get(attr):
                    self.page.metas[(attr, data[attr].lower())].append(
                        data.get("content", "").strip()
                    )
        elif tag == "link":
            self.page.links.append(data)
            if data.get("href"):
                self.page.references.append(("href", data["href"]))
        elif tag in {"a", "img", "script", "iframe", "source"}:
            attribute = "href" if tag == "a" else "src"
            if data.get(attribute):
                self.page.references.append((attribute, data[attribute]))

        if tag == "script" and data.get("type", "").lower() == "application/ld+json":
            self.page._in_jsonld = True
            self.page._jsonld_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self.page._in_title = False
        elif tag == "h1":
            self.page._in_h1 = False
        elif tag == "script" and self.page._in_jsonld:
            self.page.jsonld_raw.append("".join(self.page._jsonld_parts).strip())
            self.page._in_jsonld = False

    def handle_data(self, data: str) -> None:
        if self.page._in_title:
            self.page.title_parts.append(data)
        if self.page._in_h1 and self.page.headings:
            self.page.headings[-1].append(data)
        if self.page._in_jsonld:
            self.page._jsonld_parts.append(data)


def parse_page(path: Path) -> tuple[Page, list[str]]:
    page = Page(path)
    parser = PageParser(page)
    errors: list[str] = []
    try:
        parser.feed(path.read_text(encoding="utf-8"))
        parser.close()
    except Exception as exc:
        errors.append(f"{path}: invalid HTML: {exc}")
    return page, errors


def page_url(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if rel == "index.html":
        return f"{BASE_URL}/"
    if rel.endswith("/index.html"):
        return f"{BASE_URL}/{rel[:-10]}"
    return f"{BASE_URL}/{rel}"


def local_target(url: str, source_url: str, root: Path) -> Path | None:
    if not url or url.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    parsed = urlparse(urljoin(source_url, url))
    if parsed.netloc != urlparse(BASE_URL).netloc:
        return None
    decoded = unquote(parsed.path)
    if ".." in Path(decoded).parts:
        return root / "__invalid_parent_reference__"
    target = root / decoded.lstrip("/")
    if not decoded.lstrip("/") or decoded.endswith("/"):
        target /= "index.html"
    elif not target.exists() and (target / "index.html").exists():
        target /= "index.html"
    return target


def iter_json_objects(value: object):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from iter_json_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_json_objects(nested)


def jsonld_objects(page: Page, rel: str, errors: list[str]) -> list[dict]:
    objects: list[dict] = []
    for index, raw in enumerate(page.jsonld_raw, start=1):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{rel}: invalid JSON-LD block {index}: {exc.msg}")
            continue
        objects.extend(iter_json_objects(value))
    return objects


def has_type(obj: dict, expected: str) -> bool:
    value = obj.get("@type")
    return expected in value if isinstance(value, list) else value == expected


def valid_date(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        date.fromisoformat(value[:10])
        if "T" in value:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def parse_sitemap(root: Path, errors: list[str]) -> dict[str, str]:
    path = root / "sitemap.xml"
    if not path.exists():
        errors.append("sitemap.xml: missing")
        return {}
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        errors.append(f"sitemap.xml: invalid XML: {exc}")
        return {}
    entries: dict[str, str] = {}
    for node in tree.findall("s:url", SITEMAP_NS):
        loc = (node.findtext("s:loc", default="", namespaces=SITEMAP_NS) or "").strip()
        modified = (
            node.findtext("s:lastmod", default="", namespaces=SITEMAP_NS) or ""
        ).strip()
        if not loc:
            errors.append("sitemap.xml: URL entry missing loc")
            continue
        if loc in entries:
            errors.append(f"sitemap.xml: duplicate URL {loc}")
        if not loc.startswith(f"{BASE_URL}/"):
            errors.append(f"sitemap.xml: URL must use the canonical host: {loc}")
        if not valid_date(modified):
            errors.append(f"sitemap.xml: invalid or missing lastmod for {loc}")
        entries[loc] = modified
    return entries


def parse_registry(root: Path, errors: list[str]) -> dict[str, dict[str, str]]:
    path = root / "assets" / "script.js"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    match = re.search(r"const\s+articles\s*=\s*\[(.*?)\];", text, re.DOTALL)
    if not match:
        errors.append("assets/script.js: article registry not found")
        return {}
    registry: dict[str, dict[str, str]] = {}
    for block in re.findall(r"\{(.*?)\}", match.group(1), re.DOTALL):
        parsed = {
            item.group(1): item.group(3).strip()
            for item in re.finditer(
                r"(slug|title|description|published)\s*:\s*(['\"])(.*?)\2",
                block,
                re.DOTALL,
            )
        }
        slug = parsed.get("slug", "")
        if not slug:
            errors.append("assets/script.js: registry entry missing slug")
            continue
        if slug in registry:
            errors.append(f"assets/script.js: duplicate registry slug {slug}")
        for required in ("title", "description", "published"):
            if not parsed.get(required):
                errors.append(f"assets/script.js: {slug} missing {required}")
        if parsed.get("published") and not valid_date(parsed["published"]):
            errors.append(f"assets/script.js: {slug} has invalid published date")
        registry[slug] = parsed
    return registry


def parse_feed(root: Path, errors: list[str]) -> dict[str, dict[str, str]]:
    path = root / "feed.xml"
    if not path.exists():
        errors.append("feed.xml: missing")
        return {}
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        errors.append(f"feed.xml: invalid XML: {exc}")
        return {}
    channel = tree.find("channel")
    if channel is None:
        errors.append("feed.xml: missing RSS channel")
        return {}
    if (channel.findtext("link") or "").strip() != f"{BASE_URL}/articles/":
        errors.append("feed.xml: channel link mismatch")
    result: dict[str, dict[str, str]] = {}
    dates: list[datetime] = []
    for item in channel.findall("item"):
        entry = {
            key: (item.findtext(key) or "").strip()
            for key in ("title", "link", "guid", "pubDate", "description")
        }
        link = entry["link"]
        if not link:
            errors.append("feed.xml: item missing link")
            continue
        if link in result:
            errors.append(f"feed.xml: duplicate item {link}")
        for required in ("title", "guid", "pubDate", "description"):
            if not entry[required]:
                errors.append(f"feed.xml: {link} missing {required}")
        if entry["guid"] != link:
            errors.append(f"feed.xml: guid must match link for {link}")
        try:
            dates.append(parsedate_to_datetime(entry["pubDate"]))
        except (TypeError, ValueError):
            errors.append(f"feed.xml: invalid pubDate for {link}")
        result[link] = entry
    if dates != sorted(dates, reverse=True):
        errors.append("feed.xml: items must be ordered newest first")
    return result


def validate_site(root: Path = ROOT) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    pages: dict[Path, Page] = {}
    for path in sorted(root.rglob("*.html")):
        page, parse_errors = parse_page(path)
        pages[path] = page
        errors.extend(error.replace(str(root) + "/", "") for error in parse_errors)

    indexable_paths = {
        root / "index.html",
        root / "islam-darawsheh" / "index.html",
        root / "articles" / "index.html",
        *sorted((root / "articles").glob("*/index.html")),
    }
    missing_pages = [path for path in indexable_paths if not path.exists()]
    errors.extend(f"{path.relative_to(root)}: missing page" for path in missing_pages)
    indexable_paths -= set(missing_pages)

    sitemap = parse_sitemap(root, errors)
    expected_urls = {page_url(path, root) for path in indexable_paths}
    for url in sorted(expected_urls - set(sitemap)):
        errors.append(f"sitemap.xml: missing {url}")
    for url in sorted(set(sitemap) - expected_urls):
        errors.append(f"sitemap.xml: unexpected or non-indexable URL {url}")

    registry = parse_registry(root, errors)
    feed = parse_feed(root, errors)
    article_paths = sorted((root / "articles").glob("*/index.html"))
    article_slugs = {path.parent.name for path in article_paths}
    article_urls = {page_url(path, root) for path in article_paths}
    for label, expected, actual in (
        ("article registry", article_slugs, set(registry)),
        ("RSS feed", article_urls, set(feed)),
    ):
        for value in sorted(expected - actual):
            errors.append(f"{label}: missing {value}")
        for value in sorted(actual - expected):
            errors.append(f"{label}: unexpected {value}")

    canonical_owners: dict[str, list[str]] = defaultdict(list)
    titles: dict[str, list[str]] = defaultdict(list)
    descriptions: dict[str, list[str]] = defaultdict(list)
    for path in sorted(indexable_paths):
        page = pages[path]
        rel = path.relative_to(root).as_posix()
        expected_url = page_url(path, root)
        canonicals = page.canonical_values()
        if canonicals != [expected_url]:
            errors.append(f"{rel}: expected one canonical URL equal to {expected_url}")
        else:
            canonical_owners[canonicals[0]].append(rel)
        if page.lang.lower() != "en":
            errors.append(f"{rel}: html lang must be en")
        if not page.title:
            errors.append(f"{rel}: missing title")
        else:
            titles[page.title.casefold()].append(rel)
            if len(page.title) > 90:
                warnings.append(f"{rel}: title is long ({len(page.title)} characters)")
        description = page.value("description") or ""
        if not description:
            errors.append(f"{rel}: missing meta description")
        else:
            descriptions[description.casefold()].append(rel)
            if not 50 <= len(description) <= 180:
                warnings.append(
                    f"{rel}: description length is {len(description)} characters"
                )
        if len(page.values("description")) != 1:
            errors.append(f"{rel}: expected exactly one meta description")
        if page.value("robots") != "index,follow":
            errors.append(f"{rel}: robots must be index,follow")
        if len(page.h1s) != 1 or not page.h1s[0]:
            errors.append(f"{rel}: expected exactly one non-empty h1")
        for key, attr in (
            ("og:title", "property"),
            ("og:description", "property"),
            ("og:url", "property"),
            ("twitter:card", "name"),
        ):
            if len(page.values(key, attr)) != 1 or not page.value(key, attr):
                errors.append(f"{rel}: expected exactly one {key}")
        if page.value("og:url", "property") != expected_url:
            errors.append(f"{rel}: og:url mismatch")
        if not jsonld_objects(page, rel, errors):
            errors.append(f"{rel}: missing valid JSON-LD")
        for attr, reference in page.references:
            target = local_target(reference, expected_url, root)
            if target is not None and not target.exists():
                errors.append(f"{rel}: broken internal {attr} {reference}")

    for value, owners in canonical_owners.items():
        if len(owners) > 1:
            errors.append(f"duplicate canonical {value}: {', '.join(owners)}")
    for label, values in (("title", titles), ("meta description", descriptions)):
        for owners in values.values():
            if len(owners) > 1:
                errors.append(f"duplicate {label}: {', '.join(owners)}")

    for path in article_paths:
        page = pages[path]
        rel = path.relative_to(root).as_posix()
        slug = path.parent.name
        expected_url = page_url(path, root)
        expected_image = f"{BASE_URL}/assets/og/{slug}.svg"
        objects = jsonld_objects(page, rel, [])
        articles = [obj for obj in objects if has_type(obj, "BlogPosting")]
        if len(articles) != 1:
            errors.append(f"{rel}: expected exactly one BlogPosting JSON-LD object")
            continue
        article = articles[0]
        for key in (
            "headline",
            "description",
            "datePublished",
            "dateModified",
            "author",
            "publisher",
            "mainEntityOfPage",
            "image",
            "url",
        ):
            if not article.get(key):
                errors.append(f"{rel}: BlogPosting missing {key}")
        if article.get("url") != expected_url or article.get("mainEntityOfPage") != expected_url:
            errors.append(f"{rel}: BlogPosting URL mismatch")
        if not valid_date(article.get("datePublished")) or not valid_date(
            article.get("dateModified")
        ):
            errors.append(f"{rel}: invalid BlogPosting publication dates")
        author = article.get("author")
        if not isinstance(author, dict) or author.get("@id") != PROFILE_PERSON_ID:
            errors.append(
                f"{rel}: BlogPosting author must reference the stable Person @id"
            )
        images = article.get("image")
        images = images if isinstance(images, list) else [images]
        if expected_image not in images:
            errors.append(f"{rel}: BlogPosting image mismatch")
        for key, attr, expected in (
            ("og:image", "property", expected_image),
            ("twitter:image", "name", expected_image),
            ("twitter:card", "name", "summary_large_image"),
        ):
            if page.value(key, attr) != expected:
                errors.append(f"{rel}: {key} mismatch")
        image_path = root / "assets" / "og" / f"{slug}.svg"
        if not image_path.exists():
            errors.append(f"assets/og/{slug}.svg: missing")
        else:
            try:
                svg = ET.parse(image_path).getroot()
                width, height = svg.get("width"), svg.get("height")
                if (width, height) != ("1200", "630"):
                    warnings.append(
                        f"assets/og/{slug}.svg: social image is {width}x{height}; "
                        "prefer 1200x630 PNG/JPG"
                    )
            except ET.ParseError as exc:
                errors.append(f"assets/og/{slug}.svg: invalid SVG: {exc}")
        registry_entry = registry.get(slug, {})
        if registry_entry:
            if registry_entry.get("title") != page.value("og:title", "property"):
                errors.append(f"assets/script.js: {slug} title differs from og:title")
            if registry_entry.get("published") != str(
                article.get("datePublished", "")
            )[:10]:
                errors.append(
                    f"assets/script.js: {slug} published date differs from JSON-LD"
                )
        feed_entry = feed.get(expected_url, {})
        if feed_entry:
            if feed_entry.get("title") != page.value("og:title", "property"):
                errors.append(f"feed.xml: {slug} title differs from og:title")
            try:
                feed_date = parsedate_to_datetime(feed_entry["pubDate"]).date().isoformat()
                if feed_date != str(article.get("datePublished", ""))[:10]:
                    errors.append(f"feed.xml: {slug} pubDate differs from JSON-LD")
            except (KeyError, TypeError, ValueError):
                pass

    home_path = root / "index.html"
    home_objects = (
        jsonld_objects(pages[home_path], "index.html", errors)
        if home_path in pages
        else []
    )
    if not any(has_type(obj, "WebSite") for obj in home_objects):
        errors.append("index.html: missing WebSite JSON-LD")
    profile_path = root / "islam-darawsheh" / "index.html"
    profile_objects = (
        jsonld_objects(pages[profile_path], "islam-darawsheh/index.html", errors)
        if profile_path in pages
        else []
    )
    if not any(has_type(obj, "ProfilePage") for obj in profile_objects):
        errors.append("islam-darawsheh/index.html: missing ProfilePage JSON-LD")
    article_index_path = root / "articles" / "index.html"
    article_index_objects = (
        jsonld_objects(pages[article_index_path], "articles/index.html", errors)
        if article_index_path in pages
        else []
    )
    if not any(has_type(obj, "Blog") for obj in article_index_objects):
        errors.append("articles/index.html: missing Blog JSON-LD")

    robots = root / "robots.txt"
    if not robots.exists() or f"Sitemap: {BASE_URL}/sitemap.xml" not in robots.read_text(
        encoding="utf-8"
    ):
        errors.append("robots.txt: canonical sitemap directive missing")
    key_file = root / f"{INDEXNOW_KEY}.txt"
    if (
        not key_file.exists()
        or key_file.read_text(encoding="utf-8").strip() != INDEXNOW_KEY
    ):
        errors.append("IndexNow verification key is missing or invalid")
    return sorted(set(errors)), sorted(set(warnings))


def main() -> int:
    errors, warnings = validate_site()
    for warning in warnings:
        print(f"SEO warning: {warning}")
    if errors:
        print("SEO validation failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1
    article_count = len(list((ROOT / "articles").glob("*/index.html")))
    print(
        f"Strict SEO validation passed for {len(list(ROOT.rglob('*.html')))} "
        f"HTML page(s) and {article_count} article(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
