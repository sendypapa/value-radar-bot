from google import genai
import FinanceDataReader as fdr
import requests
import os
import time
import json
import re
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

TRADES_FILE = "trades.json"


# =============================
# 모델 선택
# =============================
def find_best_model(client):

    models = [m.name for m in client.models.list()]

    priorities = [
        "models/gemini-3.1-flash-lite-preview",
        "models/gemini-3-flash-preview",
        "models/gemini-2.5-flash",
        "models/gemini-2.5-flash-lite"
    ]

    for p in priorities:
        if p in models:
            print("📡 모델 선택:", p)
            return p

    return models[0]


# =============================
# 최근 추천 종목 불러오기
# =============================
def load_trades():

    if not os.path.exists(TRADES_FILE):
        return []

    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


# =============================
# 거래 기록 저장
# =============================
def save_trades(trades):

    with open(TRADES_FILE, "w", encoding="utf-8") as f:
        json.dump(trades, f, ensure_ascii=False, indent=4)


# =============================
# 최근 3일 추천 종목 필터
# =============================
def get_recent_symbols(trades):

    recent = set()

    today = datetime.now()

    for t in trades:

        try:
            d = datetime.strptime(t["date"], "%m월 %d일")
            d = d.replace(year=today.year)

            if (today - d).days <= 3:
                recent.add(t["symbol"])

        except:
            pass

    return recent


# =============================
# 종목 리스트 가져오기
# =============================
def get_stocks(trades):

    df = fdr.StockListing("KOSDAQ")

    marcap = next((c for c in df.columns if c.lower()=="marcap"), "Marcap")
    amount = next((c for c in df.columns if c.lower()=="amount"), "Amount")

    filtered = df[(df[marcap] >= 100000000000) & (df[marcap] <= 800000000000)]

    top = filtered.sort_values(by=amount, ascending=False).head(30)

    recent_symbols = get_recent_symbols(trades)

    stocks = []

    for _, r in top.iterrows():

        symbol = r["Code"]

        if symbol in recent_symbols:
            continue

        stocks.append({
            "symbol": symbol,
            "name": r["Name"]
        })

    return stocks[:10]


# =============================
# 거래대금 급증 필터
# =============================
def volume_filter(symbol):

    try:

        df = fdr.DataReader(symbol).tail(6)

        if len(df) < 6:
            return False

        today = df["Volume"].iloc[-1]
        avg = df["Volume"].iloc[:-1].mean()

        return today > avg

    except:
        return False


# =============================
# 가격 로드
# =============================
def load_prices(symbols):

    prices = {}

    for s in symbols:

        try:

            if not volume_filter(s):
                continue

            df = fdr.DataReader(s).tail(1)

            if not df.empty:
                prices[s] = int(df["Close"].iloc[0])

        except:
            pass

    return prices


# =============================
# 숫자 추출
# =============================
def extract_number(text):

    nums = re.findall(r'\d+', text.replace(",", ""))

    if nums:
        return int(nums[0])

    return None


# =============================
# AI 분석
# =============================
def analyze_all(client, model, stocks, prices):

    stock_list = ""

    for s in stocks:

        name = s["name"]
        price = prices.get(s["symbol"], 0)

        stock_list += f"{name} 현재가:{price}\n"

    prompt = f"""
너는 밸류레이더의 주식 전문가 노부장이다.

단기 스윙(1~3일) 관점에서 분석하라.

규칙
목표가 현재가 기준 +6~8%
손절가 현재가 기준 -3%

출력 형식

종목명
목표가: 숫자
손절가: 숫자
분석: 2~3줄 설명

종목 목록
{stock_list}
"""

    res = client.models.generate_content(
        model=model,
        contents=prompt
    )

    text = res.text.replace("*", "").replace("#", "")

    print(text)

    result = {}

    lines = text.split("\n")

    current = None
    data = {}

    stock_names = [s["name"] for s in stocks]

    for line in lines:

        line = line.strip()

        if not line:
            continue

        for name in stock_names:

            if name in line:

                if current:
                    result[current] = data

                current = name
                data = {}
                break

        if "목표가" in line:

            num = extract_number(line)

            if num:
                data["tp"] = num

        elif "손절가" in line:

            num = extract_number(line)

            if "%" in line or (num and num < 1000):
                data["sl"] = None
            else:
                data["sl"] = num

        elif "분석" in line:

            if ":" in line:
                data["analysis"] = line.split(":",1)[1].strip()

    if current:
        result[current] = data

    return result


# =============================
# 텔레그램 전송
# =============================
def send_telegram(text):

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except:
        return False


# =============================
# 메시지 생성
# =============================
def make_message(name, price, tp, sl, analysis):

    today = datetime.now().strftime("%m월 %d일")

    return f"""
📢 <b>[밸류레이더] 오늘의 단기 공략주</b>

🔹 <b>종목명</b>: {name}
🔹 <b>매수 타점</b>: <b>{price:,}원</b>

안녕하세요 밸류레이더 노부장입니다.
<b>{today} 금일 단기 공략주 공유드립니다.</b>

📌 <b>[{name} 분석 리포트]</b>

✅ <b>조건부 매도</b>
익절 목표가: <b>{tp:,}원</b>
손절 대응가: <b>{sl:,}원</b>

📖 <b>분석 포인트</b>
{analysis}

⚠️ 장중 변동성이 큰 만큼 조건부 매도 전략을 권장드립니다.
"""


# =============================
# MAIN
# =============================
if __name__ == "__main__":

    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={"api_version": "v1beta"}
    )

    model = find_best_model(client)

    existing_trades = load_trades()

    stocks = get_stocks(existing_trades)

    symbols = [s["symbol"] for s in stocks]

    prices = load_prices(symbols)

    analysis = analyze_all(client, model, stocks, prices)

    today = datetime.now().strftime("%m월 %d일")

    new_trades = []

    for s in stocks:

        name = s["name"]
        symbol = s["symbol"]

        if symbol not in prices:
            continue

        price = prices[symbol]

        data = analysis.get(name, {})

        tp = data.get("tp")
        sl = data.get("sl")

        if not tp or tp < price:
            tp = int(price * 1.07)

        if not sl or sl > price or sl < price*0.8:
            sl = int(price * 0.97)

        text = data.get("analysis", "AI 분석 데이터 없음")

        msg = make_message(name, price, tp, sl, text)

        if send_telegram(msg):

            print("✅ 전송:", name)

            profit = ((tp - price) / price) * 100

            new_trades.append({
                "date": today,
                "name": name,
                "symbol": symbol,
                "buy_price": price,
                "tp": tp,
                "sl": sl,
                "expected_profit": round(profit, 2)
            })

        time.sleep(8)

    all_trades = existing_trades + new_trades

    save_trades(all_trades)

    print(f"📒 거래 기록 저장 완료 (누적 {len(all_trades)}건)")
