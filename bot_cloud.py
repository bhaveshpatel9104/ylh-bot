"""
YouLikeHits Bot - GitHub Actions Continuous Mode
=================================================
Continuously likes videos until GitHub Actions timeout.
Har 6 ghante mein naya session automatically start hota hai.
"""

import time
import random
import logging
import os
import sys
import json
from datetime import datetime
from playwright.sync_api import sync_playwright

# ---- Credentials from GitHub Secrets ----
YLH_LOGIN_ID    = os.environ.get("YLH_LOGIN_ID",    "patelbhavesh9130@gmail.com")
YLH_PASSWORD    = os.environ.get("YLH_PASSWORD",    "BHAVESH91045678VV")
GOOGLE_EMAIL    = os.environ.get("GOOGLE_EMAIL",    "patelbhavesh9130@gmail.com")
GOOGLE_PASSWORD = os.environ.get("GOOGLE_PASSWORD", "BHAVESH9104V")
YLH_USERNAME    = os.environ.get("YLH_USERNAME",    "bhavesh647383")
GOOGLE_COOKIES  = os.environ.get("GOOGLE_COOKIES",  "")

YLH_LOGIN_URL         = "https://www.youlikehits.com/login.php"
YLH_YOUTUBE_LIKES_URL = "https://www.youlikehits.com/youtubelikes.php"

# Logging
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
    if GOOGLE_COOKIES:
        try:
            cookies = json.loads(GOOGLE_COOKIES)
            context.add_cookies(cookies)
            log.info(f"[OK] Google cookies loaded! ({len(cookies)} cookies)")
            page = context.new_page()
            page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)
            log.info("[OK] YouTube session active via cookies!")
            page.close()
            return
        except Exception as e:
            log.error(f"[ERROR] Cookie load failed: {e}")

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


