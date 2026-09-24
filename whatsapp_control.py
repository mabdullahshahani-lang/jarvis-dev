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


def find_and_open_contact(contact_name, timeout=25):
    """Searches for a contact by name and opens their chat. Returns True if found."""
    driver = get_driver()
    try:
        search_box = None
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                search_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
                break
            except Exception:
                time.sleep(0.5)

        if search_box is None:
            return False  # QR not scanned in time / page not loaded

        search_box.click()
        search_box.send_keys(contact_name)
        time.sleep(2)

        result = driver.find_element(By.XPATH, f'//span[@title="{contact_name}"]')
        result.click()
        time.sleep(1)
        return True
    except Exception as e:
        print("Error finding contact:", e)
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