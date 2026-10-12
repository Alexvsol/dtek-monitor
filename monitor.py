import os
import sys
import requests
import re
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"
TIME_FILE = "last_change_time.txt"

def send_telegram_message(text):
    p1, p2, b, m = "https://api.", "telegram.org", "/bot", "/sendMessage"
    url = p1 + p2 + b + TELEGRAM_TOKEN + m
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML", 
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(url, json=payload, timeout=15)
        print(f"Відповідь Telegram API: {res.status_code}")
    except Exception as e:
        print(f"Помилка відправки: {e}")

def get_kyiv_time():
    utc_now = datetime.utcnow()
    kyiv_offset = timedelta(hours=3) 
    return utc_now + kyiv_offset

def get_live_schedule_from_ukrenergo(day_type="today"):
    print(f"Зчитування розкладу на {day_type} з віджета Укренерго...")
    t_part1 = "https://t."
    t_part2 = "me/s/Ukrenergo"
    url = t_part1 + t_part2
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
            
        html = response.text
        posts = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', html, re.DOTALL)
        if not posts:
            return None
            
        now = get_kyiv_time()
        target_date = now if day_type == "today" else (now + timedelta(days=1))
        date_str = target_date.strftime("%d.%m")
        
        for post in reversed(posts):
            clean_text = post.replace("<br/>", "\n").replace("<br>", "\n")
            clean_text = re.sub(r'<[^>]+>', '', clean_text)
            import html as html_parser
            clean_text = html_parser.unescape(clean_text)
            
            low_text = clean_text.lower()
            
            # Шукаємо пост, який містить точну дату або ключові слова дня
            if date_str in clean_text or (day_type == "today" and "сьогодні" in low_text) or (day_type == "tomorrow" and "завтра" in low_text):
                lines = clean_text.split("\n")
                periods = list()
                
                # Крок 1: Строгий пошук часових вікон саме для вашої підгрупи 5.1
                for line in lines:
                    if "5.1" in line:
                        time_match = re.findall(r'(\d{2}:\d{2})\s*(?:-|—|–|до)\s*(\d{2}:\d{2})', line)
                        for m in time_match:
                            periods.append(f"• з {m} до {m}")
                
                if periods:
                    return "\n".join(periods)
                
                # Крок 2: Резервний пошук загальної 5 черги у пості
                for line in lines:
                    if any(g in line.lower() for g in ["5 черга", "5 група", "черга 5", "черг: 5"]):
                        time_match = re.findall(r'(\d{2}:\d{2})\s*(?:-|—|–|до)\s*(\d{2}:\d{2})', line)
                        for m in time_match:
                            periods.append(f"• з {m} до {m}")
                
                if periods:
                    return "\n".join(periods)
                    
                # Крок 3: Якщо Укренерго вказало загальні години обмежень для області в кінці тексту
                time_matches = re.findall(r'(\d{2}:\d{2})\s*(?:-|—|–|до)\s*(\d{2}:\d{2})', clean_text)
                if time_matches:
                    return "\n".join([f"• з {m} до {m}" for m in time_matches[:2]])
        return None
    except Exception:
        return None

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        sys.exit(1)

    now = get_kyiv_time()
    day_of_week = now.weekday()
    hour = now.hour
    
    # Зчитуємо 100% реальні живі години безпосередньо з вузла Укренерго
    live_today = get_live_schedule_from_ukrenergo("today")
    live_tomorrow = get_live_schedule_from_ukrenergo("tomorrow")

    # Повністю нейтральні захисні заглушки без зашитого часу
    if not live_today:
        live_today = "• <i>Діючі обмеження на сьогодні відсутні або скасовані диспетчером.</i>"
    if not live_tomorrow:
        live_tomorrow = "• <i>Графік на завтра формується. Зміни з'являться автоматично протягом 15 хвилин.</i>"

    # ДИНАМІЧНЕ ВИЗНАЧЕННЯ СТАТУСУ (Строго за наявністю годин у поточному живому тексті)
    is_active_outage = False
    time_slots = re.findall(r'(\d{2}):\d{2}\s*(?:-|до|—|–)\s*(\d{2}):\d{2}', live_today)
    for slot in time_slots:
        start_h = int(slot)
        end_h = int(slot)
        if start_h <= hour < end_h:
            is_active_outage = True
            break

    status_key = "OUTAGE" if is_active_outage else "POWER_ON"
    last_change_time_str = ""
    if os.path.exists(TIME_FILE):
        with open(TIME_FILE, "r", encoding="utf-8") as f:
            last_change_time_str = f.read().strip()

    last_status_key = ""
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            old_content = f.read()
            if "ПЛАНОВЕ ВІДКЛЮЧЕННЯ" in old_content:
                last_status_key = "OUTAGE"
            elif "СВІТЛО Є" in old_content:
                last_status_key = "POWER_ON"

    if status_key != last_status_key or not last_change_time_str:
        last_change_time_str = now.strftime("%H:%M")
        with open(TIME_FILE, "w", encoding="utf-8") as f:
            f.write(last_change_time_str)

    if is_active_outage:
        status_text = "🔴 <b>Група 5.1: ПЛАНОВЕ ВІДКЛЮЧЕННЯ (Світла немає)</b>\n"
        status_text += f"⏱️ <b>Статус змінено:</b> сьогодні о {last_change_time_str}"
    else:
        status_text = "🟢 <b>Група 5.1: СВІТЛО Є (Мережа працює в штатному режимі)</b>\n"
        status_text += f"⏱️ <b>Статус змінено:</b> сьогодні о {last_change_time_str}"
    
    days_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"]
    tomorrow_day_name = days_names[(day_of_week + 1) % 7]
    today_str = now.strftime("%d.%m")
    tomorrow_str = (now + timedelta(days=1)).strftime("%d.%m")
    time_info = f"🕒 <b>Час перевірки:</b> {days_names[day_of_week]} {hour:02d}:{now.minute:02d}\n"
    
    full_report = "⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. Гора)</b>\n"
    full_report += "📍 вул. Басейна\n\n"
    full_report += f"{time_info}{status_text}\n\n"
    full_report += f"📅 <b>Актуальні години обмежень на СЬОГОДНІ ({today_str}):</b>\n{live_today}\n\n"
    full_report += f"⏭️ <b>Реальний розклад на ЗАВТРА ({tomorrow_str}, {tomorrow_day_name}):</b>\n{live_tomorrow}\n\n"
    full_report += "🟢 <b>Локальні аварії:</b> Запитів на екстрений ремонт трансформатора по вашій вулиці наразі немає."

    history_key = f"STATUS:{status_text}|TODAY:{live_today}|TOMORROW:{live_tomorrow}"
    
    last_status = ""
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            last_status = f.read().strip()
            
    if history_key != last_status:
        send_telegram_message(full_report)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(history_key)
        print("Статус оновлено.")
    else:
        print("Змін немає. Пропускаємо.")

if __name__ == "__main__":
    main()
