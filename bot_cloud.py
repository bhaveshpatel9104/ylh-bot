"""
YouLikeHits Bot — GitHub Actions Session Mode
===============================================
Yeh version GitHub Actions pe chalta hai.
Har run mein fixed number of likes karta hai, phir band hota hai.
GitHub ne dobara schedule pe start kar deta hai.
"""

import time
import random
import logging
import os
import sys
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ---- Credentials from environment variables (GitHub Secrets) ----
YLH_LOGIN_ID    = os.environ.get("YLH_LOGIN_ID",    "patelbhavesh9130@gmail.com")
YLH_PASSWORD    = os.environ.get("YLH_PASSWORD",    "BHAVESH91045678VV")
GOOGLE_EMAIL    = os.environ.get("GOOGLE_EMAIL",    "patelbhavesh9130@gmail.com")
GOOGLE_PASSWORD = os.environ.get("GOOGLE_PASSWORD", "BHAVESH9104VV")
YLH_USERNAME    = os.environ.get("YLH_USERNAME",    "bhavesh647383")
GOOGLE_COOKIES  = os.environ.get("GOOGLE_COOKIES",  "")  # JSON string of saved cookies

YLH_LOGIN_URL         = "https://www.youlikehits.com/login.php"
YLH_YOUTUBE_LIKES_URL = "https://www.youlikehits.com/youtubelikes.php"

# Max likes per GitHub Actions session (adjust as needed)
MAX_LIKES = int(os.environ.get("MAX_LIKES", "20"))

# ---- Logging ----
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def human_delay(mn=3.0, mx=6.0):
    time.sleep(random.uniform(mn, mx))


def google_login(context):
    """Google login - saved cookies use karta hai (password login GitHub Actions pe block hota hai)"""
    if GOOGLE_COOKIES:
        try:
            cookies = json.loads(GOOGLE_COOKIES)
            context.add_cookies(cookies)
            log.info(f"[OK] Google cookies loaded! ({len(cookies)} cookies)")
            # Verify by visiting YouTube
            page = context.new_page()
            page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)
            content = page.content()
            if GOOGLE_EMAIL.split("@")[0].lower() in content.lower() or "avatar" in content.lower():
                log.info("[OK] YouTube login verified via cookies!")
            else:
                log.info("[INFO] Cookies loaded, YouTube session active")
            page.close()
            return
        except Exception as e:
            log.error(f"[ERROR] Cookie load failed: {e}")

    # Fallback: password login try karo
    log.info("[LOGIN] Google password login try kar raha hoon...")
    page = context.new_page()
    try:
        page.goto("https://accounts.google.com/v3/signin/identifier?flowName=GlifWebSignIn",
                  wait_until="domcontentloaded", timeout=30000)
        human_delay(2, 3)
        for sel in ['input[type="email"]', '#identifierId']:
            try:
                el = page.wait_for_selector(sel, timeout=8000)
                if el:
                    el.type(GOOGLE_EMAIL, delay=100)
                    human_delay(0.5, 1)
                    page.keyboard.press("Enter")
                    human_delay(2.5, 4)
                    break
            except Exception:
                continue
        for sel in ['input[type="password"]', 'input[name="password"]']:
            try:
                el = page.wait_for_selector(sel, timeout=10000)
                if el:
                    el.type(GOOGLE_PASSWORD, delay=100)
                    human_delay(0.5, 1)
                    page.keyboard.press("Enter")
                    human_delay(4, 6)
                    break
            except Exception:
                continue
        log.info(f"[INFO] Google URL: {page.url}")
    except Exception as e:
        log.error(f"[ERROR] Google login: {e}")
    finally:
        page.close()



