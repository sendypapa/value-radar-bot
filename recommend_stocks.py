from google import genai
import FinanceDataReader as fdr
import requests
import os
import time
import json
import re
from datetime import datetime

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
# 장부 로드 / 저장
# =============================
def load_trades():
    if not os.path.exists(TRADES_FILE):
        return []

    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_trades(trades):
    with open(TRADES_FILE, "w", encoding="utf-8") as f:
        json.dump(trades, f, ensure_ascii=False, indent=4)


# =============================
# 최근 3일 추천 종목 제외
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
# 종목 선정
# =============================
def get_stocks(trades):
    df = fdr.StockListing("KOSDAQ")

    marcap = next((c for c in df.columns if c.lower() == "marcap"), "Marcap")
    amount = next((c for c in df.columns if c.lower() == "amount"), "Amount")

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
# 거래량 필터
# =============================
def volume_filter(symbol):
    try:
        df = fdr.DataReader(symbol).tail(6)

        if len(df) < 6:
            return False

        today_vol = df["Volume"].iloc[-1]
        avg_vol = df["Volume"].iloc[:-1].mean()

        return today_vol > avg_vol
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
# 분석 말투 정리
# =============================
def normalize_analysis_tone(text):
    if not text or not text.strip():
        return "단기 수급 유입과 가격 탄력이 동반될 가능성이 있는 구간으로 보입니다. 변동성이 큰 만큼 목표가와 손절가를 사전에 설정해 대응하시는 전략이 유효하겠습니다."

    replacements = {
        "일세": "입니다",
        "하네": "합니다",
        "보게": "보입니다",
        "하였네": "했습니다",
        "자리일세": "구간입니다",
        "구간일세": "구간입니다",
        "노려볼 만하지": "노려볼 만한 구간으로 판단됩니다",
        "노려볼 만하네": "관심 있게 볼 수 있는 구간으로 보입니다",
        "좋아 보이네": "양호한 흐름으로 보입니다",
        "유효해 보이네": "유효한 흐름으로 보입니다",
        "빠른 수익 실현을 노려 볼만 자리일세": "단기 수익 실현을 시도해볼 수 있는 구간으로 판단됩니다",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"\s+", " ", text).strip()

    bad_endings = ["다.", "네.", "세.", "지.", "군.", "게."]
    good_endings = ("입니다.", "보입니다.", "판단됩니다.", "좋겠습니다.", "유효하겠습니다.", "가능성이 있습니다.")

    if not text.endswith(good_endings):
        if any(text.endswith(x) for x in bad_endings):
            text = text[:-1] + "니다."
        else:
            text += "."

    return text


# =============================
# AI 분석
# =============================
def analyze_all(client, model, stocks, prices):
    valid_stocks = [s for s in stocks if s["symbol"] in prices]

    stock_list = ""
    for s in valid_stocks:
        name = s["name"]
        price = prices.get(s["symbol"], 0)
        stock_list += f"{name} 현재가:{price}\n"

    if not stock_list.strip():
        return {}

    prompt = f"""
너는 밸류레이더 소속의 전문 애널리스트다.
아래 종목들을 단기 스윙(1~3일) 관점에서 분석하라.

규칙
- 목표가는 현재가 기준 +6~8%
- 손절가는 현재가 기준 -3%
- 반드시 한국어로 작성
- 반드시 정중한 존댓말만 사용
- 반말, 고어체, 옛말투, 과장된 표현 절대 금지
- "일세", "하네", "보게", "자리일세", "하였네" 같은 표현 절대 금지
- 텔레그램 투자 리포트에 맞는 짧고 단정한 문장으로 작성
- 각 종목마다 반드시 '분석:'으로 시작하는 줄을 포함
- 분석은 2문장 이내로 작성
- 특수문자 *, # 사용 금지

출력 형식은 반드시 아래 형식을 정확히 지켜라.

종목명
목표가: 숫자
손절가: 숫자
분석: 문장

종목 목록
{stock_list}
"""

    try:
        res = client.models.generate_content(
            model=model,
            contents=prompt
        )
        text = (res.text or "").replace("*", "").replace("#", "")
    except Exception as e:
        print("🚨 AI 분석 호출 실패:", e)
        return {}

    print("===== AI RESPONSE =====")
    print(text)
    print("=======================")

    result = {}
    lines = text.split("\n")
    stock_names = [s["name"] for s in valid_stocks]

    current = None
    data = {}
    analysis_mode = False

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            continue

        matched_name = None
        for name in stock_names:
            if line == name or line.startswith(name):
                matched_name = name
                break

        if matched_name:
            if current:
                result[current] = data
            current = matched_name
            data = {}
            analysis_mode = False
            continue

        if not current:
            continue

        if "목표가" in line:
            num = extract_number(line)
            if "%" in line or not num or num < 1000:
                data["tp"] = None
            else:
                data["tp"] = num
            analysis_mode = False
            continue

        if "손절가" in line:
            num = extract_number(line)
            if "%" in line or not num or num < 1000:
                data["sl"] = None
            else:
                data["sl"] = num
            analysis_mode = False
            continue

        if any(keyword in line for keyword in ["분석", "분석 포인트", "코멘트", "설명"]):
            if ":" in line:
                data["analysis"] = line.split(":", 1)[1].strip()
            else:
                data["analysis"] = ""
            analysis_mode = True
            continue

        if analysis_mode:
            existing = data.get("analysis", "")
            data["analysis"] = (existing + " " + line).strip()

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

    return f"""📢 <b>[밸류레이더] 오늘의 단기 공략주</b>

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

    if not prices:
        print("🚨 가격 데이터를 불러오지 못했습니다.")
        exit()

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

        if not tp or tp <= price or tp > int(price * 1.15):
            tp = int(price * 1.07)

        if not sl or sl >= price or sl < int(price * 0.90):
            sl = int(price * 0.97)

        text = data.get("analysis", "")
        text = normalize_analysis_tone(text)

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
