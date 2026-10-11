import os
import sys
import requests

# ------- ВАША АДРЕСА (Київська обл.) -------
CITY = "Гора"
STREET = "Центральна"
HOUSE = "1"
# -------------------------------------------

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"

def send_telegram_message(text):
    # Використовуємо офіційне API без текстових доменів у коді
    api_endpoint = "https://telegram.org"
    url = f"{api_endpoint}/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Відповідь Telegram API: {response.status_code}")
    except Exception as e:
        print(f"Помилка Telegram: {e}")

def get_current_status():
    print(f"Запит до ДТЕК: с. {CITY}, вул. {STREET}, буд. {HOUSE}")
    
    # Використовуємо коректне внутрішнє API ДТЕК КРЕМ
    base_site = "https://dtek-krem.com.ua"
    api_url = f"{base_site}/ua/ajax"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    payload = {
        "method": "getDisconnections",
        "city": CITY,
        "street": STREET,
        "house": HOUSE
    }
    
    response = requests.post(api_url, data=payload, headers=headers, timeout=30)
    
    if response.status_code != 200:
        raise Exception(f"Помилка сервера ДТЕК: код {response.status_code}")
        
    try:
        data = response.json()
    except Exception:
        raise Exception("Сервер ДТЕК повернув не JSON структуру")
    
    if not data or "html" not in data:
        return "Адресу не знайдено або графіки відсутні"
        
    html_content = data["html"]
    
    import re
    clean_text = re.sub(r'<[^>]+>', ' ', html_content)
    clean_text = " ".join(clean_text.split())
    
    if not clean_text.strip():
        return "Світло є (планових відключень немає)"
        
    if len(clean_text) > 400:
        return clean_text[:400] + "..."
        
    return clean_text

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка: Секрети TELEGRAM_TOKEN або TELEGRAM_CHAT_ID відсутні в GitHub Settings!")
        sys.exit(1)

    try:
        current_status = get_current_status()
        print(f"Поточний статус з сайту ДТЕК:\n{current_status}")
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
        
        if current_status != last_status:
            message = f"🚨 Зміна статусу світла (с. {CITY})!\n\n📋 Поточний стан:\n{current_status}"
            send_telegram_message(message)
            
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
            print("Статус оновлено, повідомлення надіслано.")
        else:
            print("Статус не змінився.")
                
    except Exception as e:
        print(f"Критична помилка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
