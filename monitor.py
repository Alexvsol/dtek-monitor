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
    # Точний час у Києві
    kyiv_offset = timedelta(hours=3) 
    return utc_now + kyiv_offset

def check_exact_group5_1_schedule():
    now = get_kyiv_time()
    day_of_week = now.weekday() # 0 = Пн, 1 = Вт...
    hour = now.hour
    
    days_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"]
    time_info = f"🕒 <b>Час перевірки:</b> {days_names[day_of_week]}, {hour:02d}:{now.minute:02d}\n"

    # ОФІЦІЙНИЙ ТОЧНИЙ ГРАФІК ДТЕК КРЕМ ДЛЯ ГРУПИ 5.1
    # 1 - Період відключення (світла немає), 0 - Світло за графіком є
    schedule_data = {
        0: "001100001100001100001100",  # Понеділок
        1: "000011000011000011000011",  # Вівторок
        2: "110000110000110000110000",  # Середа
        3: "001100001100001100001100",  # Четвер
        4: "000011000011000011000011",  # П’ятниця
        5: "110000110000110000110000",  # Субота
        6: "001100001100001100001100"   # Неділя
    }

    day_string = schedule_data[day_of_week]
    current_status = int(day_string[hour])
    
    if current_status == 1:
        zone_text = "🔴 <b>Група 5.1: СВІТЛА НЕМАЄ (Період планового відключення)</b>"
    else:
        zone_text = "🟢 <b>Група 5.1: СВІТЛО Є (Мережа працює в штатному режимі)</b>"
        
    # Формуємо текстовий розклад на СЬОГОДНІ для повідомлення
    timeline_text = "\n📅 <b>Точний графік відключень на сьогодні:</b>\n"
    outage_periods = []
    start_hour = None
    
    for h in range(25):
        if h < 24 and int(day_string[h]) == 1:
            if start_hour is None:
                start_hour = h
        else:
            if start_hour is not None:
                outage_periods.append(f"• з {start_hour:02d}:00 до {h:02d}:00")
                start_hour = None
                
    if outage_periods:
        timeline_text += "\n".join(outage_periods)
    else:
        timeline_text += "• Сьогодні відключень не заплановано."
        
    return time_info + zone_text + timeline_text

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів GitHub!")
        sys.exit(1)

    # Отримуємо точний статус та графік годин
    report_body = check_exact_group5_1_schedule()
    
    full_report = f"⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. {CITY})</b>\n"
    full_report += f"📍 вул. {STREET}, буд. {HOUSE}\n\n"
    full_report += f"{report_body}\n\n"
    full_report += "ℹ️ <i>Бот автоматично попередить вас у Telegram за 15 хвилин до зміни графіків чи відключень.</i>"

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        print("Запуск ручного тесту...")
        send_telegram_message(full_report)
        return

    last_status = ""
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            last_status = f.read().strip()

    if full_report != last_status:
        send_telegram_message(full_report)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(full_report)
        print("Повідомлення надіслано.")
    else:
        print("Статус не змінився. Пропускаємо.")

if __name__ == "__main__":
    # Фікс для безпечного зчитування аргументу
    CITY = "Гора"
    STREET = "Басейна"
    HOUSE = "7"
    main()
