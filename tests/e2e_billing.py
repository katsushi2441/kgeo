"""Read-only browser smoke test for the Kurage GEO billing presentation."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = os.getenv("KGEO_E2E_URL", "http://127.0.0.1:18308/")
OUTPUT = Path(__file__).resolve().parents[1] / "outputs" / "kgeo-billing-dialog.png"
MOBILE_OUTPUT = (
    Path(__file__).resolve().parents[1] / "outputs" / "kgeo-billing-dialog-mobile.png"
)


def main() -> None:
    token = os.environ["KGEO_INTERNAL_TOKEN"]
    console_errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.route(
            "**/api/**",
            lambda route, request: route.continue_(
                headers={
                    **request.headers,
                    "X-KGeo-Token": token,
                    "X-KGeo-User": "billing-browser-smoke",
                }
            ),
        )
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        assert page.locator(".pricing-strip").is_visible()
        assert "初回無料" in page.locator(".pricing-strip").inner_text()
        assert "200円" in page.locator(".pricing-strip").inner_text()
        assert "20,000 URLAI" in page.locator(".pricing-strip").inner_text()

        page.locator("#billingDialog").evaluate("dialog => dialog.showModal()")
        assert page.locator("#billingDialog").is_visible()
        assert "200円（PayPal）" in page.locator("#billingDialog").inner_text()
        assert "20,000 URLAI（Base）" in page.locator("#billingDialog").inner_text()
        page.screenshot(path=str(OUTPUT), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(100)
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth"
        )
        page.screenshot(path=str(MOBILE_OUTPUT), full_page=True)
        browser.close()

    if console_errors:
        raise AssertionError(f"browser console errors: {console_errors}")
    print(f"billing browser smoke passed: {OUTPUT}, {MOBILE_OUTPUT}")


if __name__ == "__main__":
    main()
