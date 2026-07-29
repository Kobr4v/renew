from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from datetime import datetime
import time
import random
from dateutil import parser
import os
import requests
import json
import re
import subprocess
import undetected_chromedriver as uc

USERNAME = os.getenv('USERNAME', '')
PASSWORD = os.getenv('PASSWORD', '')
SESSION_COOKIE = os.getenv('PTERODACTYL_SESSION', '')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

APP_URL = 'https://tickhosting.com'


def random_delay(min_s=0.3, max_s=1.5):
    time.sleep(random.uniform(min_s, max_s))


def human_type(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.03, 0.12))


def human_click(driver, element):
    actions = ActionChains(driver)
    actions.move_to_element_with_offset(element, random.randint(-8, 8), random.randint(-8, 8))
    actions.pause(random.uniform(0.1, 0.3))
    actions.move_to_element(element)
    actions.pause(random.uniform(0.05, 0.2))
    actions.click()
    actions.pause(random.uniform(0.1, 0.3))
    actions.perform()


def setup_driver():
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36')

    driver = uc.Chrome(options=options, use_subprocess=True)
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
        except Exception as e:
            print(f"Failed to add cookie {name}: {e}")


def login_to_dashboard(driver):
    try:
        driver.get("https://tickhosting.com/")
        time.sleep(5)
        add_cookies(driver)
        driver.refresh()
        time.sleep(5)

        driver.get("https://tickhosting.com")
        time.sleep(5)

        if driver.current_url.startswith('https://tickhosting.com') and 'Dashboard' in driver.title:
            print("Cookie login successful")
            return True

        print("Cookie login failed, trying email/password...")
    except Exception as e:
        print(f"Cookie login error: {e}")

    try:
        if not USERNAME or not PASSWORD:
            raise ValueError("USERNAME or PASSWORD not set")

        driver.get('https://tickhosting.com/auth/login')
        time.sleep(8)

        driver.save_screenshot('debug_login_page.png')
        print(f"Login page title: {driver.title}")
        print(f"Login page URL: {driver.current_url}")
        print(f"Page source (first 3000 chars):\n{driver.page_source[:3000]}")

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

        email_input = None
        for by, val in email_selectors:
            try:
                email_input = driver.find_element(by, val)
                if email_input:
                    print(f"Found email input: {by}={val}")
                    break
            except Exception:
                continue

        password_input = None
        for by, val in password_selectors:
            try:
                password_input = driver.find_element(by, val)
                if password_input:
                    print(f"Found password input: {by}={val}")
                    break
            except Exception:
                continue

        login_button = None
        for by, val in button_selectors:
            try:
                login_button = driver.find_element(by, val)
                if login_button:
                    print(f"Found login button: {by}={val}")
                    break
            except Exception:
                continue

        if not email_input or not password_input:
            raise Exception(f"Could not find login fields (email={'found' if email_input else 'missing'}, password={'found' if password_input else 'missing'})")
        if not login_button:
            raise Exception("Could not find login button")

        random_delay(0.5, 1)
        email_input.clear()
        human_type(email_input, USERNAME)
        random_delay(0.3, 0.8)
        password_input.clear()
        human_type(password_input, PASSWORD)
        random_delay(0.5, 1)

        solve_recaptcha(driver)
        random_delay(0.5, 1.5)

        human_click(driver, login_button)
        time.sleep(10)

        driver.get("https://tickhosting.com")
        time.sleep(5)

        if driver.current_url.startswith('https://tickhosting.com') and 'Dashboard' in driver.title:
            print("Email/password login successful")
            return True

        raise Exception("Login did not reach dashboard")
    except Exception as e:
        print(f"Login failed: {e}")
        if driver:
            driver.save_screenshot('debug_login_error.png')
        send_renew_error(f"Login failed: {e}")
        return False


