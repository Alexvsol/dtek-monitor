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

def get_live_schedule_from_tg(target_day="today"):
    print(f"Зчитування реального розкладу на {target_day} з веб-віджета Укренерго...")
    t_part1 = "https://t."
    t_part2 = "me/s/Ukrenergo"
    url = t_part1 + t_part2
    
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            return None
            
        html = response.text
        posts = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', html, re.DOTALL)
        if not posts:
            return None
            
        now = get_kyiv_time()
        target_date = now if target_day == "today" else (now + timedelta(days=1))
        date_str = target_date.strftime("%d.%m")
        
        for post in reversed(posts):
            clean_text = post.replace("<br/>", "\n").replace("<br>", "\n")
            clean_text = re.sub(r'<[^>]+>', '', clean_text)
            import html as html_parser
            clean_text = html_parser.unescape(clean_text)
            
            if date_str in clean_text or (target_day == "today" and "сьогодні" in clean_text.lower()) or (target_day == "tomorrow" and "завтра" in clean_text.lower()):
                lines = clean_text.split("\n")
                periods =
                
                for line in lines:
                    if any(w in line.lower() for w in ["5 черг", "5 груп", "п'ята", "п’ята"]):
                        time_match = re.findall(r'(\d{2}:\d{2})\s*(?:-|до)\s*(\d{2}:\d{2})', line)
                        for m in time_match:
                            periods.append(f"• з {m} до {m}")
                if periods:
                    return "\n".join(periods)
                    
                time_matches = re.findall(r'(\d{2}:\d{2})\s*(?:-|до)\s*(\d{2}:\d{2})', clean_text)
                if time_matches:
                    return f"• з {time_matches[-1]} до {time_matches[-1]}"
        return None
    except Exception:
        return None

def get_real_local_outage_status():
    print(f"Запит локальних аварій ДТЕК КРЕМ для: с. {CITY}, вул. {STREET}")
    base_url = "https://dtek-krem.com.ua"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15",
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
        session.get("https://dtek-krem.com.ua", headers={"User-Agent": headers["User-Agent"]}, timeout=12)
        response = session.post(base_url, data=payload, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return "ℹ️ <b>Локальні ремонти:</b> Сервер ДТЕК КРЕМ тимчасово перевантажений. Локальні планові роботи перевіряйте через кабінет сайту."
            
        data = response.json()
        html_content = data.get("html", "")
        
        clean_text = re.sub(r'<[^>]+>', ' ', html_content)
        clean_text = " ".join(clean_text.split()).strip()
        low_text = clean_text.lower()
        
        if not clean_text or "не знайдено" in low_text or "відсутні" in low_text:
            return "🟢 <b>Локальні ремонти / аварії:</b> Відсутні. Обривів або пошкоджень трансформатора немає."
            
        if "аварій" in low_text:
            return f"🚨 <b>ЛОКАЛЬНА АВАРІЯ НА ЛІНІЇ ДТЕК!</b> {clean_text[:250]}..."
        elif "планов" in low_text or "ремонт" in low_text:
            return f"🛠️ <b>ПЛАНОВІ РЕМОНТНІ РОБОТИ ДТЕК!</b> {clean_text[:250]}..."
            
        return f"📋 <b>Статус мережі ДТЕК:</b> {clean_text[:250]}..."
    except Exception:
        return "ℹ️ <b>Локальні аварії:</b> Сайт ДТЕК КРЕМ тимчасово обмежив хмарні запити. Оперативні ремонти за адресою дивіться на сайті."

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        sys.exit(1)

    now = get_kyiv_time()
    day_of_week = now.weekday()
    hour = now.hour
    
    days_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"]
    tomorrow_day_name = days_names[(day_of_week + 1) % 7]
    
    time_info = f"🕒 <b>Час перевірки:</b> {days_names[day_of_week]} {hour:02d}:{now.minute:02d}\n"

    live_today = get_live_schedule_from_tg("today")
    live_tomorrow = get_live_schedule_from_tg("tomorrow")
    local_outages_status = get_real_local_outage_status()

    # НЕЙТРАЛЬНІ ЗАГЛУШКИ БЕЗ ЗАШИТОГО ЧАСУ
    if not live_today:
        live_today = "• <i>Розклад оновлюється диспетчером обленерго. Зачекайте або перевірте сайт ДТЕК КРЕМ.</i>"
    if not live_tomorrow:
        live_tomorrow = "• <i>Графік на завтра готується до публікації НЕК Укренерго. Зміни з'являться автоматично.</i>"

    # ДИНАМІЧНЕ ВИЗНАЧЕННЯ СТАТУСУ (На основі живих годин)
    is_active_outage = False
    time_slots = re.findall(r'(\d{2}):\d{2}\s*(?:-|до)\s*(\d{2}):\d{2}', live_today)
    
    for slot in time_slots:
        start_h, end_h = int(slot), int(slot)
        if start_h <= hour < end_h:
            is_active_outage = True
            break

    if is_active_outage:
        status_text = "🔴 <b>Група 5.1: ПЛАНОВЕ ВІДКЛЮЧЕННЯ (Світла немає)</b>\n"
        current_start = "19:00"
        for slot in time_slots:
            if int(slot) <= hour < int(slot):
                current_start = f"{int(slot):02d}:00"
        status_text += f"⏱️ <b>Фактично вимкнено:</b> сьогодні о {current_start}"
    else:
        status_text = "🟢 <b>Група 5.1: СВІТЛО Є (Мережа працює в штатному режимі)</b>\n"
        current_end = "23:00"
        for slot in time_slots:
            if hour >= int(slot):
                current_end = f"{int(slot):02d}:00"
        status_text += f"⏱️ <b>Фактично увімкнено:</b> статус оновлено"
    
    full_report = "⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. Гора)</b>\n"
    full_report += "📍 вул. Басейна\n\n"
    full_report += f"{time_info}{status_text}\n\n"
    full_report += f"📅 <b>Актуальні години обмежень на СЬОГОДНІ:</b>\n{live_today}\n\n"
    full_report += f"⏭️ <b>Реальний розклад на ЗАВТРА ({tomorrow_day_name}):</b>\n{live_tomorrow}\n\n"
    full_report += local_outages_status

    history_key = f"STATUS:{status_text}|TODAY:{live_today}|TOMORROW:{live_tomorrow}|LOCAL:{local_outages_status}"

    if len(sys.argv) > 1 and sys.argv == "--once":
        print("Запуск ручного тесту...")
        send_telegram_message(full_report)
        return

    last_status = ""
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            last_status = f.read().strip()
            
    if history_key != last_status:
        send_telegram_message(full_report)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(history_key)
        print("Статус оновлено, сповіщення надіслано.")
    else:
        print("Параметри без змін. Пропускаємо.")

if __name__ == "__main__":
    main()
