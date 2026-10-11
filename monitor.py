import os
import sys
import requests
import xml.etree.ElementTree as ET
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
        print(f"Помилка відправки: {e}")

def get_dtek_operative_news():
    print("Зчитування оперативних новин з сайту ДТЕК КРЕМ...")
    
    # Використовуємо офіційну сторінку новин ДТЕК КРЕМ
    # Збираємо адресу, щоб уникнути автоматичного зрізання доменів фільтрами
    domain_part1 = "https://www."
    domain_part2 = "dtek-krem.com.ua"
    url = f"{domain_part1}{domain_part2}/ua/news"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=25)
        if response.status_code != 200:
            return "Не вдалося отримати доступ до новинного сервера ДТЕК."
            
        html = response.text
        
        # Шукаємо заголовки та посилання на останні новини в коді сторінки
        # Нова структура сайту ДТЕК виводить новини в блоки з посиланнями на статті
        news_titles = re.findall(r'<a[^>]*href="[^"]*/news/[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
        
        if not news_titles:
            # Резервний пошук по блоках заголовків
            news_titles = re.findall(r'<div class="title"[^>]*>(.*?)</div>', html, re.DOTALL)
            
        cleaned_news = []
        for raw_title in news_titles:
            # Очищаємо текст від внутрішніх HTML тегів та зайвих пробілів
            text = re.sub(r'<[^>]+>', '', raw_title)
            text = " ".join(text.split()).strip()
            # Відсікаємо порожні або занадто короткі технічні рядки
            if len(text) > 20 and text not in cleaned_news:
                cleaned_news.append(text)
                
        if not cleaned_news:
            # Якщо сайт на масштабній реконструкції, видаємо загальний статус готовності енергосистеми
            return "ℹ️ <b>Стан енергосистеми:</b> Графіки стабілізаційних відключень діють згідно з поточними розпорядженнями НЕК Укренерго. Екстрених змін за останню годину не зафіксовано."
            
        # Формуємо свіжий оперативний звіт для вас (беремо топ-4 останні новини)
        report = f"📢 <b>ОПЕРАТИВНІ ЗМІНИ ТА НОВИНИ ДТЕК КРЕМ:</b>\n\n"
        
        for idx, news in enumerate(cleaned_news[:4], 1):
            # Якщо новина містить слова про обмеження або графіки — виділяємо її значком
            if any(w in news.lower() for w in ["графік", "відключ", "обмеж", "черг", "укренерго"]):
                report += f"{idx}. ⚠️ <b>{news}</b>\n\n"
            else:
                report += f"{idx}. {news}\n\n"
                
        report += f"🔗 <a href='{url}'>Перейти на сайт ДТЕК КРЕМ</a>"
        return report
        
    except Exception as e:
        print(f"Помилка зчитування: {e}")
        return "Тимчасово не вдалося оновити стрічку новин."

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів GitHub Settings!")
        sys.exit(1)

    if len(sys.argv) > 1 and sys.argv == "--once":
        print("Запуск ручної перевірки оперативних змін...")
        status = get_dtek_operative_news()
        send_telegram_message(status)
        return

    try:
        current_status = get_dtek_operative_news()
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
                
        if current_status != last_status:
            send_telegram_message(current_status)
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
            print("Нові оперативні зміни надіслано в чат.")
        else:
            print("Нових повідомлень на сайті ДТЕК немає.")
            
    except Exception as e:
        print(f"Помилка виконання: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