def try_extract_grecaptcha_token(driver):
    try:
        token = driver.execute_script("""
            try {
                var ta = document.getElementById('g-recaptcha-response');
                if (ta && ta.value && ta.value.length > 50) return ta.value;
                var clients = ___grecaptcha_cfg && ___grecaptcha_cfg.clients;
                if (clients) {
                    for (var cid in clients) {
                        for (var wid in clients[cid]) {
                            var w = clients[cid][wid];
                            if (w && w.callback && typeof w.callback === 'function') {
                                return 'callback_found';
                            }
                        }
                    }
                }
            } catch(e) {}
            return null;
        """)
        return token
    except Exception:
        return None


def transcribe_audio(mp3_bytes):
    try:
        proc = subprocess.run(
            ['ffmpeg', '-i', 'pipe:0', '-f', 's16le', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', 'pipe:1'],
            input=mp3_bytes, capture_output=True, timeout=30
        )
        if proc.returncode != 0:
            print(f"[STT] ffmpeg error: {proc.stderr.decode(errors='ignore')[:200]}")
            return None
        raw_data = proc.stdout

        if not raw_data or len(raw_data) < 100:
            print(f"[STT] ffmpeg produced empty output ({len(raw_data or b'')} bytes)")
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
                    return data['result'][0]['alternative'][0]['transcript']
            except Exception:
                continue
        return None
    except subprocess.TimeoutExpired:
        print("[STT] ffmpeg timed out")
        return None
    except Exception as e:
        print(f"[STT] Error: {e}")
        return None


def solve_audio_challenge(driver):
    try:
        random_delay(1, 2)
        audio_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "recaptcha-audio-button"))
        )
        human_click(driver, audio_btn)
        print("[AUDIO] Clicked audio challenge button")
        random_delay(2, 3)
    except Exception as e:
        print(f"[AUDIO] No audio button: {e}")
        return False

    try:
        audio_el = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "audio-source"))
        )
        audio_url = audio_el.get_attribute("src")
        print(f"[AUDIO] Downloading from {audio_url}")

        audio_resp = requests.get(audio_url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        text = transcribe_audio(audio_resp.content)
        if not text:
            print("[AUDIO] Transcription failed (all backends)")
            driver.switch_to.default_content()
            return False

        print(f"[AUDIO] Transcribed: '{text}'")
    except Exception as e:
        print(f"[AUDIO] Download/transcribe error: {e}")
        driver.switch_to.default_content()
        return False

    try:
        resp_input = driver.find_element(By.ID, "audio-response")
        resp_input.clear()
        random_delay(0.2, 0.5)
        human_type(resp_input, text.lower())
        random_delay(0.5, 1)

        verify_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.ID, "recaptcha-verify-button"))
        )
        human_click(driver, verify_btn)
        print("[AUDIO] Submitted answer")
        random_delay(2, 3)

        driver.switch_to.default_content()
        random_delay(1, 2)

        token = driver.execute_script(
            "return document.getElementById('g-recaptcha-response')?.value"
        )
        if token and len(token) > 50:
            print("[AUDIO] Solved successfully")
            return True

        print("[AUDIO] Answer was wrong")
        return False
    except Exception as e:
        print(f"[AUDIO] Submit error: {e}")
        driver.switch_to.default_content()
        return False


