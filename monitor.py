import os
import sys
import requests
import json

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"

def send_telegram_message(text):
    part1 = "https://api."
    part2 = "telegram.org"
    url = f"{part1}{part2}/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": text, 
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Відповідь Telegram API: {response.status_code}")
    except Exception as e:
        print(f"Помилка відправки в Telegram: {e}")

def get_latest_energy_news():
    print("Отримання офіційних сповіщень про світло...")
    
    # Використовуємо відкритий RSS/вбудований сервіс Telegram-каналу ДТЕК Офіційний
    # Це дозволяє читати пости без авторизації та використання важких бібліотек
    channel_url = "https://rss2json.com"
    
    # Резервний канал Укренерго, якщо перший не віддає дані
    backup_url = "https://rss2json.com"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(channel_url, headers=headers, timeout=20)
        if response.status_code != 200:
            response = requests.get(backup_url, headers=headers, timeout=20)
            
        data = response.json()
        items = data.get("items", [])
        
        if not items:
            return "Наразі свіжих офіційних публікацій про зміну графіків немає."
            
        # Беремо найостанніший опублікований пост
        latest_post = items[0]
        title = latest_post.get("title", "")
        content = latest_post.get("content", "")
        link = latest_post.get("link", "")
        
        # Очищаємо текст від зайвих HTML тегів, які можуть зламати Telegram
        import re
        clean_text = re.sub(r'<[^>]+>', ' ', content)
        clean_text = " ".join(clean_text.split())
        
        # Формуємо красиве повідомлення для вас
        report = f"📢 <b>Офіційне сповіщення про стан енергосистеми:</b>\n\n"
        report += f"📝 {clean_text[:500]}...\n\n"
        report += f"🔗 <a href='{link}'>Читати повний пост у каналі</a>"
        
        return report
        
    except Exception as e:
        print(f"Помилка зчитування каналу: {e}")
        return "Не вдалося отримати дані з офіційних каналів сповіщень."

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів!")
        sys.exit(1)

    # Якщо запуск тестовий (--once)
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        print("Запуск тестового поодинокого режиму...")
        status = get_latest_energy_news()
        send_telegram_message(status)
        return

    # Стандартний режим порівняння статусів для постійного крону
    try:
        current_status = get_latest_energy_news()
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
                
        # Сповіщаємо лише тоді, коли з'явився новий пост
        if current_status != last_status:
            send_telegram_message(current_status)
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
            print("Нове сповіщення відправлено.")
        else:
            print("Нових публікацій енергетиків немає.")
            
    except Exception as e:
        print(f"Помилка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
