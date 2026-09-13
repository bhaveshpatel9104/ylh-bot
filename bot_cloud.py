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


def cookie_filename(acc: dict) -> str:
    num = acc["num"]
    return f"google_cookies{'_'+str(num) if num > 1 else ''}.json"


def get_cookies(acc: dict) -> str:
    """Load cookies: env var (GitHub Actions) OR local JSON file (local test)"""
    val = os.environ.get(acc["cookies_env"], "")
    if val:
        return val
    fname = cookie_filename(acc)
    if os.path.exists(fname):
        with open(fname, encoding="utf-8") as f:
            log.info(f"[LOCAL] Cookies from file: {fname}")
            return f.read()
    return ""


def prepare_cookies(raw):
    now = time.time()
    out = []
    seen = set()
    for c in raw:
        name = c.get("name")
        domain = c.get("domain")
        if not name or not domain:
            continue
        expires = c.get("expires") if c.get("expires") not in (None,) else c.get("expirationDate")
        if expires not in (None, -1, 0, -1.0) and float(expires) < now:
            continue
        same = c.get("sameSite") or "Lax"
        if same in ("no_restriction", "unspecified", "None"):
            same = "None"
        elif same not in ("Strict", "Lax", "None"):
            same = "Lax"
        key = (name, domain, c.get("path") or "/")
        if key in seen:
            continue
        seen.add(key)
        item = {
            "name": name,
            "value": c.get("value", ""),
            "domain": domain,
            "path": c.get("path") or "/",
            "secure": bool(c.get("secure")) or same == "None",
            "httpOnly": bool(c.get("httpOnly")),
            "sameSite": same,
        }
        if expires not in (None, -1, 0, -1.0):
            item["expires"] = float(expires)
        out.append(item)
    return out


def youtube_is_signed_in(page) -> bool:
    """Check if YouTube is signed in. Checks multiple selectors for robustness."""
    try:
        return bool(
            page.evaluate(
                """
                () => {
                    // Method 1: ytcfg LOGGED_IN flag
                    try {
                        if (window.ytcfg && typeof window.ytcfg.get === 'function' && window.ytcfg.get('LOGGED_IN'))
                            return true;
                    } catch (e) {}
                    // Method 2: Modern avatar element (yt-img-shadow)
                    if (document.querySelector('yt-img-shadow#avatar')) return true;
                    // Method 3: Old avatar button
                    if (document.querySelector('#avatar-btn')) return true;
                    // Method 4: Account button
                    if (document.querySelector('button[aria-label*="Account"]')) return true;
                    // Method 5: Account icon in topbar
                    if (document.querySelector('yt-avatar-shape, ytd-avatar-shadow')) return true;
                    // Method 6: Negative check - sign-in button present = NOT logged in
                    if (document.querySelector('a[href*="ServiceLogin"], a[href*="accounts.google.com"]'))
                        return false;
                    // Method 7: No sign-in button visible = likely logged in
                    const bodyText = (document.body && document.body.innerText || '').toLowerCase();
                    if (bodyText.includes('sign in to youtube') || bodyText.includes('sign in to like'))
                        return false;
                    // If avatar selector not found but no sign-in prompt, try ytInitialData
                    try {
                        if (window.ytInitialData && window.ytInitialData.header) return true;
                    } catch(e) {}
                    return false;
                }
                """
            )
        )
    except Exception:
        return False


def save_context_cookies(context, acc):
    """Save fresh cookies after successful login. Works locally AND on GitHub Actions."""
    try:
        cookies = context.cookies()
        # Always save locally if cookie file exists
        fname = cookie_filename(acc) if acc else None
        if fname:
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(cookies, f)
            log.info(f"[OK] Cookies refreshed -> {fname} ({len(cookies)})")

        # On GitHub Actions: auto-update the GitHub Secret with fresh cookies
        if os.environ.get("GITHUB_ACTIONS") and acc:
            _update_github_secret(acc, cookies)
    except Exception as e:
        log.warning(f"[WARN] Cookie save failed: {e}")


