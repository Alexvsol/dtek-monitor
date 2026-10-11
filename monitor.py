import os
import sys
import requests
from playwright.sync_api import sync_playwright

# ------- ВАША АДРЕСА (Київська обл.) -------
CITY = "Гора"
STREET = "Басейна"
HOUSE = "7"
# -------------------------------------------

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"

def send_telegram_message(text):
    # Прямий захищений запит до API Telegram
    url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Відповідь Telegram: {response.status_code}")
    except Exception as e:
        print(f"Помилка відправки Telegram: {e}")

def get_current_status():
    with sync_playwright() as p:
        # Запускаємо браузер із маскуванням під звичайного користувача
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Перехід на сторінку графіків ДТЕК КРЕМ...")
        page.goto("https://dtek-krem.com.ua", timeout=60000, wait_until="domcontentloaded")
        
        # Чекаємо повного завантаження форми
        page.wait_for_selector("input[placeholder*='Населений']", timeout=20000)
        
        print(f"Вибір населеного пункту: {CITY}")
        # Знаходимо ПЕРШЕ ВИДИМЕ поле, клікаємо по ньому для активації та вводимо текст
        city_input = page.locator("input[placeholder*='Населений'] >> visible=true").first
        city_input.click()
        city_input.fill(CITY)
        page.wait_for_timeout(1000)
        city_input.press("Enter")
        page.wait_for_timeout(1000)
        
        print(f"Вибір вулиці: {STREET}")
        street_input = page.locator("input[placeholder*='Вулиця'] >> visible=true").first
        street_input.click()
        street_input.fill(STREET)
        page.wait_for_timeout(1000)
        street_input.press("Enter")
        page.wait_for_timeout(1000)
        
        print(f"Вибір будинку: {HOUSE}")
        house_input = page.locator("input[placeholder*='Будинок'] >> visible=true").first
        house_input.click()
        house_input.fill(HOUSE)
        page.wait_for_timeout(1000)
        house_input.press("Enter")
        
        print("Очікування появи результатів графіка...")
        # Сайт завантажує дані динамічно в блок результатів. Чекаємо на плашку або таблицю
        page.wait_for_selector(".current-status-box, .disconetion-status, .schedule-table, .alert", timeout=20000)
        
        # Пробуємо зчитати статус з різних можливих блоків ДТЕК
        status_box = page.locator(".current-status-box, .disconetion-status, .schedule-table-info, .alert").first
        status_text = status_box.inner_text()
        
        browser.close()
        return status_text.strip()

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка: Перевірте секрети TELEGRAM_TOKEN та TELEGRAM_CHAT_ID у налаштуваннях!")
        sys.exit(1)

    try:
        current_status = get_current_status()
        # Якщо ДТЕК вивів забагато тексту, очищаємо зайві пробіли
        current_status = " ".join(current_status.split())
        print(f"Отримано чистий статус з сайту:\n{current_status}")
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
        
        if current_status != last_status:
            message = f"🚨 Зміна статусу світла у с. {CITY}!\n\n📋 Стан:\n{current_status}"
            send_telegram_message(message)
            
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
            print("Статус оновлено, сповіщення надіслано.")
        else:
            print("Статус не змінився з минулої перевірки.")
                
    except Exception as e:
        print(f"Критична помилка під час виконання: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
