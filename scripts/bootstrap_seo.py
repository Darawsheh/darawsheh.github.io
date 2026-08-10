#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import seo_tools as tools

ROOT = Path(__file__).resolve().parents[1]
BRANCH_WORKFLOW = ROOT / ".github" / "workflows" / "bootstrap-seo.yml"
LEGACY_TOOL = ROOT / "scripts" / "seo_tools.py"
SELF = Path(__file__).resolve()


def fixed_common_head_links(text: str) -> str:
    if 'rel="icon"' not in text:
        anchor = '  <meta name="theme-color" content="#111827">\n'
        text = text.replace(anchor, anchor + '  <link rel="icon" href="/favicon.svg" type="image/svg+xml">\n', 1)

    if 'rel="alternate" type="application/rss+xml"' not in text:
        match = re.search(r'(^\s*<link\s+rel="canonical"[^>]+>\s*$)', text, re.MULTILINE)
        if match:
            rss = '  <link rel="alternate" type="application/rss+xml" title="Islam Darawsheh Articles" href="/feed.xml">'
            text = text[: match.end()] + "\n" + rss + text[match.end() :]

    if 'property="og:site_name"' not in text and 'property="og:type"' in text:
        match = re.search(r'(^\s*<meta\s+property="og:type"[^>]+>\s*$)', text, re.MULTILINE)
        if match:
            site_name = '  <meta property="og:site_name" content="Islam Darawsheh">'
            text = text[: match.end()] + "\n" + site_name + text[match.end() :]

    return text


def load_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def fit_wrapped_text(draw: ImageDraw.ImageDraw, title: str, max_width: int, max_lines: int = 4):
    for size in range(58, 35, -2):
        font = load_font(size, bold=True)
        words = title.split()
        lines: list[str] = []
        current = ""
        for word in words:
            trial = word if not current else f"{current} {word}"
            width = draw.textbbox((0, 0), trial, font=font)[2]
            if width <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        if len(lines) <= max_lines:
            return lines, font
    return textwrap.wrap(title, width=34)[:max_lines], load_font(36, bold=True)


def generate_og_image(info: dict) -> None:
    out = ROOT / "assets" / "og" / f"{info['slug']}.png"
    out.parent.mkdir(parents=True, exist_ok=True)

    width, height = 1200, 675
    image = Image.new("RGB", (width, height), "#0b1220")
    draw = ImageDraw.Draw(image)

    # Subtle architecture-grid treatment; deliberately simple and readable.
    for x in range(0, width, 80):
        draw.line((x, 0, x, height), fill="#172033", width=1)
    for y in range(0, height, 80):
        draw.line((0, y, width, y), fill="#172033", width=1)

    draw.rounded_rectangle((70, 65, 170, 165), radius=22, fill="#ffffff")
    draw.text((92, 82), "ID", font=load_font(42, bold=True), fill="#111827")

    eyebrow = ".NET • SOFTWARE ARCHITECTURE • ISLAM DARAWSHEH"
    draw.text((70, 205), eyebrow, font=load_font(23, bold=True), fill="#9fb0c8")

    lines, title_font = fit_wrapped_text(draw, info["title"], 1030)
    y = 255
    for line in lines:
        draw.text((70, y), line, font=title_font, fill="#ffffff")
        y += title_font.size + 16

    draw.line((70, 595, 1130, 595), fill="#35445f", width=2)
    draw.text((70, 615), "darawsheh.github.io/articles", font=load_font(21), fill="#b8c5d8")

    image.save(out, "PNG", optimize=True)


def main() -> int:
    # seo_tools.py is a one-time transformer. Replace its helper in memory with
    # a corrected idempotent implementation, then remove the transformer from
    # the final branch so only the validator remains.
    tools.add_common_head_links = fixed_common_head_links
    tools.upgrade()

    article_paths = sorted((ROOT / "articles").glob("*/index.html"))
    infos = [tools.article_info(path) for path in article_paths]
    for info in infos:
        generate_og_image(info)

    errors = tools.validate()
    if errors:
        print("Bootstrap validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    # Remove temporary bootstrap machinery from the final PR.
    if LEGACY_TOOL.exists():
        LEGACY_TOOL.unlink()
    if BRANCH_WORKFLOW.exists():
        BRANCH_WORKFLOW.unlink()
    if SELF.exists():
        SELF.unlink()

    print("SEO bootstrap completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