def _update_github_secret(acc, cookies):
    """Auto-update GitHub Secret with fresh cookies (permanent session fix)."""
    try:
        import base64, urllib.request
        token = os.environ.get("GITHUB_TOKEN", "")
        repo  = os.environ.get("GITHUB_REPOSITORY", "")
        if not token or not repo:
            return
        acc_num = acc if isinstance(acc, int) else None
        if not acc_num:
            return
        secret_name = "GOOGLE_COOKIES" if acc_num == 1 else f"GOOGLE_COOKIES_{acc_num}"
        # Get repo public key for secret encryption
        api_base = f"https://api.github.com/repos/{repo}"
        req = urllib.request.Request(
            f"{api_base}/actions/secrets/public-key",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            pk_data = json.loads(r.read())
        # Encrypt secret value using PyNaCl if available
        try:
            from nacl import encoding, public
            pk_bytes = base64.b64decode(pk_data["key"])
            pub_key = public.PublicKey(pk_bytes)
            box = public.SealedBox(pub_key)
            encrypted = base64.b64encode(box.encrypt(json.dumps(cookies).encode())).decode()
            update_req = urllib.request.Request(
                f"{api_base}/actions/secrets/{secret_name}",
                data=json.dumps({"encrypted_value": encrypted, "key_id": pk_data["key_id"]}).encode(),
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json",
                         "Content-Type": "application/json"},
                method="PUT"
            )
            urllib.request.urlopen(update_req, timeout=10)
            log.info(f"[OK] GitHub Secret '{secret_name}' auto-updated with fresh cookies!")
        except ImportError:
            log.info("[INFO] PyNaCl not available - Secret auto-update skipped (install PyNaCl for this)")
    except Exception as e:
        log.warning(f"[WARN] GitHub Secret update failed: {e}")

def google_auto_login(context, email: str, password: str) -> bool:
    """
    PERMANENT FIX: Auto-login to Google using email+password.
    Robust: multiple selectors, handles Choose Account page, screenshots on failure.
    """
    import urllib.parse
    log.info(f"[AUTO-LOGIN] Cookies expire -- auto-login for {email}...")
    page = context.new_page()
    try:
        # Navigate with email pre-filled (skips Choose Account page)
        login_url = (
            "https://accounts.google.com/signin/v2/identifier"
            f"?Email={urllib.parse.quote(email)}&hl=en"
            "&flowName=GlifWebSignIn&flowEntry=ServiceLogin"
        )
        page.goto(login_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        # Handle "Choose account" screen
        for txt in ["Use another account", "Use a different account"]:
            try:
                btn = page.locator(f'text="{txt}"')
                if btn.is_visible(timeout=2000):
                    btn.click()
                    time.sleep(2)
                    break
            except Exception:
                pass

        # Enter email - multiple selectors
        EMAIL_SELS = ['#identifierId', 'input[name="identifier"]',
                      'input[type="email"]', 'input[autocomplete="username"]']
        email_ok = False
        for sel in EMAIL_SELS:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=3000):
                    loc.fill(email)
                    email_ok = True
                    log.info(f"[AUTO-LOGIN] Email field: {sel}")
                    break
            except Exception:
                continue

        if not email_ok:
            log.error(f"[AUTO-LOGIN] Email field not found! URL: {page.url}")
            try:
                page.screenshot(path="autologin_debug_email.png")
            except Exception:
                pass
            page.close()
            return False

        page.keyboard.press("Enter")
        time.sleep(3)

        # Enter password - multiple selectors
        PWD_SELS = ['input[type="password"]', 'input[name="password"]',
                    'input[name="Passwd"]', 'input[autocomplete="current-password"]']
        pwd_ok = False
        for sel in PWD_SELS:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=5000):
                    loc.fill(password)
                    pwd_ok = True
                    log.info(f"[AUTO-LOGIN] Password field: {sel}")
                    break
            except Exception:
                continue

        if not pwd_ok:
            log.error(f"[AUTO-LOGIN] Password field not found! URL: {page.url}")
            try:
                page.screenshot(path="autologin_debug_pwd.png")
            except Exception:
                pass
            page.close()
            return False

        page.keyboard.press("Enter")
        time.sleep(6)

        # Handle 2FA / challenge
        url = page.url
        if any(x in url for x in ["challenge", "2sv", "signin/v2/challenge", "selectchallenge"]):
            log.warning(f"[AUTO-LOGIN] 2FA detected for {email} -- waiting 60s...")
            time.sleep(60)

        # Verify on YouTube
        try:
            page.goto("https://www.youtube.com", wait_until="networkidle", timeout=30000)
        except Exception:
            page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=20000)
        time.sleep(5)

        if youtube_is_signed_in(page):
            log.info(f"[AUTO-LOGIN] Login successful for {email}!")
            page.close()
            return True

        page.reload(wait_until="domcontentloaded", timeout=15000)
        time.sleep(3)
        if youtube_is_signed_in(page):
            log.info(f"[AUTO-LOGIN] Login OK (2nd check) for {email}!")
            page.close()
            return True

        log.error(f"[AUTO-LOGIN] Login failed for {email}. URL: {page.url}")
        page.close()
        return False
    except Exception as e:
        log.error(f"[AUTO-LOGIN] Error: {e}")
        try:
            page.close()
        except Exception:
            pass
        return False

