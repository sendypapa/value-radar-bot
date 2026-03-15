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
        print("텔레그램 전송 예외:", e)
        return False


def load_sent():
    if not os.path.exists(SENT_FILE):
        return {}

    try:
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("sent_stocks.json 로드 실패:", e)
        return {}


def save_sent(data):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_change_value(change_text):
    try:
        cleaned = (
            change_text.replace("%", "")
            .replace("+", "")
            .replace("▲", "")
            .replace("상한가", "")
            .strip()
        )
        return float(cleaned)
    except:
        return None


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
    candidate_count = 0

    for row in rows:
        cols = row.find_all("td")

        if len(cols) < 7:
            continue

        name = cols[1].get_text(strip=True)
        price = cols[2].get_text(strip=True)
        change = cols[3].get_text(strip=True)
        volume = cols[5].get_text(strip=True)

        if not name:
            continue

        change_val = parse_change_value(change)
        if change_val is None:
            continue

        print(f"후보 확인 | 종목: {name} | 현재가: {price} | 등락률: {change} | 거래량: {volume}")

        # 운영용 기준: 7% 이상
        if change_val < 7:
            continue

        candidate_count += 1

        # 당일 중복 발송 방지
        if name in today_sent:
            print("중복 제외:", name)
            continue

        msg = f"""🚨 <b>급등 포착</b>

<b>{name}</b>
현재가 : {price}원
상승률 : <b>{change}</b>
거래량 : {volume}

📊 단기 모멘텀 구간으로 보입니다.
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

    print("조건 충족 후보 수:", candidate_count)
    print("총 전송 건수:", sent_count)

    if candidate_count == 0:
        print("조건 충족 종목 없음")


if __name__ == "__main__":
    detect()
