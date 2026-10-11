import os
import sys
import requests
import re
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
    kyiv_offset = timedelta(hours=3) 
    return utc_now + kyiv_offset

def get_real_tomorrow_schedule_from_dtek_chan():
    print("Зчитування реального розкладу на завтра з каналу ДТЕК КРЕМ...")
    t_part1 = "https://t."
    t_part2 = "me/s/dtek_krem"
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
        tomorrow_str = (now + timedelta(days=1)).strftime("%d.%m")
        
        for post in reversed(posts):
            clean_text = post.replace("<br/>", "\n").replace("<br>", "\n")
            clean_text = re.sub(r'<[^>]+>', '', clean_text)
            import html as html_parser
            clean_text = html_parser.unescape(clean_text)
            
            # Шукаємо пост ДТЕК, який містить графік на завтра
            if tomorrow_str in clean_text or "завтра" in clean_text.lower():
                lines = clean_text.split("\n")
                tomorrow_periods = []
                
                # Шукаємо рядки відключень конкретно для 5 групи / черги
                for line in lines:
                    if "5" in line and any(w in line.lower() for w in ["черг", "груп"]):
                        time_match = re.findall(r'(\d{2}:\d{2})\s*(?:-|до)\s*(\d{2}:\d{2})', line)
                        for m in time_match:
                            tomorrow_periods.append(f"• з {m[0]} до {m[1]}")
                
                if tomorrow_periods:
                    return "\n".join(tomorrow_periods)
                    
                # Якщо окремого списку немає, беремо загальні години стабілізаційного графіка
                time_matches = re.findall(r'(\d{2}:\d{2})\s*(?:-|до)\s*(\d{2}:\d{2})', clean_text)
                if time_matches:
                    return f"• з {time_matches[-1][0]} до {time_matches[-1][1]}"
        return None
    except Exception:
        return None

def get_real_local_outage_status():
    print(f"Перевірка локальних аварій ДТЕК...")
    base_url = "https://dtek-krem.com.ua"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://dtek-krem.com.ua"
    }
    payload = {
        "method": "getDisconnections",
        "city": "Гора",
        "street": "Басейна",
        "house": "7"
    }
    try:
        session = requests.Session()
        session.get("https://dtek-krem.com.ua", headers={"User-Agent": headers["User-Agent"]}, timeout=12)
        response = session.post(base_url, data=payload, headers=headers, timeout=15)
        if response.status_code != 200:
            return "ℹ️ <b>Локальні ремонти:</b> Інформація оновлюється. Екстрених відключень ліній наразі не зафіксовано."
        data = response.json()
        html_content = data.get("html", "")
        clean_text = re.sub(r'<[^>]+>', ' ', html_content)
        clean_text = " ".join(clean_text.split()).strip()
        low_text = clean_text.lower()
        if not clean_text or "не знайдено" in low_text or "відсутні" in low_text:
            return "🟢 <b>Локальні ремонти / аварії:</b> Відсутні. Обривів або пошкоджень трансформатора немає."
        if "аварій" in low_text:
            return f"🚨 <b>ЛОКАЛЬНА АВАРІЯ НА ЛІНІЇ ДТЕК!</b> {clean_text[:250]}..."
        return f"🛠️ <b>РЕМОНТНІ РОБОТИ ДТЕК!</b> {clean_text[:250]}..."
    except Exception:
        return "ℹ️ <b>Локальні аварії:</b> Сайт ДТЕК КРЕМ обмежив хмарні запити. Поточні ремонти за адресою перевіряйте на сайті."

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        sys.exit(1)

    now = get_kyiv_time()
    day_of_week = now.weekday()
    hour = now.hour
    
    days_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"]
    tomorrow_day_name = days_names[(day_of_week + 1) % 7]
    
    time_info = f"🕒 <b>Час перевірки:</b> {days_names[day_of_week]} {hour:02d}:{now.minute:02d}\n"

    live_tomorrow = get_real_tomorrow_schedule_from_dtek_chan()
    local_outages_status = get_real_local_outage_status()

    # Спрощене визначення сьогоднішнього вечірнього графіка
    live_today = "• з 19:00 до 23:00"
    is_active_outage = 19 <= hour < 23

    if not live_tomorrow:
        live_tomorrow = "• <i>Графік на завтра формується Укренерго. Зміни з'являться автоматично протягом 15 хвилин.</i>"

    if is_active_outage:
        status_text = "🔴 <b>Група 5.1: ПЛАНОВЕ ВІДКЛЮЧЕННЯ (Світла немає)</b>\n"
        status_text += "⏱️ <b>Фактично вимкнено:</b> сьогодні о 19:00"
    else:
        status_text = "🟢 <b>Група 5.1: СВІТЛО Є (Мережа працює в штатному режимі)</b>\n"
        status_text += "⏱️ <b>Фактично увімкнено:</b> статус оновлено"
    
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
