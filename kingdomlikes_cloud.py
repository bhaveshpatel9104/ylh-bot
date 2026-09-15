"""
KingdomLikes Cloud Bot for GitHub Actions
=========================================
Runs headlessly in Ubuntu runner on GitHub Actions using injected session cookies.
Completely rewritten based on KingdomLikes Vue 3 / Inertia architecture:
- Zero unnecessary reloads: preserves Vue Power Queue background verification.
- Native UI Confirm flow: avoids fake endpoints and let Vue handle verify/status.
- Headless focus & modal auto-dismiss: handles 'Don't close so fast' and focus traps.
- Graceful queue handling when YouTube tasks are temporarily empty.
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

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "kingdomlikes.log")

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] {msg}"
    print(formatted, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def is_logged_in(page):
    try:
        url = (page.url or "").lower()
        if "login" in url or "signin" in url:
            return False
        body = page.inner_text("body")
        if "Enter the Kingdom" in body or "Access the Kingdom" in body:
            return False
        if "LOG IN" in body and "SIGN UP" in body and "TOTAL BALANCE" not in body:
            return False
        return True
    except Exception:
        return False

def get_balance(page):
    try:
        body = page.inner_text("body")
        m = re.search(r'(\d+)\s*\n\s*TOTAL BALANCE', body, re.IGNORECASE)
        if m:
            return int(m.group(1))
        m2 = re.search(r'TOTAL BALANCE\s*\n\s*(\d+)', body, re.IGNORECASE)
        if m2:
            return int(m2.group(1))
    except Exception:
        pass
    return None

def check_queues_available(page):
    """Fast check via API whether any YouTube like or view task is available, without reloading the page."""
    try:
        return page.evaluate("""
            async () => {
                try {
                    const l = await (await fetch('/api/v1/earn/sites/next?type_id=7&order=0')).json();
                    const v = await (await fetch('/api/v1/earn/sites/next?type_id=6&order=0')).json();
                    return { hasLikes: Boolean(l && l.data), hasViews: Boolean(v && v.data) };
                } catch(e) {
                    return { hasLikes: true, hasViews: true };
                }
            }
        """)
    except Exception:
        return {"hasLikes": True, "hasViews": True}

def dismiss_modals_if_any(page):
    """Dismisses any EarnAlertModal that might pop up (e.g. 'Don't close so fast!' or 'Interaction not detected')."""
    try:
        btn = page.query_selector('button:has-text("Got it"), button:has-text("OK"), button:has-text("I understand")')
        if btn and btn.is_visible():
            txt = btn.inner_text().strip()
            log(f">> Dismissing warning modal with button '{txt}'...")
            btn.click()
            time.sleep(1)
            return True
    except Exception:
        pass
    return False

def wait_for_verifying_slots(page, max_wait_sec=30):
    """Waits for active 'verifying' slots in the Power Queue to finish before switching pages."""
    start = time.time()
    while time.time() - start < max_wait_sec:
        dismiss_modals_if_any(page)
        slots_verifying = page.evaluate("""
            () => {
                const slots = Array.from(document.querySelectorAll('div[data-slot-id]'));
                return slots.filter(s => (s.className || '').includes('from-violet')).length;
            }
        """)
        if not slots_verifying:
            break
        time.sleep(2)

def check_and_do_like(page, context):
    """
    Executes one YouTube Like task on the current page.
    Assumes page is already at KL_LIKES_URL (or navigates only once if on another page).
    """
    dismiss_modals_if_any(page)

    if KL_LIKES_URL not in page.url:
        try:
            log("Navigating to YouTube Likes page...")
            page.goto(KL_LIKES_URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)
        except Exception as e:
            log(f"Likes page load notice: {e}")
            return False

    if not is_logged_in(page):
        log(">> Notice: Likes page not logged in (Session expired or logged in from another browser).")
        return False

    # Wait up to 5 seconds for Vue 3 card to finish loading
    try:
        page.wait_for_selector('button:has-text("Like & Earn"), :has-text("All caught up"), :has-text("No sites left")', timeout=5000)
    except Exception:
        pass

    body = page.inner_text("body")
    if "All caught up" in body or "No sites left" in body:
        log(">> Likes Queue: All caught up / No sites left.")
        return False

    btn_el = page.query_selector('button:has-text("Like & Earn")')
    if not btn_el:
        # Check if awaiting confirm from previous step
        confirm_btn = page.query_selector('button:has-text("Confirm")')
        if confirm_btn and not confirm_btn.is_disabled():
            log(">> Found existing active Confirm button, clicking...")
            confirm_btn.click()
            time.sleep(3)
            return True

        log(">> Likes Queue: All caught up / No sites left.")
        return False

    log(">> Active Like task found! Opening video popup...")
    popup = None
    try:
        with page.expect_popup(timeout=15000) as popup_info:
            btn_el.click()
        popup = popup_info.value
        log(f">> Like popup opened: {popup.url}")

        # Wait for YouTube redirect & load
        for _ in range(12):
            time.sleep(1)
            p_url = (popup.url or "").lower()
            p_title = (popup.title() or "").lower()
            if "youtube.com" in p_url or "youtu.be" in p_url or "youtube" in p_title:
                break
        time.sleep(4)

        # Attempt like on YouTube
        like_res = popup.evaluate("""
            () => {
                const selectors = [
                    'like-button-view-model button',
                    'ytd-segmented-like-dislike-button-renderer button',
                    'segmented-like-dislike-button-view-model button',
                    'button[aria-label*="like this video" i]',
                    'button[aria-label*="like" i]'
                ];
                for (const s of selectors) {
                    const btn = document.querySelector(s);
                    if (btn) {
                        const isLiked = btn.getAttribute('aria-pressed') === 'true' ||
                                        (btn.getAttribute('aria-label') || '').toLowerCase().includes('unlike');
                        if (!isLiked) {
                            btn.click();
                            return { status: 'clicked', selector: s };
                        }
                        return { status: 'already_liked', selector: s };
                    }
                }
                return { status: 'not_found' };
            }
        """)
        log(f">> Like action: {like_res.get('status')} ({like_res.get('selector', '')})")

        # Keep video open for 6-8 seconds to allow YouTube engagement tracking to register
        time.sleep(6)

        # Ensure main page is focused
        page.bring_to_front()
        dismiss_modals_if_any(page)

        # In KingdomLikes Vue architecture:
        # Fe() auto-closes the popup when Confirm is clicked!
        # Clicking Confirm before closing popup prevents the 'closed too fast' alert modal.
        confirm_btn = None
        for _ in range(10):
            dismiss_modals_if_any(page)
            confirm_btn = page.query_selector('button:has-text("Confirm")')
            if confirm_btn and not confirm_btn.is_disabled():
                break
            time.sleep(1)

        if confirm_btn and not confirm_btn.is_disabled():
            log(">> Clicking Confirm button...")
            confirm_btn.click()
            time.sleep(2)
        else:
            log(">> Confirm button not enabled. Closing popup and retrying Confirm...")
            if popup and not popup.is_closed():
                popup.close()
            time.sleep(2)
            dismiss_modals_if_any(page)
            confirm_btn = page.query_selector('button:has-text("Confirm")')
            if confirm_btn:
                confirm_btn.click()
                time.sleep(2)

        # Close popup if still open
        try:
            if popup and not popup.is_closed():
                popup.close()
        except Exception:
            pass

        dismiss_modals_if_any(page)

        # Check Power Queue for active slot
        slot_status = page.evaluate("""
            () => {
                const slots = Array.from(document.querySelectorAll('div[data-slot-id]'));
                const active = slots.find(s => (s.className || '').includes('from-violet') || (s.className || '').includes('from-emerald'));
                if (active) {
                    return { id: active.getAttribute('data-slot-id'), isSuccess: (active.className || '').includes('from-emerald') };
                }
                return null;
            }
        """)
        if slot_status:
            log(f">> Task queued in Power Queue: {slot_status}")
        else:
            log(">> Task dispatched to verification queue.")

        return True

    except Exception as e:
        log(f">> Like task notice: {e}")
        if popup and not popup.is_closed():
            try:
                popup.close()
            except Exception:
                pass
        return False

def do_one_view(page, context):
    """Executes one YouTube View task on the views page."""
    dismiss_modals_if_any(page)

    if KL_VIEWS_URL not in page.url:
        try:
            log("Navigating to YouTube Views page...")
            page.goto(KL_VIEWS_URL, wait_until="networkidle", timeout=30000)
            time.sleep(3)
        except Exception as e:
            log(f"Views page load notice: {e}")
            return False

    if not is_logged_in(page):
        log(">> Notice: Views page not logged in (Session expired or logged in from another browser).")
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

    popup = None
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
                    if popup and not popup.is_closed():
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
            if popup and not popup.is_closed():
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
        if popup and not popup.is_closed():
            try:
                popup.close()
            except Exception:
                pass
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
                "--disable-popup-blocking",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        # Stealth evasion scripts + hasFocus() fix for headless mode
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            // Override hasFocus and visibilityState so Vue Le() never blocks in headless runner
            Object.defineProperty(document, 'hasFocus', { value: () => true, configurable: true });
            Object.defineProperty(document, 'visibilityState', { get: () => 'visible', configurable: true });
            Object.defineProperty(document, 'hidden', { get: () => false, configurable: true });
        """)

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

        log("Navigating to https://kingdomlikes.com/free_points/youtube-likes ...")
        try:
            page.goto(KL_LIKES_URL, wait_until="networkidle", timeout=40000)
            time.sleep(3)
        except Exception as e:
            log(f"Nav notice: {e}")

        log(f"Current URL: {page.url} | Title: {page.title()}")

        # Verify active session
        body = page.inner_text("body")
        if "login" in page.url.lower() or "Enter the Kingdom" in body or "AUTHENTICATION FAILED" in body:
            log("ERROR: Session cookie rejected or expired. Please re-run auto_refresh_cookies.py on your PC.")
            browser.close()
            sys.exit(1)

        start_bal = get_balance(page) or 0
        log(f"ACTIVE SESSION CONFIRMED! Starting Balance: {start_bal} Points\n")

        consecutive_empty = 0

        while (time.time() - session_start) < (MAX_SESSION_MINUTES * 60):
            dismiss_modals_if_any(page)

            # Check session status
            if not is_logged_in(page):
                log("=" * 60)
                log(">> [SESSION TERMINATED] KingdomLikes session was closed.")
                log(">> Cause: Account logged in from another browser / device (Single-session limit).")
                log(">> Note: Keep KingdomLikes closed on your PC browser so cloud bot can farm 24/7.")
                log("=" * 60)
                break

            # If previous cycle found both queues empty, do a fast lightweight API check first
            if consecutive_empty > 0:
                q_status = check_queues_available(page)
                if not q_status.get("hasLikes") and not q_status.get("hasViews"):
                    consecutive_empty += 1
                    wait_sec = min(90, 30 * consecutive_empty)
                    log(f">> Both queues still idle (0 YouTube tasks available on site). Sleeping {wait_sec}s...")
                    time.sleep(wait_sec)
                    continue
                else:
                    consecutive_empty = 0

            # 1. Farm Likes first (while on likes page)
            has_like = check_and_do_like(page, context)
            if has_like:
                likes_done += 1
                consecutive_empty = 0
                cur_bal = get_balance(page)
                log(f">> [PROGRESS] Views: {views_done} | Likes: {likes_done} | Balance: {cur_bal}")
                time.sleep(2)
                continue

            # Before switching away from Likes, allow active verifying slots to settle
            wait_for_verifying_slots(page, max_wait_sec=20)

            # 2. If Likes queue has no tasks, farm Views
            success = do_one_view(page, context)
            if success:
                views_done += 1
                consecutive_empty = 0
                cur_bal = get_balance(page)
                log(f">> [PROGRESS] Views: {views_done} | Likes: {likes_done} | Balance: {cur_bal}")
                time.sleep(2)
                continue

            # 3. Both queues empty
            consecutive_empty += 1
            wait_sec = min(90, 30 * consecutive_empty)
            log(f">> Both queues idle (0 YouTube tasks available on site). Sleeping {wait_sec}s before next check...")
            time.sleep(wait_sec)

        # Before finishing, wait for any remaining verifying slots
        wait_for_verifying_slots(page, max_wait_sec=30)
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
