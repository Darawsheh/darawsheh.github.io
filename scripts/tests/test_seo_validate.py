from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
REPOSITORY = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from seo_validate import validate_site  # noqa: E402


class SeoValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "site"
        shutil.copytree(
            REPOSITORY,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__"),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def validate(self) -> list[str]:
        errors, _ = validate_site(self.root)
        return errors

    def test_current_site_passes(self) -> None:
        self.assertEqual([], self.validate())

    def test_article_missing_from_feed_fails(self) -> None:
        feed = self.root / "feed.xml"
        text = feed.read_text(encoding="utf-8")
        start = text.index("    <item>")
        end = text.index("    </item>", start) + len("    </item>\n")
        feed.write_text(text[:start] + text[end:], encoding="utf-8")
        self.assertTrue(any("RSS feed: missing" in error for error in self.validate()))

    def test_broken_internal_link_fails(self) -> None:
        home = self.root / "index.html"
        text = home.read_text(encoding="utf-8").replace(
            'href="/articles/"', 'href="/missing-page/"', 1
        )
        home.write_text(text, encoding="utf-8")
        self.assertTrue(
            any("broken internal href /missing-page/" in error for error in self.validate())
        )

    def test_duplicate_canonical_fails(self) -> None:
        profile = self.root / "islam-darawsheh" / "index.html"
        text = profile.read_text(encoding="utf-8").replace(
            '<link rel="canonical" href="https://darawsheh.github.io/islam-darawsheh/">',
            '<link rel="canonical" href="https://darawsheh.github.io/">',
        )
        profile.write_text(text, encoding="utf-8")
        self.assertTrue(
            any("expected one canonical URL" in error for error in self.validate())
        )

    def test_invalid_jsonld_fails(self) -> None:
        article = (
            self.root
            / "articles"
            / "mcp-dotnet-build-mcp-server-csharp"
            / "index.html"
        )
        text = article.read_text(encoding="utf-8").replace(
            '"@context": "https://schema.org",',
            '"@context": "https://schema.org", invalid',
            1,
        )
        article.write_text(text, encoding="utf-8")
        self.assertTrue(any("invalid JSON-LD" in error for error in self.validate()))

    def test_registry_date_mismatch_fails(self) -> None:
        script = self.root / "assets" / "script.js"
        text = script.read_text(encoding="utf-8").replace(
            "published: '2026-08-31'", "published: '2026-08-30'", 1
        )
        script.write_text(text, encoding="utf-8")
        self.assertTrue(
            any("published date differs from JSON-LD" in error for error in self.validate())
        )


if __name__ == "__main__":
    unittest.main()
