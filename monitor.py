import os
import sys
import requests
from playwright.sync_api import sync_playwright

# ------- ВАША АДРЕСА (Київська обл.) -------
CITY = "Гора"                     # Ваше населений пункт
STREET = "Басейна"             # Ваша вулиця (вкажіть свою)
HOUSE = "7"                       # Ваш будинок (вкажіть свій)
# -------------------------------------------

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"

def send_telegram_message(text):
    url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Помилка Telegram: {e}")

def get_current_status():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Емуляція реального комп'ютера, щоб сайт не блокував
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Перехід на сторінку ДТЕК КРЕМ...")
        page.goto("https://dtek-krem.com.ua", timeout=60000)
        page.wait_for_load_state("networkidle")
        
        # Використовуємо лічильник >> visible=true, щоб обійти приховані мобільні елементи
        print(f"Введення населеного пункту: {CITY}")
        city_input = page.locator("input[placeholder*='Населений'] >> visible=true").first
        city_input.fill(CITY)
        page.wait_for_timeout(1500)
        city_input.press("Enter")
        page.wait_for_timeout(1500)
        
        print(f"Введення вулиці: {STREET}")
        street_input = page.locator("input[placeholder*='Вулиця'] >> visible=true").first
        street_input.fill(STREET)
        page.wait_for_timeout(1500)
        street_input.press("Enter")
        page.wait_for_timeout(1500)
        
        print(f"Введення будинку: {HOUSE}")
        house_input = page.locator("input[placeholder*='Будинок'] >> visible=true").first
        house_input.fill(HOUSE)
        page.wait_for_timeout(1500)
        house_input.press("Enter")
        
        print("Очікування результату таблиці...")
        # Чекаємо появи блоку графіка або статусу (пробуємо кілька можливих селекторів ДТЕК)
        page.wait_for_selector(".current-status-box, .disconetion-status, .schedule-table", timeout=30000)
        
        status_element = page.locator(".current-status-box, .disconetion-status, .schedule-table-info").first
        status_text = status_element.inner_text()
        
        browser.close()
        return status_text.strip()

def main():
    try:
        current_status = get_current_status()
        print(f"Поточний статус з сайту:\n{current_status}")
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
        
        if current_status != last_status:
            message = f"🚨 Зміна статусу світла (с. {CITY})!\n\n📋 Поточний стан:\n{current_status}"
            send_telegram_message(message)
            
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
                
    except Exception as e:
        print(f"Помилка під час виконання: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
