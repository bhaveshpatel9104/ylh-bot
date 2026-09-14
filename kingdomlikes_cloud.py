"""
KingdomLikes Cloud Bot for GitHub Actions
=========================================
Runs headlessly in Ubuntu runner on GitHub Actions.
Performs continuous YouTube Views farming and priority YouTube Likes checks.
"""

import os
import sys
import time
import re
import json
import datetime
from playwright.sync_api import sync_playwright

KL_EMAIL = os.environ.get("KL_EMAIL", "patelbhavesh9130@gmail.com")
KL_PASSWORD = os.environ.get("KL_PASSWORD", "BHAVESH91045678VV")
KL_COOKIES_RAW = os.environ.get("KL_COOKIES", "")
GOOGLE_COOKIES_RAW = os.environ.get("GOOGLE_COOKIES", "")

KL_BASE = "https://kingdomlikes.com"
KL_VIEWS_URL = f"{KL_BASE}/free_points/youtube-views"
KL_LIKES_URL = f"{KL_BASE}/free_points/youtube-likes"
KL_FREE_POINTS = f"{KL_BASE}/free_points"

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def parse_timer_seconds(time_str):
    if not time_str:
        return 60
    parts = time_str.strip().split(":")
    if len(parts) == 2:
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            return 60
    try:
        return int(parts[0])
    except ValueError:
        return 60

def get_balance(page):
    try:
        body = page.inner_text("body")
        m = re.search(r'(\d+)\s*\n\s*TOTAL BALANCE', body)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None

def login_to_kingdomlikes(page):
    log("Navigating to KingdomLikes...")
    page.goto(KL_FREE_POINTS, wait_until="networkidle", timeout=35000)
    time.sleep(2)

    # Check if already logged in via injected cookies
    bal = get_balance(page)
    if bal is not None:
        log(f"Already logged in via session cookies! Balance: {bal} Points")
        return True

    log(f"Session not active. Navigating to login page...")
    page.goto("https://kingdomlikes.com/login", wait_until="networkidle", timeout=35000)
    time.sleep(2)

    log(f"Filling login form for {KL_EMAIL}...")
    page.fill('input[type="email"], input[name*="email"]', KL_EMAIL)
    page.fill('input[type="password"]', KL_PASSWORD)

    # Check Remember me
    rem = page.query_selector('input[type="checkbox"]')
    if rem and not rem.is_checked():
        rem.check()

    # Look for reCAPTCHA iframe and click checkbox
    for frame in page.frames:
        if "recaptcha" in frame.url or "google.com/recaptcha" in frame.url:
            try:
                cb = frame.query_selector(".recaptcha-checkbox-border, #recaptcha-anchor")
                if cb:
                    cb.click()
                    log("Clicked reCAPTCHA checkbox in frame.")
                    time.sleep(3)
            except Exception as e:
                log(f"reCAPTCHA frame interaction note: {e}")

    time.sleep(1)
    submit_btn = page.query_selector('button[type="submit"], button:has-text("Enter the Kingdom"), button:has-text("Log In")')
    if submit_btn:
        submit_btn.click()
    time.sleep(6)

    # Check if redirected to dashboard or free_points
    page.goto(KL_FREE_POINTS, wait_until="networkidle", timeout=30000)
    time.sleep(3)

    bal = get_balance(page)
    if bal is not None:
        log(f"Successfully logged in! Starting Balance: {bal} Points")
        return True
    else:
        log("Warning: Could not detect TOTAL BALANCE after login. Current URL: " + page.url)
        # Check body text snippet for debugging
        body = page.inner_text("body")
        for l in body.split("\n")[:10]:
            if l.strip():
                log("   " + l.strip())
        return False

def check_and_do_like(page, context):
    try:
        page.goto(KL_LIKES_URL, wait_until="networkidle", timeout=25000)
        time.sleep(2)
    except Exception as e:
        log(f"Likes page load notice: {e}")
        return False

    body = page.inner_text("body")
    if "All caught up" in body or "No sites left" in body:
        return False

    btn_el = page.query_selector('button:has-text("Like"), a:has-text("Like")')
    if not btn_el:
        return False

    log(">> Active Like task found! Opening video popup...")
    try:
        with page.expect_popup(timeout=12000) as popup_info:
            btn_el.click()
        popup = popup_info.value
        log(f">> Like popup opened: {popup.url}")
        time.sleep(4)

        # Attempt like in popup
        res = popup.evaluate("""
            () => {
                const btn = document.querySelector('like-button-view-model button, button[aria-label*="like this video" i], button[aria-label*="like" i]');
                if (btn) {
                    const isLiked = btn.getAttribute('aria-pressed') === 'true';
                    if (!isLiked) {
                        btn.click();
                        return 'Liked video';
                    }
                    return 'Already liked';
                }
                return 'Like button not found';
            }
        """)
        log(f">> Like action: {res}")
        time.sleep(6)

        if not popup.is_closed():
            popup.close()

        time.sleep(3)
        confirm_btn = page.query_selector('button:has-text("Confirm")')
        if confirm_btn and not confirm_btn.is_disabled():
            confirm_btn.click()
            time.sleep(4)

        log(">> Completed Like task!")
        return True
    except Exception as e:
        log(f">> Like task notice: {e}")
        return False

