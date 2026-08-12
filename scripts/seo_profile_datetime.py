#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "islam-darawsheh" / "index.html"
JSONLD_RE = re.compile(
    r'<script\s+type="application/ld\+json">\s*(\{.*?\})\s*</script>',
    re.DOTALL | re.IGNORECASE,
)


def find_profile_page(text: str) -> dict | None:
    for match in JSONLD_RE.finditer(text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if data.get("@type") == "ProfilePage":
            return data
    return None


def validate_datetime(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or "T" not in value:
        return f'{name} must be an ISO 8601 DateTime, not a date-only value'

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return f'{name} is not a valid ISO 8601 DateTime: {value}'

    if parsed.tzinfo is None:
        return f'{name} must include a timezone offset: {value}'
    return None


def main() -> int:
    profile = find_profile_page(PROFILE.read_text(encoding="utf-8"))
    if profile is None:
        print("ProfilePage JSON-LD not found", file=sys.stderr)
        return 1

    errors = [
        error
        for key in ("dateCreated", "dateModified")
        if (error := validate_datetime(key, profile.get(key))) is not None
    ]

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print("ProfilePage datetime validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
