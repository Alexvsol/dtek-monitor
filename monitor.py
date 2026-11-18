import asyncio
import os
import sys
import requests
import re
import aiohttp
from imouapi.api import ImouAPIClient
from imouapi.device import ImouDiscoverService
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
IMOU_APP_ID = "lc4901c257de0e41b6"
IMOU_APP_SECRET = "f02568f0436b486384212b2add5064"
IMOU_DEVICE_ID_1 = "HDBW1320E-W-2384"  # Обычно указан на наклейке камеры (S/N)
IMOU_DEVICE_ID_2 = "Bullet Lite 4MP-95CF" # Друга камера
STATUS_FILE = "last_status.txt"
TIME_FILE = "last_change_time.txt"

HOME_HOST = "alexvsol.tplinkdns.com" 
HOME_PORT = 554

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
    return datetime.now(ZoneInfo("Europe/Kyiv")) # Автоматичний контроль зима/літо
    
async def check_real_power_by_imou_api():
    if not IMOU_APP_ID or not IMOU_APP_SECRET:
        return None, None
    try:
        async with aiohttp.ClientSession() as session:
            api_client = ImouAPIClient(IMOU_APP_ID, IMOU_APP_SECRET, session)
            discover_service = ImouDiscoverService(api_client)
            
            print("Зв'язуємось з офіційним хмаровим сервером Imou...")
            discovered_devices = await discover_service.async_discover_devices()
            
            status_1 = None
            status_2 = None
            
            if IMOU_DEVICE_ID_1 in discovered_devices:
                camera = discovered_devices.get(IMOU_DEVICE_ID_1)
                if camera:
                    await camera.async_get_data()
                    camera_status = camera.get_status()
                    print(f"DEBUG Imou API: Поточний статус камери у хмарі: {camera_status}")
                    
                    # За документацією: "0" означає, що камера повністю OFFLINE (світла немає)
                    if camera_status == "0":
                        status_1 = False
                    else:
                        status_1 = True
            else:
                print(f"Попередження: Пристрій {IMOU_DEVICE_ID_1} не знайдено в акаунті Imou Developer.")
                status_1 = None
                
            if IMOU_DEVICE_ID_2 in discovered_devices:
                camera = discovered_devices.get(IMOU_DEVICE_ID_2)
                if camera:
                    await camera.async_get_data()
                    camera_status = camera.get_status()
                    print(f"DEBUG Imou API: Поточний статус камери у хмарі: {camera_status}")
                    
                    # За документацією: "0" означає, що камера повністю OFFLINE (світла немає)
                    if camera_status == "0":
                        status_2 = False
                    else:
                        status_2 = True
            else:
                print(f"Попередження: Пристрій {IMOU_DEVICE_ID_2} не знайдено в акаунті Imou Developer.")
                status_2 = None
                
            return status_1, status_2
              
    except Exception as e:
        print(f"Помилка при роботі з офіційним API Imou: {e}")
        return None, None


def fetch_hours_from_bez_svitla(target_date, is_tomorrow=False):
    url = "https://bezsvitla.com.ua/kyivska-oblast/girska-hromada/gora"
    if is_tomorrow:
        url = "https://bezsvitla.com.ua/kyivska-oblast/girska-hromada/gora/grafik-na-zavtra"
        
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return "ERROR"
            
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
        return "ERROR"

