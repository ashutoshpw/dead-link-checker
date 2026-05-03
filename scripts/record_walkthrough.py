#!/usr/bin/env python3
"""
Website Walkthrough Recorder
Opens a URL with a real browser, discovers top N internal links, visits each,
and saves a video of the entire session.
"""

import os
import sys
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

WEBSITE_URL = os.environ.get('WEBSITE_URL', '')
MAX_LINKS = int(os.environ.get('MAX_LINKS', '5'))
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', 'recordings')
VIEWPORT_WIDTH = int(os.environ.get('VIEWPORT_WIDTH', '1280'))
VIEWPORT_HEIGHT = int(os.environ.get('VIEWPORT_HEIGHT', '720'))
WAIT_AFTER_NAV_MS = int(os.environ.get('WAIT_AFTER_NAV_MS', '3000'))
NAV_TIMEOUT_MS = 30_000


def is_recordable_link(href: str, base_origin: str) -> bool:
    if not href or href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
        return False
    try:
        parsed = urlparse(href)
    except Exception:
        return False
    if parsed.scheme and parsed.scheme not in ('http', 'https'):
        return False
    # cdn-cgi paths are internal Cloudflare endpoints — skip (mirrors project convention)
    if parsed.path.startswith('/cdn-cgi/'):
        return False
    link_origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else base_origin
    return link_origin == base_origin


def collect_internal_links(page, base_origin: str, limit: int) -> list[str]:
    hrefs = page.eval_on_selector_all('a[href]', 'els => els.map(e => e.href)')
    seen = set()
    links = []
    for href in hrefs:
        if not is_recordable_link(href, base_origin):
            continue
        # Normalise: strip fragment
        clean = href.split('#')[0].rstrip('/')
        if clean in seen or clean == base_origin.rstrip('/'):
            continue
        seen.add(clean)
        links.append(clean)
        if len(links) >= limit:
            break
    return links


def navigate(page, url: str, label: str) -> bool:
    print(f"  → {label}: {url}")
    try:
        page.goto(url, wait_until='networkidle', timeout=NAV_TIMEOUT_MS)
    except PlaywrightTimeout:
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=NAV_TIMEOUT_MS)
            print(f"    (networkidle timed out, fell back to domcontentloaded)")
        except Exception as e:
            print(f"    FAILED: {e}")
            return False
    # Scroll slowly so the video captures the full page
    page.evaluate("""
        () => new Promise(resolve => {
            const step = 300;
            const delay = 120;
            let scrolled = 0;
            const id = setInterval(() => {
                window.scrollBy(0, step);
                scrolled += step;
                if (scrolled >= document.body.scrollHeight) {
                    clearInterval(id);
                    window.scrollTo(0, 0);
                    resolve();
                }
            }, delay);
        })
    """)
    page.wait_for_timeout(WAIT_AFTER_NAV_MS)
    return True


def main() -> int:
    if not WEBSITE_URL:
        print("ERROR: WEBSITE_URL environment variable is required.")
        return 1

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    parsed_base = urlparse(WEBSITE_URL)
    base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

    print(f"Recording walkthrough of: {WEBSITE_URL}")
    print(f"Max links to visit: {MAX_LINKS}")
    print(f"Output dir: {OUTPUT_DIR}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir=OUTPUT_DIR,
            record_video_size={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
        )
        page = context.new_page()

        # Step 1: land on the input URL
        ok = navigate(page, WEBSITE_URL, "Landing page")
        if not ok:
            context.close()
            browser.close()
            print("ERROR: Could not load the starting URL.")
            return 1

        # Step 2: collect internal links from the landing page
        links = collect_internal_links(page, base_origin, MAX_LINKS)
        print(f"\nFound {len(links)} internal link(s) to visit:")
        for i, l in enumerate(links, 1):
            print(f"  {i}. {l}")

        # Step 3: visit each link in the same page (same video context)
        print()
        for i, link in enumerate(links, 1):
            navigate(page, link, f"Link {i}/{len(links)}")

        context.close()  # finalises the .webm file
        browser.close()

    # Discover what was written
    recordings = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.webm')]
    if recordings:
        print(f"\nRecording saved:")
        for r in recordings:
            path = os.path.join(OUTPUT_DIR, r)
            size_kb = os.path.getsize(path) // 1024
            print(f"  {path}  ({size_kb} KB)")
    else:
        print("\nWARNING: No .webm file found in output directory.")
        return 1

    _write_summary(links, recordings)
    print("\nDone.")
    return 0


def _write_summary(links: list[str], recordings: list[str]) -> None:
    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if not summary_path:
        return

    server = os.environ.get('GITHUB_SERVER_URL', 'https://github.com')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    artifact_url = f"{server}/{repo}/actions/runs/{run_id}" if repo and run_id else None

    lines = ["## 🎬 Walkthrough Recording", ""]
    lines += [
        "| | |",
        "|---|---|",
        f"| **Starting URL** | {WEBSITE_URL} |",
        f"| **Links visited** | {len(links)} |",
    ]
    for i, link in enumerate(links, 1):
        lines.append(f"| &nbsp;&nbsp;&nbsp;&nbsp;{i}. | {link} |")

    total_kb = sum(
        os.path.getsize(os.path.join(OUTPUT_DIR, r)) // 1024 for r in recordings
    )
    lines.append(f"| **Recording size** | {total_kb} KB |")
    if artifact_url:
        lines.append(f"| **Download** | [⬇️ walkthrough-video artifact]({artifact_url}) |")

    lines += ["", "_Video recorded with Playwright (Chromium headless)_"]

    with open(summary_path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    sys.exit(main())