def do_one_view(page, context):
    try:
        page.goto(KL_VIEWS_URL, wait_until="networkidle", timeout=25000)
        time.sleep(2)
    except Exception as e:
        log(f"Views page load notice: {e}")
        return False

    body = page.inner_text("body")
    if "All caught up" in body or "No sites left" in body:
        log(">> Views Queue: Empty.")
        return False

    play_btn = page.query_selector("button:has-text('Play & Earn')")
    if not play_btn:
        log(">> No Play & Earn button found.")
        return False

    credits_m = re.search(r'\+(\d+)\s*CREDITS', body)
    task_credits = credits_m.group(1) if credits_m else "?"
    log(f">> Starting View task (+{task_credits} Credits)...")

    try:
        with page.expect_popup(timeout=15000) as popup_info:
            play_btn.click()
        popup = popup_info.value
        log(f">> YouTube popup opened: {popup.url}")

        time.sleep(3)
        # Ensure video is playing
        try:
            popup.evaluate("""
                () => {
                    const v = document.querySelector('video');
                    if (v) {
                        v.muted = true;
                        v.play();
                    }
                }
            """)
        except Exception:
            pass

        confirm_clicked = False
        log(">> Waiting for video countdown timer...")

        for tick in range(1, 330):
            time.sleep(1)

            status = page.evaluate("""
                () => {
                    const text = document.body.innerText;
                    const m = text.match(/(\\d+:\\d+)\\s+of\\s+(\\d+:\\d+)/i) || text.match(/MUST PLAY FOR[\\s\\S]*?(\\d+:\\d+)/i);
                    const btns = Array.from(document.querySelectorAll('button')).filter(b => (b.innerText || '').includes('Confirm'));
                    let unlocked = false;
                    if (btns.length > 0) {
                        const b = btns[0];
                        unlocked = !b.disabled && !b.classList.contains('cursor-not-allowed') && !b.classList.contains('opacity-50') && b.getAttribute('aria-disabled') !== 'true';
                    }
                    return {
                        timer: m ? m[0] : null,
                        unlocked: unlocked
                    };
                }
            """)

            if tick % 15 == 0:
                log(f"   [{tick}s] Timer: {status.get('timer')} | Unlocked: {status.get('unlocked')}")
                try:
                    if not popup.is_closed():
                        popup.evaluate("() => { const v = document.querySelector('video'); if (v && v.paused) v.play(); }")
                except Exception:
                    pass

            if status.get('unlocked'):
                log(f">> Timer finished at {tick}s! Clicking Confirm...")
                c_btn = page.query_selector("button:has-text('Confirm')")
                if c_btn:
                    c_btn.click()
                    confirm_clicked = True
                    time.sleep(5)
                    break

        try:
            if not popup.is_closed():
                popup.close()
        except Exception:
            pass

        if confirm_clicked:
            log(">> View task confirmed successfully!")
            return True
        else:
            log(">> View task did not unlock in time.")
            return False

    except Exception as e:
        log(f">> View task notice: {e}")
        return False

def main():
    log("=" * 60)
    log("KINGDOMLIKES CLOUD BOT (GITHUB ACTIONS)")
    log("=" * 60)

    # Session limit: 300 minutes (GitHub Actions allows up to 350)
    MAX_SESSION_MINUTES = 300
    session_start = time.time()

    views_done = 0
    likes_done = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        # 1. Inject KingdomLikes cookies if provided
        if KL_COOKIES_RAW:
            try:
                kl_cookies = json.loads(KL_COOKIES_RAW)
                context.add_cookies(kl_cookies)
                log(f"Injected {len(kl_cookies)} KingdomLikes cookies into browser context.")
            except Exception as e:
                log(f"KingdomLikes cookies parse warning: {e}")

        # 2. Inject Google cookies if provided
        if GOOGLE_COOKIES_RAW:
            try:
                g_cookies = json.loads(GOOGLE_COOKIES_RAW)
                context.add_cookies(g_cookies)
                log(f"Injected {len(g_cookies)} Google cookies into browser context.")
            except Exception as e:
                log(f"Google cookies parse warning: {e}")

        page = context.new_page()

        if not login_to_kingdomlikes(page):
            log("Login failed. Exiting.")
            browser.close()
            sys.exit(1)

        start_bal = get_balance(page) or 0
        log(f"Session started! Initial Balance: {start_bal} Points\n")

        consecutive_empty = 0

        while (time.time() - session_start) < (MAX_SESSION_MINUTES * 60):
            # 1. Check Likes first
            has_like = check_and_do_like(page, context)
            if has_like:
                likes_done += 1
                consecutive_empty = 0
                time.sleep(3)

            # 2. Farm Views (Main engine)
            success = do_one_view(page, context)
            if success:
                views_done += 1
                consecutive_empty = 0
                cur_bal = get_balance(page)
                log(f">> [PROGRESS] Views: {views_done} | Likes: {likes_done} | Balance: {cur_bal}")
                time.sleep(3)
            else:
                consecutive_empty += 1
                wait_sec = min(60, 15 * consecutive_empty)
                log(f">> Both queues empty/idle. Sleeping {wait_sec}s before next check...")
                time.sleep(wait_sec)

        end_bal = get_balance(page) or 0
        earned = end_bal - start_bal
        log("=" * 60)
        log("CLOUD SESSION COMPLETE")
        log(f"Views Completed: {views_done} | Likes Completed: {likes_done}")
        log(f"Start Balance: {start_bal} | End Balance: {end_bal} | Earned: +{earned} Points")
        log("=" * 60)

        browser.close()

if __name__ == "__main__":
    main()
