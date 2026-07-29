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

        email_input = driver.find_element(By.NAME, 'email')
        password_input = driver.find_element(By.NAME, 'password')
        login_button = driver.find_element(By.XPATH, "//button[@type='submit']")

        email_input.clear()
        email_input.send_keys(EMAIL)
        password_input.clear()
        password_input.send_keys(PASSWORD)
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
        send_renew_error(f"Login failed: {e}")
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


if __name__ == "__main__":
    main()
