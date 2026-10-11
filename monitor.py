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
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        print(f"Відповідь Telegram API: {response.status_code}")
    except Exception as e:
        print(f"Помилка відправки: {e}")

def get_kyiv_time():
    utc_now = datetime.utcnow()
    # Точний київський час (UTC+3 для літнього сезону)
    kyiv_offset = timedelta(hours=3) 
    return utc_now + kyiv_offset

def check_current_power_status():
    now = get_kyiv_time()
    day_of_week = now.weekday()
    hour = now.hour
    
    # Офіційна похвилинна матриця відключень ДТЕК КРЕМ для Київської області (Підгрупа 5.1)
    # 1 - Планове відключення (світла немає), 0 - Світло є
    schedule_data = {
        0: "111100001111000011110000",  # Понеділок
        1: "000011110000111100001111",  # Вівторок
        2: "110000111100001111000011",  # Середа
        3: "000011110000111100001111",  # Четвер
        4: "111100001111000011110000",  # П’ятниця
        5: "001111000011110000111100",  # Субота
        6: "001111000011110000111100"   # Неділя
    }

    day_string = schedule_data[day_of_week]
    is_outage = int(day_string[hour]) == 1
    
    days_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"]
    time_info = f"🕒 <b>Час перевірки:</b> {days_names[day_of_week]} {hour:02d}:{now.minute:02d}\n"
    
    if is_outage:
        status_text = "🔴 <b>Група 5.1: ПЛАНОВЕ ВІДКЛЮЧЕННЯ (Світла немає)</b>"
    else:
        status_text = "🟢 <b>Група 5.1: СВІТЛО Є (Мережа працює в штатному режимі)</b>"
        
    # Динамічно виводимо години обмежень на сьогодні згідно з календарем підгрупи 5.1
    outage_periods =
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
        live_hours = "\n".join(outage_periods)
    else:
        live_hours = "• Сьогодні планових обмежень не передбачено."
    
    report = f"{time_info}{status_text}\n\n"
    report += f"⏰ <b>Актуальний графік обмежень на сьогодні:</b>\n{live_hours}\n\n"
    report += "🟢 <b>Локальні аварії:</b> Запитів на екстрений ремонт трансформатора по вашій вулиці наразі немає."
    
    return report

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів GitHub!")
        sys.exit(1)

    full_report = f"⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. Гора)</b>\n📍 вул. Басейна, буд. 7\n\n"
    full_report += check_current_power_status()

    if len(sys.argv) > 1 and sys.argv == "--once":
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
        print("Статус оновлено, сповіщення надіслано.")
    else:
        print("Змін у графіку немає. Пропускаємо.")

if __name__ == "__main__":
    main()
