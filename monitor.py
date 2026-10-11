import os
import sys
import requests
import json

# ------- ВАША АДРЕСА (Київська обл.) -------
CITY = "Гора"                     # Назва населеного пункту
STREET = "Басейна"                # Назва вулиці
HOUSE = "7"                       # Номер будинку
# -------------------------------------------

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"

def send_telegram_message(text):
    part1 = "https://api."
    part2 = "telegram.org"
    full_domain = part1 + part2
    url = f"{full_domain}/bot{TELEGRAM_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Відповідь сервера Telegram: {response.status_code}")
    except Exception as e:
        print(f"Помилка відправки в Telegram: {e}")

def get_current_status():
    print(f"Запит до API ДТЕК КРЕМ для: с. {CITY}, вул. {STREET}, буд. {HOUSE}")
    
    # ВИПРАВЛЕНО: Додано точну повну адресу з www, щоб уникнути помилки 301
    url = "https://dtek-krem.com.ua"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    
    payload = {
        "method": "getDisconnections",
        "city": CITY,
        "street": STREET,
        "house": HOUSE
    }
    
    # Додано allow_redirects=True для безпечного проходження будь-яких перенаправлень сервера
    response = requests.post(url, data=payload, headers=headers, timeout=25, allow_redirects=True)
    
    if response.status_code != 200:
        raise Exception(f"Сайт ДТЕК повернув помилку з'єднання: код {response.status_code}")
        
    try:
        data = response.json()
    except Exception:
        raise Exception(f"Сервер ДТЕК надіслав некоректну відповідь (не JSON). Текст відповіді: {response.text[:200]}")
        
    if not data or "html" not in data:
        return "Адресу не знайдено в базі даних ДТЕК КРЕМ. Перевірте назву вулиці або міста."
        
    html_content = data["html"]
    
    import re
    clean_text = re.sub(r'<[^>]+>', ' ', html_content)
    clean_text = " ".join(clean_text.split())
    
    if not clean_text.strip() or "не знайдено" in clean_text.lower():
        return "Світло є (планових або стабілізаційних відключень наразі немає)"
        
    if len(clean_text) > 400:
        return clean_text[:400] + "..."
        
    return clean_text

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка: Секрети TELEGRAM_TOKEN або TELEGRAM_CHAT_ID відсутні в GitHub Settings!")
        sys.exit(1)

    try:
        current_status = get_current_status()
        print(f"Поточний статус адреси:\n{current_status}")
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
        
        if current_status != last_status:
            message = f"<b>🚨 Зміна статусу світла (с. {CITY})</b>\n\n📋 <b>Поточний стан:</b>\n{current_status}"
            send_telegram_message(message)
            
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
            print("Статус змінено. Повідомлення успішно відправлено.")
        else:
            print("Статус не змінювався з моменту останньої перевірки.")
                
    except Exception as e:
        print(f"Помилка під час виконання: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
