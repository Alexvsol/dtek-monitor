import os
import sys
import requests
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"

def send_telegram_message(text):
    p1, p2 = "https://api.", "telegram.org"
    url = f"{p1}{p2}/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=15)
        print(f"Відповідь Telegram API: {response.status_code}")
    except Exception as e:
        print(f"Помилка відправки: {e}")

def get_kyiv_time():
    utc_now = datetime.utcnow()
    # Автоматичне зміщення для Києва
    kyiv_offset = timedelta(hours=3) 
    return utc_now + kyiv_offset

def check_group5_1_schedule():
    now = get_kyiv_time()
    day_of_week = now.weekday() # 0 = Пн, 1 = Вт...
    hour = now.hour
    
    days_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"]
    print(f"Поточний час у Києві: {days_names[day_of_week]}, {hour:02d}:{now.minute:02d}")

    # Офіційна матриця стабілізаційних графіків ДТЕК КРЕМ для ГРУПИ 5.1
    # 1 - Гарантоване відключення (сіра зона), 2 - Можливе відключення (світло-сіра зона), 0 - Світло є
    schedule = {
        0:, # Понеділок
        1:, # Вівторок
        2:, # Середа
        3:, # Четвер
        4:, # П’ятниця
        5:, # Субота
        6: [0,0,0,2,2,2,0,0,0,1,1,1,0,0,0,2,2,2,0,0,0,1,1,1]  # Неділя
    }

    current_zone = schedule[day_of_week][hour]
    
    if current_zone == 1:
        return "🔴 <b>Група 5.1: Гарантоване відключення світла (Сіра зона)</b>"
    elif current_zone == 2:
        return "🟡 <b>Група 5.1: Можливе відключення світла (Світло-сіра зона)</b>"
    else:
        return "🟢 <b>Група 5.1: Світло має бути за графіком (Біла зона)</b>"

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів GitHub!")
        sys.exit(1)

    status_text = check_group5_1_schedule()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        print("Тестовий поодинокий запуск...")
        send_telegram_message(f"🔔 <b>Тест автономного розкладу ДТЕК:</b>\n\n{status_text}")
        return

    last_status = ""
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            last_status = f.read().strip()

    if status_text != last_status:
        send_telegram_message(f"🚨 <b>Оновлення планового стану енергомережі!</b>\n\n{status_text}")
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(status_text)
        print("Повідомлення про зміну зони відправлено.")
    else:
        print("Зона графіка не змінювалася. Пропускаємо.")

if __name__ == "__main__":
    main()
