import os
import sys
import requests

# ------- ВАША АДРЕСА (Київська обл.) -------
CITY = "Гора"                     # Назва населеного пункту
STREET = "Басейна"             # Назва вулиці
HOUSE = "7"                       # Номер будинку
# -------------------------------------------

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"

def send_telegram_message(text):
    # Виправлено адресу надсилання на правильний шлях Telegram API
    url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        response = requests.post(url, json=payload)
        print(f"Відповідь Telegram API: {response.status_code}")
    except Exception as e:
        print(f"Помилка відправки в Telegram: {e}")

def get_current_status():
    print(f"Надсилання прямого API-запиту для: с. {CITY}, вул. {STREET}, буд. {HOUSE}")
    
    # Використовуємо прямий внутрішній шлях обробника ДТЕК Київські регіональні електромережі
    api_url = "https://dtek-krem.com.ua"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    
    # Дані, які сайт зазвичай відправляє фоном при пошуку
    payload = {
        "method": "getDisconnections",
        "city": CITY,
        "street": STREET,
        "house": HOUSE
    }
    
    # Запит до бази даних графіків
    response = requests.post(api_url, data=payload, headers=headers, timeout=30)
    
    if response.status_code != 200:
        raise Exception(f"Сайт ДТЕК повернув помилку з'єднання: код {response.status_code}")
        
    data = response.json()
    
    # Перевіряємо відповідь від сервера
    if not data or "html" not in data:
        return "Адресу не знайдено або графіки відсутні"
        
    html_content = data["html"]
    
    # Базовий швидкий аналіз відповіді (шукаємо ключові статуси ДТЕК)
    if "Група" in html_content:
        # Спроба витягнути рядок з номером групи та поточним станом
        import re
        # Очищаємо HTML від тегів для отримання чистого тексту
        clean_text = re.sub(r'<[^>]+>', ' ', html_content)
        # Прибираємо зайві пробіли
        clean_text = " ".join(clean_text.split())
        
        # Обрізаємо занадто довгий текст, залишаючи головну інформацію про поточний стан
        if len(clean_text) > 400:
            return clean_text[:400] + "..."
        return clean_text
        
    if "Світло є" in html_content or "не планується" in html_content:
        return "Світло є (відключення не плануються)"
        
    if "Відключення" in html_content:
        return "Графік активовано: За адресою присутні обмеження"
        
    return "Статус невизначений (можливо, світло є, або оновлюється база даних)"

def main():
    try:
        current_status = get_current_status()
        print(f"Отримано статус:\n{current_status}")
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
        
        if current_status != last_status:
            message = f"🚨 Зміна статусу світла (с. {CITY})!\n\n📋 Поточний стан:\n{current_status}"
            send_telegram_message(message)
            
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
        else:
            print("Статус не змінився. Сповіщення не потрібне.")
                
    except Exception as e:
        print(f"Помилка під час виконання скрипта: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
        
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
