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
    assert "GEO Optimizer・AiCMOを日本語" in page.title()
    assert page.get_by_role("heading", name="GEO Optimizer／AiCMOを日本語で活用").is_visible()
    assert page.locator('link[rel="canonical"]').get_attribute("href") == PUBLIC_URL
    assert page.locator('meta[property="og:image"]').get_attribute("content") == (
        "https://kurage.exbridge.jp/images/kgeo-ogp.png"
    )
    assert page.locator('script[src*="googletagmanager.com/gtag/js"]').count() == 1
    assert page.locator('script[src*="simpletrack.php"]').count() == 1
    login = page.get_by_role("link", name="Xでログイン")
    assert login.is_visible()
    assert login.get_attribute("href") == "?login=1"

    api_response = page.request.get(f"{PUBLIC_URL}?api=%2Fapi%2Fsites")
    assert api_response.status == 401
    assert api_response.json()["detail"] == "Xログインが必要です"
    asset_response = page.request.get(f"{PUBLIC_URL}?asset=app.js")
    assert asset_response.status == 200
    assert "loadAll" in asset_response.text()
    ogp_response = page.request.get("https://kurage.exbridge.jp/images/kgeo-ogp.png")
    assert ogp_response.status == 200
    assert ogp_response.headers.get("content-type") == "image/png"
    sitemap_response = page.request.get("https://kurage.exbridge.jp/sitemap.php")
    assert sitemap_response.status == 200
    assert "https://kurage.exbridge.jp/kgeo.php" in sitemap_response.text()
    llms_response = page.request.get("https://kurage.exbridge.jp/llms.txt")
    assert llms_response.status == 200
    assert "GEO Optimizer Skill" in llms_response.text()
    assert "AiCMO" in llms_response.text()
    assert "Kurage GEO" in llms_response.text()

    page.screenshot(path=str(OUTPUT), full_page=True)
    assert not console_errors, console_errors
    browser.close()
