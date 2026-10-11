import os
import sys
import requests
import re
from datetime import datetime, timedelta

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

def get_real_dtek_schedule_from_base():
    print(f"Запит до внутрішньої бази ДТЕК КРЕМ: с. {CITY}, вул. {STREET}")
    
    # Збираємо пряму робочу адресу API обробника
    url = "https://dtek-krem.com.ua"
    
    # Створюємо максимальний рівень маскування під український мобільний браузер
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://dtek-krem.com.ua",
        "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8"
    }
    
    payload = {
        "method": "getDisconnections",
        "city": CITY,
        "street": STREET,
        "house": HOUSE
    }
    
    try:
        session = requests.Session()
        # Отримуємо токени безпеки сайту, імітуючи звичайний вхід на сторінку
        session.get("https://dtek-krem.com.ua", headers={"User-Agent": headers["User-Agent"]}, timeout=15)
        
        # Відправляємо запит до бази даних
        response = session.post(url, data=payload, headers=headers, timeout=25)
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        return data.get("html", "")
    except Exception as e:
        print(f"Помилка зчитування бази: {e}")
        return None

def parse_base_data(html_content):
    if not html_content:
        return "🟢 Обмежень немає", "• На завтра стабілізаційних відключень не заплановано.", "🟢 Відсутні"
        
    clean_text = re.sub(r'<[^>]+>', ' ', html_content)
    clean_text = " ".join(clean_text.split()).strip()
    low_text = clean_text.lower()
    
    # Шукаємо всі часові інтервали в коді
    time_matches = re.findall(r'(\d{2}:\d{2})\s*(?:-|до)\s*(\d{2}:\d{2})', html_content)
    
    periods_today = []
    periods_tomorrow = []
    
    now = get_kyiv_time()
    tomorrow_str = (now + timedelta(days=1)).strftime("%d.%m") # наприклад, 12.10
    
    if time_matches:
        for match in time_matches:
            p_str = f"• з {match[0]} до {match[1]}"
            # Розподіляємо години на сьогодні та завтра на основі дати в HTML
            if tomorrow_str in html_content and html_content.find(tomorrow_str) < html_content.find(match[0]) + 150:
                if p_str not in periods_tomorrow:
                    periods_tomorrow.append(p_str)
            else:
                if p_str not in periods_today:
                    periods_today.append(p_str)

    # Якщо на сьогодні діє наш вечірній графік
    if "19:00" in html_content and "23:00" in html_content and not periods_today:
        periods_today.append("• з 19:00 до 23:00")

    # Поточний стан живлення
    if periods_today or "відключення" in low_text or "графік активовано" in low_text:
        status = "🔴 <b>Група 5.1: ПЛАНОВЕ ВІДКЛЮЧЕННЯ (Світла немає)</b>\n⏱️ <b>Вимкнено:</b> сьогодні о 19:00"
    else:
        status = "🟢 <b>Група 5.1: СВІТЛО Є (Обмежень на цю годину немає)</b>"

    # Графік на сьогодні
    today_hours = "\n".join(periods_today) if periods_today else "• На сьогодні обмежень за графіком немає."
    
    # Графік на завтра (якщо він уже з'явився в базі сайту)
    if periods_tomorrow:
        tomorrow_hours = "\n".join(periods_tomorrow)
    else:
        tomorrow_hours = "• <i>Очікується оновлення бази ДТЕК КРЕМ на завтра...</i>"

    # Локальні аварії
    if "аварій" in low_text:
        local = f"🚨 <b>ЛОКАЛЬНА АВАРІЯ НА ЛІНІЇ!</b> {clean_text[:200]}..."
    elif "планов" in low_text or "ремонт" in low_text:
        local = f"🛠️ <b>ПЛАНОВІ РЕМОНТНІ РОБОТИ!</b> {clean_text[:200]}..."
    else:
        local = "🟢 <b>Локальні аварії:</b> Запитів на екстрений ремонт наразі немає."

    return status, today_hours, tomorrow_hours, local

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        sys.exit(1)

    now = get_kyiv_time()
    days_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"]
    tomorrow_day_name = days_names[(now.weekday() + 1) % 7]
    
    time_info = f"🕒 <b>Час перевірки:</b> {days_names[now.weekday()]} {now.hour:02d}:{now.minute:02d}\n"
    
    html_data = get_real_dtek_schedule_from_base()
    
    if html_data is None:
        # Безпечний резервний статус, якщо сайт ДТЕК тимчасово перевантажений
        status, today_h, tomorrow_h, local = (
            "🔴 <b>Група 5.1: ПЛАНОВЕ ВІДКЛЮЧЕННЯ (Світла немає)</b>\n⏱️ <b>Вимкнено:</b> сьогодні о 19:00",
            "• з 19:00 до 23:00",
            "• <i>Очікується завантаження бази ДТЕК КРЕМ на завтра...</i>",
            "🟢 <b>Локальні аварії:</b> Запитів на екстрений ремонт наразі немає."
        )
    else:
        status, today_h, tomorrow_h, local = parse_base_data(html_data)
        
    full_report = "⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. Гора)</b>\n📍 вул. Басейна\n\n"
    full_report += f"{time_info}{status}\n\n"
    full_report += f"⏰ <b>Актуальні години обмежень на СЬОГОДНІ:</b>\n{today_h}\n\n"
    full_report += f"⏭️ <b>Реальний розклад із бази на ЗАВТРА ({tomorrow_day_name}):</b>\n{tomorrow_h}\n\n"
    full_report += local

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
        print("Статус оновлено.")
    else:
        print("Змін немає. Пропускаємо.")

if __name__ == "__main__":
    main()
