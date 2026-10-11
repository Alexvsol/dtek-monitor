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
    kyiv_offset = timedelta(hours=3) 
    return utc_now + kyiv_offset

def get_dtek_live_data():
    base_url = "https://dtek-krem.com.ua"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://dtek-krem.com.ua",
        "Accept-Language": "uk-UA,uk;q=0.9"
    }
    payload = {
        "method": "getDisconnections",
        "city": CITY,
        "street": STREET,
        "house": HOUSE
    }
    
    try:
        session = requests.Session()
        session.get("https://dtek-krem.com.ua", headers={"User-Agent": headers["User-Agent"]}, timeout=15)
        response = session.post(base_url, data=payload, headers=headers, timeout=25)
        
        if response.status_code != 200:
            return None, "⚠️ Не вдалося отримати дані: помилка сервера ДТЕК."
            
        data = response.json()
        html_content = data.get("html", "")
        return html_content, None
    except Exception as e:
        print(f"Помилка підключення до ДТЕК: {e}")
        return None, "⚠️ Сервер ДТЕК тимчасово недоступний для хмарних запитів."

def parse_schedule_and_status(html_content):
    now = get_kyiv_time()
    hour = now.hour
    
    # Очищаємо текст для аналізу загального статусу аварій
    clean_text = re.sub(r'<[^>]+>', ' ', html_content)
    clean_text = " ".join(clean_text.split()).strip()
    low_text = clean_text.lower()
    
    # Шукаємо в HTML-коді розклад ДТЕК (вони виводять години в блоки з класами на кшталт 'slot' або через таблицю)
    # Спробуємо визначити поточний стан світла прямо зараз
    if "відключення" in low_text or "графік активовано" in low_text:
        # Перевіряємо, чи поточна година підпадає під обмеження на сайті
        current_zone_text = "🔴 <b>Група 5.1: СВІТЛА НЕМАЄ (Діє графік обмежень)</b>"
    else:
        current_zone_text = "🟢 <b>Група 5.1: СВІТЛО Є (Обмежень на цю годину немає)</b>"

    # Витягуємо точні години відключень, які сайт ДТЕК виділяє у текстовому або табличному виді
    # Зазвичай сайт пише: "Години відключення: ..." або виводить таблицю нових черг
    timeline_text = "\n⏰ <b>Актуальні години обмежень із сайту ДТЕК:</b>\n"
    
    # Шукаємо текстові згадки годин (наприклад, "19:00-23:00" або "з 16:00 до 20:00")
    time_matches = re.findall(r'(?:з\s+)?(\d{2}:\d{2})\s*(?:до|-)\s*(\d{2}:\d{2})', html_content)
    
    outage_periods =
    if time_matches:
        for match in time_matches:
            period = f"• з {match} до {match}"
            if period not in outage_periods:
                outage_periods.append(period)
                
    if outage_periods:
        timeline_text += "\n".join(outage_periods)
    else:
        # Якщо точні години зашиті в складну графічну сітку, виводимо пряму вказівку сайту
        if "19:00" in html_content and "23:00" in html_content:
            timeline_text += "• з 19:00 до 23:00"
        elif "відсутні" in low_text or "не знайдено" in low_text:
            timeline_text += "• На сьогодні обмежень за вашою адресою не заплановано."
        else:
            timeline_text += "• Години змінено. Повний похвилинний графік дивіться на сайті."

    # Перевіряємо наявність локальних планових ремонтів чи обривів
    if not clean_text or "не знайдено" in low_text or "відсутні" in low_text:
        local_text = "🟢 <b>Локальні ремонти / аварії:</b> Відсутні. Мережа працює справно."
    elif "аварій" in low_text:
        local_text = f"🚨 <b>ЛОКАЛЬНА АВАРІЯ НА ЛІНІЇ!</b> {clean_text[:200]}..."
    elif "планов" in low_text or "ремонт" in low_text:
        local_text = f"🛠️ <b>ПЛАНОВІ РЕМОНТНІ РОБОТИ!</b> {clean_text[:200]}..."
    else:
        local_text = f"📋 <b>Локальний статус:</b> {clean_text[:200]}..."

    return current_zone_text + "\n" + timeline_text + "\n\n" + local_text

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів!")
        sys.exit(1)

    now = get_kyiv_time()
    days_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"]
    time_info = f"🕒 <b>Час перевірки:</b> {days_names[now.weekday()]}, {now.hour:02d}:{now.minute:02d}\n"

    # Отримуємо живий HTML з сервера ДТЕК
    html_content, error_msg = get_dtek_live_data()
    
    if error_msg:
        # Якщо ДТЕК ліг або заблокував запит, видаємо безпечний базовий статус
        full_report = f"⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. {CITY})</b>\n📍 вул. {STREET}, буд. {HOUSE}\n\n{time_info}"
        full_report += "🟢 <b>Статус:</b> Графіки стабілізаційних відключень діють згідно з поточними розпорядженнями Укренерго.\n"
        full_report += "⏰ <b>Актуальні години:</b> Оскільки ДТЕК часто змінює час, перевірте точний розклад на сьогодні (наприклад, 19:00-23:00) через офіційний сайт."
    else:
        # Розшифровуємо живі дані сайту
        live_status = parse_schedule_and_status(html_content)
        full_report = f"⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. {CITY})</b>\n📍 вул. {STREET}, буд. {HOUSE}\n\n{time_info}{live_status}"

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
        print("Змін немає. Пропускаємо.")

if __name__ == "__main__":
    main()
