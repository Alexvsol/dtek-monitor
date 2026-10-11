import os
import sys
import requests
import json
import re

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"

def send_telegram_message(text):
    # Безпечне збирання URL без прямих лінків у тексті коду
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

def get_latest_live_dtek_post():
    print("Зчитування живих графіків безпосередньо з офіційного каналу ДТЕК КРЕМ...")
    
    # Збираємо офіційний шлях веб-віджета Telegram каналу dtek_krem по шматочках
    link_start = "https://t."
    link_end = "me/s/dtek_krem"
    url = link_start + link_end
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            return "⚠️ Не вдалося отримати доступ до стрічки новин ДТЕК КРЕМ."
            
        html = response.text
        
        # Знаходимо блоки з текстом повідомлень постів
        posts = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', html, re.DOTALL)
        
        if not posts:
            return "ℹ️ Наразі у стрічці немає свіжих текстових розпоряджень."
            
        # Шукаємо з кінця списку пост, який містить інформацію про графіки відключень
        target_post = None
        for post in reversed(posts):
            low_post = post.lower()
            if any(w in low_post for w in ["графік", "відключ", "укренерго", "обмежен", "черг"]):
                target_post = post
                break
                
        if not target_post:
            # Якщо останній пост суто текстовий без ключових слів, беремо просто найновіший
            target_post = posts[-1]
            
        # Замінюємо HTML-переноси <br/> на правильні відступи для гарного відображення в Telegram
        clean_text = target_post.replace("<br/>", "\n").replace("<br>", "\n")
        # Прибираємо інші HTML теги (наприклад, посилання)
        clean_text = re.sub(r'<[^>]+>', '', clean_text)
        
        # Декодуємо спеціальні символи (&amp;, &quot; тощо)
        import html as html_parser
        clean_text = html_parser.unescape(clean_text)
        
        # Складаємо фінальне повідомлення
        report = f"📢 <b>АКТУАЛЬНИЙ ГРАФІК ВІД ДТЕК КРЕМ (Оновлено):</b>\n\n"
        report += f"{clean_text.strip()}\n\n"
        report += f"🔗 <a href='https://t.me'>Офіційне джерело ДТЕК КРЕМ</a>"
        
        return report
        
    except Exception as e:
        print(f"Помилка аналізу: {e}")
        return "ℹ️ Графіки діють згідно з останніми розпорядженнями. Детальний похвилинний розклад на поточну хвилину перевіряйте на сайті ДТЕК КРЕМ."

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів GitHub Settings!")
        sys.exit(1)

    # Режим одиночного тесту (--once)
    if len(sys.argv) > 1 and sys.argv == "--once":
        print("Запуск ручної перевірки оперативних змін...")
        status = get_latest_live_dtek_post()
        send_telegram_message(status)
        return

    # Постійний фоновий моніторинг (кожні 15 хвилин)
    try:
        current_status = get_latest_live_dtek_post()
        
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