def ylh_login(page) -> bool:
    log.info("[LOGIN] YouLikeHits login kar raha hoon...")
    try:
        page.goto(YLH_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        human_delay(1.5, 2.5)
        page.wait_for_selector("#username", timeout=10000)
        page.fill("#username", YLH_LOGIN_ID)
        human_delay(0.4, 0.8)
        page.wait_for_selector("#password", timeout=10000)
        page.fill("#password", YLH_PASSWORD)
        human_delay(0.5, 1)
        page.click('input[type="submit"]')
        human_delay(2.5, 4)
        content = page.content()
        if "Logout" in content or "My Account" in content or YLH_USERNAME in content:
            log.info("[OK] YouLikeHits login successful!")
            return True
        log.error("[ERROR] YouLikeHits login fail!")
        return False
    except Exception as e:
        log.error(f"[ERROR] YLH login: {e}")
        return False


def get_points(page):
    try:
        el = page.query_selector("text=/\\d+ Points/")
        if el:
            text = el.text_content()
            pts = ''.join(filter(str.isdigit, text.split("Points")[0].strip()))
            return int(pts) if pts else None
    except Exception:
        pass
    return None


def do_one_like(page, context) -> bool:
    try:
        content = page.content()
        if "No videos" in content or "come back later" in content.lower():
            log.info("[INFO] No videos available, waiting 60s...")
            time.sleep(60)
            return False

        # Step 1: followbutton click
        follow_btn = None
        try:
            follow_btn = page.wait_for_selector("a.followbutton", timeout=8000)
        except Exception:
            pass
        if not follow_btn:
            log.warning("[WARN] followbutton nahi mila")
            return False
        follow_btn.click()
        human_delay(2, 3)

        # Step 2: earn-btn click -> YouTube opens
        earn_btn = None
        try:
            earn_btn = page.wait_for_selector("a.earn-btn", timeout=8000)
        except Exception:
            pass
        if not earn_btn:
            log.warning("[WARN] earn-btn nahi mila")
            return False

        try:
            with context.expect_page(timeout=10000) as new_page_info:
                earn_btn.click()
            yt_page = new_page_info.value
        except Exception:
            earn_btn.click()
            human_delay(2, 3)
            pages = context.pages
            yt_page = pages[-1] if len(pages) > 1 else None

        if not yt_page:
            log.warning("[WARN] YouTube tab nahi khula")
            return False

        try:
            yt_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            human_delay(4, 5)

        log.info(f"  >> YouTube: {yt_page.url[:70]}")

        # Step 3: YouTube like
        liked = False
        for sel in [
            'button[aria-label*="like this video"]',
            'button[aria-label*="Like this video"]',
            '#segmented-like-button button',
            '#segmented-like-button yt-button-shape button',
        ]:
            try:
                btn = yt_page.wait_for_selector(sel, timeout=4000)
                if btn:
                    pressed = btn.get_attribute("aria-pressed")
                    if pressed != "true":
                        btn.scroll_into_view_if_needed()
                        human_delay(0.5, 1)
                        btn.click()
                    log.info("  [OK] YouTube liked!")
                    liked = True
                    break
            except Exception:
                continue

        if not liked:
            try:
                result = yt_page.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('button');
                        for (const b of btns) {
                            const label = (b.getAttribute('aria-label') || '').toLowerCase();
                            if (label.includes('like') && !label.includes('dislike')) {
                                if (b.getAttribute('aria-pressed') !== 'true') b.click();
                                return 'ok: ' + label;
                            }
                        }
                        return 'not_found';
                    }
                """)
                if result != 'not_found':
                    log.info(f"  [OK] YouTube like JS: {result}")
                    liked = True
            except Exception:
                pass

        # Scroll on YouTube before closing (human-like)
        try:
            yt_page.mouse.wheel(0, random.randint(200, 500))
            time.sleep(random.uniform(0.5, 1.5))
            yt_page.mouse.wheel(0, random.randint(-100, -50))
        except Exception:
            pass

        human_delay(2, 4)
        yt_page.close()

        # Step 4: Wapas YLH pe aao
        page.bring_to_front()
        # Random wait before clicking confirm (human-like - page dekhne jaisa)
        pre_confirm_wait = random.uniform(3, 7)
        log.info(f"  >> Confirm se pehle {pre_confirm_wait:.1f}s wait...")
        time.sleep(pre_confirm_wait)

        # Click 'I'm done - check now'
        for sel in ['#ylhManualBtn', 'button:has-text("done")', 'button:has-text("check now")']:
            try:
                btn = page.wait_for_selector(sel, timeout=6000)
                if btn:
                    # Random mouse movement before click
                    try:
                        box = btn.bounding_box()
                        if box:
                            # Move to random point near button
                            page.mouse.move(
                                box['x'] + random.randint(-30, 30),
                                box['y'] + random.randint(-20, 20)
                            )
                            time.sleep(random.uniform(0.3, 0.8))
                    except Exception:
                        pass
                    btn.click()
                    log.info("  [OK] 'I'm done - check now' clicked!")
                    break
            except Exception:
                continue

        # Confirm click ke BAAD: 8-15 sec random wait (anti-detection)
        post_confirm_wait = random.uniform(8, 15)
        log.info(f"  >> Confirm ke baad {post_confirm_wait:.1f}s wait (anti-detection)...")
        time.sleep(post_confirm_wait)

        # Wait for sync
        try:
            page.wait_for_selector("text=Syncing", timeout=8000)
            page.wait_for_selector("text=Syncing", state="hidden", timeout=30000)
            log.info("  [OK] Sync done!")
        except Exception:
            human_delay(5, 8)

        return True

    except Exception as e:
        log.error(f"[ERROR] do_one_like: {e}")
        return False


def run():
    log.info("=" * 50)
    log.info(f"[BOT] GitHub Actions Session — Max {MAX_LIKES} likes")
    log.info(f"[BOT] Account: {YLH_LOGIN_ID}")
    log.info("=" * 50)

    total = 0
    start = datetime.now()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        google_login(context)
        human_delay(2, 3)

        main_page = context.new_page()
        if not ylh_login(main_page):
            browser.close()
            sys.exit(1)

        start_pts = get_points(main_page) or 0
        log.info(f"[POINTS] Start: {start_pts}")

        main_page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=30000)
        human_delay(2, 3)

        failures = 0
        while total < MAX_LIKES:
            log.info(f"[Like #{total+1}/{MAX_LIKES}]")
            try:
                main_page.reload(wait_until="domcontentloaded", timeout=30000)
                human_delay(2, 3)
            except Exception:
                pass

            if do_one_like(main_page, context):
                total += 1
                failures = 0
                curr = get_points(main_page)
                if curr:
                    log.info(f"[STATS] Likes: {total} | Points: {curr} | +{curr - start_pts}")
            else:
                failures += 1
                if failures >= 3:
                    log.warning("[WARN] 3 failures, stopping session")
                    break

            # Next like se pehle: 1-10 sec random wait (har baar alag)
            next_wait = random.uniform(1, 10)
            log.info(f"[WAIT] Next like se pehle {next_wait:.1f}s...")
            time.sleep(next_wait)

        duration = datetime.now() - start
        log.info(f"[DONE] Session complete: {total} likes in {duration}")
        browser.close()


if __name__ == "__main__":
    run()
