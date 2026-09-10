"""
Cookie Saver Script
====================
Yeh script Google/YouTube session cookies save karta hai.
Ek baar run karo, phir cookies GitHub pe upload karo.
"""
import json
import sys
from playwright.sync_api import sync_playwright

GOOGLE_EMAIL    = "patelbhavesh9130@gmail.com"
GOOGLE_PASSWORD = "BHAVESH9104VV"

print("=" * 50)
print("Google Cookie Saver")
print("=" * 50)
print("Browser khul raha hai... login karo")
print()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    page = context.new_page()

    # Step 1: Google login
    print("[1/3] Google login kar raha hoon...")
    page.goto("https://accounts.google.com/v3/signin/identifier?flowName=GlifWebSignIn",
              wait_until="domcontentloaded", timeout=30000)
    import time; time.sleep(2)

    try:
        el = page.wait_for_selector('input[type="email"]', timeout=8000)
        el.type(GOOGLE_EMAIL, delay=100)
        time.sleep(0.5)
        page.keyboard.press("Enter")
        time.sleep(3)
    except Exception as e:
        print(f"  Email field error: {e}")

    try:
        el = page.wait_for_selector('input[type="password"]', timeout=10000)
        el.type(GOOGLE_PASSWORD, delay=100)
        time.sleep(0.5)
        page.keyboard.press("Enter")
        time.sleep(5)
    except Exception as e:
        print(f"  Password field error: {e}")

    print(f"  Google URL: {page.url}")

    # Step 2: YouTube visit to establish session
    print("[2/3] YouTube session establish kar raha hoon...")
    page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=30000)
    time.sleep(4)
    print(f"  YouTube URL: {page.url}")

    # Step 3: Save cookies
    print("[3/3] Cookies save kar raha hoon...")
    cookies = context.cookies()
    
    # Filter YouTube + Google cookies only
    yt_cookies = [c for c in cookies if 
                  any(d in c.get('domain', '') for d in ['youtube.com', 'google.com', 'accounts.google.com'])]
    
    cookies_json = json.dumps(yt_cookies)
    
    with open("google_cookies.json", "w") as f:
        json.dump(yt_cookies, f, indent=2)
    
    print(f"\n  {len(yt_cookies)} cookies saved to: google_cookies.json")
    print(f"  File size: {len(cookies_json)} characters")
    print()
    print("=" * 50)
    print("NEXT STEP: google_cookies.json ka content copy karke")
    print("GitHub Secret mein paste karo:")
    print("Name: GOOGLE_COOKIES")
    print("=" * 50)
    
    browser.close()

print("\nDone! Ab google_cookies.json file kholke content copy karo.")
