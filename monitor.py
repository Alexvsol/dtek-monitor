import os
import sys
import requests
from playwright.sync_api import sync_playwright

# ------- ВАША АДРЕСА (Київська обл.) -------
CITY = "Гора"               # Назва вашого міста чи села
STREET = "Басейна"        # Назва вулиці
HOUSE = "9"                     # Номер будинку
# -------------------------------------------

# Беремо секрети з оточення GitHub
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
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        
        print("Перехід на сторінку ДТЕК...")
        page.goto("https://dtek-krem.com.ua", timeout=60000)
        
        # Заповнення форми за текстом placeholder-ів (найбільш стабільний варіант)
        page.fill("input[placeholder*='Населений']", CITY)
        page.keyboard.press("Enter")
        page.wait_for_timeout(2000)
        
        page.fill("input[placeholder*='Вулиця']", STREET)
        page.keyboard.press("Enter")
        page.wait_for_timeout(2000)
        
        page.fill("input[placeholder*='Будинок']", HOUSE)
        page.keyboard.press("Enter")
        
        print("Очікування завантаження графіка...")
        # ДТЕК виводить поточний стан у блок з класом disconetion-status або схожим
        # Якщо селектори сайту зміняться, цей рядок треба буде підправити
        page.wait_for_selector(".current-status-box, .disconetion-status", timeout=20000)
        
        status_text = page.locator(".current-status-box, .disconetion-status").first.inner_text()
        browser.close()
        return status_text.strip()

def main():
    try:
        current_status = get_current_status()
        print(f"Поточний статус: {current_status}")
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
        
        if current_status != last_status:
            message = f"🚨 Зміна статусу світла у {CITY}!\nСтарий: {last_status if last_status else 'Невідомо'}\nНовий: {current_status}"
            send_telegram_message(message)
            
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
                
    except Exception as e:
        print(f"Помилка під час виконання: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
