"""
YouLikeHits Bot - GitHub Actions Multi-Account Mode
====================================================
Har account ki 120 daily like limit achive hone ke baad
agle account pe switch karta hai.
Accounts: 5 (120 × 5 = 600 points/day max)
"""

import time
import random
import logging
import os
import sys
import json
from datetime import datetime
from playwright.sync_api import sync_playwright

# ---- All 5 Accounts ----
ACCOUNTS = [
    {
        "num":    1,
        "email":  "patelbhavesh9130@gmail.com",
        "password": "BHAVESH91045678VV",
        "cookies_env": "GOOGLE_COOKIES",
    },
    {
        "num":    2,
        "email":  "222lovable222@gmail.com",
        "password": "BHAVESH91045678VV",
        "cookies_env": "GOOGLE_COOKIES_2",
    },
    {
        "num":    3,
        "email":  "anti46286@gmail.com",
        "password": "BHAVESH91045678VV",
        "cookies_env": "GOOGLE_COOKIES_3",
    },
    {
        "num":    4,
        "email":  "vercal400@gmail.com",
        "password": "BHAVESH91045678VV",
        "cookies_env": "GOOGLE_COOKIES_4",
    },
    {
        "num":    5,
        "email":  "a31949377@gmail.com",
        "password": "BHAVESH91045678VV",
        "cookies_env": "GOOGLE_COOKIES_5",
    },
]

YLH_LOGIN_URL         = "https://www.youlikehits.com/login.php"
YLH_YOUTUBE_LIKES_URL = "https://www.youlikehits.com/youtubelikes.php"
YLH_YOUTUBE_VIEWS_URL = "https://www.youlikehits.com/youtubenew2.php"

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


def google_login(context, cookies_json):
    if cookies_json:
        try:
            cookies = json.loads(cookies_json)
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
    log.warning("[WARN] No cookies - skipping Google login")


