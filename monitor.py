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

def get_live_channel_text():
    # Перемикаємося на офіційну текстову стрічку Укренерго
    link_p1 = "https://t."
    link_p2 = "me/s/Ukrenergo"
    url = link_p1 + link_p2
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.text
    except Exception:
        return ""
    return ""

def extract_exact_hours_by_logic(html_content, target_date, day_keyword):
    posts = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', html_content, re.DOTALL)
    if not posts:
        return None
        
    months_ua = {
        1: "січня", 2: "лютого", 3: "березня", 4: "квітня", 5: "травня", 6: "червня",
        7: "липня", 8: "серпня", 9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня"
    }
    
    dot_date = target_date.strftime("%d.%m")
    full_dot_date = target_date.strftime("%d.%m.%Y")
    text_date = f"{target_date.day} {months_ua[target_date.month]}"
    
    search_variants = [dot_date, text_date, full_dot_date, day_keyword]
    
    for post in reversed(posts):
        clean_text = post.replace("<br/>", "\n").replace("<br>", "\n")
        clean_text = re.sub(r'<[^>]+>', '', clean_text)
        import html as html_parser
        clean_text = html_parser.unescape(clean_text)
        
        low_text = clean_text.lower()
        
        start_index = -1
        # КРОК 1: Шукаємо точку входу по даті
        for variant in search_variants:
            if variant.lower() in low_text:
                start_index = low_text.find(variant.lower())
                break
                
        if start_index != -1:
            fresh_chunk = clean_text[start_index:]
            lines = fresh_chunk.split("\n")
            
            # КРОК 2: Точно локалізуємо початок списку черг Київської області
            kyiv_line_index = -1
            for idx, line in enumerate(lines):
                # Пропускаємо заголовки компаній та столицю
                if "київськ" in line.lower():
                    kyiv_line_index = idx
                    break
            
            # КРОК 3: У знайденому блоці витягуємо чистий текст рядка 5 черги
            if kyiv_line_index != -1:
                sub_block = lines[kyiv_line_index:kyiv_line_index + 12]
                
                # Пошук підгрупи 5.1
                for line in sub_block:
                    if "5.1" in line:
                        clean_line = line.strip().replace("•", "").strip()
                        return f"• {clean_line}"
                            
                # Резервний пошук загальної 5 черги
                for line in sub_block:
                    if any(g in line.lower() for g in ["5 черга", "5 група", "черга 5"]):
                        clean_line = line.strip().replace("•", "").strip()
                        return f"• {clean_line}"
                            
    return None

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        sys.exit(1)

    now = get_kyiv_time()
    day_of_week = now.weekday()
    hour = now.hour
    
    html_content = get_live_channel_text()
    
    today_date = now
    tomorrow_date = now + timedelta(days=1)
    
    live_today = extract_exact_hours_by_logic(html_content, today_date, "сьогодні")
    live_tomorrow = extract_exact_hours_by_logic(html_content, tomorrow_date, "завтра")

    if not live_today:
        live_today = "• <i>Обмеження на сьогодні відсутні або скасовані диспетчером обленерго.</i>"
    if not live_tomorrow:
        live_tomorrow = "• <i>Графік на завтра формується. Зміни з'являться автоматично протягом 15 хвилин.</i>"

    # ДИНАМІЧНЕ ВИЗНАЧЕННЯ СТАТУСУ НА ОСНОВІ ЖИВОГО ТЕКСТУ
    is_active_outage = False
    time_slots = re.findall(r'(\d{2}):\d{2}\s*(?:-|до|—|–)\s*(\d{2}):\d{2}', live_today)
    for slot in time_slots:
        start_h = int(slot[0])
        end_h = int(slot[1])
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
    today_str = today_date.strftime("%d.%m")
    tomorrow_str = tomorrow_date.strftime("%d.%m")
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
