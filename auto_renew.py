from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime
import time
from dateutil import parser
import os
import requests
import re

EMAIL = os.getenv('EMAIL', '')
PASSWORD = os.getenv('PASSWORD', '')
SESSION_COOKIE = os.getenv('PTERODACTYL_SESSION', '')
CAPTCHA_API_KEY = os.getenv('CAPTCHA_API_KEY', '')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

APP_URL = 'https://tickhosting.com'


def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    return webdriver.Chrome(options=options)


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
        if not EMAIL or not PASSWORD:
            raise ValueError("EMAIL or PASSWORD not set")

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

        email_input.clear()
        email_input.send_keys(EMAIL)
        password_input.clear()
        password_input.send_keys(PASSWORD)

        solve_recaptcha(driver)

        login_button.click()
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


def solve_recaptcha(driver):
    if not CAPTCHA_API_KEY:
        print("CAPTCHA_API_KEY not set, skipping captcha solve")
        return False

    try:
        sitekey = None
        try:
            recaptcha_div = driver.find_element(By.CSS_SELECTOR, ".g-recaptcha")
            sitekey = recaptcha_div.get_attribute("data-sitekey")
        except Exception:
            pass

        if not sitekey:
            try:
                sitekey = driver.execute_script(
                    "return ___grecaptcha_cfg && ___grecaptcha_cfg.clients && "
                    "___grecaptcha_cfg.clients[0] && "
                    "Object.values(___grecaptcha_cfg.clients[0])[0] && "
                    "Object.values(___grecaptcha_cfg.clients[0])[0].sitekey"
                )
            except Exception:
                pass

        if not sitekey:
            print("Could not find reCAPTCHA sitekey")
            return False

        page_url = driver.current_url
        print(f"Found reCAPTCHA sitekey: {sitekey}")
        print(f"Submitting to 2Captcha (page: {page_url})...")

        submit_url = "https://2captcha.com/in.php"
        submit_data = {
            "key": CAPTCHA_API_KEY,
            "method": "userrecaptcha",
            "googlekey": sitekey,
            "pageurl": page_url,
            "json": 1,
        }
        resp = requests.post(submit_url, data=submit_data, timeout=30)
        result = resp.json()

        if result.get("status") != 1:
            print(f"2Captcha submit failed: {result}")
            return False

        request_id = result["request"]
        print(f"2Captcha request ID: {request_id}, waiting for solution...")

        poll_url = "https://2captcha.com/res.php"
        for attempt in range(60):
            time.sleep(5)
            poll_resp = requests.get(poll_url, params={
                "key": CAPTCHA_API_KEY,
                "action": "get",
                "id": request_id,
                "json": 1,
            }, timeout=15)
            poll_result = poll_resp.json()

            if poll_result.get("status") == 1:
                token = poll_result["request"]
                print(f"reCAPTCHA solved, injecting token...")

                driver.execute_script(f"""
                    var textarea = document.getElementById('g-recaptcha-response');
                    if (textarea) {{
                        textarea.style.display = 'block';
                        textarea.innerHTML = '{token}';
                    }}
                """)
                time.sleep(1)
                print("reCAPTCHA token injected")
                return True
            elif poll_result.get("request") != "CAPCHA_NOT_READY":
                print(f"2Captcha error: {poll_result}")
                return False

        print("2Captcha timed out")
        return False
    except Exception as e:
        print(f"reCAPTCHA solver error: {e}")
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