def google_login(context, cookies_json, acc=None) -> bool:
    """Return True only if YouTube is signed in AND API session is valid (not 401)."""
    if cookies_json:
        try:
            cookies = prepare_cookies(json.loads(cookies_json))
            context.add_cookies(cookies)
            log.info(f"[OK] Google cookies loaded! ({len(cookies)} cookies)")
        except Exception as e:
            log.error(f"[ERROR] Cookie load failed: {e}")
            cookies_json = ""

    page = context.new_page()
    try:
        try:
            page.goto("https://accounts.google.com", wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)
        except Exception:
            pass
        # networkidle so YouTube JS (ytcfg, avatar) fully initializes
        try:
            page.goto("https://www.youtube.com", wait_until="networkidle", timeout=30000)
        except Exception:
            try:
                page.goto("https://www.youtube.com", wait_until="domcontentloaded", timeout=20000)
            except Exception:
                pass
        time.sleep(5)
        signed_in = youtube_is_signed_in(page)
        if signed_in:
            # PERMANENT FIX: Also verify API session is valid (not just UI)
            log.info("[OK] YouTube SIGNED IN (session real hai)")
            log.info("[CHECK] API session health check...")
            health = yt_session_health_check(page, "jNQXAC9IVRw")  # Oldest YT video
            if health == '401':
                log.error("[SESSION] 401 UNAUTHENTICATED — session revoked by Google!")
                log.error("[SESSION] Yeh tab hota hai jab same cookies alag-alag IPs se use hon.")
                log.error("[SESSION] FIX: Fresh cookies export karo aur GitHub Secret update karo.")
                page.close()
                return False  # Skip this account — session is dead
            elif health == 'ok':
                log.info("[SESSION] API session healthy! (like API working)")
                save_context_cookies(context, acc)
            else:
                log.info("[SESSION] API check inconclusive — proceeding anyway")
            page.close()
            return True

        log.warning("[WARN] YouTube NOT signed in — cookies stale / rejected")

        # PERMANENT FIX: Auto re-login using stored credentials
        acc_email    = acc.get('email', '')    if acc else ''
        acc_password = acc.get('password', '') if acc else ''
        if acc_email and acc_password:
            log.info("[AUTO-LOGIN] Cookies expire ho gayi - auto re-login try kar raha hoon...")
            auto_ok = google_auto_login(context, acc_email, acc_password)
            if auto_ok:
                save_context_cookies(context, acc)  # Save fresh cookies + update GitHub Secret
                page.close()
                return True
            else:
                log.error("[AUTO-LOGIN] Auto-login bhi fail — account skip")
                page.close()
                return False

        if os.environ.get("GITHUB_ACTIONS"):
            page.close()
            return False

        log.warning("[ACTION] Bot wale Chrome window mein YouTube Sign in karo. 3 min wait...")
        deadline = time.time() + 180
        while time.time() < deadline:
            if youtube_is_signed_in(page):
                log.info("[OK] YouTube SIGNED IN (manual login)")
                save_context_cookies(context, acc)
                page.close()
                return True
            remaining = int(deadline - time.time())
            if remaining % 15 == 0:
                log.info(f"  ... waiting for YouTube login ({remaining}s left)")
            time.sleep(1)

        log.error("[ERROR] 3 min mein YouTube login nahi hua — ye account skip")
        page.close()
        return False
    except Exception as e:
        log.error(f"[ERROR] YouTube session check: {e}")
        try:
            page.close()
        except Exception:
            pass
        return False


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

LIKE_BUTTON_SELECTORS = [
    "like-button-view-model button",
    'button[aria-label*="like this video"]',
    'button[aria-label*="Like this video"]',
    "segmented-like-dislike-button-view-model like-button-view-model button",
    "#top-level-buttons-computed like-button-view-model button",
    "ytd-segmented-like-dislike-button-renderer like-button-view-model button",
    "#segmented-like-button button",
]


