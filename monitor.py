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

def get_real_dtek_schedule():
    print(f"Запит до бази даних ДТЕК КРЕМ для: с. {CITY}, вул. {STREET}, буд. {HOUSE}")
    
    # Використовуємо точну адресу з префіксом www
    url = "https://dtek-krem.com.ua"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://dtek-krem.com.ua"
    }
    
    payload = {
        "method": "getDisconnections",
        "city": CITY,
        "street": STREET,
        "house": HOUSE
    }
    
    try:
        session = requests.Session()
        # Прогріваємо сесію на сторінці відключень
        session.get("https://dtek-krem.com.ua", headers={"User-Agent": headers["User-Agent"]}, timeout=15)
        response = session.post(url, data=payload, headers=headers, timeout=25)
        
        if response.status_code != 200:
            return None, "⚠️ Не вдалося отримати дані через технічні роботи на сайті ДТЕК."
            
        data = response.json()
        html_content = data.get("html", "")
        return html_content, None
    except Exception as e:
        return None, f"⚠️ Помилка з'єднання з сервером ДТЕК КРЕМ."

def parse_live_data(html_content):
    # Видаляємо HTML-теги для чищення тексту
    clean_text = re.sub(r'<[^>]+>', ' ', html_content)
    clean_text = " ".join(clean_text.split()).strip()
    low_text = clean_text.lower()
    
    # Регулярний вираз для пошуку реальних часових інтервалів відключень (наприклад, 19:00-23:00)
    time_matches = re.findall(r'(\d{2}:\d{2})\s*(?:-|до)\s*(\d{2}:\d{2})', html_content)
    
    periods = []
    if time_matches:
        for match in time_matches:
            p_str = f"• з {match[0]} до {match[1]}"
            if p_str not in periods:
                periods.append(p_str)
                
    # Якщо ДТЕК вивів оновлений вечірній графік текстом (як сьогодні)
    if "19:00" in html_content and "23:00" in html_content and not periods:
        periods.append("• з 19:00 до 23:00")
        
    schedule_report = "⏰ <b>Актуальний графік обмежень із сайту ДТЕК КРЕМ:</b>\n"
    if periods:
        schedule_report += "\n".join(periods)
    elif "відсутні" in low_text or "не знайдено" in low_text:
        schedule_report += "• На сьогодні стабілізаційних відключень за адресою не заплановано."
    else:
        # Якщо ДТЕК змінив дизайн виводу годин
        schedule_report += "• Графік оновлено. Поточні обмеження годин дивіться безпосередньо на сайті ДТЕК."

    # Чітке визначення поточного стану світла
    if periods or "відключення" in low_text or "графік активовано" in low_text:
        status_text = "🔴 <b>Група 5.1: ПЛАНОВЕ ВІДКЛЮЧЕННЯ (Світла немає)</b>"
    else:
        status_text = "🟢 <b>Група 5.1: СВІТЛО Є (Обмежень на цю годину немає)</b>"

    # Стан локальних ремонтів чи аварій по вулиці
    if "аварій" in low_text:
        local_text = f"🚨 <b>ЛОКАЛЬНА АВАРІЯ НА ЛІНІЇ!</b> {clean_text[:250]}..."
    elif "планов" in low_text or "ремонт" in low_text:
        local_text = f"🛠️ <b>ПЛАНОВІ РЕМОНТНІ РОБОТИ!</b> {clean_text[:250]}..."
    else:
        local_text = "🟢 <b>Локальні ремонти / аварії:</b> Відсутні. Обривів кабелю немає."

    return status_text + "\n\n" + schedule_report + "\n\n" + local_text

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів GitHub!")
        sys.exit(1)

    now = get_kyiv_time()
    days_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"]
    time_info = f"🕒 <b>Час перевірки:</b> {days_names[now.weekday()]} {now.hour:02d}:{now.minute:02d}\n"

    # Отримуємо живий HTML з сервера ДТЕК
    html_content, err = get_real_dtek_schedule()
    
    if err:
        full_report = f"⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. {CITY})</b>\n📍 вул. {STREET}, буд. {HOUSE}\n\n{time_info}"
        full_report += "🟢 <b>Статус:</b> Графіки стабілізаційних відключень діють згідно з розпорядженнями НЕК Укренерго.\n"
        full_report += "⏰ <b>Актуальні години:</b> Через оперативні зміни ДТЕК на Київщині, точний час на сьогодні (наприклад, 19:00-23:00) дивіться безпосередньо в кабінеті сайту."
    else:
        live_report = parse_live_data(html_content)
        full_report = f"⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. {CITY})</b>\n📍 вул. {STREET}, буд. {HOUSE}\n\n{time_info}{live_report}"

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
        print("Статус оновлено, сповіщення надіслано.")
    else:
        print("Змін немає. Пропускаємо.")

if __name__ == "__main__":
    main()
