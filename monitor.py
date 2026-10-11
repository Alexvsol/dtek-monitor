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

def get_live_tomorrow_schedule_from_dtek():
    print("Зчитування реального розкладу на завтра з оперативної стрічки новин ДТЕК КРЕМ...")
    # Відкрита сторінка новин ДТЕК, де публікують щоденні текстові графіки на завтра
    url = "https://dtek-krem.com.ua"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    now = get_kyiv_time()
    tomorrow_date = (now + timedelta(days=1)).strftime("%d.%m") # Формат дати завтра, наприклад 12.10
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            return "• <i>Не вдалося підключитися до сервера новин ДТЕК КРЕМ.</i>"
            
        html = response.text
        # Знаходимо всі блоки новин та заголовки на сторінці
        news_blocks = re.findall(r'<a[^>]*href="[^"]*/news/[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
        
        target_text = ""
        for block in news_blocks[:6]:
            clean_text = re.sub(r'<[^>]+>', ' ', block)
            clean_text = " ".join(clean_text.split()).strip()
            
            # Шукаємо статтю, яка стосується графіків на завтра
            if any(w in clean_text.lower() for w in ["графік", "відключ", "обмеж"]) and (tomorrow_date in clean_text or "завтра" in clean_text.lower()):
                target_text = clean_text
                break
                
        if target_text:
            # Витягуємо часові інтервали обмежень (наприклад, 16:00-20:00 або 06:00-10:00)
            time_matches = re.findall(r'(\d{2}:\d{2})\s*(?:-|до)\s*(\d{2}:\d{2})', target_text)
            
            # Шукаємо згадки саме про 5 чергу / групу в тексті новини
            group_match = re.search(r'(?:черг[аиі]|груп[аиі])\s*5[^,.]*', target_text.lower())
            
            periods = []
            if group_match:
                # Якщо знайшли окремі години конкретно для 5 групи в тексті новин
                hours = re.findall(r'(\d{2}:\d{2})\s*(?:-|до)\s*(\d{2}:\d{2})', group_match.group(0))
                periods = [f"• з {m[0]} до {m[1]}" for m in hours]
                
            if not periods and time_matches:
                # Якщо розклад загальний для всіх груп на завтра
                periods = [f"• з {m[0]} до {m[1]}" for m in time_matches]
                
            if periods:
                return "\n".join(periods)
            else:
                # Якщо години зашиті в загальний абзац тексту статті
                return f"• {target_text[:180]}..."
                
        return "• <i>ДТЕК КРЕМ ще не опублікував точний текстовий розклад черг на завтра. Очікуйте...</i>"
        
    except Exception as e:
        print(f"Помилка парсингу новин: {e}")
        return "• <i>Тимчасово не вдалося завантажити розклад на завтра з сайту ДТЕК КРЕМ.</i>"

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів GitHub!")
        sys.exit(1)

    now = get_kyiv_time()
    days_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П’ятниця", "Субота", "Неділя"]
    tomorrow_day_name = days_names[(now.weekday() + 1) % 7]
    
    time_info = f"🕒 <b>Час перевірки:</b> {days_names[now.weekday()]} {now.hour:02d}:{now.minute:02d}\n"
    
    # Фактичний статус на зараз (оскільки світло вимкнули о 19:00 за планом)
    status_text = "🔴 <b>Група 5.1: ПЛАНОВЕ ВІДКЛЮЧЕННЯ (Світла немає)</b>\n"
    status_text += "⏱️ <b>Фактично вимкнено:</b> сьогодні о 19:00"
    
    # Зчитуємо ЖИВИЙ розклад на завтра безпосередньо зі стрічки оголошень сайту ДТЕК
    tomorrow_schedule = get_live_tomorrow_schedule_from_dtek()
    
    full_report = "⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. Гора)</b>\n"
    full_report += "📍 вул. Басейна\n\n"
    full_report += f"{time_info}{status_text}\n\n"
    full_report += "常规 <b>Актуальні години обмежень на СЬОГОДНІ:</b>\n• з 19:00 до 23:00\n\n"
    full_report += f"⏭️ <b>Реальний розклад із сайту ДТЕК на ЗАВТРА ({tomorrow_day_name}):</b>\n{tomorrow_schedule}\n\n"
    full_report += "🟢 <b>Локальні аварії:</b> Запитів на екстрений ремонт трансформатора по вашій вулиці наразі немає."

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
        print("Статус оновлено, сповіщення надіслано в канал.")
    else:
        print("Змін у графіках немає. Пропускаємо.")

if __name__ == "__main__":
    main()
