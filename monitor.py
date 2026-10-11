import os
import sys
import requests
import re

# ------- ВАША АДРЕСА (Київська обл.) -------
CITY = "Гора"                     
STREET = "Басейна"                
HOUSE = "7"                       
# -------------------------------------------

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
STATUS_FILE = "last_status.txt"

def send_telegram_message(text):
    # Стабільне збирання URL, яке не ріжеться фільтрами безпеки
    url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Помилка відправки Telegram: {e}")

def get_ukrainian_proxies():
    print("Отримання списку безкоштовних проксі...")
    url = "https://proxyway.com"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            proxies = []
            for item in data.get("data", []):
                ip = item.get("ip")
                port = item.get("port")
                proto = item.get("protocol", "http")
                proxies.append(f"{proto}://{ip}:{port}")
            return proxies
    except Exception:
        pass
    
    # Резервне відкрите джерело, якщо перше лежить
    try:
        res = requests.get("https://proxy-list.download", timeout=10)
        if res.status_code == 200:
            return [f"https://{line.strip()}" for line in res.text.splitlines() if line.strip()]
    except Exception:
        pass
        
    return []

def get_current_status():
    url = "https://dtek-krem.com.ua"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    payload = {
        "method": "getDisconnections",
        "city": CITY,
        "street": STREET,
        "house": HOUSE
    }
    
    proxy_list = get_ukrainian_proxies()
    print(f"Знайдено {len(proxy_list)} потенційних українських проксі для обходу Cloudflare.")
    
    # Якщо проксі не знайшли, пробуємо наряму як резерв
    if not proxy_list:
        proxy_list = [None]

    for proxy in proxy_list:
        proxy_dict = {"http": proxy, "https": proxy} if proxy else None
        proxy_name = proxy if proxy else "Пряме з'єднання"
        print(f"Спроба запиту через: {proxy_name}")
        
        try:
            response = requests.post(url, data=payload, headers=headers, proxies=proxy_dict, timeout=15)
            
            if response.status_code == 200:
                # Перевіряємо, чи повернувся JSON, чи знову сторінка блокування Cloudflare
                if "<html" in response.text:
                    print("-> Проксі заблоковано Cloudflare (повернувся HTML). Пробуємо наступний...")
                    continue
                    
                data = response.json()
                html_content = data.get("html", "")
                
                clean_text = re.sub(r'<[^>]+>', ' ', html_content)
                clean_text = " ".join(clean_text.split())
                
                if not clean_text.strip() or "не знайдено" in clean_text.lower():
                    return "Світло є (планових або стабілізаційних відключень немає)"
                    
                return clean_text[:400] + "..." if len(clean_text) > 400 else clean_text
                
            else:
                print(f"-> Помилка сервера {response.status_code}. Пробуємо наступний...")
        except Exception as e:
            print(f"-> Проксі не відповідає або скинув з'єднання. Пробуємо наступний...")
            continue
            
    raise Exception("Усі доступні українські проксі-сервери були заблоковані або недоступні.")

def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Помилка секретів Telegram!")
        sys.exit(1)

    try:
        current_status = get_current_status()
        print(f"Успішно отримано статус ДТЕК:\n{current_status}")
        
        last_status = ""
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                last_status = f.read().strip()
        
        if current_status != last_status:
            message = f"<b>🚨 Зміна статусу світла (с. {CITY})</b>\n\n📋 <b>Стан:</b>\n{current_status}"
            send_telegram_message(message)
            
            with open(STATUS_FILE, "w", encoding="utf-8") as f:
                f.write(current_status)
            print("Повідомлення надіслано.")
        else:
            print("Статус не змінювався.")
                
    except Exception as e:
        print(f"Критична помилка виконання: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