def extract_video_id(url: str) -> str:
    if not url:
        return ""
    if "watch?v=" in url:
        return url.split("watch?v=")[1].split("&")[0]
    if "/shorts/" in url:
        return url.split("/shorts/")[1].split("?")[0].split("/")[0]
    return ""


def yt_like_state(yt_page) -> str:
    """Liked if any like-button aria-label contains 'unlike this video'. No aria-pressed."""
    try:
        return yt_page.evaluate(
            """
            () => {
                const nodes = document.querySelectorAll(
                    'like-button-view-model button, ytd-segmented-like-dislike-button-renderer button, button[aria-label]'
                );
                for (const b of nodes) {
                    const l = (b.getAttribute('aria-label') || '').toLowerCase();
                    if (!l || l.includes('dislike')) continue;
                    if (l.includes('unlike this video') || l.includes('unlike')) return 'liked';
                    if (l.includes('like this video')) return 'unliked';
                }
                return 'unknown';
            }
            """
        )
    except Exception:
        return "unknown"


def yt_dismiss_overlays(yt_page):
    for sel in [
        'button[aria-label="Accept all"]',
        'button:has-text("Accept all")',
        'button:has-text("I agree")',
        'button:has-text("No thanks")',
        "#dismiss-button button",
        'button[aria-label="Dismiss"]',
    ]:
        try:
            el = yt_page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=800)
                time.sleep(0.4)
        except Exception:
            pass


def yt_skip_ad(yt_page) -> bool:
    for sel in [
        ".ytp-skip-ad-button",
        ".ytp-ad-skip-button-modern",
        ".ytp-ad-skip-button",
        "button.ytp-ad-skip-button-modern",
    ]:
        try:
            el = yt_page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=800)
                log.info("  [YT] Ad skipped")
                return True
        except Exception:
            pass
    return False


def yt_ensure_playing(yt_page):
    try:
        paused = yt_page.evaluate(
            """
            () => {
                const v = document.querySelector('video.html5-main-video, video');
                if (!v) return true;
                v.play().catch(() => {});
                return v.paused;
            }
            """
        )
        if paused:
            player = yt_page.query_selector("#movie_player, video.html5-main-video, video")
            if player:
                box = player.bounding_box()
                if box and box["width"] > 20 and box["height"] > 20:
                    yt_page.mouse.click(
                        box["x"] + box["width"] * 0.5,
                        box["y"] + box["height"] * 0.42,
                    )
    except Exception:
        pass


def yt_signed_out_prompt(yt_page) -> bool:
    try:
        return bool(
            yt_page.evaluate(
                """
                () => {
                    const t = (document.body && document.body.innerText || '').toLowerCase();
                    return t.includes('sign in to like') || t.includes('sign in to youtube');
                }
                """
            )
        )
    except Exception:
        return False


def yt_watch_before_like(yt_page, seconds=None):
    """Play the video and wait so YouTube treats the session as real engagement."""
    yt_dismiss_overlays(yt_page)
    yt_ensure_playing(yt_page)
    watch = seconds if seconds is not None else random.uniform(15, 22)
    log.info(f"  >> Watch before like: {watch:.1f}s")
    end = time.time() + watch
    while time.time() < end:
        yt_skip_ad(yt_page)
        yt_ensure_playing(yt_page)
        time.sleep(1.0)


