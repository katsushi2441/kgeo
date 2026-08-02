from pathlib import Path

from playwright.sync_api import sync_playwright

OUTPUT = Path(__file__).resolve().parents[1] / "outputs" / "kgeo-mobile-smoke.png"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    console_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.goto("http://127.0.0.1:18308/", wait_until="networkidle")
    page.get_by_label("サイト名").fill("E2E Example")
    page.get_by_label("公開URL").fill("https://example.com")
    page.get_by_label("ブランド名").fill("Example Domain")
    page.get_by_role("button", name="サイトを登録").click()
    page.get_by_text("サイトを登録しました。").wait_for()
    page.locator(".site-card").first.click()
    page.get_by_role("button", name="GEO監査を実行").click()
    page.get_by_text("GEO監査が完了しました。").wait_for(timeout=60000)
    page.locator("#auditReport").wait_for(state="visible")
    score = page.locator("#score").inner_text()
    assert score.isdigit(), score
    assert page.locator("#breakdown .metric").count() >= 8
    assert page.locator("#recommendations li").count() >= 1
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(OUTPUT), full_page=True)
    assert not console_errors, console_errors
    browser.close()