def solve_recaptcha(driver):
    print("=== reCAPTCHA Solver ===")

    try:
        token = try_extract_grecaptcha_token(driver)
        if token and len(token) > 50:
            print("[SOLVER] Already solved, skipping")
            return True
    except Exception:
        pass

    iframes = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha/api2/anchor']")
    if not iframes:
        print("[SOLVER] No reCAPTCHA iframe found")
        return False

    driver.switch_to.frame(iframes[0])
    random_delay(0.5, 1.5)

    try:
        checkbox = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "recaptcha-anchor"))
        )
        human_click(driver, checkbox)
        print("[SOLVER] Checkbox clicked")
    except Exception as e:
        print(f"[SOLVER] Cannot click checkbox: {e}")
        driver.switch_to.default_content()
        return False

    random_delay(1, 2)
    driver.switch_to.default_content()

    try:
        token = driver.execute_script(
            "return document.getElementById('g-recaptcha-response')?.value"
        )
        if token and len(token) > 50:
            print("[SOLVER] Checkbox passed, no challenge needed")
            return True
    except Exception:
        pass

    random_delay(0.5, 1)

    try:
        challenge = driver.find_element(By.CSS_SELECTOR, "iframe[src*='recaptcha/api2/bframe']")
        driver.switch_to.frame(challenge)
        print("[SOLVER] Challenge detected, solving...")
    except Exception:
        try:
            token = driver.execute_script(
                "return document.getElementById('g-recaptcha-response')?.value"
            )
            if token and len(token) > 50:
                print("[SOLVER] Already solved after checkbox")
                return True
        except Exception:
            pass
        print("[SOLVER] No challenge - assuming passed")
        return True

    result = solve_audio_challenge(driver)
    if result:
        return True

    print("[SOLVER] Audio solve failed, checking if token was injected anyway...")
    try:
        token = driver.execute_script(
            "return document.getElementById('g-recaptcha-response')?.value"
        )
        if token and len(token) > 50:
            print("[SOLVER] Token found after failed audio attempt")
            return True
    except Exception:
        pass

    return False


def send_telegram_message(message, parse_mode='Markdown'):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Telegram notification sent")
        return True
    except Exception as e:
        print(f"Telegram send failed: {e}")
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


def send_renew_error(error_msg):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = (
        f"\U0001F6A8 *TickHosting Auto-Renew Error* \U0001F6A8\n\n"
        f"\U0001F4DD  Error: `{error_msg}`\n"
        f"\U0001F4C5  Time: `{now}`\n\n"
        f"\U0001F517 [Open TickHosting]({APP_URL})"
    )
    send_telegram_message(msg)


def send_start_notice():
    msg = (
        f"\U0001F504 *TickHosting Auto-Renew Started* \U0001F504\n\n"
        f"Checking your server and attempting renewal..."
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
        print(f"Error getting expiration time: {e}")
        return None


def main():
    driver = None
    try:
        send_start_notice()

        driver = setup_driver()
        driver.set_page_load_timeout(30)

        driver.get("https://tickhosting.com")
        time.sleep(5)

        if not login_to_dashboard(driver):
            raise Exception("Unable to login to dashboard")

        driver.refresh()
        time.sleep(5)

        server_selectors = [
            ("xpath", "//div[contains(@class, 'status-bar')]"),
            ("xpath", "//div[contains(@class, 'server-status')]"),
            ("xpath", "//div[contains(@class, 'server-card')]"),
        ]

        time.sleep(10)

        server_element = None
        for selector_type, selector in server_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector) if selector_type == "xpath" else driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    server_element = elements[0]
                    break
            except Exception:
                continue

        if not server_element:
            raise Exception("Could not find server element")

        driver.execute_script("arguments[0].click();", server_element)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        current_url = driver.current_url
        server_id = 'Unknown'
        match = re.search(r'/server/([a-f0-9]+)', current_url)
        if match:
            server_id = match.group(1)

        renew_button_selectors = [
            ("xpath", "//span[contains(@class, 'Button___StyledSpan')]/parent::button"),
            ("xpath", "//button[.//span[contains(text(), 'ADD 96 HOUR')]]"),
            ("xpath", "//button[@color='primary' and contains(@class, 'Button__ButtonStyle')]"),
        ]

        renew_button = None
        for selector_type, selector in renew_button_selectors:
            try:
                elements = driver.find_elements(By.XPATH if selector_type == "xpath" else By.CSS_SELECTOR, selector)
                if elements:
                    renew_button = elements[0]
                    break
            except Exception:
                continue

        if not renew_button:
            raise Exception("Could not find renew button")

        initial_time = get_expiration_time(driver)
        renew_button.click()

        time.sleep(70)
        driver.refresh()
        time.sleep(8)

        new_expiration_time = get_expiration_time(driver)

        if initial_time and new_expiration_time:
            try:
                initial_dt = parser.parse(initial_time)
                new_dt = parser.parse(new_expiration_time)

                if new_dt > initial_dt:
                    print("Renewal successful! Time extended.")
                    print(f"  Before: {initial_time}")
                    print(f"  After:  {new_expiration_time}")
                    update_last_renew_file(success=True, new_time=new_expiration_time, server_id=server_id)
                    send_renew_success(server_id, initial_time, new_expiration_time)
                else:
                    print("Renewal may have failed - time not extended")
                    update_last_renew_file(success=False, error_message="Time not extended", server_id=server_id)
                    send_renew_failure(server_id, "Time not extended after renewal click")
            except Exception as e:
                print(f"Date parsing error: {e}")
                update_last_renew_file(success=False, error_message=f"Date parsing error: {e}", server_id=server_id)
                send_renew_failure(server_id, f"Date parsing error: {e}")
        else:
            print("Could not verify renewal - could not get expiration times")
            update_last_renew_file(success=False, error_message="Could not find expiration times", server_id=server_id)
            send_renew_failure(server_id, "Could not find expiration times on page")

    except TimeoutException as e:
        msg = f"Timeout: {e}"
        print(msg)
        if driver:
            driver.save_screenshot('error_timeout.png')
        update_last_renew_file(False, error_message=msg)
        send_renew_error(msg)
    except Exception as e:
        msg = f"Error: {e}"
        print(msg)
        if driver:
            driver.save_screenshot('error.png')
        update_last_renew_file(False, error_message=msg)
        send_renew_error(msg)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                print(f"Error closing browser: {e}")


