from pathlib import Path

from playwright.sync_api import sync_playwright

PUBLIC_URL = "https://kurage.exbridge.jp/kgeo.php"
OUTPUT = Path(__file__).resolve().parents[1] / "outputs" / "kgeo-public-login.png"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    console_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    response = page.goto(PUBLIC_URL, wait_until="networkidle")
    assert response is not None and response.status == 200
    assert page.get_by_role("heading", name="Kurage GEO").is_visible()
    login = page.get_by_role("link", name="Xでログイン")
    assert login.is_visible()
    assert login.get_attribute("href") == "?login=1"

    api_response = page.request.get(f"{PUBLIC_URL}?api=%2Fapi%2Fsites")
    assert api_response.status == 401
    assert api_response.json()["detail"] == "Xログインが必要です"
    asset_response = page.request.get(f"{PUBLIC_URL}?asset=app.js")
    assert asset_response.status == 200
    assert "loadAll" in asset_response.text()

    page.screenshot(path=str(OUTPUT), full_page=True)
    assert not console_errors, console_errors
    browser.close()