def yt_click_like(yt_page) -> bool:
    """
    PRIMARY: YouTube internal API like (SAPISIDHASH + fetch) — bypasses button detection.
    FALLBACK: Trusted Playwright mouse.click() on visible like button.
    """
    # ---- METHOD 1: YouTube Internal API (most reliable) ----
    try:
        video_id = yt_page.evaluate(
            "() => new URLSearchParams(location.search).get('v') || location.pathname.split('/shorts/')[1]?.split('?')[0] || ''"
        )
        if video_id:
            log.info(f"  [API] Trying YouTube API like for {video_id}...")
            if yt_api_like(yt_page, video_id):
                time.sleep(2)
                state = yt_like_state(yt_page)
                if state == "liked":
                    log.info("  [OK] API like confirmed in DOM!")
                    return True
                log.info(f"  [API] Sent OK but DOM state: {state} (may update async)")
                return True  # Trust API 200 response even if DOM lags
    except Exception as e:
        log.warning(f"  [API] Error: {e}")

    # ---- METHOD 2: Trusted mouse click (fallback) ----
    log.info("  [FALLBACK] Trying trusted mouse click...")
    loc = None

    # Scroll to where like button appears
    try:
        yt_page.evaluate("window.scrollTo(0, 220)")
        time.sleep(0.8)
    except Exception:
        pass

    for sel in LIKE_BUTTON_SELECTORS:
        try:
            all_locs = yt_page.locator(sel).all()
            for candidate in all_locs:
                try:
                    box = candidate.bounding_box()
                    if not box or box.get("width", 0) == 0 or box.get("height", 0) == 0:
                        continue
                    label = (candidate.get_attribute("aria-label") or "").lower()
                    if "dislike" in label:
                        continue
                    if "unlike" in label:
                        log.info("  [OK] YouTube already liked (unlike in label)")
                        return True
                    if "like" in label:
                        log.info(f"  [FOUND] Visible like btn: sel='{sel}' box={box}")
                        loc = candidate
                        break
                except Exception:
                    continue
            if loc:
                break
        except Exception:
            continue

    if loc is None:
        log.warning("  [WARN] Like button not found (no visible element)")
        return False

    human_delay(0.4, 0.9)

    def _trusted_click():
        box = loc.bounding_box()
        if box and box.get("width", 0) > 0:
            yt_page.mouse.move(
                box["x"] + box["width"] * 0.5 + random.uniform(-4, 4),
                box["y"] + box["height"] * 0.5 + random.uniform(-3, 3),
            )
            time.sleep(random.uniform(0.15, 0.4))
            yt_page.mouse.click(
                box["x"] + box["width"] * 0.5,
                box["y"] + box["height"] * 0.5,
            )
        else:
            loc.click(timeout=4000)

    _trusted_click()

    deadline = time.time() + 6
    while time.time() < deadline:
        if yt_like_state(yt_page) == "liked":
            log.info("  [OK] YouTube liked! CHECK (label changed to unlike)")
            return True
        time.sleep(0.45)

    log.info("  [RETRY] Like did not stick — clicking once more")
    try:
        _trusted_click()
    except Exception:
        try:
            loc.click(timeout=3000)
        except Exception:
            pass

    deadline = time.time() + 5
    while time.time() < deadline:
        if yt_like_state(yt_page) == "liked":
            log.info("  [OK] YouTube liked! CHECK (retry)")
            return True
        time.sleep(0.45)

    state = yt_like_state(yt_page)
    log.info(f"  [WARN] YouTube like dom check: {state}")
    return state == "liked"