def do_one_like(page, context, seen_videos: set) -> str:
    """
    Returns:
      'ok'   - like successful
      'skip' - duplicate video skipped
      'fail' - some error
      'novid'- no videos available
    """
    yt_video_id = ""
    try:
        content = page.content()
        if "No videos" in content or "come back later" in content.lower():
            return 'novid'

        # Step 1: Click followbutton
        follow_btn = None
        try:
            follow_btn = page.wait_for_selector("a.followbutton", timeout=8000)
        except Exception:
            pass
        if not follow_btn:
            # Check WHY followbutton nahi mila
            page_content = page.content().lower()
            title = page.title()
            log.warning(f"[WARN] followbutton nahi mila | Title: {title[:50]}")
            # Detect various "no more videos" states
            if any(x in page_content for x in [
                "no videos", "come back", "no more", "queue", "ran out",
                "start liking", "login", "sign in"
            ]):
                log.info("[WAIT] No videos/session issue detected - novid return")
                return 'novid'
            return 'fail'

        follow_btn.click()
        human_delay(2, 3)

        # Step 2: Click earn-btn
        earn_btn = None
        try:
            earn_btn = page.wait_for_selector("a.earn-btn", timeout=8000)
        except Exception:
            pass
        if not earn_btn:
            log.warning("[WARN] earn-btn nahi mila")
            return 'fail'

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
            return 'fail'

        try:
            yt_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            human_delay(4, 5)

        yt_url = yt_page.url
        if "watch?v=" in yt_url:
            yt_video_id = yt_url.split("watch?v=")[1].split("&")[0]

        log.info(f"  >> YouTube: {yt_url[:70]} | ID: {yt_video_id}")

        # DUPLICATE CHECK
        if yt_video_id and yt_video_id in seen_videos:
            log.warning(f"  [SKIP] Video {yt_video_id} already liked - skipping!")
            yt_page.close()
            page.bring_to_front()
            try:
                skip_link = page.wait_for_selector("text=Skip", timeout=3000)
                if skip_link:
                    skip_link.click()
                    log.info("  [SKIP] YLH Skip link clicked!")
                    human_delay(2, 3)
            except Exception:
                page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=20000)
                human_delay(2, 3)
            return 'skip'

        # YouTube scroll
        try:
            yt_page.mouse.wheel(0, random.randint(200, 500))
            time.sleep(random.uniform(0.5, 1.5))
            yt_page.mouse.wheel(0, random.randint(-100, -50))
        except Exception:
            pass

        # YouTube Like - check if already liked
        liked = False
        already_liked = False

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
                    if pressed == "true":
                        log.warning("  [WARN] Video YouTube pe already liked hai - skipping!")
                        already_liked = True
                    else:
                        btn.scroll_into_view_if_needed()
                        human_delay(0.5, 1)
                        btn.click()
                        log.info("  [OK] YouTube liked! (fresh)")
                        liked = True
                    break
            except Exception:
                continue

        if not liked and not already_liked:
            try:
                js_result = yt_page.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('button');
                        for (const b of btns) {
                            const label = (b.getAttribute('aria-label') || '').toLowerCase();
                            if (label.includes('like') && !label.includes('dislike')) {
                                const wasLiked = b.getAttribute('aria-pressed') === 'true';
                                if (!wasLiked) b.click();
                                return wasLiked ? 'already_liked: ' + label : 'ok: ' + label;
                            }
                        }
                        return 'not_found';
                    }
                """)
                if js_result.startswith('already_liked:'):
                    log.warning(f"  [WARN] Already liked (JS): {js_result}")
                    already_liked = True
                elif js_result.startswith('ok:'):
                    log.info(f"  [OK] YouTube like JS: {js_result}")
                    liked = True
            except Exception:
                pass

        # Already liked on YouTube - YLH pe Skip karo, confirm mat karo
        if already_liked:
            yt_page.close()
            page.bring_to_front()
            log.info("  [SKIP] Already liked - YLH pe Skip click kar raha hoon...")
            try:
                skip_link = page.wait_for_selector("text=Skip", timeout=3000)
                if skip_link:
                    skip_link.click()
                    human_delay(2, 3)
            except Exception:
                page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=20000)
                human_delay(2, 3)
            return 'skip'


        human_delay(2, 4)
        yt_page.close()
        page.bring_to_front()

        # Pre-confirm wait
        pre_confirm = random.uniform(3, 7)
        log.info(f"  >> Pre-confirm wait: {pre_confirm:.1f}s")
        time.sleep(pre_confirm)

        # Click confirm
        for sel in ['#ylhManualBtn', 'button:has-text("done")', 'button:has-text("check now")']:
            try:
                btn = page.wait_for_selector(sel, timeout=6000)
                if btn:
                    try:
                        box = btn.bounding_box()
                        if box:
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

        # Post-confirm wait
        post_confirm = random.uniform(8, 15)
        log.info(f"  >> Post-confirm wait: {post_confirm:.1f}s (anti-detection)")
        time.sleep(post_confirm)

        # Sync wait
        try:
            page.wait_for_selector("text=Syncing", timeout=8000)
            page.wait_for_selector("text=Syncing", state="hidden", timeout=30000)
            log.info("  [OK] Sync done!")
        except Exception:
            human_delay(5, 8)

        # Track video
        if yt_video_id:
            seen_videos.add(yt_video_id)
            log.info(f"  [TRACK] {yt_video_id} tracked ({len(seen_videos)} total)")

        return 'ok'

    except Exception as e:
        log.error(f"[ERROR] do_one_like: {e}")
        return 'fail'


def run():
    log.info("=" * 50)
    log.info("[BOT] GitHub Actions - Continuous Mode (no stop)")
    log.info(f"[BOT] Account: {YLH_LOGIN_ID}")
    log.info("=" * 50)

    start = datetime.now()
    total_likes = 0
    start_pts = 0

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

        seen_videos = set()
        consecutive_fails = 0
        consecutive_no_vid = 0
        round_num = 1

        log.info("[BOT] Continuous loop shuru - GitHub timeout tak chalega!")

        while True:
            result = do_one_like(main_page, context, seen_videos)

            if result == 'ok':
                total_likes += 1
                consecutive_fails = 0
                consecutive_no_vid = 0
                curr = get_points(main_page)
                elapsed = datetime.now() - start
                if curr:
                    log.info(f"[STATS] Round {round_num} | Likes: {total_likes} | Points: {curr} | +{curr - start_pts} | Time: {elapsed}")
                # Grid view pe wapas jaao (followbutton ke liye)
                try:
                    main_page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=20000)
                    human_delay(2, 3)
                except Exception:
                    pass
                # Next like wait
                time.sleep(random.uniform(1, 5))


            elif result == 'skip':
                consecutive_fails = 0
                consecutive_no_vid = 0
                # Grid pe wapas jaao (skip ke baad bhi followbutton chahiye)
                try:
                    main_page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=20000)
                    human_delay(2, 3)
                except Exception:
                    pass
                time.sleep(random.uniform(1, 3))

            elif result == 'novid':
                consecutive_no_vid += 1
                log.info(f"[WAIT] No videos available (#{consecutive_no_vid}) - 5 min wait...")
                if consecutive_no_vid >= 3:
                    # Reset seen videos - purane videos phir available ho sakte hain
                    log.info("[RESET] seen_videos reset kar raha hoon - naye videos ke liye")
                    seen_videos = set()
                    consecutive_no_vid = 0
                    round_num += 1
                time.sleep(300)  # 5 min wait
                # Reload page
                try:
                    main_page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=30000)
                    human_delay(2, 3)
                except Exception:
                    pass

            elif result == 'fail':
                consecutive_fails += 1
                log.warning(f"[WARN] Fail #{consecutive_fails}")
                if consecutive_fails >= 5:
                    log.warning("[WARN] 5 consecutive fails - page reload kar raha hoon")
                    consecutive_fails = 0
                    try:
                        main_page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=30000)
                        human_delay(3, 5)
                    except Exception:
                        pass
                time.sleep(random.uniform(5, 15))

        # This line never reached - GitHub Actions kills after timeout
        browser.close()


if __name__ == "__main__":
    run()
