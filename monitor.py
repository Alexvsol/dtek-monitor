import os
import sys
import requests
import json
import re

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
        print(f"Помилка відправки в Telegram: {e}")

def get_live_dtek_schedule():
    print("Отримання оперативних змін графіків ДТЕК КРЕМ...")
    
    # Використовуємо стабільний відкритий шлюз текстових новин ДТЕК Київські регіональні електромережі
    url = "https://rss2json.com"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            # Резервний шлюз Укренерго, якщо сервер ДТЕК перевантажений
            backup_url = "https://rss2json.com"
            response = requests.get(backup_url, headers=headers, timeout=20)
            
        if response.status_code != 200:
            return "⚠️ Не вдалося зв'язатися з сервером новин ДТЕК. Спробуйте оновити пізніше."
            
        data = response.json()
        items = data.get("items",)
        
        if not items:
            return "ℹ️ Наразі свіжих офіційних розпоряджень щодо екстрених змін годин немає."
            
        # Шукаємо останню публікацію про введення, скасування або зміну годин графіків
        for item in items[:3]:
            content = item.get("content", "")
            link = item.get("link", "")
            
            # Очищаємо текст від зайвих HTML тегів
            clean_text = re.sub(r'<[^>]+>', ' ', content)
            clean_text = " ".join(clean_text.split())
            
            low_text = clean_text.lower()
            # Перевіряємо, чи цей пост містить оперативну інформацію про час відключень
            if any(word in low_text for word in ["графік", "відключ", "укренерго", "обмежен", "черг"]):
                
                # Формуємо актуальне повідомлення для вашого бота
                report = f"📢 <b>АКТУАЛЬНІ ЗМІНИ ЧАСУ ВІД ДТЕК КРЕМ:</b>\n\n"
                
                # Залишаємо перші 600 символів тексту, де зазвичай розписані всі години та черги
                if len(clean_text) > 600:
                    report += f"📝 {clean_text[:600]}...\n\n"
                else:
                    report += f"📝 {clean_text}\n\n"
                    
                report += f"🔗 <a href='{link}'>Офіційний пост ДТЕК КРЕМ</a>"
                return report
                
        return "ℹ️ Нових повідомлень про зміну годин відключень на цю хвилину немає."
        
    except Exception as e:
        print(f"Помилка аналізу змін: {e}")
        return "ℹ️ Графіки діють згідно з останніми розпорядженнями. Детальний похвилинний розклад на поточну хвилину перевіряйте на сайті ДТЕК КРЕМ."

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів GitHub Settings!")
        sys.exit(1)

    # Режим одиночного тесту (--once)
    if len(sys.argv) > 1 and sys.argv == "--once":
        print("Запуск ручної перевірки оперативних змін...")
        status = get_live_dtek_schedule()
        send_telegram_message(status)
        return

    # Постійний фоновий моніторинг (кожні 15 хвилин)
    try:
        current_status = get_live_dtek_schedule()
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
                
        # Бот надсилає пуш на телефон ТІЛЬКИ тоді, коли ДТЕК опублікував нові зміни годин
        if current_status != last_status:
            send_telegram_message(current_status)
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
            print("Нові оперативні зміни надіслано в чат.")
        else:
            print("Нових коригувань часу від ДТЕК немає.")
            
    except Exception as e:
        print(f"Помилка виконання: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