def yt_api_like(yt_page, video_id: str) -> bool:
    """
    Like via YouTube internal API (/youtubei/v1/like/like).
    FIX: Uses target.videoId (not videoId at root) + proper context.
    """
    try:
        result = yt_page.evaluate("""
            async (videoId) => {
                try {
                    // Get SAPISID cookie (not httpOnly, accessible in JS)
                    let sapisid = '';
                    document.cookie.split(';').forEach(c => {
                        c = c.trim();
                        if (c.startsWith('__Secure-3PAPISID=')) sapisid = c.split('=').slice(1).join('=');
                        else if (!sapisid && c.startsWith('SAPISID=')) sapisid = c.split('=').slice(1).join('=');
                    });
                    if (!sapisid) return {ok: false, error: 'no_sapisid'};

                    // SAPISIDHASH
                    const ts = Math.floor(Date.now() / 1000);
                    const msgBuf = new TextEncoder().encode(ts + ' ' + sapisid + ' https://www.youtube.com');
                    const hashBuf = await crypto.subtle.digest('SHA-1', msgBuf);
                    const hashHex = Array.from(new Uint8Array(hashBuf)).map(b => b.toString(16).padStart(2,'0')).join('');

                    // YouTube innertube config
                    const ytc = (typeof ytcfg !== 'undefined' && ytcfg.get) ? ytcfg : null;
                    const cv  = ytc ? (ytc.get('INNERTUBE_CLIENT_VERSION') || '2.20240101.00.00') : '2.20240101.00.00';
                    const key = ytc ? (ytc.get('INNERTUBE_API_KEY') || '') : '';
                    const hl  = ytc ? (ytc.get('HL') || 'en') : 'en';
                    const gl  = ytc ? (ytc.get('GL') || 'US') : 'US';
                    const vd  = ytc ? (ytc.get('VISITOR_DATA') || '') : '';

                    // CORRECT body format: target.videoId
                    const body = {
                        context: {
                            client: {
                                clientName: 'WEB',
                                clientVersion: cv,
                                hl: hl, gl: gl,
                                userAgent: navigator.userAgent,
                                originalUrl: location.href,
                                platform: 'DESKTOP',
                                clientFormFactor: 'UNKNOWN_FORM_FACTOR',
                                ...(vd ? {visitorData: vd} : {})
                            },
                            user: {lockedSafetyMode: false},
                            request: {useSsl: true}
                        },
                        target: {videoId: videoId}
                    };

                    const hdrs = {
                        'Content-Type': 'application/json',
                        'Authorization': 'SAPISIDHASH ' + ts + '_' + hashHex,
                        'X-Goog-AuthUser': '0',
                        'X-Origin': 'https://www.youtube.com',
                        'X-Youtube-Client-Name': '1',
                        'X-Youtube-Client-Version': cv,
                    };

                    // Try with key, then without
                    let lastStatus = 0;
                    const urls = key
                        ? ['/youtubei/v1/like/like?key=' + key, '/youtubei/v1/like/like']
                        : ['/youtubei/v1/like/like'];

                    for (const url of urls) {
                        const resp = await fetch(url, {
                            method: 'POST', credentials: 'include',
                            headers: hdrs, body: JSON.stringify(body)
                        });
                        // 200/204 = success, 403 = already liked (also success)
                        if (resp.ok || resp.status === 204 || resp.status === 403) {
                            return {ok: true, status: resp.status};
                        }
                        if (resp.status !== 400) break;
                        lastStatus = resp.status;
                    }
                    return {ok: false, status: lastStatus || 400};
                } catch(e) {
                    return {ok: false, error: String(e)};
                }
            }
        """, video_id)

        if result and result.get('ok'):
            log.info(f"  [OK] YouTube API like! status={result.get('status')}")
            return True
        else:
            log.warning(f"  [WARN] YouTube API like failed: {result}")
            return False
    except Exception as e:
        log.warning(f"  [WARN] yt_api_like error: {e}")
        return False


