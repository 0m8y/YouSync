#!/usr/bin/env python3
"""
Debug Spotify playlist preview scraping.

Usage:
    python debug_spotify_preview.py "https://open.spotify.com/playlist/5UkD1s2ZTwRvzCFz84t3aF"

Goal:
    - Fetch the Spotify playlist page.
    - Save the raw HTML locally.
    - Print every useful metadata field.
    - Detect if Spotify only returned the generic Web Player shell.
    - Try Spotify oEmbed as a comparison.
    - Dump script tags that may contain embedded state/config.
"""

from __future__ import annotations

import base64
import json
import re
import sys
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


DEFAULT_URL = "https://open.spotify.com/playlist/5UkD1s2ZTwRvzCFz84t3aF"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def print_section(title: str) -> None:
    print("\n" + "=" * 100)
    print(title)
    print("=" * 100)


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    return unescape(str(value)).strip()


def fetch_text(url: str) -> tuple[int, str, str]:
    response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    response.encoding = response.encoding or "utf-8"
    return response.status_code, str(response.url), response.text


def try_json_loads(value: str) -> Any | None:
    try:
        return json.loads(value)
    except Exception:
        return None


def try_base64_json(value: str) -> Any | None:
    try:
        padded = value + "=" * (-len(value) % 4)
        decoded = base64.b64decode(padded).decode("utf-8", errors="replace")
        return json.loads(decoded)
    except Exception:
        return None


def walk_find_keys(obj: Any, interesting_keys: set[str], path: str = "$", max_results: int = 80) -> list[tuple[str, Any]]:
    results: list[tuple[str, Any]] = []

    def walk(current: Any, current_path: str) -> None:
        if len(results) >= max_results:
            return

        if isinstance(current, dict):
            for key, value in current.items():
                next_path = f"{current_path}.{key}"
                if key in interesting_keys:
                    results.append((next_path, value))
                walk(value, next_path)
        elif isinstance(current, list):
            for index, value in enumerate(current[:100]):
                walk(value, f"{current_path}[{index}]")

    walk(obj, path)
    return results


