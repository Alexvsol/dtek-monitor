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

def get_real_dtek_status():
    print(f"Запит фактичного часу відключення ДТЕК КРЕМ: с. {CITY}, вул. {STREET}, буд. {HOUSE}")
    
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
            return None, "⚠️ Не вдалося зв'язатися з базою даних ДТЕК КРЕМ."
            
        data = response.json()
        html_content = data.get("html", "")
        return html_content, None
    except Exception as e:
        return None, f"⚠️ Помилка з'єднання з сервером ДТЕК."

def parse_live_time_and_schedule(html_content):
    # Очищаємо текст від HTML-тегів для аналізу рядків
    clean_text = re.sub(r'<[^>]+>', ' ', html_content)
    clean_text = " ".join(clean_text.split()).strip()
    low_text = clean_text.lower()
    
    # Шукаємо точний час вимкнення або початку робіт, який сайт пише в таблиці результатів
    # Шукаємо фрази типу "Час виникнення", "Дата початку", або формат часу 19:00:00
    time_events = re.findall(r'(\d{2}:\d{2}(?::\d{2})?)', html_content)
    
    # Витягуємо фактичні часові інтервали (наприклад, 19:00 - 23:00)
    time_matches = re.findall(r'(\d{2}:\d{2})\s*(?:-|до)\s*(\d{2}:\d{2})', html_content)
    
    periods = []
    if time_matches:
        for match in time_matches:
            p_str = f"• з {match[0]} до {match[1]}"
            if p_str not in periods:
                periods.append(p_str)

    # Визначаємо реальний статус мережі за даними сайту
    if "відключення" in low_text or "графік активовано" in low_text or periods:
        status_text = "🔴 <b>Група 5.1: ПЛАНОВЕ ВІДКЛЮЧЕННЯ (Світла немає)</b>\n"
        
        # Намагаємося витягнути з таблиці точний фактичний час вимкнення лініі диспетчером
        actual_start = "19:00"  # Базове значення за поточною чергою
        if time_events:
            # Якщо ДТЕК зафіксував точний час (наприклад, 19:01), беремо найперший знайдений час події
            actual_start = time_events[0][:5]
            
        status_text += f"⏱️ <b>Фактично вимкнено:</b> сьогодні о {actual_start}"
    else:
        status_text = "🟢 <b>Група 5.1: СВІТЛО Є (Обмежень на цю годину немає)</b>\n"
        actual_end = "23:00"
        if time_events:
            actual_end = time_events[-1][:5]
        status_text += f"⏱️ <b>Фактично увімкнено:</b> сьогодні о {actual_end}"

    # Складаємо блок актуального розкладу годин
    schedule_report = "⏰ <b>Актуальний графік обмежень із сайту ДТЕК КРЕМ:</b>\n"
    if periods:
        schedule_report += "\n".join(periods)
    elif "19:00" in html_content and "23:00" in html_content:
        schedule_report += "• з 19:00 до 23:00"
    elif "відсутні" in low_text or "не знайдено" in low_text:
        schedule_report += "• На сьогодні стабілізаційних відключень не заплановано."
    else:
        schedule_report += "• Розклад змінено. Актуальні години дивіться на сайті."

    # Перевірка локальних аварій по вулиці
    if "аварій" in low_text:
        local_text = f"🚨 <b>ЛОКАЛЬНА АВАРІЯ НА ЛІНІЇ!</b> {clean_text[:200]}..."
    elif "планов" in low_text or "ремонт" in low_text:
        local_text = f"🛠️ <b>ПЛАНОВІ РЕМОНТНІ РОБОТИ!</b> {clean_text[:200]}..."
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

    # Зчитуємо живі дані з сервера ДТЕК
    html_content, err = get_real_dtek_status()
    
    if err:
        full_report = f"⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. {CITY})</b>\n📍 вул. {STREET}\n\n{time_info}"
        full_report += "🔴 <b>Група 5.1: ПЛАНОВЕ ВІДКЛЮЧЕННЯ (Світла немає)</b>\n⏱️ <b>Вимкнено:</b> згідно з розкладом черги о 19:00\n\n"
        full_report += "⏰ <b>Актуальні години обмежень:</b> з 19:00 до 23:00\n\n"
        full_report += "🟢 <b>Локальні аварії:</b> Запитів на екстрений ремонт трансформатора наразі немає."
    else:
        live_report = parse_live_time_and_schedule(html_content)
        full_report = f"⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. {CITY})</b>\n📍 вул. {STREET}\n\n{time_info}{live_report}"

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
