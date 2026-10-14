"""Screenshot-based, disposable SQLite UI review; no real users or secrets."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = "http://127.0.0.1:8000"
OUT = Path("artifacts/atelier-visual")
OUT.mkdir(parents=True, exist_ok=True)

def login(page, email, password):
    page.goto(BASE + "/accounts/login/", wait_until="networkidle")
    page.locator("#id_username").fill(email)
    page.locator("#id_password").fill(password)
    page.locator("button[type=submit]").click()
    expect(page).not_to_have_url("**/accounts/login/")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    desktop = browser.new_context(viewport={"width": 1440, "height": 920}, device_scale_factor=1)
    page = desktop.new_page()
    page.goto(BASE + "/accounts/login/", wait_until="networkidle")
    expect(page.get_by_text("Your workspace awaits.")).to_be_visible()
    page.screenshot(path=str(OUT / "01-login-desktop.png"), full_page=True)
    login(page, "owner-ui@example.test", "visual-only-owner-password-2026")
    page.goto(BASE + "/org/visual-design/", wait_until="networkidle")
    expect(page.get_by_text("Everything in its place.")).to_be_visible()
    expect(page.locator(".metric")).to_have_count(4)
    page.screenshot(path=str(OUT / "02-overview-desktop.png"), full_page=True)
    page.goto(BASE + "/org/visual-design/team/", wait_until="networkidle")
    expect(page.get_by_text("Your people, together.")).to_be_visible()
    page.screenshot(path=str(OUT / "03-team-desktop.png"), full_page=True)
    page.goto(BASE + "/org/visual-design/clock/", wait_until="networkidle")
    expect(page.get_by_text("Make today count.")).to_be_visible()
    page.screenshot(path=str(OUT / "04-clock-desktop.png"), full_page=True)
    desktop.close()

    mobile = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True)
    m = mobile.new_page()
    login(m, "staff-ui@example.test", "visual-only-staff-password-2026")
    m.goto(BASE + "/org/visual-design/clock/", wait_until="networkidle")
    expect(m.locator('button[name="action"][value="in"]')).to_be_visible()
    m.screenshot(path=str(OUT / "05-clock-mobile.png"), full_page=True)
    m.locator("[data-toggle-sidebar]").click()
    expect(m.locator("#sidebar")).to_have_class(__import__("re").compile("is-open"))
    m.screenshot(path=str(OUT / "06-mobile-navigation.png"), full_page=True)
    m.locator("[data-sidebar-scrim]").click(position={"x": 380, "y": 500})
    expect(m.locator("#sidebar")).not_to_have_class(__import__("re").compile("is-open"))
    m.locator('button[name="action"][value="in"]').click()
    expect(m.locator('button[name="action"][value="out"]')).to_be_visible()
    m.screenshot(path=str(OUT / "07-active-shift-mobile.png"), full_page=True)
    m.locator('button[name="action"][value="out"]').click()
    expect(m.locator('button[name="action"][value="in"]')).to_be_visible()
    print("Desktop and mobile UI smoke passed; server-confirmed clock-in/out succeeded.")
    mobile.close()
    browser.close()
