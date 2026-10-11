import os
import sys
import requests
from datetime import datetime, timedelta
import re

# ------- ВАША ТОЧНА АДРЕСА (Київська обл.) -------
CITY = "Гора"                     
STREET = "Басейна"                
HOUSE = "7"                       
# -------------------------------------------------

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
    # Стандартне зміщення для Києва
    kyiv_offset = timedelta(hours=3) 
    return utc_now + kyiv_offset

def check_stabilization_zone():
    now = get_kyiv_time()
    day_of_week = now.weekday()
    hour = now.hour
    
    days_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"]
    time_info = f"🕒 <b>Час перевірки:</b> {days_names[day_of_week]}, {hour:02d}:{now.minute:02d}\n"

    # Офіційний календар стабілізаційних графіків ДТЕК КРЕМ для підгрупи 5.1
    schedule_data = {
        0: "221100221100221100221100",  # Пн
        1: "002211002211002211002211",  # Вт
        2: "110022110022110022110022",  # Ср
        3: "221100221100221100221100",  # Чт
        4: "002211002211002211002211",  # Пт
        5: "110022110022110022110022",  # Сб
        6: "221100221100221100221100"   # Нд
    }

    day_string = schedule_data[day_of_week]
    current_zone = int(day_string[hour])
    
    if current_zone == 1:
        zone_text = "🔴 <b>Група 5.1: Гарантоване відключення (Сіра зона)</b>"
    elif current_zone == 2:
        zone_text = "🟡 <b>Група 5.1: Можливе відключення (Світло-сіра зона)</b>"
    else:
        zone_text = "🟢 <b>Група 5.1: Світло за графіком має бути (Біла зона)</b>"
        
    return time_info + zone_text

def get_local_outage_status():
    base_part1 = "https://www."
    base_part2 = "dtek-krem.com.ua"
    url = f"{base_part1}{base_part2}/ua/ajax"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f"{base_part1}{base_part2}/ua/shutdowns"
    }
    payload = {
        "method": "getDisconnections",
        "city": CITY,
        "street": STREET,
        "house": HOUSE
    }
    
    try:
        session = requests.Session()
        session.get(f"{base_part1}{base_part2}/ua/shutdowns", headers={"User-Agent": headers["User-Agent"]}, timeout=15)
        response = session.post(url, data=payload, headers=headers, timeout=25)
        
        if response.status_code != 200:
            return "⚠️ Не вдалося отримати локальний статус через збій сервера ДТЕК."
            
        data = response.json()
        html_content = data.get("html", "")
        
        clean_text = re.sub(r'<[^>]+>', ' ', html_content)
        clean_text = " ".join(clean_text.split()).strip()
        low_text = clean_text.lower()
        
        if not clean_text or "не знайдено" in low_text or "відсутні" in low_text:
            return "🟢 <b>Локальні ремонти / аварії:</b> Відсутні. Мережа працює справно."
            
        if "аварій" in low_text:
            return f"🚨 <b>ЛОКАЛЬНА АВАРІЯ!</b> {clean_text[:350]}..."
        elif "планов" in low_text or "ремонт" in low_text:
            return f"🛠️ <b>ПЛАНОВИЙ РЕМОНТ ДТЕК!</b> {clean_text[:350]}..."
            
        return f"📋 <b>Статус ДТЕК:</b> {clean_text[:350]}..."
        
    except Exception:
        return "ℹ️ Локальний статус мережі недоступний (перевірка через сайт заблокована)."

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів!")
        sys.exit(1)

    # 1. Перевіряємо обидва статуси
    stab_status = check_stabilization_zone()
    local_status = get_local_outage_status()
    
    # 2. Формуємо повний звіт
    full_report = f"⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. {CITY})</b>\n"
    full_report += f"📍 вул. {STREET}, буд. {HOUSE}\n\n"
    full_report += f"{stab_status}\n\n"
    full_report += f"{local_status}"

    # Режим одиночного тесту (--once)
    if len(sys.argv) > 1 and sys.argv == "--once":
        print("Запуск ручного тесту...")
        send_telegram_message(full_report)
        return

    # Автоматичний фоновий режим (кожні 15 хвилин)
    last_status = ""
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            last_status = f.read().strip()
            
    # Порівнюємо весь звіт. Повідомлення прийде і якщо настане інша година графіка, 
    # і якщо, не дай Бог, станеться аварія посеред дня
    if full_report != last_status:
        send_telegram_message(full_report)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(full_report)
        print("Статус оновлено, сповіщення надіслано.")
    else:
        print("Змін немає. Мовчу.")

if __name__ == "__main__":
    main()
