#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = "darawsheh.github.io"
KEY = "a89b01a4784870dc7fd5375a3d755561"
KEY_LOCATION = f"https://{HOST}/{KEY}.txt"
ENDPOINT = "https://api.indexnow.org/indexnow"


def sitemap_urls() -> list[str]:
    tree = ET.parse(ROOT / "sitemap.xml")
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [node.text.strip() for node in tree.findall("s:url/s:loc", namespace) if node.text]


def wait_for_key() -> bool:
    for _ in range(6):
        try:
            request = urllib.request.Request(KEY_LOCATION, headers={"User-Agent": "Darawsheh-IndexNow/1.0"})
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8").strip()
                if response.status == 200 and body == KEY:
                    return True
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(10)
    return False


def submit(urls: list[str]) -> int:
    payload = json.dumps(
        {
            "host": HOST,
            "key": KEY,
            "keyLocation": KEY_LOCATION,
            "urlList": urls,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "Darawsheh-IndexNow/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status in {200, 202}:
                print(f"IndexNow accepted {len(urls)} URL(s) with HTTP {response.status}.")
                return 0
            print(f"IndexNow returned HTTP {response.status}.")
            return 1
    except urllib.error.HTTPError as exc:
        print(f"IndexNow returned HTTP {exc.code}: {exc.reason}")
        return 1
    except urllib.error.URLError as exc:
        print(f"IndexNow request failed: {exc.reason}")
        return 1


def main() -> int:
    urls = sitemap_urls()
    if not urls:
        print("No sitemap URLs found; nothing to submit.")
        return 1
    if not wait_for_key():
        print(f"IndexNow key is not yet reachable at {KEY_LOCATION}.")
        return 1
    return submit(urls)


if __name__ == "__main__":
    raise SystemExit(main())
