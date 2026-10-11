import os
import sys
import requests
import re

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"

def send_telegram_message(text):
    # Пряма захищена адреса API Telegram
    url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Відповідь Telegram: {response.status_code}")
    except Exception as e:
        print(f"Помилка відправки Telegram: {e}")

def get_dtek_news():
    print("Отримання новин з офіційного сайту ДТЕК КРЕМ...")
    # Відкрита сторінка новин, яка не блокує роботів
    url = "https://dtek-krem.com.ua"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code != 200:
        raise Exception(f"Не вдалося отримати новини ДТЕК: код {response.status_code}")
        
    html = response.text
    
    # Знаходимо заголовки та тексти останніх новин за допомогою регулярних виразів
    # Шукаємо блоки з класом новин (зазвичай це посилання або блоки новин)
    news_blocks = re.findall(r'<a[^>]*class="[^"]*news[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)
    
    if not news_blocks:
        # Спроба знайти будь-які блоки з текстом новин, якщо класи інші
        news_blocks = re.findall(r'<h3>(.*?)</h3>', html, re.DOTALL)
        
    cleaned_news = []
    for block in news_blocks[:5]:  # Беремо топ-5 останніх новин
        text = re.sub(r'<[^>]+>', ' ', block)
        text = " ".join(text.split())
        if text:
            cleaned_news.append(text)
            
    if not cleaned_news:
        return "Не вдалося зчитати стрічку новин ДТЕК."
        
    # Формуємо звіт з останніх новин
    result = "📋 *Останні новини ДТЕК Київські регіональні електромережі:*\n\n"
    for idx, news in enumerate(cleaned_news, 1):
        # Виділяємо важливі слова про відключення
        if any(word in news.lower() for word in ["відключення", "графік", "обмежен", "світл", "черг"]):
            result += f"{idx}. ⚠️ *{news}*\n"
        else:
            result += f"{idx}. {news}\n"
            
    return result

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка: Перевірте секрети TELEGRAM_TOKEN та TELEGRAM_CHAT_ID у GitHub Settings!")
        sys.exit(1)

    try:
        current_status = get_dtek_news()
        print(f"Поточний стан стрічки новин:\n{current_status}")
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
        
        if current_status != last_status:
            send_telegram_message(current_status)
            
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
            print("Новини оновлено, сповіщення надіслано в Telegram.")
        else:
            print("Нових повідомлень на сайті ДТЕК немає.")
                
    except Exception as e:
        print(f"Помилка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
