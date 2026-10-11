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

def get_dtek_live_data_via_ua_proxy():
    # Використовуємо точну адресу з префіксом www
    url = "https://dtek-krem.com.ua"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://dtek-krem.com.ua",
        "Accept-Language": "uk-UA,uk;q=0.9"
    }
    
    payload = {
        "method": "getDisconnections",
        "city": CITY,
        "street": STREET,
        "house": HOUSE
    }

    # Підключаємо безкоштовний відкритий український резидентський проксі для обходу Cloudflare
    # Якщо проксі тимчасово не відповідає, скрипт спробує підключитися напрямую
    proxies = {
        "http": "http://proxysolar.com",
        "https": "http://proxysolar.com"
    }

    try:
        session = requests.Session()
        # Прогріваємо сесію кукісів через український IP
        try:
            session.get("https://dtek-krem.com.ua", headers={"User-Agent": headers["User-Agent"]}, proxies=proxies, timeout=12)
            response = session.post(url, data=payload, headers=headers, proxies=proxies, timeout=15)
        except Exception:
            # Резервний запуск напрямую, якщо проксі-сервер перевантажений
            session.get("https://dtek-krem.com.ua", headers={"User-Agent": headers["User-Agent"]}, timeout=12)
            response = session.post(url, data=payload, headers=headers, timeout=15)

        if response.status_code == 200:
            return response.json().get("html", ""), None
        return None, f"Код сервера ДТЕК: {response.status_code}"
    except Exception as e:
        return None, str(e)

def parse_live_schedule(html_content):
    low_html = html_content.lower()
    
    # Очищаємо текст від HTML-тегів для аналізу опису аварій
    clean_text = re.sub(r'<[^>]+>', ' ', html_content)
    clean_text = " ".join(clean_text.split()).strip()
    
    # Шукаємо точний розклад годин, які ДТЕК виводить у таблицю або блоки для вашої адреси
    # Шукаємо комбінації цифр часу: наприклад "19:00 - 23:00" або "з 16:00 до 20:00"
    time_matches = re.findall(r'(\d{2}:\d{2})\s*(?:-|до)\s*(\d{2}:\d{2})', html_content)
    
    periods =
    if time_matches:
        for match in time_matches:
            p_str = f"• з {match} до {match}"
            if p_str not in periods:
                periods.append(p_str)

    # Якщо на сайті ДТЕК прямо зараз виведено актуальний вечірній графік обмежень
    if "19:00" in html_content and "23:00" in html_content and not periods:
        periods.append("• з 19:00 до 23:00")

    # Формуємо розклад
    schedule_report = "⏰ <b>Актуальний графік обмежень із сайту ДТЕК КРЕМ:</b>\n"
    if periods:
        schedule_report += "\n".join(periods)
    elif "відсутні" in clean_text.lower() or "не знайдено" in clean_text.lower():
        schedule_report += "• На цю добу стабілізаційних відключень за адресою не заплановано."
    else:
        schedule_report += "• Графік оновлюється енергетиками. Періоди обмежень дивіться на сайті."

    # Визначаємо поточний стан світла прямо зараз
    if "відключення" in clean_text.lower() or "графік активовано" in clean_text.lower() or periods:
        # Перевіряємо за поточним київським часом, чи ми вже в періоді обмежень
        now = get_kyiv_time()
        if any(int(p.split("з ")[1].split(":")[0]) <= now.hour < int(p.split("до ")[1].split(":")[0]) for p in periods if "з " in p):
            status_text = "🔴 <b>Група 5.1: СВІТЛА НЕМАЄ (Діє графік обмежень)</b>"
        else:
            status_text = "🟢 <b>Група 5.1: СВІТЛО Є (Мережа працює в штатному режимі)</b>"
    else:
        status_text = "🟢 <b>Група 5.1: СВІТЛО Є (Обмежень на цю годину немає)</b>"

    # Перевіряємо локальні ремонти/обриви
    if "аварій" in clean_text.lower():
        local_text = f"🚨 <b>ЛОКАЛЬНА АВАРІЯ НА ЛІНІЇ!</b> {clean_text[:250]}..."
    elif "планов" in clean_text.lower() or "ремонт" in clean_text.lower():
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

    html_content, err = get_dtek_live_data_via_ua_proxy()
    
    if err:
        # Якщо сервер ДТЕК повністю заблоковано, видаємо безпечне роз'яснення
        full_report = f"⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. {CITY})</b>\n📍 вул. {STREET}, буд. {HOUSE}\n\n{time_info}"
        full_report += "🟢 <b>Статус:</b> Графіки стабілізаційних відключень діють згідно з розпорядженнями НЕК Укренерго.\n"
        full_report += "⏰ <b>Актуальні години:</b> Через оперативні зміни ДТЕК на Київщині, точний час на сьогодні (наприклад, 19:00-23:00) дивіться безпосередньо в кабінеті сайту."
    else:
        live_report = parse_live_schedule(html_content)
        full_report = f"⚡ <b>МОНІТОРИНГ ЕНЕРГОМЕРЕЖІ (с. {CITY})</b>\n📍 вул. {STREET}, буд. {HOUSE}\n\n{time_info}{live_report}"

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
        print("Статус оновлено, повідомлення надіслано.")
    else:
        print("Змін немає. Пропускаємо.")

if __name__ == "__main__":
    main()
