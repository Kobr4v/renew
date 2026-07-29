from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from datetime import datetime
import time
import random
import traceback
from dateutil import parser
import os
import requests
import json
import re
import subprocess
import sys
from webdriver_manager.chrome import ChromeDriverManager

USERNAME = os.getenv('USERNAME', '')
PASSWORD = os.getenv('PASSWORD', '')
SESSION_COOKIE = os.getenv('PTERODACTYL_SESSION', '')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

APP_URL = 'https://tickhosting.com'


def log(msg, level='INFO'):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] [{level}] {msg}')


def random_delay(min_s=0.3, max_s=1.5):
    time.sleep(random.uniform(min_s, max_s))


def human_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.03, 0.12))
    random_delay(0.1, 0.4)


def human_scroll(driver, element):
    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
            element
        )
        random_delay(0.3, 0.8)
    except Exception:
        pass


def human_click(driver, element):
    human_scroll(driver, element)
    actions = ActionChains(driver)
    offset_x = random.randint(-15, 15)
    offset_y = random.randint(-15, 15)
    actions.move_to_element_with_offset(element, offset_x, offset_y)
    actions.pause(random.uniform(0.2, 0.5))
    actions.move_to_element(element)
    actions.pause(random.uniform(0.1, 0.3))
    actions.click()
    actions.pause(random.uniform(0.1, 0.3))
    actions.perform()
    random_delay(0.2, 0.5)


def human_scroll_page(driver):
    try:
        height = driver.execute_script("return document.body.scrollHeight")
        if height > 800:
            target = random.randint(100, min(height - 200, 600))
            driver.execute_script(f"window.scrollTo({{top: {target}, behavior: 'smooth'}})")
            random_delay(0.5, 1.2)
            driver.execute_script("window.scrollTo({top: 0, behavior: 'smooth'})")
            random_delay(0.3, 0.7)
    except Exception:
        pass


def find_element_fallback(driver, selectors):
    for by, val in selectors:
        try:
            el = driver.find_element(by, val)
            if el and el.is_displayed():
                log(f"Found element: {by}={val}")
                return el
        except Exception:
            continue
    return None


def send_telegram_message(message, parse_mode='Markdown'):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        log("Telegram notification sent")
        return True
    except Exception as e:
        log(f"Telegram send failed: {e}", 'WARN')
        return False


def send_error_telegram(context, e):
    tb = traceback.format_exc()
    lines = tb.strip().split('\n')
    suspected = None
    for line in lines:
        m = re.search(r'File "[^"]+", line (\d+)', line)
        if m:
            suspected = m.group(1)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg = (
        f"\U0001F6A8 *TickHosting Auto-Renew Error* \U0001F6A8\n\n"
        f"\U0001F4DD  Context: `{context}`\n"
        f"\U0001F50D  Error: `{str(e)[:200]}`\n"
    )
    if suspected:
        msg += f"\U0001F4CB  Line: `{suspected}`\n"
    msg += f"\U0001F4C5  Time: `{now}`\n\n"
    msg += f"\U0001F517 [Open TickHosting]({APP_URL})"
    send_telegram_message(msg)


