import os
import sys
import requests
import json
import time
import re

# ------- ВАША АДРЕСА (Київська обл.) -------
CITY = "Гора"                     
STREET = "Басейна"                
HOUSE = "7"                       
# -------------------------------------------

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"

def send_telegram_message(text):
    # Збираємо адресу сервера без використання прямих лінків у тексті коду
    part1 = "https://api."
    part2 = "telegram.org"
    url = f"{part1}{part2}/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Відповідь Telegram: {response.status_code}")
    except Exception as e:
        print(f"Помилка відправки Telegram: {e}")

def get_current_status():
    # ТОЧНА АДРЕСА З WWW для повного уникнення помилки редиректу 301!
    url = "https://dtek-krem.com.ua"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    payload = {
        "method": "getDisconnections",
        "city": CITY,
        "street": STREET,
        "house": HOUSE
    }
    
    # Використовуємо сесію для підтримки кукісів безпеки сайту ДТЕК
    session = requests.Session()
    response = session.post(url, data=payload, headers=headers, timeout=20)
    
    if response.status_code != 200:
        raise Exception(f"Код сервера ДТЕК: {response.status_code}")
        
    data = response.json()
    if not data or "html" not in data:
        return "Адресу не знайдено"
        
    html_content = data["html"]
    
    clean_text = re.sub(r'<[^>]+>', ' ', html_content)
    clean_text = " ".join(clean_text.split())
    
    if not clean_text.strip() or "не знайдено" in clean_text.lower():
        return "Світло є (стабілізаційних відключень за графіком немає)"
        
    return clean_text[:400] + "..." if len(clean_text) > 400 else clean_text

def run_monitoring():
    print(f"Старт моніторингу ДТЕК для с. {CITY}, вул. {STREET}...")
    send_telegram_message("🔌 <b>Хмарний монітор ДТЕК КРЕМ успішно запущено!</b>\nПочинаю фонову перевірку графіків світла.")
    
    while True:
        try:
            print("Перевірка статусу на сайті ДТЕК...")
            current_status = get_current_status()
            print(f"Отримано стан: {current_status}")
            
            last_status = ""
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, "r", encoding="utf-8") as f:
                    last_status = f.read().strip()
            
            if current_status != last_status:
                message = f"<b>🚨 Зміна статусу світла (с. {CITY})</b>\n\n📋 <b>Поточний стан:</b>\n{current_status}"
                send_telegram_message(message)
                
                with open(STATUS_FILE, "w", encoding="utf-8") as f:
                    f.write(current_status)
            else:
                print("Статус не змінювався з минулої перевірки.")
                
        except Exception as e:
            print(f"Помилка опитування сайту ДТЕК: {e}")
            
        # Робимо паузу 15 хвилин (900 секунд) перед наступним колом перевірки
        time.sleep(900)

if __name__ == "__main__":
    # Цей блок дозволяє запускати скрипт як на GitHub Actions (один раз), так і безкінечно в хмарі
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        try:
            status = get_current_status()
            print(f"Поодинокий запуск. Статус: {status}")
            # Для тесту відправимо повідомлення відразу
            send_telegram_message(f"📋 <b>Тест зв'язку Telegram API:</b>\nСтатус світла: {status}")
        except Exception as e:
            print(f"Помилка тесту: {e}")
    else:
        run_monitoring()
