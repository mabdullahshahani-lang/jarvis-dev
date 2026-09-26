import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.keys import Keys
from webdriver_manager.microsoft import EdgeChromiumDriverManager

_driver = None

# A SEPARATE profile just for JARVIS's automation (not your everyday Edge).
# First run: you'll scan the WhatsApp QR code once. After that, it stays logged in.
PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_whatsapp_profile")


def get_driver():
    global _driver
    if _driver is None:
        options = webdriver.EdgeOptions()
        options.add_argument(f"--user-data-dir={PROFILE_DIR}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--remote-allow-origins=*")
        options.add_experimental_option("detach", True)  # keep window open after script logic moves on

        service = Service(EdgeChromiumDriverManager().install())
        _driver = webdriver.Edge(service=service, options=options)
    return _driver


def open_whatsapp():
    driver = get_driver()
    driver.get("https://web.whatsapp.com")
    time.sleep(3)
    return driver


def find_and_open_contact(contact_name, timeout=30):
    """Searches for a contact by name and opens their chat. Returns True if found."""
    driver = get_driver()
    try:
        print(f"[WhatsApp] Waiting for search box to appear (up to {timeout}s)...")
        search_box = None
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                search_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
                break
            except Exception:
                pass
            try:
                # fallback: newer WhatsApp Web layouts sometimes use a different data-tab or aria-label
                search_box = driver.find_element(By.XPATH, '//div[@aria-label="Search input textbox"]')
                break
            except Exception:
                pass
            time.sleep(0.5)

        if search_box is None:
            print("[WhatsApp] Search box never appeared - page may not have loaded, or QR not scanned yet.")
            return False

        print("[WhatsApp] Search box found, typing contact name...")
        search_box.click()
        search_box.send_keys(contact_name)
        time.sleep(2)

        print("[WhatsApp] Looking for first search result...")
        first_result = None
        try:
            first_result = driver.find_element(
                By.XPATH, '//div[@aria-label="Search results."]//div[@role="listitem"][1]'
            )
        except Exception:
            pass
        if first_result is None:
            try:
                first_result = driver.find_element(
                    By.XPATH, '(//div[@data-testid="cell-frame-container"])[1]'
                )
            except Exception:
                pass
        if first_result is None:
            try:
                # broad fallback: any span containing the searched name, case-insensitive
                first_result = driver.find_element(
                    By.XPATH, f'//span[contains(translate(@title, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "{contact_name.lower()}")]'
                )
            except Exception:
                pass

        if first_result is None:
            print("[WhatsApp] No search result found for:", contact_name)
            return False

        first_result.click()
        time.sleep(1)
        print("[WhatsApp] Contact opened successfully.")
        return True
    except Exception as e:
        print("[WhatsApp] Error finding contact:", e)
        return False


def type_message(message):
    driver = get_driver()
    try:
        msg_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]')
        msg_box.click()
        msg_box.send_keys(message)
        return True
    except Exception as e:
        print("Error typing message:", e)
        return False


def send_message():
    driver = get_driver()
    try:
        msg_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]')
        msg_box.send_keys(Keys.ENTER)
        return True
    except Exception as e:
        print("Error sending message:", e)
        return False