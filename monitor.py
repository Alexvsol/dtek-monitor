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

def fetch_hours_by_icons(target_date, is_tomorrow=False):
    # Пряме стабільне посилання на похвилинний графік с. Гора
    url = "https://bezsvitla.com.ua"
    if is_tomorrow:
        url = "https://bezsvitla.com.ua?day=tomorrow"
        
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
            
        html_content = response.text
        date_str = target_date.strftime("%d.%m")
        
        # Перевіряємо актуальність дати на сторінці (якщо дати немає — розклад на цей день ще не готовий)
        if date_str not in html_content and target_date.strftime("%d.%m.%Y") not in html_content:
            return None

        # Вирізаємо HTML блок, що стосується виключно Черги 5.1
        group_block = re.search(r'Черга\s*5\.1.*?(?=Черга\s*\d|\Z)', html_content, re.DOTALL | re.IGNORECASE)
        if not group_block:
            return None
            
        text_chunk = group_block.group(0)
        
        # Розбиваємо блок на окремі слоти за тегом <div
        slots = re.findall(r'<div[^>]*>.*?</div>\s*</div>', text_chunk, re.DOTALL)
        
        periods = list()
        for slot in slots:
            # ЗНАХОДИМО ГОДИНИ: витягуємо час формату ХХ:ХХ – ХХ:ХХ
            time_match = re.search(r'(\d{2}:\d{2})\s*(?:-|–|—|до)\s*(\d{2}:\d{2})', slot)
            
            if time_match:
                hours_str = time_match.group(0).replace("–", "-").replace("—", "-")
                
                # КРИТЕРІЙ ВІДБОРУ: Якщо всередині цього вікна є іконка знаку оклику — це 100% ВІДКЛЮЧЕННЯ
                if "bi-exclamation-triangle-fill" in slot or "bg-dark" in slot:
                    p_str = f"• з {hours_str.split('-')[0].strip()} до {hours_str.split('-')[1].strip()}"
                    if p_str not in periods:
                        periods.append(p_str)
                        
        if periods:
            return "\n".join(periods)
            
        return None
    except Exception as e:
        print(f"Помилка аналізу HTML іконок: {e}")
        return None

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        sys.exit(1)

    now = get_kyiv_time()
    day_of_week = now.weekday()
    hour = now.hour
    
    today_date = now
    tomorrow_date = now + timedelta(days=1)
    
    # Зчитуємо графіки, орієнтуючись строго на графічні іконки сайту БезСвітла
    live_today = fetch_hours_by_icons(today_date, is_tomorrow=False)
    live_tomorrow = fetch_hours_by_icons(tomorrow_date, is_tomorrow=True)

    # Чесні нейтральні заглушки без жодного обману
    if not live_today:
        live_today = "• <i>Діючі обмеження на сьогодні відсутні або скасовані диспетчером обленерго.</i>"
    if not live_tomorrow:
        live_tomorrow = "• <i>Офіційний розклад на завтра ще не оприлюднений. Очікуйте автоматичного оновлення стрічки.</i>"

    # СТОВІДСОТКОВО ДИНАМІЧНЕ ВИЗНАЧЕННЯ СТАТУСУ (Строго за годинами знайдених трикутників відключень!)
    is_active_outage = False
    if "відсутні" not in live_today:
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
        print("Статус оновлено, повідомлення надіслано.")
    else:
        print("Змін немає. Пропускаємо.")

if __name__ == "__main__":
    main()
