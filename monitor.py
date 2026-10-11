import os
import sys
import requests
import json

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

def get_latest_dtek_schedule():
    print("Зчитування актуальних змін графіків ДТЕК КРЕМ...")
    
    # Використовуємо стабільний відкритий інформ-шлюз ДТЕК Київські регіональні електромережі
    url = "https://rss2json.com"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            return "Не вдалося зв'язатися з сервером оновлень графіків."
            
        data = response.json()
        items = data.get("items", [])
        
        if not items:
            return "Свіжих розпоряджень щодо змін графіків наразі немає."
            
        # Беремо останні 3 публікації, щоб не пропустити екстрені зміни
        for item in items[:3]:
            content = item.get("content", "")
            link = item.get("link", "")
            
            # Очищаємо текст від HTML-сміття для аналізу
            import re
            clean_text = re.sub(r'<[^>]+>', ' ', content)
            clean_text = " ".join(clean_text.split())
            
            # Перевіряємо, чи цей пост стосується актуальних графіків відключень
            low_text = clean_text.lower()
            if any(word in low_text for word in ["графік", "відключен", "укренерго", "обмежен", "черг"]):
                
                # Формуємо красивий та зрозумілий вивід для Telegram
                report = f"📋 <b>АКТУАЛЬНІ ЗМІНИ ГРАФІКА ВІД ДТЕК:</b>\n\n"
                
                # Якщо текст занадто довгий, акуратно обрізаємо його до суті
                if len(clean_text) > 700:
                    report += f"📝 {clean_text[:700]}...\n\n"
                else:
                    report += f"📝 {clean_text}\n\n"
                    
                report += f"🔗 <a href='{link}'>Офіційне джерело ДТЕК КРЕМ</a>"
                return report
                
        return "Нових повідомлень про зміну годин відключень немає."
        
    except Exception as e:
        print(f"Помилка аналізу змін: {e}")
        return "Тимчасовий збій отримання оперативних даних."

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Критична помилка: секрети не знайдені!")
        sys.exit(1)

    # Режим одиночного ручного тесту
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        print("Запуск ручної перевірки оперативних змін...")
        status = get_latest_dtek_schedule()
        send_telegram_message(status)
        return

    # Постійний фоновий моніторинг (крон запускає кожні 15 хвилин)
    try:
        current_status = get_latest_dtek_schedule()
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
                
        # Робот надсилає повідомлення ТОК ТІЛЬКИ тоді, коли ДТЕК опублікував нові зміни годин
        if current_status != last_status:
            send_telegram_message(current_status)
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
            print("Оперативні зміни надіслано в чат.")
        else:
            print("Нових коригувань часу від ДТЕК немає.")
            
    except Exception as e:
        print(f"Помилка виконання: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