def run_tests():
    results = []
    failed = False

    print("=== TEST MODE ===")

    results.append(("Telegram notification", False))
    tg_ok = send_telegram_message(
        "\U0001F9EA *TickHosting Test Results* \U0001F9EA\n\n"
        "\U0001F504 Running diagnostic tests...\n"
        "Checking login and configuration..."
    )
    if tg_ok:
        results[-1] = ("Telegram notification", True)
        print("  [PASS] Telegram message sent")
    else:
        results[-1] = ("Telegram notification", False)
        print("  [FAIL] Telegram not configured or send failed")

    print("\n--- Testing login ---")
    driver = None
    login_ok = False
    try:
        driver = setup_driver()
        driver.set_page_load_timeout(30)
        driver.get("https://tickhosting.com")
        time.sleep(5)
        login_ok = login_to_dashboard(driver)
    except Exception as e:
        print(f"  [FAIL] Login threw exception: {e}")
    finally:
        if driver:
            driver.quit()

    results.append(("TickHosting login", login_ok))
    if login_ok:
        print("  [PASS] Login successful")
    else:
        print("  [FAIL] Login failed")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)

    content = (
        f"Test Results ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n"
        f"{'='*40}\n"
    )
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        content += f"  [{status}] {name}\n"
    content += f"\n{passed}/{total} tests passed\n"

    with open('test_results.txt', 'w') as f:
        f.write(content)

    print(f"\n{content}")

    all_pass = passed == total
    verdict = "\U00002705 *All checks passed* \U0001F680" if all_pass else "\U0001F6A8 *Needs more development* \U0001F4A1"
    commit = os.getenv('GITHUB_SHA', '')
    commit_link = f"\n\U0001F517 `{commit[:7]}`" if commit else ""

    summary = (
        f"{verdict}\n\n"
        f"{' '.join(['\U00002705' if ok else '\U0000274C' for _, ok in results])}\n\n"
    )
    for name, ok in results:
        icon = "\U00002705" if ok else "\U0000274C"
        summary += f"{icon}  `{name}`\n"
    summary += f"\n**{passed}/{total} tests passed**\n"
    if not all_pass:
        failed_names = [name for name, ok in results if not ok]
        summary += f"\n\U0001F6A7 Failing: {', '.join(f'`{n}`' for n in failed_names)}"
    summary += commit_link

    send_telegram_message(summary)

    return 0 if passed == total else 1


if __name__ == "__main__":
    if os.getenv('TEST_MODE', '').lower() in ('true', '1'):
        exit(run_tests())
    else:
        main()