def ylh_login(page, email, password) -> bool:
    log.info("[LOGIN] YouLikeHits login kar raha hoon...")
    try:
        page.goto(YLH_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        human_delay(1.5, 2.5)
        page.wait_for_selector("#username", timeout=10000)
        page.fill("#username", email)
        human_delay(0.4, 0.8)
        page.wait_for_selector("#password", timeout=10000)
        page.fill("#password", password)
        human_delay(0.5, 1)
        page.click('input[type="submit"]')
        human_delay(2.5, 4)
        content = page.content()
        if "Logout" in content or "My Account" in content:
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


DAILY_LIMIT = 120  # YLH daily like limit


def do_one_view(views_page, context, seen_views: set) -> str:
    """
    Returns:
      'ok'             - view successful, points earned
      'skip'           - already viewed
      'fail'           - error
      'novid'          - no videos available
      'view_hour_limit'  - hourly view limit reached
      'view_daily_limit' - daily view limit reached
    """
    import re
    try:
        content = views_page.content()

        # Limit detection for views
        if "view limit" in content.lower() or "viewing limit" in content.lower():
            if "hourly" in content.lower() or "per hour" in content.lower():
                log.warning("[VIEW_LIMIT] Hourly view limit reached!")
                return 'view_hour_limit'
            else:
                log.warning("[VIEW_LIMIT] Daily view limit reached!")
                return 'view_daily_limit'

        if "No videos" in content or "come back" in content.lower():
            return 'novid'

        # Find View button - confirmed selector: a.earn-btn
        view_btn = None
        try:
            view_btn = views_page.wait_for_selector("a.earn-btn", timeout=8000)
        except Exception:
            pass
        if not view_btn:
            log.warning("[VIEW] No earn-btn found")
            page_text = views_page.inner_text("body")[:200]
            log.warning(f"[VIEW] Page snippet: {page_text}")
            return 'novid'

        # Click View → YouTube opens in new tab
        try:
            with context.expect_page(timeout=8000) as new_page_info:
                view_btn.click()
            yt_page = new_page_info.value
            yt_page.wait_for_load_state("domcontentloaded", timeout=15000)
            yt_url = yt_page.url
        except Exception as e:
            log.warning(f"[VIEW] New tab error: {e}")
            # Maybe no new tab - just wait
            yt_page = None
            yt_url = ""

        # Extract YouTube video ID
        yt_id = ""
        match = re.search(r'v=([a-zA-Z0-9_-]+)', yt_url)
        if match:
            yt_id = match.group(1)
        log.info(f"[VIEW] Video: {yt_url[:60]} | ID: {yt_id}")

        # Wait 3s for timer to appear on YLH page after click
        time.sleep(3)

        # Read required watch time from body text: "Watching X / Y s"
        watch_seconds = 180  # default
        try:
            page_text = views_page.inner_text("body") or ""
            m = re.search(r'Watching\s+\d+\s*/\s*(\d+)\s*s', page_text)
            if m:
                watch_seconds = int(m.group(1))
                log.info(f"[VIEW] Timer: {watch_seconds}s")
            else:
                log.warning(f"[VIEW] Timer not found in page - using default {watch_seconds}s")
        except Exception as e:
            log.warning(f"[VIEW] Timer read error: {e} - using {watch_seconds}s")

        # Wait for timer + 10s buffer
        wait_time = watch_seconds + 10
        log.info(f"[VIEW] Waiting {wait_time}s (timer={watch_seconds}s)...")
        time.sleep(wait_time)

        # Close YouTube tab
        if yt_page:
            try:
                yt_page.close()
            except Exception:
                pass

        # Check for "Points Added!" on YLH page
        try:
            content = views_page.content()
            if "Points Added" in content:
                m = re.search(r'(\d+)\s*Points Added', content)
                pts = m.group(1) if m else "?"
                log.info(f"[VIEW] ✓ +{pts} pts earned! Video: {yt_id}")
            else:
                log.info(f"[VIEW] Done (no pts confirm). Video: {yt_id}")
        except Exception:
            pass

        if yt_id:
            seen_views.add(yt_id)
        return 'ok'

    except Exception as e:
        log.error(f"[ERROR] do_one_view: {e}")
        return 'fail'


def run_views_session(account: dict, duration_seconds: int = 3600) -> None:
    """Run views for an account for up to duration_seconds."""
    acc_num   = account["num"]
    acc_email = account["email"]
    cookies_json = os.environ.get(account["cookies_env"], "")

    if not cookies_json:
        return

    log.info(f"[VIEWS] Account {acc_num} ({acc_email}) - {duration_seconds//60} min session")
    deadline = time.time() + duration_seconds
    seen_views = set()
    view_count = 0
    fail_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        google_login(context, cookies_json)
        human_delay(2, 3)

        views_page = context.new_page()
        # YLH login required!
        acc_password = account["password"]
        if not ylh_login(views_page, acc_email, acc_password):
            log.error(f"[VIEWS] YLH login failed for Account {acc_num}")
            browser.close()
            return
        human_delay(1, 2)

        try:
            views_page.goto(YLH_YOUTUBE_VIEWS_URL, wait_until="domcontentloaded", timeout=20000)
            human_delay(2, 3)
        except Exception:
            browser.close()
            return

        while time.time() < deadline:
            result = do_one_view(views_page, context, seen_views)

            if result == 'ok':
                view_count += 1
                fail_count = 0
                log.info(f"[VIEWS] Acc {acc_num}: {view_count} views done")
                # YLH auto-refreshes to next video after points credited
                # Just wait a few seconds for next card to load
                human_delay(3, 5)

            elif result in ('view_hour_limit', 'view_daily_limit'):
                log.info(f"[VIEWS] Acc {acc_num}: {result} - stopping views")
                break

            elif result == 'novid':
                log.info(f"[VIEWS] Acc {acc_num}: No videos - 2 min wait")
                time.sleep(120)
                try:
                    views_page.goto(YLH_YOUTUBE_VIEWS_URL, wait_until="domcontentloaded", timeout=20000)
                    human_delay(2, 3)
                except Exception:
                    pass

            elif result == 'fail':
                fail_count += 1
                if fail_count >= 3:
                    log.warning(f"[VIEWS] Acc {acc_num}: 3 fails - stopping")
                    break
                time.sleep(30)

        browser.close()
    log.info(f"[VIEWS] Acc {acc_num} session done: {view_count} total views")


def do_one_like(page, context, seen_videos: set) -> str:
    """
    Returns:
      'ok'    - like successful (points earned)
      'ok0'   - like done but 0 points (already liked before)
      'skip'      - duplicate video skipped
      'fail'      - some error
      'novid'     - no videos available
      'hour_limit'  - hourly 30 limit reached (1 hr wait)
      'daily_limit' - daily 120 limit reached (next account)
    """
    yt_video_id = ""
    try:
        content = page.content()
        # Limit check - hourly vs daily
        if "Like Limit Reached" in content or "like limit" in content.lower():
            if "hourly" in content.lower() or "per hour" in content.lower() or "30 videos" in content:
                log.warning("[HOUR_LIMIT] Hourly 30 limit! 65 min baad wapas aayenge.")
                return 'hour_limit'
            else:
                log.warning("[DAILY_LIMIT] Daily 120 limit! Next account pe ja rahe hain.")
                return 'daily_limit'
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

        # DUPLICATE CHECK - verify on YouTube first (don't blindly skip!)
        if yt_video_id and yt_video_id in seen_videos:
            log.warning(f"  [DUP] Video {yt_video_id} seen before - YouTube pe verify kar raha hoon...")
            # Check if video is ACTUALLY liked on YouTube
            actually_liked = False
            try:
                yt_page.wait_for_load_state("domcontentloaded", timeout=10000)
                for sel in [
                    'button[aria-label*="like this video"]',
                    'button[aria-label*="Like this video"]',
                    '#segmented-like-button button',
                ]:
                    try:
                        btn = yt_page.wait_for_selector(sel, timeout=3000)
                        if btn:
                            actually_liked = (btn.get_attribute("aria-pressed") == "true")
                            break
                    except Exception:
                        continue
                if not actually_liked:
                    # JS fallback check
                    result = yt_page.evaluate("""
                        () => {
                            const btns = document.querySelectorAll('button');
                            for (const b of btns) {
                                const label = (b.getAttribute('aria-label') || '').toLowerCase();
                                if (label.includes('like') && !label.includes('dislike')) {
                                    return b.getAttribute('aria-pressed') === 'true';
                                }
                            }
                            return false;
                        }
                    """)
                    actually_liked = bool(result)
            except Exception as e:
                log.warning(f"  [DUP] YouTube check error: {e} - skipping to be safe")
                actually_liked = True  # safe fallback

            if actually_liked:
                log.info(f"  [DUP] {yt_video_id} YouTube pe liked hai - YLH Skip")
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
            else:
                log.info(f"  [DUP] {yt_video_id} YouTube pe liked NAHI! Like karke points earn karte hain!")
                seen_videos.discard(yt_video_id)  # Allow re-tracking
                # Continue to like logic below (don't return here)


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


def run_account(account: dict) -> str:
    """
    Ek account chalao.
    Returns: 'limit' - daily limit reached, 'done' - 120 likes complete, 'error' - login fail
    """
    acc_num   = account["num"]
    acc_email = account["email"]
    acc_pass  = account["password"]
    cookies_json = os.environ.get(account["cookies_env"], "")

    log.info("=" * 50)
    log.info(f"[ACCOUNT {acc_num}/5] {acc_email}")
    log.info("=" * 50)

    if not cookies_json:
        log.warning(f"[SKIP] Account {acc_num}: GOOGLE_COOKIES_{acc_num} not set - skipping!")
        return 'skip'

    start = datetime.now()
    total_likes = 0

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

        google_login(context, cookies_json)
        human_delay(2, 3)

        main_page = context.new_page()
        if not ylh_login(main_page, acc_email, acc_pass):
            browser.close()
            return 'error'

        start_pts = get_points(main_page) or 0
        log.info(f"[POINTS] Start: {start_pts}")

        main_page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=30000)
        human_delay(2, 3)

        seen_videos = set()
        consecutive_fails = 0
        consecutive_no_vid = 0
        round_num = 1
        daily_likes = 0      # Points earn karne wale likes
        prev_pts = start_pts

        log.info(f"[BOT] Continuous loop - Daily limit: {DAILY_LIMIT} likes")

        while True:
            result = do_one_like(main_page, context, seen_videos)

            if result == 'hour_limit':
                curr = get_points(main_page)
                log.info(f"[ACC {acc_num}] Hourly limit! Earned: {daily_likes} likes so far.")
                browser.close()
                return 'hour_limit'

            elif result == 'daily_limit':
                curr = get_points(main_page)
                log.info(f"[ACC {acc_num}] Daily limit done! Total: {daily_likes} likes.")
                browser.close()
                return 'daily_limit'

            elif result == 'ok':
                total_likes += 1
                consecutive_fails = 0
                consecutive_no_vid = 0
                curr = get_points(main_page)
                elapsed = datetime.now() - start
                # Check if points actually earned
                if curr and curr > prev_pts:
                    daily_likes += 1
                    log.info(f"[STATS] Like #{daily_likes}/{DAILY_LIMIT} | Points: {curr} | +{curr - start_pts} | Time: {elapsed}")
                    prev_pts = curr
                    if daily_likes >= DAILY_LIMIT:
                        log.info(f"[ACC {acc_num}] {DAILY_LIMIT} likes done! Next account...")
                        browser.close()
                        return 'done'
                else:
                    log.info(f"[STATS] Like done (no pts) | Total: {total_likes} | Daily earned: {daily_likes}/{DAILY_LIMIT}")
                # Grid view pe wapas jaao
                try:
                    main_page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=20000)
                    human_delay(2, 3)
                except Exception:
                    pass
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

        # Timeout ya unexpected exit
        browser.close()
        return 'hour_limit'


