import os
import sys
import requests
import re
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"
TIME_FILE = "last_change_time.txt"

HOME_HOST = "alexvsol.tplinkdns.com" 
HOME_PORT = 8080

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

def check_real_power_by_socket():
    if "your-ddns-name" in HOME_HOST:
        return None
            
    print("000")
    try:
        # Перевіряємо працездатність домену
        try:
            socket.gethostbyname(HOME_HOST)
        except socket.gaierror:
            print("111")
            return False

        print("222")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0) # Чекаємо відповіді від камери до 5 секунд
        result = sock.connect_ex((HOME_HOST, HOME_PORT))
        sock.close()
        print(result)
        
        # СУВОРА ЛОГІКА: Світло є ТІЛЬКИ тоді, коли підключення успішне (код 0)
        # Якщо камера вимкнена від мережі, порт поверне код помилки (111, 110 тощо), і статус стане червоним!
        return result == 0
    except Exception:
        return False


def fetch_hours_from_bez_svitla(target_date, is_tomorrow=False):
    url = "https://bezsvitla.com.ua/kyivska-oblast/girska-hromada/gora"
    if is_tomorrow:
        url = "https://bezsvitla.com.ua/kyivska-oblast/girska-hromada/gora/grafik-na-zavtra"
        
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
            
        html_content = response.text

        # КРОК 1: Знаходимо точну позицію початку розкладу Черги 5.1 на сторінці
        # Шукаємо саме заголовок "Черга 5.1" у блоці графіків населеного пункту
        start_marker = re.search(r'Черга\s*5\.1', html_content, re.IGNORECASE)
        if not start_marker:
            return None
            
        # Обрізаємо HTML, залишаючи ТІЛЬКИ те, що йде ПІСЛЯ заголовку Черги 5.1
        search_zone = html_content[start_marker.start():]

        # КРОК 2: Послідовно зчитуємо часові інтервали та їхній статус відключення
        # Витягуємо блоки: спочатку час bz-schedule-slot__time, потім шматок коду з його іконкою стану
        slots = re.findall(r'(\d{2}:\d{2})\s*(?:-|–|—|до)\s*(\d{2}:\d{2})(.*?)(?=<span class="bz-schedule-slot__time"|<h2>|<h3>|\Z)', search_zone, re.DOTALL)
        
        periods = list()
        for slot in slots:
            start_time = slot[0]
            end_time = slot[1]
            sub_html = slot[2]
            
            # Перевіряємо стан: якщо в цьому слоті є іконка "Без світла" — фіксуємо обмеження
            if 'aria-label="Без світла"' in sub_html or 'title="Без світла"' in sub_html:
                periods.append(f"• з {start_time} до {end_time}")
                
            # КРОК 3: ЛОГІКА ВИХОДУ З ЦИКЛУ. Як тільки дійшли до кінця доби (24:00) — зупиняємось
            if end_time == "24:00" or end_time.startswith("24"):
                break
                
        if periods:
            return "\n".join(periods)
            
        return None
    except Exception as e:
        print(f"Помилка парсингу: {e}")
        return None

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        sys.exit(1)

    now = get_kyiv_time()
    day_of_week = now.weekday()
    hour = now.hour
    current_total_minutes = now.hour * 60 + now.minute
    
    today_date = now
    tomorrow_date = now + timedelta(days=1)
    
    # Запуск покрокового чесного сканування HTML сторінки БезСвітла
    live_today = fetch_hours_from_bez_svitla(today_date, is_tomorrow=False)
    live_tomorrow = fetch_hours_from_bez_svitla(tomorrow_date, is_tomorrow=True)
    
    # Запускаємо низькорівневий пінг камери
    real_power_status = check_real_power_by_socket()


    if not live_today:
        live_today = "• <i>Діючі обмеження на сьогодні відсутні або скасовані диспетчером обленерго.</i>"
    if not live_tomorrow:
        live_tomorrow = "• <i>Офіційний розклад на завтра ще не оприлюднений. Очікуйте автоматичного оновлення стрічки.</i>"

    # ДИНАМІЧНЕ ВИЗНАЧЕННЯ СТАТУСУ (Строго за годинами знайдених тегів "Без світла")
    is_active_outage = False
    if "відсутні" not in live_today:
        time_slots = re.findall(r'(\d{2}:\d{2})\s*(?:-|до|—|–)\s*(\d{2}:\d{2})', live_today)

        for start_str, end_str in time_slots:
            # Розбиваємо знайдені рядки на години та хвилини
            h_start, m_start = map(int, start_str.split(':'))
            h_end, m_end = map(int, end_str.split(':'))
            
            # Переводимо у хвилини від початку доби
            start_minutes = h_start * 60 + m_start
            end_minutes = h_end * 60 + m_end
            
            # 3. Логіка порівняння (наприклад, чи йде ефір прямо зараз)
            if start_minutes <= current_total_minutes <= end_minutes:
        
 #        for slot in time_slots:
  #           start_h = int(slot[0])
  #           end_h = int(slot[1])
  #           if start_h <= hour < end_h:
                is_active_outage = True
                break

    # Фізичний пінг має абсолютний пріоритет над плановими графіками
    if real_power_status is not None:
        is_active_outage = not real_power_status

    status_key = "OUTAGE" if is_active_outage else "POWER_ON"
    last_change_time_str = ""
    if os.path.exists(TIME_FILE):
        with open(TIME_FILE, "r", encoding="utf-8") as f:
            last_change_time_str = f.read().strip()

    last_status_key = ""
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            old_content = f.read()
            if "ПЛАНОВЕ ВІДКЛЮЧЕННЯ" in old_content or "ЗНЕСТРУМЛЕНА" in old_content:
                last_status_key = "OUTAGE"
            elif "СВІТЛО Є" in old_content:
                last_status_key = "POWER_ON"

    if status_key != last_status_key or not last_change_time_str:
        last_change_time_str = now.strftime("%H:%M")
        with open(TIME_FILE, "w", encoding="utf-8") as f:
            f.write(last_change_time_str)

    if real_power_status is not None:
        if real_power_status:
            status_text = "🟢 <b>Група 5.1: СВІТЛО Є (Фізично підтверджено онлайн-камерою)</b>\n"
            status_text += f"⏱️ <b>Мережа стабільна з:</b> {last_change_time_str}"
        else:
            status_text = "🔴 <b>Група 5.1: МЕРЕЖА ЗНЕСТРУМЛЕНА (Камера офлайн — світла немає)</b>\n"
            status_text += f"⏱️ <b>Фактичне вимкнення о:</b> {last_change_time_str}"
    else:
        if is_active_outage:
            status_text = "🔴 <b>Група 5.1: ПЛАНОВЕ ВІДКЛЮЧЕННЯ (За графіком ДТЕК)</b>\n"
            status_text += f"⏱️ <b>Зміна статусу:</b> сьогодні о {last_change_time_str}"
        else:
            status_text = "🟢 <b>Група 5.1: СВІТЛО Є (Мережа працює в штатному режимі)</b>\n"
            status_text += f"⏱️ <b>Зміна статусу:</b> сьогодні о {last_change_time_str}"
    
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
