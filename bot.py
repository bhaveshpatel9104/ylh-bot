"""
YouLikeHits YouTube Likes Automation Bot
=========================================
Yeh bot automatically YouTube videos ko like karke
YouLikeHits pe points earn karta hai -- HAMESHA chalta rehta hai.

Usage:
    python bot.py

Band karne ke liye: Ctrl+C dabao ya window close karo.
"""

import time
import random
import logging
import os
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

import config

# ---- Fix Windows console Unicode issue ----
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ---- Logging Setup ----

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ---- Helpers ----

def human_delay(min_s: float = None, max_s: float = None):
    """Random human-like delay"""
    mn = min_s if min_s is not None else config.MIN_DELAY
    mx = max_s if max_s is not None else config.MAX_DELAY
    t = random.uniform(mn, mx)
    time.sleep(t)


# ---- Google / YouTube Login ----

def google_login(context):
    """Google account mein login -- YouTube likes ke liye"""
    log.info("[LOGIN] Google/YouTube login kar raha hoon...")
    page = context.new_page()
    try:
        # Go to YouTube directly -- it will redirect to Google login if needed
        page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=30000)
        human_delay(2, 3)

        # Check if already logged in
        content = page.content()
        if config.GOOGLE_EMAIL.split("@")[0].lower() in content.lower() or \
           "avatar" in content.lower():
            log.info("[OK] Already logged in to Google!")
            page.close()
            return

        # Click Sign In button on YouTube
        try:
            sign_in_btn = page.wait_for_selector(
                'a[href*="accounts.google.com"], yt-button-renderer:has-text("Sign in"), '
                'a:has-text("Sign in")',
                timeout=8000
            )
            if sign_in_btn:
                sign_in_btn.click()
                human_delay(2, 3)
        except Exception:
            # Go directly to Google accounts
            page.goto(
                "https://accounts.google.com/v3/signin/identifier?flowName=GlifWebSignIn",
                wait_until="domcontentloaded", timeout=30000
            )
            human_delay(2, 3)

        # Email field -- try multiple selectors
        email_filled = False
        for sel in ['input[type="email"]', '#identifierId', 'input[name="identifier"]']:
            try:
                el = page.wait_for_selector(sel, timeout=8000)
                if el:
                    el.click()
                    human_delay(0.3, 0.6)
                    el.type(config.GOOGLE_EMAIL, delay=80)
                    email_filled = True
                    break
            except Exception:
                continue

        if not email_filled:
            log.warning("[WARN] Google email field nahi mila")
            page.close()
            return

        human_delay(0.5, 1)
        page.keyboard.press("Enter")
        human_delay(2.5, 4)

        # Password field
        pass_filled = False
        for sel in ['input[type="password"]', 'input[name="password"]', '#password input']:
            try:
                el = page.wait_for_selector(sel, timeout=10000)
                if el:
                    el.click()
                    human_delay(0.3, 0.6)
                    el.type(config.GOOGLE_PASSWORD, delay=80)
                    pass_filled = True
                    break
            except Exception:
                continue

        if not pass_filled:
            log.warning("[WARN] Google password field nahi mila -- 2FA ya CAPTCHA ho sakta hai")
            page.close()
            return

        human_delay(0.5, 1)
        page.keyboard.press("Enter")
        human_delay(4, 6)

        current_url = page.url
        if "myaccount.google.com" in current_url or "youtube.com" in current_url \
                or "google.com" in current_url:
            log.info("[OK] Google login successful!")
        else:
            log.warning(f"[WARN] Google URL: {current_url} -- check karo agar CAPTCHA/2FA hai")

    except Exception as e:
        log.error(f"[ERROR] Google login error: {e}")
    finally:
        try:
            page.close()
        except Exception:
            pass


# ---- YouLikeHits Login ----