def yt_session_health_check(yt_page, video_id: str) -> str:
    """Quick API health check. Returns 'ok', '401', or 'error'."""
    try:
        result = yt_page.evaluate("""
            async (videoId) => {
                let sapisid = '';
                document.cookie.split(';').forEach(c => {
                    c = c.trim();
                    if (c.startsWith('__Secure-3PAPISID=')) sapisid = c.split('=').slice(1).join('=');
                    else if (!sapisid && c.startsWith('SAPISID=')) sapisid = c.split('=').slice(1).join('=');
                });
                if (!sapisid) return {status: 'no_sapisid'};
                const ts = Math.floor(Date.now() / 1000);
                const msgBuf = new TextEncoder().encode(ts + ' ' + sapisid + ' https://www.youtube.com');
                const hashBuf = await crypto.subtle.digest('SHA-1', msgBuf);
                const hashHex = Array.from(new Uint8Array(hashBuf)).map(b => b.toString(16).padStart(2,'0')).join('');
                const ytc = (typeof ytcfg !== 'undefined' && ytcfg.get) ? ytcfg : null;
                const key = ytc ? (ytc.get('INNERTUBE_API_KEY') || '') : '';
                const cv  = ytc ? (ytc.get('INNERTUBE_CLIENT_VERSION') || '2.20240101.00.00') : '2.20240101.00.00';
                const url = '/youtubei/v1/like/like' + (key ? '?key=' + key : '');
                const resp = await fetch(url, {
                    method: 'POST', credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'SAPISIDHASH ' + ts + '_' + hashHex,
                        'X-Goog-AuthUser': '0', 'X-Origin': 'https://www.youtube.com',
                        'X-Youtube-Client-Name': '1', 'X-Youtube-Client-Version': cv,
                    },
                    body: JSON.stringify({
                        context: {client: {clientName:'WEB',clientVersion:cv},user:{lockedSafetyMode:false}},
                        target: {videoId: videoId}
                    })
                });
                return {httpStatus: resp.status, ok: resp.ok};
            }
        """, video_id)
        status = result.get('httpStatus', 0) if result else 0
        if result and result.get('ok'): return 'ok'  # Like succeeded!
        if status == 401: return '401'
        return 'error'
    except Exception:
        return 'error'


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
    cookies_json = get_cookies(account)

    if not cookies_json:
        return

    log.info(f"[VIEWS] Account {acc_num} ({acc_email}) - {duration_seconds//60} min session")
    deadline = time.time() + duration_seconds
    seen_views = set()
    view_count = 0
    fail_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # Non-headless = YouTube cannot detect automation!
            args=["--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage", "--disable-gpu",
                  "--window-size=1280,800"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        # Stealth: hide automation fingerprints
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            window.chrome = {runtime: {}};
        """)
        if not google_login(context, cookies_json, account):
            log.error(f"[VIEWS] YouTube not signed in for Account {acc_num} — skip")
            browser.close()
            return
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


def do_one_like(page, context, seen_videos: set, last_video: list = None) -> str:
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
        yt_video_id = extract_video_id(yt_url)

        log.info(f"  >> YouTube: {yt_url[:70]} | ID: {yt_video_id}")

        # DUPLICATE CHECK - verify on YouTube first (don't blindly skip!)
        if yt_video_id and yt_video_id in seen_videos:
            perm_key  = yt_video_id + "_PERM"
            nopt_key  = yt_video_id + "_NOPT"
            final_key = yt_video_id + "_FINAL"

            # PERM = permanently skip (no need to open YouTube)
            if perm_key in seen_videos:
                log.warning(f"  [PERM_SKIP] {yt_video_id} - permanently skip")
                yt_page.close()
                page.bring_to_front()
                try:
                    sl = page.wait_for_selector("text=Skip", timeout=3000)
                    if sl: sl.click(); human_delay(1, 2)
                except Exception:
                    page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=20000)
                    human_delay(2, 3)
                return 'skip'

            if nopt_key in seen_videos or final_key in seen_videos:
                # Verify quickly: is it actually liked on YouTube?
                log.info(f"  [NOPT/FINAL] {yt_video_id} - quick verify...")
                is_liked = False
                try:
                    yt_page.wait_for_load_state("domcontentloaded", timeout=8000)
                    time.sleep(2)
                    is_liked = yt_like_state(yt_page) == "liked"
                except Exception:
                    is_liked = True  # Assume liked if can't verify

                yt_page.close()
                page.bring_to_front()
                if is_liked:
                    log.info(f"  [SKIP] {yt_video_id} liked ✓ - YLH task skip")
                    try:
                        skip_link = page.wait_for_selector("text=Skip", timeout=3000)
                        if skip_link:
                            skip_link.click()
                            human_delay(2, 3)
                    except Exception:
                        page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=20000)
                        human_delay(2, 3)
                    return 'skip'
                else:
                    # Verify failed - permanently skip to break infinite loop!
                    log.warning(f"  [PERM] {yt_video_id} verify failed - PERMANENT SKIP")
                    seen_videos.add(yt_video_id + "_PERM")
                    seen_videos.discard(nopt_key)
                    seen_videos.discard(final_key)
                    try:
                        skip_link = page.wait_for_selector("text=Skip", timeout=3000)
                        if skip_link:
                            skip_link.click()
                            human_delay(2, 3)
                    except Exception:
                        page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=20000)
                        human_delay(2, 3)
                    return 'skip'

            else:
                # First DUP: verify then try once more
                log.warning(f"  [DUP] Video {yt_video_id} seen before - YouTube pe verify kar raha hoon...")
                actually_liked = False
                try:
                    yt_page.wait_for_load_state("domcontentloaded", timeout=10000)
                    time.sleep(2)
                    actually_liked = yt_like_state(yt_page) == "liked"
                except Exception as e:
                    log.warning(f"  [DUP] verify error: {e} - assuming liked")
                    actually_liked = True

                if actually_liked:
                    log.info(f"  [DUP] {yt_video_id} YouTube pe liked hai - skip")
                    yt_page.close()
                    page.bring_to_front()
                    try:
                        skip_link = page.wait_for_selector("text=Skip", timeout=3000)
                        if skip_link:
                            skip_link.click()
                            human_delay(2, 3)
                    except Exception:
                        page.goto(YLH_YOUTUBE_LIKES_URL, wait_until="domcontentloaded", timeout=20000)
                        human_delay(2, 3)
                    return 'skip'
                else:
                    log.info(f"  [DUP] {yt_video_id} NOT liked - try karte hain, FINAL mark lagega")
                    seen_videos.add(yt_video_id + "_FINAL")
                    seen_videos.discard(yt_video_id)
                    # Continue to like logic

        # Wait for YouTube page to be fully interactive
        try:
            yt_page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(2)
        except Exception:
            pass

        try:
            yt_page.mouse.wheel(0, random.randint(180, 360))
            time.sleep(random.uniform(0.4, 0.9))
        except Exception:
            pass

        liked = False
        already_liked = False

        yt_watch_before_like(yt_page)

        if yt_signed_out_prompt(yt_page) or not youtube_is_signed_in(yt_page):
            log.warning("  [WARN] YouTube NOT signed in — like possible nahi, YLH confirm skip")
            try:
                yt_page.close()
            except Exception:
                pass
            page.bring_to_front()
            return "fail"

        state = yt_like_state(yt_page)
        if state == "liked":
            log.warning("  [WARN] Video YouTube pe already liked hai! (unlike detected)")
            already_liked = True
        else:
            liked = yt_click_like(yt_page)
            if not liked:
                log.warning("  [WARN] Like did not register after retry — still confirming on YLH")

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
            if last_video is not None:
                last_video[0] = yt_video_id
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
    cookies_json = get_cookies(account)

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
            headless=False,  # Non-headless = YouTube cannot detect automation!
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--window-size=1280,800",
            ]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        # Stealth: hide automation fingerprints
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            window.chrome = {runtime: {}};
        """)

        if not google_login(context, cookies_json, account):
            log.error(f"[SKIP] Account {acc_num}: YouTube signed in nahi — cookies refresh chahiye")
            browser.close()
            return "skip"
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
        last_video  = [None]   # Tracks last liked video_id for NOPT marking
        consecutive_fails = 0
        consecutive_no_vid = 0
        consecutive_no_pts = 0   # Track consecutive 0-pts to detect exhausted account
        round_num = 1
        daily_likes = 0      # Points earn karne wale likes
        prev_pts = start_pts

        log.info(f"[BOT] Continuous loop - Daily limit: {DAILY_LIMIT} likes")

        while True:
            result = do_one_like(main_page, context, seen_videos, last_video)

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
                    consecutive_no_pts = 0
                    log.info(f"[STATS] Like #{daily_likes}/{DAILY_LIMIT} | Points: {curr} | +{curr - start_pts} | Time: {elapsed}")
                    prev_pts = curr
                    if daily_likes >= DAILY_LIMIT:
                        log.info(f"[ACC {acc_num}] {DAILY_LIMIT} likes done! Next account...")
                        browser.close()
                        return 'done'
                else:
                    consecutive_no_pts += 1
                    vid = last_video[0]
                    if vid:
                        if vid + "_NOPT" in seen_videos:
                            seen_videos.add(vid + "_PERM")
                            seen_videos.discard(vid + "_NOPT")
                            log.info(f"[PERM] {vid} - 2nd 0-pts, permanent skip added")
                        else:
                            seen_videos.add(vid + "_NOPT")
                    log.info(f"[STATS] Like done (no pts) | Total: {total_likes} | Daily earned: {daily_likes}/{DAILY_LIMIT} | Consec 0-pts: {consecutive_no_pts}")
                    # Account exhausted check: 8 consecutive 0-pts = move to next account
                    if consecutive_no_pts >= 8:
                        log.info(f"[ACC {acc_num}] 8 consecutive 0-pts - account tasks exhausted! Next account...")
                        browser.close()
                        return 'exhausted'
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
            'has_cookies': bool(get_cookies(acc)),
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
        elif result in ('daily_limit', 'done', 'exhausted'):
            state['daily_done'] = True
            reason = 'tasks exhausted' if result == 'exhausted' else 'daily limit'
            log.info(f"[DAILY] Account {acc['num']} {reason} - moving to next!")
        elif result == 'error':
            log.error(f"[ERROR] Account {acc['num']} login failed - skipping")
            state['daily_done'] = True
        elif result == 'skip':
            # BUG FIX: cookies stale - mark done so we move to next account (don't loop!)
            log.warning(f"[SKIP] Account {acc['num']} auth failed - moving to next account")
            state['daily_done'] = True

        time.sleep(5)


if __name__ == "__main__":
    run()
