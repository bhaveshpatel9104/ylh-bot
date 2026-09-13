"""
Cookie Saver - Final Fixed Version
Cookies navigation error ke bawajood save karta hai
"""
import json
import time
import subprocess
from playwright.sync_api import sync_playwright

GOOGLE_EMAIL    = "patelbhavesh9130@gmail.com"
GOOGLE_PASSWORD = "BHAVESH9104V"

print("=" * 55)
print("AUTO GOOGLE COOKIE SAVER")
print("=" * 55)

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    page = context.new_page()

    print("[1] Google login page...")
    page.goto("https://accounts.google.com/v3/signin/identifier?flowName=GlifWebSignIn",
              wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)

    # Enter email
    print("[2] Email enter kar raha hoon...")
    for sel in ['input[type="email"]', '#identifierId']:
        try:
            el = page.wait_for_selector(sel, timeout=5000)
            if el and el.is_visible():
                el.click()
                el.fill("")
                el.type(GOOGLE_EMAIL, delay=80)
                time.sleep(0.5)
                page.keyboard.press("Enter")
                print("   Email entered!")
                break
        except Exception:
            continue
    time.sleep(3)

    # Enter password
    print("[3] Password enter kar raha hoon...")
    for sel in ['input[type="password"]', 'input[name="password"]', 'input[name="Passwd"]']:
        try:
            el = page.wait_for_selector(sel, timeout=8000)
            if el and el.is_visible():
                el.click()
                el.fill("")
                el.type(GOOGLE_PASSWORD, delay=80)
                time.sleep(0.5)
                page.keyboard.press("Enter")
                print("   Password entered!")
                break
        except Exception:
            continue
    time.sleep(5)

    print(f"   URL: {page.url}")

    # 2FA check
    if "challenge" in page.url or "signin/v2/challenge" in page.url:
        print()
        print("!! Verification required - browser mein complete karo !!")
        input("   Complete hone ke baad ENTER dabao: ")
        time.sleep(3)

    # *** COOKIES PEHLE SAVE KARO - navigation se pehle ***
    print("[4] Cookies save kar raha hoon (navigation se pehle)...")
    cookies = context.cookies()
    print(f"   {len(cookies)} cookies mili!")

    # Navigate to YouTube (error ignore karo)
    try:
        page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=15000)
        time.sleep(3)
        print(f"   YouTube URL: {page.url}")
        # More cookies after YouTube
        yt_cookies = context.cookies()
        print(f"   YouTube ke baad: {len(yt_cookies)} cookies")
        cookies = yt_cookies  # Use YouTube cookies (more complete)
    except Exception as e:
        print(f"   YouTube navigation skipped ({str(e)[:50]})")
        print("   Pehle waali Google cookies use kar raha hoon...")

    # Save cookies
    print("[5] File mein save kar raha hoon...")
    cookies_str = json.dumps(cookies)
    with open("google_cookies.json", "w", encoding="utf-8") as f:
        f.write(cookies_str)
    print(f"   Saved! ({len(cookies)} cookies, {len(cookies_str)} chars)")

    # Clipboard
    print("[6] Clipboard mein copy kar raha hoon...")
    try:
        proc = subprocess.run(
            ["clip"],
            input=cookies_str.encode("utf-8"),
            capture_output=True,
            shell=True
        )
        print("   Clipboard mein copy ho gayi!")
    except Exception as e:
        print(f"   Clipboard error: {e}")
        print("   google_cookies.json file se manually copy karo")

    browser.close()

print()
print("=" * 55)
print("DONE!")
print()
print("Ab GitHub pe jaao:")
print("github.com/bhaveshpatel9104/ylh-bot/settings/secrets/actions/new")
print()
print("Name:  GOOGLE_COOKIES")
print("Value: Ctrl+V  (clipboard mein hai)")
print("       YA google_cookies.json file kholo aur copy karo")
print("=" * 55)