async def async_main():
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
    
    # Якщо зафіксовано реальну мережеву помилку сервера (ERROR) — тихо виходимо, чекаючи 15 хв
    if "ERROR" in [live_today, live_tomorrow]:
        print("Критичний збій зв'язку з сервером БезСвітла. Перевірку перенесено на наступний цикл.")
        return

    
    last_status = ""
    old_status_text = ""
    old_cameras_footer = ""
    last_status_key = ""
    
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            last_status = f.read().strip()
            if "ЗНЕСТРУМЛЕНА" in last_status or "ПЛАНОВЕ ВІДКЛЮЧЕННЯ" in last_status:
                last_status_key = "OUTAGE"
            elif "СВІТЛО Є" in last_status:
                last_status_key = "POWER_ON"
                
            status_match = re.search(r'STATUS:(.*?)\|TODAY:', last_status, re.DOTALL)
            if status_match:
                old_status_text = status_match.group(1)
            footer_match = re.search(r'FOOTER:(.*)', last_status, re.DOTALL)
            if footer_match:
                old_cameras_footer = footer_match.group(1)

    last_change_time_str = ""
    if os.path.exists(TIME_FILE):
        with open(TIME_FILE, "r", encoding="utf-8") as f:
            last_change_time_str = f.read().strip()
    # Викликаємо нову асинхронну офіційну хмарову перевірку Imou Cloud
    cam1_online, cam2_online = await check_real_power_by_imou_api()

    real_power_status = None
    if cam1_online is not None or cam2_online is not None:
        real_power_status = (cam1_online or cam2_online)


    if not live_today:
        live_today = "• <i>Діючі обмеження на сьогодні відсутні або скасовані диспетчером обленерго.</i>"
    if not live_tomorrow:
        live_tomorrow = "• <i>Офіційний розклад на завтра ще не оприлюднений. Очікуйте автоматичного оновлення стрічки.</i>"

    # ДИНАМІЧНЕ ВИЗНАЧЕННЯ СТАТУСУ (Строго за годинами знайдених тегів "Без світла")
    if real_power_status is not None:
        # API камер відповіло коректно — оновлюємо статус світла та час
        is_active_outage = not real_power_status
        status_key = "OUTAGE" if is_active_outage else "POWER_ON"

        if status_key != last_status_key or not last_change_time_str:
            last_change_time_str = now.strftime("%H:%M")
            with open(TIME_FILE, "w", encoding="utf-8") as f:
                f.write(last_change_time_str)

        if real_power_status:
            status_text = "🟢 <b>Група 5.1: СВІТЛО Є (Фізично підтверджено онлайн-камерою Imou)</b>\n"
            status_text += f"⏱️ <b>Мережа стабільна з:</b> {last_change_time_str}"
        else:
            status_text = "🔴 <b>Група 5.1: МЕРЕЖА ЗНЕСТРУМЛЕНА (Камера офлайн — світла немає)</b>\n"
            status_text += f"⏱️ <b>Фактичне вимкнення о:</b> {last_change_time_str}"

        icon_c1 = "🟢" if cam1_online else "🔴"
        icon_c2 = "🟢" if cam2_online else "🔴"
        cameras_footer = f"📊 <b>Контроль:</b> {icon_c1} {icon_c2}"
    else:
        # API камер не відповіло — залишаємо старий статус світла незмінним!
        print("Увага: Збій API Imou. Зберігаємо попередній статус світла, але перевіряємо графіки.")
        if old_status_text:
            status_text = old_status_text
            cameras_footer = old_cameras_footer if old_cameras_footer else "📊 <b>Контроль:</b> ⚠️ ⚠️"
        else:
            status_text = "🟡 <b>Група 5.1: ОЧІКУВАННЯ ЗВ'ЯЗКУ З КАМЕРАМИ</b>\n"
            status_text += f"⏱️ <b>Час перевірки:</b> {now.strftime('%H:%M')}"
            cameras_footer = "📊 <b>Контроль:</b> ⚠️ ⚠️"

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
    #full_report += "🟢 <b>Локальні аварії:</b> Запитів на екстрений ремонт трансформатора по вашій вулиці наразі немає."
    full_report += f"{cameras_footer}"
    
    history_key = f"STATUS:{status_text}|TODAY:{live_today_text}|TOMORROW:{live_tomorrow_text}|ACCIDENTS:{live_accidents}|FOOTER:{cameras_footer}"
            
    if history_key != last_status:
        send_telegram_message(full_report)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(history_key)
        print("Статус або графік оновлено, повідомлення надіслано.")
    else:
        print("Змін немає. Пропускаємо.")
            
    if history_key != last_status:
        send_telegram_message(full_report)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            f.write(history_key)
        print("Статус оновлено, повідомлення надіслано.")
    else:
        print("Змін немає. Пропускаємо.")

if __name__ == "__main__":
    asyncio.run(async_main())