def setup_driver():
    log("Setting up Chrome driver...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' }
                ]
            });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'es'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });
            Object.defineProperty(navigator.connection || {}, 'rtt', { get: () => 100 });
            Object.defineProperty(navigator.connection || {}, 'downlink', { get: () => 10 });
            Object.defineProperty(navigator.connection || {}, 'effectiveType', { get: () => '4g' });
            const origQuery = navigator.permissions.query.bind(navigator.permissions);
            navigator.permissions.query = (p) => {
                if (p.name === 'notifications' || p.name === 'clipboard-read') return Promise.resolve({ state: 'denied' });
                return origQuery(p);
            };
            const origGetParam = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(p) {
                if (p === 37445) return 'Intel Inc.';
                if (p === 37446) return 'Intel Iris OpenGL Engine';
                return origGetParam(p);
            };
            const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                const ctx = this.getContext('2d');
                if (ctx) {
                    const imgData = ctx.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < imgData.data.length; i += 4) { imgData.data[i] ^= 1; }
                    ctx.putImageData(imgData, 0, 0);
                }
                return origToDataURL.apply(this, arguments);
            };
        '''
    })
    log("Driver ready")
    return driver


def add_cookies(driver):
    driver.delete_all_cookies()
    for name in ['PTERODACTYL_SESSION', 'pterodactyl_session']:
        try:
            driver.add_cookie({
                'name': name,
                'value': os.environ['PTERODACTYL_SESSION'],
                'domain': '.tickhosting.com'
            })
            log(f"Added cookie: {name}")
        except Exception as e:
            log(f"Failed to add cookie {name}: {e}", 'WARN')


def login_to_dashboard(driver):
    try:
        log("Attempting cookie login...")
        driver.get("https://tickhosting.com/")
        random_delay(3, 5)
        add_cookies(driver)
        driver.refresh()
        random_delay(3, 5)

        driver.get("https://tickhosting.com")
        random_delay(3, 5)

        if driver.current_url.startswith('https://tickhosting.com') and 'Dashboard' in driver.title:
            log("Cookie login successful")
            return True

        log("Cookie login failed, trying email/password...")
    except Exception as e:
        log(f"Cookie login error: {e}", 'ERROR')

    try:
        if not USERNAME or not PASSWORD:
            raise ValueError("USERNAME or PASSWORD not set")

        log("Navigating to login page...")
        driver.get('https://tickhosting.com/auth/login')
        random_delay(3, 5)

        page_title = driver.title
        page_url = driver.current_url
        log(f"Page title: {page_title}")
        log(f"Page URL: {page_url}")

        if 'Just a moment' in page_title:
            log("Cloudflare challenge detected, waiting...", 'WARN')
            random_delay(10, 15)
            page_title = driver.title
            log(f"After wait - title: {page_title}")

        email_selectors = [
            (By.ID, 'username'),
            (By.NAME, 'username'),
            (By.NAME, 'email'),
            (By.ID, 'email'),
            (By.CSS_SELECTOR, "input[placeholder*='email' i]"),
        ]
        password_selectors = [
            (By.NAME, 'password'),
            (By.ID, 'password'),
            (By.XPATH, "//input[@type='password']"),
            (By.CSS_SELECTOR, "input[type='password']"),
        ]
        button_selectors = [
            (By.ID, 'btn-text'),
            (By.XPATH, "//button[@type='submit']"),
            (By.XPATH, "//button[contains(@class, 'submit-btn')]"),
            (By.XPATH, "//button[contains(text(), 'Sign In') or contains(text(), 'Login')]"),
            (By.CSS_SELECTOR, "button[type='submit']"),
        ]

        email_input = find_element_fallback(driver, email_selectors)
        password_input = find_element_fallback(driver, password_selectors)
        login_button = find_element_fallback(driver, button_selectors)

        if not email_input or not password_input:
            driver.save_screenshot('debug_login_fields.png')
            raise Exception(f"Login fields not found (email={'ok' if email_input else 'missing'}, pass={'ok' if password_input else 'missing'})")
        if not login_button:
            raise Exception("Login button not found")

        random_delay(1, 2)
        email_input.clear()
        human_type(email_input, USERNAME)
        log("Username entered")
        random_delay(0.5, 1.5)

        password_input.clear()
        human_type(password_input, PASSWORD)
        log("Password entered")
        random_delay(0.8, 2)

        human_scroll_page(driver)
        random_delay(0.3, 0.8)

        solve_recaptcha(driver)
        random_delay(0.8, 2)

        log("Clicking login button...")
        human_click(driver, login_button)
        random_delay(5, 8)

        driver.get("https://tickhosting.com")
        random_delay(3, 5)

        if driver.current_url.startswith('https://tickhosting.com') and 'Dashboard' in driver.title:
            log("Email/password login successful")
            return True

        raise Exception(f"Login did not reach dashboard (url: {driver.current_url}, title: {driver.title})")
    except Exception as e:
        log(f"Login failed: {e}", 'ERROR')
        if driver:
            driver.save_screenshot('debug_login_error.png')
        send_error_telegram('login_to_dashboard', e)
        return False


def transcribe_audio(mp3_bytes):
    try:
        proc = subprocess.run(
            ['ffmpeg', '-i', 'pipe:0', '-f', 's16le', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', 'pipe:1'],
            input=mp3_bytes, capture_output=True, timeout=30
        )
        if proc.returncode != 0:
            log(f"ffmpeg error: {proc.stderr.decode(errors='ignore')[:200]}", 'ERROR')
            return None
        raw_data = proc.stdout

        if not raw_data or len(raw_data) < 100:
            log(f"ffmpeg empty output ({len(raw_data or b'')} bytes)", 'WARN')
            return None

        url = "https://www.google.com/speech-api/v2/recognize"
        params = {"output": "json", "lang": "en-US", "key": "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"}
        headers = {"Content-Type": "audio/l16; rate=16000; channels=1"}
        resp = requests.post(url, params=params, headers=headers, data=raw_data, timeout=15)

        for line in resp.text.strip().split('\n'):
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get('result'):
                    transcript = data['result'][0]['alternative'][0]['transcript']
                    return transcript
            except Exception:
                continue
        return None
    except subprocess.TimeoutExpired:
        log("ffmpeg timed out", 'ERROR')
        return None
    except Exception as e:
        log(f"Transcribe error: {e}", 'ERROR')
        return None


def solve_audio_challenge(driver):
    try:
        random_delay(1, 2)
        audio_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "recaptcha-audio-button"))
        )
        human_click(driver, audio_btn)
        log("[AUDIO] Clicked audio challenge button")
        random_delay(2, 4)
    except Exception as e:
        log(f"[AUDIO] No audio button: {e}", 'WARN')
        return False

    try:
        audio_el = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "audio-source"))
        )
        audio_url = audio_el.get_attribute("src")
        log(f"[AUDIO] Downloading from {audio_url}")

        audio_resp = requests.get(audio_url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        log(f"[AUDIO] Downloaded {len(audio_resp.content)} bytes")
        text = transcribe_audio(audio_resp.content)
        if not text:
            log("[AUDIO] Transcription failed", 'ERROR')
            driver.switch_to.default_content()
            return False

        log(f"[AUDIO] Transcribed: '{text}'")
    except Exception as e:
        log(f"[AUDIO] Download/transcribe error: {e}", 'ERROR')
        driver.switch_to.default_content()
        return False

    try:
        resp_input = driver.find_element(By.ID, "audio-response")
        resp_input.clear()
        random_delay(0.2, 0.5)
        human_type(resp_input, text.lower())
        random_delay(0.5, 1.5)

        verify_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.ID, "recaptcha-verify-button"))
        )
        human_click(driver, verify_btn)
        log("[AUDIO] Submitted answer")
        random_delay(2, 4)

        driver.switch_to.default_content()
        random_delay(1, 2)

        token = driver.execute_script(
            "return document.getElementById('g-recaptcha-response')?.value"
        )
        if token and len(token) > 50:
            log("[AUDIO] Solved successfully")
            return True

        log("[AUDIO] Answer was wrong", 'WARN')
        return False
    except Exception as e:
        log(f"[AUDIO] Submit error: {e}", 'ERROR')
        driver.switch_to.default_content()
        return False


def solve_recaptcha(driver):
    log("=== reCAPTCHA Solver ===")

    try:
        token = driver.execute_script(
            "return document.getElementById('g-recaptcha-response')?.value"
        )
        if token and len(token) > 50:
            log("[SOLVER] Already solved, skipping")
            return True
    except Exception:
        pass

    iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha/api2/anchor']")
    if not iframes:
        log("[SOLVER] No reCAPTCHA iframe found, skipping")
        return False

    driver.switch_to.frame(iframes[0])
    random_delay(0.5, 1.5)

    try:
        checkbox = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "recaptcha-anchor"))
        )
        human_click(driver, checkbox)
        log("[SOLVER] Checkbox clicked")
    except Exception as e:
        log(f"[SOLVER] Cannot click checkbox: {e}", 'WARN')
        driver.switch_to.default_content()
        return False

    random_delay(1.5, 3)
    driver.switch_to.default_content()

    try:
        token = driver.execute_script(
            "return document.getElementById('g-recaptcha-response')?.value"
        )
        if token and len(token) > 50:
            log("[SOLVER] Checkbox passed, no challenge")
            return True
    except Exception:
        pass

    random_delay(0.5, 1.5)

    try:
        challenge = driver.find_element(By.CSS_SELECTOR, "iframe[src*='recaptcha/api2/bframe']")
        driver.switch_to.frame(challenge)
        log("[SOLVER] Challenge detected, solving...")
    except Exception:
        try:
            token = driver.execute_script(
                "return document.getElementById('g-recaptcha-response')?.value"
            )
            if token and len(token) > 50:
                log("[SOLVER] Solved after checkbox")
                return True
        except Exception:
            pass
        log("[SOLVER] No challenge needed")
        return True

    result = solve_audio_challenge(driver)
    if result:
        log("[SOLVER] Audio solve succeeded")
        return True

    log("[SOLVER] Audio solve failed", 'WARN')
    try:
        token = driver.execute_script(
            "return document.getElementById('g-recaptcha-response')?.value"
        )
        if token and len(token) > 50:
            log("[SOLVER] Token found anyway")
            return True
    except Exception:
        pass

    return False


def send_renew_success(server_id, initial_time, new_time):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"\U00002705 *TickHosting Renewal Successful* \U00002705\n\n"
        f"\U0001F5A5  Server ID: `{server_id}`\n"
        f"\U0001F550  Before: `{initial_time}`\n"
        f"\U0001F551  After:  `{new_time}`\n"
        f"\U0001F4C5  Renewed at: `{now}`\n\n"
        f"\U0001F517 [Open TickHosting]({APP_URL})"
    )
    send_telegram_message(msg)


def send_renew_failure(server_id, reason):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"\U0000274C *TickHosting Renewal Failed* \U0000274C\n\n"
        f"\U0001F5A5  Server ID: `{server_id}`\n"
        f"\U000026A0  Reason: `{reason}`\n"
        f"\U0001F4C5  Attempted at: `{now}`\n\n"
        f"\U0001F517 [Open TickHosting]({APP_URL})"
    )
    send_telegram_message(msg)


def update_last_renew_file(success, new_time=None, error_message=None, server_id=None):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "Success" if success else "Failed"
    content = (
        f"Server ID: {server_id or 'Unknown'}\n"
        f"Renew status: {status}\n"
        f"Last renewal time: {current_time}\n"
    )
    if success and new_time:
        content += f"New expiration time: {new_time}"
    elif not success and error_message:
        content += f"Error: {error_message}"
    with open('last_renew_data.txt', 'w', encoding='utf-8') as f:
        f.write(content)


def get_expiration_time(driver):
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, ".RenewBox___StyledP-sc-1inh2rq-4")
        if not elements:
            return None
        text = elements[0].text
        if text.startswith("EXPIRED: "):
            text = text.replace("EXPIRED: ", "").strip()
        return text
    except Exception as e:
        log(f"Error getting expiration time: {e}", 'WARN')
        return None


def navigate_to_server(driver):
    log("Looking for server on dashboard...")
    random_delay(3, 6)

    server_selectors = [
        ("xpath", "//div[contains(@class, 'status-bar')]"),
        ("xpath", "//div[contains(@class, 'server-status')]"),
        ("xpath", "//div[contains(@class, 'server-card')]"),
    ]

    server_element = None
    for selector_type, selector in server_selectors:
        try:
            elements = driver.find_elements(By.XPATH if selector_type == "xpath" else By.CSS_SELECTOR, selector)
            if elements:
                server_element = elements[0]
                log(f"Found server element: {selector}")
                break
        except Exception:
            continue

    if not server_element:
        raise Exception("Could not find server element on dashboard")

    human_click(driver, server_element)
    random_delay(3, 5)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    current_url = driver.current_url
    server_id = 'Unknown'
    match = re.search(r'/server/([a-f0-9]+)', current_url)
    if match:
        server_id = match.group(1)
        log(f"Server ID: {server_id}")
    return server_id


def click_renew_button(driver):
    log("Looking for renew button...")
    random_delay(2, 4)

    renew_selectors = [
        ("xpath", "//span[contains(@class, 'Button___StyledSpan')]/parent::button"),
        ("xpath", "//button[.//span[contains(text(), 'ADD 96 HOUR')]]"),
        ("xpath", "//button[@color='primary' and contains(@class, 'Button__ButtonStyle')]"),
    ]

    renew_button = None
    for selector_type, selector in renew_selectors:
        try:
            elements = driver.find_elements(By.XPATH if selector_type == "xpath" else By.CSS_SELECTOR, selector)
            if elements:
                renew_button = elements[0]
                log(f"Found renew button: {selector}")
                break
        except Exception:
            continue

    if not renew_button:
        raise Exception("Could not find renew button")

    initial_time = get_expiration_time(driver)
    log(f"Current expiration: {initial_time or 'unknown'}")

    human_click(driver, renew_button)
    log("Clicked renew button, waiting 70s...")
    time.sleep(70)

    driver.refresh()
    random_delay(5, 8)

    new_time = get_expiration_time(driver)
    log(f"New expiration: {new_time or 'unknown'}")

    return initial_time, new_time


def main():
    driver = None
    try:
        send_telegram_message(
            f"\U0001F504 *TickHosting Auto-Renew Started* \U0001F504\n\n"
            f"Checking your server and attempting renewal..."
        )

        driver = setup_driver()
        driver.set_page_load_timeout(40)

        log("Loading dashboard...")
        driver.get("https://tickhosting.com")
        random_delay(3, 5)

        if not login_to_dashboard(driver):
            raise Exception("Unable to login to dashboard")

        driver.refresh()
        random_delay(3, 5)

        server_id = navigate_to_server(driver)
        initial_time, new_time = click_renew_button(driver)

        if initial_time and new_time:
            try:
                initial_dt = parser.parse(initial_time)
                new_dt = parser.parse(new_time)
                if new_dt > initial_dt:
                    log("Renewal successful! Time extended.")
                    update_last_renew_file(success=True, new_time=new_time, server_id=server_id)
                    send_renew_success(server_id, initial_time, new_time)
                else:
                    log("Renewal failed - time not extended", 'WARN')
                    update_last_renew_file(success=False, error_message="Time not extended", server_id=server_id)
                    send_renew_failure(server_id, "Time not extended after renewal")
            except Exception as e:
                log(f"Date parsing error: {e}", 'ERROR')
                update_last_renew_file(success=False, error_message=f"Date parse: {e}", server_id=server_id)
                send_renew_failure(server_id, f"Date parse error: {e}")
        else:
            log("Could not verify renewal - no expiration times", 'WARN')
            update_last_renew_file(success=False, error_message="No expiration times found", server_id=server_id)
            send_renew_failure(server_id, "Could not find expiration times")

    except TimeoutException as e:
        msg = f"Timeout: {e}"
        log(msg, 'ERROR')
        if driver:
            driver.save_screenshot('error_timeout.png')
        update_last_renew_file(False, error_message=msg)
        send_error_telegram('main_timeout', e)
    except Exception as e:
        msg = f"Error: {e}"
        log(msg, 'ERROR')
        if driver:
            driver.save_screenshot('error.png')
        update_last_renew_file(False, error_message=msg)
        send_error_telegram('main', e)
    finally:
        if driver:
            try:
                driver.quit()
                log("Browser closed")
            except Exception as e:
                log(f"Error closing browser: {e}", 'WARN')


def run_tests():
    results = []
    log("=== TEST MODE ===")

    results.append(("Telegram notification", False))
    tg_ok = send_telegram_message(
        f"\U0001F9EA *TickHosting Test* \U0001F9EA\n\n"
        f"\U0001F504 Running diagnostic tests..."
    )
    results[-1] = ("Telegram", tg_ok)
    log(f"  Telegram: {'PASS' if tg_ok else 'FAIL'}")

    log("--- Testing login ---")
    driver = None
    login_ok = False
    try:
        driver = setup_driver()
        driver.set_page_load_timeout(40)
        driver.get("https://tickhosting.com")
        random_delay(3, 5)
        login_ok = login_to_dashboard(driver)
    except Exception as e:
        log(f"  Login threw exception: {e}", 'ERROR')
        send_error_telegram('test_login', e)
    finally:
        if driver:
            driver.quit()

    results.append(("TickHosting login", login_ok))
    log(f"  Login: {'PASS' if login_ok else 'FAIL'}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    content = (
        f"Test Results ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n"
        f"{'='*40}\n"
    )
    for name, ok in results:
        content += f"  [{'PASS' if ok else 'FAIL'}] {name}\n"
    content += f"\n{passed}/{total} tests passed\n"

    with open('test_results.txt', 'w') as f:
        f.write(content)

    log(f"\n{content}")

    all_pass = passed == total
    verdict = (
        f"\U00002705 *All checks passed* \U0001F680"
        if all_pass
        else f"\U0001F6A8 *Needs more development* \U0001F4A1"
    )
    commit = os.getenv('GITHUB_SHA', '')
    commit_link = f"\n\U0001F517 `{commit[:7]}`" if commit else ""

    summary = f"{verdict}\n\n"
    for name, ok in results:
        icon = "\U00002705" if ok else "\U0000274C"
        summary += f"{icon}  `{name}`\n"
    summary += f"\n**{passed}/{total} tests passed**\n"
    if not all_pass:
        failed = [n for n, ok in results if not ok]
        summary += f"\n\U0001F6A7 Failing: {', '.join(f'`{n}`' for n in failed)}"
    summary += commit_link

    send_telegram_message(summary)
    return 0 if passed == total else 1


if __name__ == "__main__":
    if os.getenv('TEST_MODE', '').lower() in ('true', '1'):
        sys.exit(run_tests())
    else:
        main()