def analyze_html(html: str, final_url: str) -> None:
    soup = BeautifulSoup(html, "html.parser")

    print_section("BASIC PAGE INFO")
    print(f"Final URL: {final_url}")
    print(f"HTML length: {len(html)} chars")
    print(f"Page title: {safe_text(soup.title.string if soup.title else None)!r}")

    if "Spotify – Web Player" in html or "Spotify - Web Player" in html:
        print("⚠️ Generic Spotify Web Player shell detected.")
    else:
        print("✅ Not the obvious generic Web Player shell.")

    print_section("META TAGS")
    meta_rows = []
    for tag in soup.find_all("meta"):
        key = tag.get("property") or tag.get("name") or tag.get("itemprop")
        content = tag.get("content")
        if key or content:
            meta_rows.append((safe_text(key), safe_text(content)))

    if not meta_rows:
        print("No meta tags found.")
    else:
        for key, content in meta_rows:
            print(f"{key:35} = {content}")

    print_section("LIKELY TITLE/COVER CANDIDATES")
    candidates = {
        "og:title": soup.find("meta", property="og:title"),
        "twitter:title": soup.find("meta", attrs={"name": "twitter:title"}),
        "description": soup.find("meta", attrs={"name": "description"}),
        "og:description": soup.find("meta", property="og:description"),
        "og:image": soup.find("meta", property="og:image"),
        "twitter:image": soup.find("meta", attrs={"name": "twitter:image"}),
    }

    for label, tag in candidates.items():
        value = tag.get("content") if tag else None
        print(f"{label:20} -> {safe_text(value)!r}")

    print_section("SCRIPT TAGS OVERVIEW")
    scripts = soup.find_all("script")
    print(f"Script count: {len(scripts)}")

    for index, script in enumerate(scripts):
        script_id = script.get("id")
        script_type = script.get("type")
        src = script.get("src")
        text = script.string or script.get_text() or ""
        print(
            f"[{index}] id={script_id!r} type={script_type!r} "
            f"src={src!r} text_len={len(text)}"
        )

    print_section("SCRIPT TAG CONTENT CHECKS")
    interesting_keys = {
        "title",
        "name",
        "display_name",
        "description",
        "image",
        "images",
        "total",
        "trackCount",
        "track_count",
        "tracks",
        "playlist",
    }

    for index, script in enumerate(scripts):
        script_id = script.get("id")
        text = (script.string or script.get_text() or "").strip()
        if not text:
            continue

        print(f"\n--- script[{index}] id={script_id!r} len={len(text)} ---")

        # Print direct keyword occurrences around title-like text.
        for keyword in ["YouSync", "playlist", "track", "Spotify"]:
            pos = text.lower().find(keyword.lower())
            if pos != -1:
                start = max(0, pos - 250)
                end = min(len(text), pos + 500)
                print(f"\nKeyword {keyword!r} around char {pos}:")
                print(text[start:end])

        # Try plain JSON.
        parsed = try_json_loads(text)
        if parsed is not None:
            print("\nParsed as JSON.")
            matches = walk_find_keys(parsed, interesting_keys)
            for path, value in matches[:30]:
                print(f"{path} = {repr(value)[:500]}")
            continue

        # Try base64 JSON for Spotify config scripts.
        parsed_b64 = try_base64_json(text)
        if parsed_b64 is not None:
            print("\nParsed as base64 JSON.")
            matches = walk_find_keys(parsed_b64, interesting_keys)
            for path, value in matches[:30]:
                print(f"{path} = {repr(value)[:500]}")
            continue

    print_section("REGEX SCAN IN RAW HTML")
    regexes = {
        "escaped title": r'"title"\s*:\s*"([^"]+)"',
        "escaped name": r'"name"\s*:\s*"([^"]+)"',
        "track total": r'"total"\s*:\s*(\d+)',
        "track count": r'"trackCount"\s*:\s*(\d+)',
        "og title raw": r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
    }

    for label, pattern in regexes.items():
        matches = re.findall(pattern, html, flags=re.IGNORECASE)
        print(f"{label:20} -> {len(matches)} match(es)")
        for match in matches[:20]:
            print(f"  - {unescape(str(match))[:500]}")


def analyze_oembed(url: str) -> None:
    print_section("SPOTIFY OEMBED")
    oembed_url = f"https://open.spotify.com/oembed?url={quote(url, safe='')}"
    print(f"oEmbed URL: {oembed_url}")

    try:
        response = requests.get(oembed_url, headers=HEADERS, timeout=20)
        print(f"HTTP status: {response.status_code}")
        print(f"Final URL: {response.url}")
        print(f"Raw response: {response.text[:2000]}")

        if response.ok:
            data = response.json()
            print("\nParsed JSON:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("\nUseful fields:")
            print(f"title         = {data.get('title')!r}")
            print(f"thumbnail_url = {data.get('thumbnail_url')!r}")
    except Exception as exc:
        print(f"oEmbed failed: {type(exc).__name__}: {exc}")


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL

    print_section("FETCH SPOTIFY PLAYLIST PAGE")
    print(f"Input URL: {url}")

    status, final_url, html = fetch_text(url)
    print(f"HTTP status: {status}")
    print(f"Final URL: {final_url}")

    output_path = Path("spotify_debug_page.html")
    output_path.write_text(html, encoding="utf-8")
    print(f"Saved raw HTML to: {output_path.resolve()}")

    analyze_html(html, final_url)
    analyze_oembed(url)

    print_section("NEXT STEP")
    print("Open spotify_debug_page.html and search for:")
    print("- YouSync")
    print("- og:title")
    print("- appServerConfig")
    print("- __NEXT_DATA__")
    print("- trackCount")
    print("- total")
    print("- playlist")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
