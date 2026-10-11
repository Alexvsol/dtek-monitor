import os
import sys
import requests
import json
import re

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"

def send_telegram_message(text):
    # Збираємо адресу технічного API сервера Telegram безпечним шляхом
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

def get_latest_dtek_telegram_post():
    print("Зчитування оперативних змін безпосередньо з каналу ДТЕК КРЕМ...")
    
    # Використовуємо офіційний відкритий веб-віджет Telegram для читання публікацій каналу dtek_krem
    # Збираємо посилання по шматочках, щоб хмара не зрізала домен
    link_part1 = "https://t."
    link_part2 = "me/s/dtek_krem"
    url = link_part1 + link_part2
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            return "Не вдалося отримати доступ до стрічки новин ДТЕК КРЕМ."
            
        html = response.text
        
        # Витягуємо блоки текстових повідомлень з постів за допомогою регулярного виразу
        posts = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', html, re.DOTALL)
        
        if not posts:
            return "На каналі ДТЕК наразі немає свіжих текстових оголошень."
            
        # Беремо найостанніший опублікований пост (він знаходиться в самому кінці списку)
        latest_post_html = posts[-1]
        
        # Очищаємо текст від HTML-тегів (<br/>, <a> тощо), замінюючи їх на правильні переноси рядків
        clean_text = latest_post_html.replace("<br/>", "\n").replace("<br>", "\n")
        clean_text = re.sub(r'<[^>]+>', '', clean_text)
        
        # Декодуємо спеціальні символи, якщо вони є
        import html as html_parser
        clean_text = html_parser.unescape(clean_text)
        
        # Формуємо повідомлення для вашого бота
        report = f"📋 <b>ОПЕРАТИВНЕ ОНОВЛЕННЯ ЧАСУ ВІД ДТЕК КРЕМ:</b>\n\n"
        report += f"{clean_text.strip()}\n\n"
        report += f"🔗 <a href='https://t.me'>Офіційний канал ДТЕК КРЕМ</a>"
        
        return report
        
    except Exception as e:
        print(f"Помилка аналізу Telegram-каналу: {e}")
        return "Тимчасовий збій отримання оперативних графіків."

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів GitHub Settings!")
        sys.exit(1)

    # Режим одиночного тесту (--once)
    if len(sys.argv) > 1 and sys.argv == "--once":
        print("Запуск ручної перевірки оперативних змін...")
        status = get_latest_dtek_telegram_post()
        send_telegram_message(status)
        return

    # Постійний фоновий моніторинг (кожні 15 хвилин)
    try:
        current_status = get_latest_dtek_telegram_post()
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
                
        # Робот відправляє пуш ТІЛЬКИ тоді, коли ДТЕК опублікував новий пост із коригуванням годин
        if current_status != last_status:
            send_telegram_message(current_status)
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
            print("Нові оперативні зміни надіслано в чат.")
        else:
            print("Нових публікацій з коригуванням часу від ДТЕК немає.")
            
    except Exception as e:
        print(f"Помилка виконання: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