def ylh_login(page) -> bool:
    """YouLikeHits mein email se login karta hai"""
    log.info("[LOGIN] YouLikeHits login kar raha hoon...")
    try:
        page.goto(config.YLH_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        human_delay(1.5, 2.5)

        # Fill username using ID selector (not name)
        page.wait_for_selector("#username", timeout=10000)
        page.fill("#username", config.YLH_LOGIN_ID)
        human_delay(0.4, 0.8)

        page.wait_for_selector("#password", timeout=10000)
        page.fill("#password", config.YLH_PASSWORD)
        human_delay(0.5, 1)

        # Submit
        page.click('input[type="submit"]')
        human_delay(2.5, 4)

        # Verify login success
        content = page.content()
        if "Logout" in content or "My Account" in content or \
           config.YLH_USERNAME in content or "Earn Points" in content:
            log.info("[OK] YouLikeHits login successful!")
            return True

        if "login" in page.url.lower():
            log.error("[ERROR] YouLikeHits login fail -- credentials check karo")
            return False

        log.info("[OK] YouLikeHits login complete!")
        return True

    except Exception as e:
        log.error(f"[ERROR] YouLikeHits login error: {e}")
        return False



# ---- Points Parser ----

def get_current_points(page) -> int | None:
    """Current points balance fetch karta hai"""
    try:
        el = page.query_selector("text=/\\d+ Points/")
        if el:
            text = el.text_content()
            pts = ''.join(filter(str.isdigit, text.split("Points")[0].strip()))
            return int(pts) if pts else None
    except Exception:
        pass
    return None


# ---- Process One Like ----

def process_one_like(page, context) -> bool:
    """
    Ek complete like cycle:
    1. Grid pe 'Like' button click (a.followbutton)
    2. Detail view mein 'Like Video' click (a.earn-btn) -> YouTube tab opens
    3. YouTube pe like karo
    4. YouLikeHits pe confirm karo
    5. Points earn!
    """
    try:
        # Check agar videos available hain
        content = page.content()
        if "No videos" in content or "come back later" in content.lower():
            log.info("[INFO] Abhi koi video available nahi. 60s wait...")
            time.sleep(60)
            return False

        # ---- Step 1: Grid pe 'Like' button click karo (a.followbutton) ----
        log.info("  >> Grid 'Like' button dhund raha hoon...")
        follow_btn = None
        try:
            follow_btn = page.wait_for_selector("a.followbutton", timeout=8000)
        except Exception:
            pass

        if not follow_btn:
            log.warning("  [WARN] 'Like' (followbutton) nahi mila page pe.")
            return False

        follow_btn.click()
        human_delay(2, 3)
        log.info("  >> 'Like' clicked! Detail view load ho raha hai...")

        # ---- Step 2: Detail view mein 'Like Video' button (a.earn-btn) ----
        earn_btn = None
        try:
            earn_btn = page.wait_for_selector("a.earn-btn", timeout=8000)
        except Exception:
            pass

        if not earn_btn:
            log.warning("  [WARN] 'Like Video' (earn-btn) nahi mila.")
            return False

        log.info("  >> 'Like Video' click kar raha hoon...")

        # ---- Step 3: Click earn-btn -> YouTube tab opens ----
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
            log.warning("  [WARN] YouTube tab nahi khula.")
            return False

        try:
            yt_page.wait_for_load_state("domcontentloaded", timeout=20000)
        except Exception:
            pass

        yt_url = yt_page.url
        log.info(f"  >> YouTube: {yt_url[:70]}")
        human_delay(3, 5)

        # ---- Step 4: YouTube Like karo ----
        liked = False

        # Wait for YouTube page to fully load
        try:
            yt_page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            human_delay(3, 4)

        yt_like_selectors = [
            # New YouTube UI (2024+)
            'button[aria-label*="like this video"]',
            'button[aria-label*="Like this video"]',
            'button[aria-label*="Like"][aria-label*="video"]',
            # Segmented like button
            '#segmented-like-button button',
            '#segmented-like-button yt-button-shape button',
            # Legacy selectors
            'ytd-toggle-button-renderer#segmented-like-button button',
            'ytd-segmented-like-dislike-button-renderer button:first-child',
            # Generic like button
            'yt-button-shape button[title*="like"]',
            'button.yt-spec-button-shape-next[aria-label*="like"]',
        ]
        for sel in yt_like_selectors:
            try:
                btn = yt_page.wait_for_selector(sel, timeout=4000)
                if btn:
                    pressed = btn.get_attribute("aria-pressed")
                    if pressed == "true":
                        log.info("  [INFO] Already liked hai yeh video")
                        liked = True
                        break
                    btn.scroll_into_view_if_needed()
                    human_delay(0.5, 1)
                    btn.click()
                    human_delay(1.5, 2.5)
                    log.info("  [OK] YouTube Like kiya!")
                    liked = True
                    break
            except Exception:
                continue

        # JS fallback -- find any like button
        if not liked:
            try:
                result = yt_page.evaluate("""
                    () => {
                        // Try aria-label containing 'like'
                        const btns = document.querySelectorAll('button');
                        for (const b of btns) {
                            const label = (b.getAttribute('aria-label') || '').toLowerCase();
                            if (label.includes('like') && !label.includes('dislike')) {
                                const pressed = b.getAttribute('aria-pressed');
                                if (pressed !== 'true') {
                                    b.click();
                                    return 'clicked: ' + label;
                                } else {
                                    return 'already_liked';
                                }
                            }
                        }
                        return 'not_found';
                    }
                """)
                if result and result != 'not_found':
                    log.info(f"  [OK] YouTube Like JS fallback: {result}")
                    liked = True
                else:
                    log.warning("  [WARN] YouTube like button nahi mila -- points anyway milenge")
            except Exception as je:
                log.warning(f"  [WARN] JS fallback error: {je}")

        human_delay(2, 3)
        yt_page.close()

        # ---- Step 5: YouLikeHits pe wapas aa ke confirm karo ----
        page.bring_to_front()
        log.info("  >> YouLikeHits pe confirm kar raha hoon...")
        human_delay(2, 3)

        # STEP 5a: Click "I'm done -- check now" button (#ylhManualBtn) PEHLE
        confirmed = False
        manual_btn_selectors = [
            '#ylhManualBtn',
            'button:has-text("done")',
            'button:has-text("check now")',
            'a:has-text("done")',
            'a[id*="Manual"]',
            'button[id*="Manual"]',
        ]
        for sel in manual_btn_selectors:
            try:
                btn = page.wait_for_selector(sel, timeout=6000)
                if btn:
                    btn.click()
                    log.info("  [OK] 'I'm done - check now' clicked!")
                    confirmed = True
                    break
            except Exception:
                continue

        # STEP 5b: Syncing wait karo
        try:
            page.wait_for_selector("text=Syncing", timeout=8000)
            log.info("  >> Syncing with mothership...")
            page.wait_for_selector("text=Syncing", state="hidden", timeout=30000)
            log.info("  [OK] Sync complete!")
        except Exception:
            human_delay(5, 8)

        # STEP 5c: Any additional confirm buttons
        extra_confirm_selectors = [
            'button:has-text("Confirm")',
            'input[value="Confirm"]',
            'a:has-text("Confirm")',
        ]
        for sel in extra_confirm_selectors:
            try:
                btn = page.wait_for_selector(sel, timeout=5000)
                if btn:
                    btn.click()
                    human_delay(2, 3)
                    log.info("  [OK] Extra confirm clicked!")
                    break
            except Exception:
                continue

        if confirmed:
            log.info("  [DONE] Points earn ho gaye!")
        else:
            log.info("  [INFO] Manual confirm nahi mila -- auto-credited ho sakte hain")


        return True

    except Exception as e:
        log.error(f"  [ERROR] Like process error: {e}")
        return False



# ---- Main Bot Session ----

def run_session() -> int:
    """Ek complete browser session chalata hai."""
    total_likes = 0
    session_start = datetime.now()

    log.info("[BOT] Browser start kar raha hoon...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=config.HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
            ]
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        # Google login
        google_login(context)
        human_delay(2, 3)

        # YouLikeHits login
        main_page = context.new_page()
        if not ylh_login(main_page):
            browser.close()
            log.error("[ERROR] Login fail -- 60s mein retry...")
            return 0

        # Starting points
        starting_pts = get_current_points(main_page) or 0
        log.info(f"[POINTS] Starting points: {starting_pts}")

        # YouTube Likes page pe jao
        main_page.goto(config.YLH_YOUTUBE_LIKES_URL,
                       wait_until="domcontentloaded", timeout=30000)
        human_delay(2, 3)

        log.info("[START] Like loop shuru! (Ctrl+C se band karo)")
        log.info("-" * 60)

        consecutive_failures = 0

        while True:
            # Session limit check
            if config.MAX_LIKES_PER_SESSION > 0 and total_likes >= config.MAX_LIKES_PER_SESSION:
                log.info(f"[DONE] Session limit: {total_likes} likes")
                break

            log.info(f"[Like #{total_likes + 1}] Processing...")

            # Reload for fresh videos
            try:
                main_page.reload(wait_until="domcontentloaded", timeout=30000)
                human_delay(2, 3)
            except Exception:
                pass

            success = process_one_like(main_page, context)

            if success:
                total_likes += 1
                consecutive_failures = 0
                curr_pts = get_current_points(main_page)
                if curr_pts:
                    gained = curr_pts - starting_pts
                    log.info(f"[STATS] Likes: {total_likes} | Points: {curr_pts} | Gained: +{gained}")
                else:
                    log.info(f"[STATS] Likes: {total_likes}")
            else:
                consecutive_failures += 1
                log.warning(f"[FAIL] Failure #{consecutive_failures}/5")

                if consecutive_failures >= 5:
                    log.warning("[RETRY] 5 failures -- re-login kar raha hoon...")
                    time.sleep(30)
                    if not ylh_login(main_page):
                        break
                    main_page.goto(config.YLH_YOUTUBE_LIKES_URL,
                                   wait_until="domcontentloaded", timeout=30000)
                    consecutive_failures = 0

            human_delay()

        duration = datetime.now() - session_start
        log.info(f"[SESSION] {total_likes} likes in {duration}")
        browser.close()

    return total_likes


# ---- Forever Loop (Auto-Restart) ----

def run_forever():
    """Bot hamesha chalta rehta hai -- crash ho toh auto-restart"""
    log.info("=" * 60)
    log.info("[BOT] YouLikeHits Bot -- HAMESHA CHALTA RAHEGA")
    log.info(f"   Account : {config.YLH_LOGIN_ID}")
    log.info(f"   Headless: {config.HEADLESS}")
    log.info(f"   Delay   : {config.MIN_DELAY}-{config.MAX_DELAY}s")
    log.info("=" * 60)

    grand_total = 0

    while True:
        try:
            likes = run_session()
            grand_total += likes
            log.info(f"[RESTART] Session khatam. Grand Total Likes: {grand_total}")
            log.info("[WAIT] 30s baad naya session shuru hoga...")
            time.sleep(30)

        except KeyboardInterrupt:
            log.info(f"[STOP] Bot band kiya. Grand Total Likes: {grand_total}")
            sys.exit(0)

        except Exception as e:
            log.error(f"[CRASH] Session crash: {e}")
            log.info("[WAIT] 60s baad restart hoga...")
            time.sleep(60)


if __name__ == "__main__":
    run_forever()
