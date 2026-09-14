"""
KingdomLikes Cloud Bot for GitHub Actions
=========================================
Runs headlessly in Ubuntu runner on GitHub Actions using injected session cookies.
No login form, no captcha needed!
"""

import os
import sys
import time
import re
import json
import datetime
from playwright.sync_api import sync_playwright

KL_COOKIES_RAW = os.environ.get("KL_COOKIES", "")
GOOGLE_COOKIES_RAW = os.environ.get("GOOGLE_COOKIES", "")

KL_BASE = "https://kingdomlikes.com"
KL_VIEWS_URL = f"{KL_BASE}/free_points/youtube-views"
KL_LIKES_URL = f"{KL_BASE}/free_points/youtube-likes"
KL_FREE_POINTS = f"{KL_BASE}/free_points"

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def get_balance(page):
    try:
        body = page.inner_text("body")
        m = re.search(r'(\d+)\s*\n\s*TOTAL BALANCE', body)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None

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

    if not KL_COOKIES_RAW:
        log("ERROR: KL_COOKIES secret not provided. Please sync cookies first.")
        sys.exit(1)

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

        # 1. Inject KingdomLikes cookies
        try:
            kl_cookies = json.loads(KL_COOKIES_RAW)
            context.add_cookies(kl_cookies)
            log(f"Injected {len(kl_cookies)} KingdomLikes session cookies.")
        except Exception as e:
            log(f"KingdomLikes cookies error: {e}")
            sys.exit(1)

        # 2. Inject Google cookies
        if GOOGLE_COOKIES_RAW:
            try:
                g_cookies = json.loads(GOOGLE_COOKIES_RAW)
                context.add_cookies(g_cookies)
                log(f"Injected {len(g_cookies)} Google cookies.")
            except Exception as e:
                log(f"Google cookies warning: {e}")

        page = context.new_page()

        log("Navigating to https://kingdomlikes.com/free_points ...")
        page.goto(KL_FREE_POINTS, wait_until="networkidle", timeout=35000)
        time.sleep(3)

        # Verify active session
        body = page.inner_text("body")
        if "login" in page.url.lower() or "Enter the Kingdom" in body:
            log("ERROR: Session cookie rejected or expired. Please re-run auto_refresh_cookies.py on your PC.")
            browser.close()
            sys.exit(1)

        start_bal = get_balance(page) or 0
        log(f"ACTIVE SESSION CONFIRMED! Starting Balance: {start_bal} Points\n")

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
                log(f">> Both queues idle. Sleeping {wait_sec}s before next check...")
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