def run():
    """Round-robin: 5 accounts, hourly cooldown, daily tracking."""
    from datetime import timedelta
    HOUR_COOLDOWN_MINS = 65  # 65 min baad retry

    log.info("=" * 50)
    log.info("[BOT] Round-Robin Mode - 5 accounts")
    log.info("[BOT] Hourly: 30/acc | Daily: 120/acc | Max: 600/day")
    log.info("=" * 50)

    # State per account
    states = {}
    for acc in ACCOUNTS:
        states[acc['num']] = {
            'account': acc,
            'daily_done': False,
            'cooldown_until': None,
            'has_cookies': bool(os.environ.get(acc['cookies_env'], '')),
        }

    while True:
        now = datetime.now()

        # Available: has cookies, not daily done, not on cooldown
        available = [
            s for s in states.values()
            if s['has_cookies']
            and not s['daily_done']
            and (s['cooldown_until'] is None or now >= s['cooldown_until'])
        ]

        if not available:
            # Check future availability
            future = [
                s for s in states.values()
                if s['has_cookies'] and not s['daily_done']
            ]
            if not future:
                log.info("=" * 50)
                log.info("[DONE] Sabhi 5 accounts ki daily limit ho gayi!")
                log.info("[DONE] Kal subah phir se chalu hoga!")
                log.info("=" * 50)
                break

            # Instead of sleeping, run VIEWS for all accounts!
            cooldowns = [s['cooldown_until'] for s in future if s['cooldown_until']]
            if cooldowns:
                next_wake = min(cooldowns)
                wait_secs = max((next_wake - now).total_seconds(), 0)
                log.info(f"[VIEWS] All likes on cooldown - switching to Views!")
                log.info(f"[VIEWS] Running views for {int(wait_secs/60)} min until {next_wake.strftime('%H:%M')}")

                # Run views for each account during cooldown
                view_duration = max(int(wait_secs) - 60, 60)  # 60s buffer
                for s in future:
                    acc_view = s['account']
                    log.info(f"[VIEWS] Starting Account {acc_view['num']} views ({view_duration//60} min)...")
                    run_views_session(acc_view, duration_seconds=view_duration)
                    if time.time() >= next_wake.timestamp():
                        break  # Time to go back to likes
            else:
                time.sleep(120)
            continue

        # Run next available account
        state = available[0]
        acc = state['account']

        log.info(f"\n>>> Account {acc['num']}/5: {acc['email']}")
        result = run_account(acc)

        if result == 'hour_limit':
            state['cooldown_until'] = datetime.now() + timedelta(minutes=HOUR_COOLDOWN_MINS)
            log.info(f"[COOL] Account {acc['num']} cooldown until {state['cooldown_until'].strftime('%H:%M')}")
        elif result in ('daily_limit', 'done'):
            state['daily_done'] = True
            log.info(f"[DAILY] Account {acc['num']} daily done!")
        elif result == 'error':
            log.error(f"[ERROR] Account {acc['num']} login failed - skipping")
            state['daily_done'] = True  # Skip this account

        time.sleep(5)


if __name__ == "__main__":
    run()
