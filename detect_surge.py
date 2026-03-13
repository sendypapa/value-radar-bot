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
        requests.post(url, json=payload, timeout=10)
    except:
        print("텔레그램 전송 실패")


def load_sent():

    if not os.path.exists(SENT_FILE):
        return {}

    try:
        with open(SENT_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


def save_sent(data):

    with open(SENT_FILE, "w") as f:
        json.dump(data, f)


def detect():

    url = "https://finance.naver.com/sise/sise_rise.naver"

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})

    soup = BeautifulSoup(r.text, "html.parser")

    rows = soup.select("table.type_2 tr")

    sent_data = load_sent()

    today = datetime.now().strftime("%Y-%m-%d")

    if today not in sent_data:
        sent_data = {today: []}

    today_sent = sent_data[today]

    for row in rows:

        cols = row.find_all("td")

        if len(cols) < 7:
            continue

        name = cols[1].text.strip()
        price = cols[2].text.strip()
        change = cols[3].text.strip()
        volume = cols[5].text.strip()

        try:
            change_val = float(change.replace("%",""))
        except:
            continue

        # 급등 필터
        if change_val < 10:
            continue

        # 중복 방지
        if name in today_sent:
            continue

        msg = f"""
🚨 <b>급등 포착</b>

<b>{name}</b>
현재가 : {price}원
상승률 : <b>{change}</b>

거래량 : {volume}

📊 단기 모멘텀 발생 가능
"""

        send_telegram(msg)

        print("급등 감지:", name)

        today_sent.append(name)

    sent_data[today] = today_sent

    save_sent(sent_data)


if __name__ == "__main__":
    detect()
