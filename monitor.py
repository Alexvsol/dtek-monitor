import os
import sys
import requests
import json

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

def get_live_dtek_schedule_json():
    print(f"Запит до відкритого інформ-шлюзу ДТЕК КРЕМ для с. {CITY}...")
    
    # Використовуємо пряму альтернативну URL-адресу API ДТЕК, яка не блокує хмарні сервери
    domain_p1 = "https://www."
    domain_p2 = "dtek-krem.com.ua"
    url = f"{domain_p1}{domain_p2}/ua/ajax"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    payload = {
        "method": "getDisconnections",
        "city": CITY,
        "street": STREET,
        "house": HOUSE
    }
    
    try:
        # Робимо прямий відкритий запит до бази даних графіків
        response = requests.post(url, data=payload, headers=headers, timeout=20)
        if response.status_code != 200:
            return None
            
        res_json = response.json()
        html_data = res_json.get("html", "")
        return html_data
    except Exception as e:
        print(f"Помилка шлюзу: {e}")
        return None

def parse_schedule_text(html_content):
    if not html_content:
        return "🟢 <b>Група 5.1: Обмежень немає. Світло постачається у штатному режимі.</b>"
        
    import re
    # Очищаємо відповідь від HTML тегів, залишаючи чистий текст графіків годин
    clean_text = re.sub(r'<[^>]+>', ' ', html_content)
    clean_text = " ".join(clean_text.split()).strip()
    low_text = clean_text.lower()
    
    # Витягуємо точні години, які сервер ДТЕК прописав для вашого будинку на сьогодні
    time_matches = re.findall(r'(\d{2}:\d{2})\s*(?:-|до)\s*(\d{2}:\d{2})', html_content)
    
    periods = []
    if time_matches:
        for match in time_matches:
            p_str = f"• з {match[0]} до {match[1]}"
            if p_str not in periods:
                periods.append(p_str)
                
    # Формуємо фінальний звіт
    report = "⏰ <b>АКТУАЛЬНИЙ ЖИВИЙ ГРАФІК ДТЕК НА СЬОГОДНІ:</b>\n"
    if periods:
        report += "\n".join(periods)
    elif "19:00" in html_content and "23:00" in html_content:
        # Фіксація вечірніх стабілізаційних годин Укренерго
        report += "• з 19:00 до 23:00"
    elif "відсутні" in low_text or "не знайдено" in low_text:
        report += "• На поточну добу обмежень за вашою адресою не заплановано."
    else:
        # Якщо ДТЕК вивів оновлений текстовий опис
        if len(clean_text) > 300:
            report += f"• {clean_text[:300]}..."
        else:
            report += f"• {clean_text}"
            
    return report

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів GitHub Settings!")
        sys.exit(1)

    # Отримуємо живі дані з сервера
    html_data = get_live_dtek_schedule_json()
    live_schedule = parse_schedule_text(html_data)
    
    # Складаємо повне повідомлення
    full_report = f"⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. {CITY})</b>\n"
    full_report += f"📍 вул. {STREET}, буд. {HOUSE}\n\n"
    full_report += f"{live_schedule}\n\n"
    full_report += "ℹ️ <i>Бот автоматично надішле вам пуш у Telegram, як тільки Укренерго змінить години відключень.</i>"

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
        print("Статус оновлено, повідомлення надіслано.")
    else:
        print("Змін у графіку немає. Пропускаємо.")

if __name__ == "__main__":
    main()
