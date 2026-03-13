import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

SENT_FILE = "sent_stocks.json"


def send_telegram(text):

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        requests.post(url, json=payload, timeout=10)
    except:
        print("텔레그램 전송 실패")


def load_sent():

    if not os.path.exists(SENT_FILE):
        return []

    try:
        with open(SENT_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def save_sent(data):

    with open(SENT_FILE, "w") as f:
        json.dump(data, f)


def detect_surge():

    url = "https://finance.naver.com/sise/sise_rise.naver"

    r = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0"
    })

    soup = BeautifulSoup(r.text, "html.parser")

    rows = soup.select("table.type_2 tr")

    sent = load_sent()

    new_sent = sent.copy()

    today = datetime.now().strftime("%m월 %d일")

    for row in rows:

        cols = row.find_all("td")

        if len(cols) < 7:
            continue

        name = cols[1].text.strip()
        price = cols[2].text.strip()
        change = cols[3].text.strip()

        try:
            change_val = float(change.replace("%",""))
        except:
            continue

        if change_val < 10:
            continue

        if name in sent:
            continue

        msg = f"""
🚨 <b>급등 포착</b>

종목: <b>{name}</b>
현재가: {price}원
상승률: <b>{change}</b>

📅 {today}

단기 모멘텀 발생 가능
"""

        send_telegram(msg)

        print("급등 감지:", name)

        new_sent.append(name)

    save_sent(new_sent)


if __name__ == "__main__":
    detect_surge()
