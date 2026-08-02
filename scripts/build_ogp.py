#!/usr/bin/env python3
"""Render the deterministic 1200x630 Kurage GEO OGP image."""

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "ogp" / "kgeo-ogp.html"
OUTPUT = ROOT / "static" / "images" / "kgeo-ogp.png"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
    page.goto(SOURCE.as_uri(), wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.locator(".canvas").screenshot(path=str(OUTPUT))
    browser.close()

print(f"Rendered {OUTPUT} (1200x630)")
