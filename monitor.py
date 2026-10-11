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
    # Прямий технічний шлях до Telegram API
    url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Відповідь Telegram: {response.status_code}")
    except Exception as e:
        print(f"Помилка відправки Telegram: {e}")

def get_current_status():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # КРОК 1: Переходимо за ПРЯМИМ посиланням на форму відключень
        print("Перехід на пряму сторінку графіків ДТЕК КРЕМ...")
        page.goto("https://dtek-krem.com.ua", timeout=60000, wait_until="networkidle")
        
        # КРОК 2: Прибираємо спливаючі банери, які перекривають екран
        page.wait_for_timeout(2000)
        try:
            # Шукаємо кнопки закриття можливих банерів / кукісів
            close_buttons = page.locator(".modal-close, .close-modal, [class*='close'], button:has-text('Закрити')")
            for i in range(close_buttons.count()):
                if close_buttons.nth(i).is_visible():
                    close_buttons.nth(i).click()
                    print("Сховано спливаюче вікно сайту.")
        except Exception:
            pass

        # КРОК 3: Шукаємо видиме поле для введення
        print("Очікування появи форми пошуку...")
        page.wait_for_selector("input[placeholder*='Населений'] >> visible=true", timeout=20000)
        
        print(f"Введення міста: {CITY}")
        city_input = page.locator("input[placeholder*='Населений'] >> visible=true").first
        city_input.click()
        city_input.fill(CITY)
        page.wait_for_timeout(1000)
        # Якщо з'явилося випадаюче меню, вибираємо перший елемент або тиснемо Enter
        city_input.press("Enter")
        page.wait_for_timeout(1500)
        
        print(f"Введення вулиці: {STREET}")
        street_input = page.locator("input[placeholder*='Вулиця'] >> visible=true").first
        street_input.click()
        street_input.fill(STREET)
        page.wait_for_timeout(1000)
        street_input.press("Enter")
        page.wait_for_timeout(1500)
        
        print(f"Введення будинку: {HOUSE}")
        house_input = page.locator("input[placeholder*='Будинок'] >> visible=true").first
        house_input.click()
        house_input.fill(HOUSE)
        page.wait_for_timeout(1000)
        house_input.press("Enter")
        
        print("Очікування результатів...")
        # Чекаємо на завантаження результату графіка
        page.wait_for_selector(".current-status-box, .disconetion-status, .schedule-table, .alert, [id*='search-result']", timeout=25000)
        
        status_box = page.locator(".current-status-box, .disconetion-status, .schedule-table-info, .alert, [id*='search-result']").first
        status_text = status_box.inner_text()
        
        browser.close()
        return status_text.strip()

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка: Перевірте секрети TELEGRAM_TOKEN та TELEGRAM_CHAT_ID!")
        sys.exit(1)

    try:
        current_status = get_current_status()
        current_status = " ".join(current_status.split())
        print(f"Отримано статус з сайту:\n{current_status}")
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
        
        if current_status != last_status:
            message = f"🚨 Зміна статусу світла у с. {CITY}!\n\n📋 Поточний стан:\n{current_status}"
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
