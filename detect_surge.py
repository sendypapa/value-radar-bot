import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SENT_FILE = "sent_stocks.json"


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        print("텔레그램 응답:", r.status_code, r.text)

        if r.status_code != 200:
            return False

        return True

    except Exception as e:
        print("텔레그램 예외:", e)
        return False


def load_sent():
    if not os.path.exists(SENT_FILE):
        return {}

    try:
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("sent 파일 로드 실패:", e)
        return {}


def save_sent(data):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def detect():
    url = "https://finance.naver.com/sise/sise_rise.naver"

    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        print("네이버 응답:", r.status_code)
    except Exception as e:
        print("네이버 요청 실패:", e)
        return

    soup = BeautifulSoup(r.text, "html.parser")
    rows = soup.select("table.type_2 tr")

    print("파싱된 행 개수:", len(rows))

    sent_data = load_sent()
    today = datetime.now().strftime("%Y-%m-%d")

    if today not in sent_data:
        sent_data[today] = []

    today_sent = sent_data[today]
    sent_count = 0

    for row in rows:
        cols = row.find_all("td")

        if len(cols) < 7:
            continue

        name = cols[1].text.strip()
        price = cols[2].text.strip()
        change = cols[3].text.strip()
        volume = cols[5].text.strip()

        print("후보:", name, price, change, volume)

        try:
            change_val = float(change.replace("%", "").replace("+", "").replace("▲", "").strip())
        except Exception:
            continue

        # 테스트용 임계값
        if change_val < 3:
            continue

        if name in today_sent:
            print("중복 제외:", name)
            continue

        msg = f"""🚨 <b>급등 포착</b>

<b>{name}</b>
현재가 : {price}원
상승률 : <b>{change}</b>

거래량 : {volume}

📊 단기 모멘텀 발생 가능
"""

        ok = send_telegram(msg)

        if ok:
            print("전송 성공:", name)
            today_sent.append(name)
            sent_count += 1
        else:
            print("전송 실패:", name)

    sent_data[today] = today_sent
    save_sent(sent_data)

    print("총 전송 건수:", sent_count)


if __name__ == "__main__":
    detect()
