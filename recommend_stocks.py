from google import genai
import FinanceDataReader as fdr
import requests
import os
import time
import json
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

TRADES_FILE = "trades.json"


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


def get_stocks():

    df = fdr.StockListing("KOSDAQ")

    marcap = next((c for c in df.columns if c.lower()=="marcap"), "Marcap")
    amount = next((c for c in df.columns if c.lower()=="amount"), "Amount")

    filtered = df[(df[marcap] >= 100000000000) & (df[marcap] <= 800000000000)]

    top = filtered.sort_values(by=amount, ascending=False).head(10)

    stocks = []

    for _, r in top.iterrows():

        stocks.append({
            "symbol": r["Code"],
            "name": r["Name"]
        })

    return stocks


def load_prices(symbols):

    prices = {}

    for s in symbols:

        try:

            df = fdr.DataReader(s).tail(1)

            if not df.empty:
                prices[s] = int(df["Close"].iloc[0])

        except:
            pass

    return prices


def analyze_all(client, model, stocks, prices):

    today = datetime.now().strftime("%m월 %d일")

    stock_list = ""

    for s in stocks:

        name = s["name"]
        price = prices.get(s["symbol"],0)

        stock_list += f"{name} 현재가:{price}\n"

    prompt = f"""
너는 밸류레이더의 주식 전문가 노부장이다.

아래 종목들을 단기 스윙(1~3일) 관점에서 분석하라.

반드시 아래 규칙을 지켜라.

목표가
현재가 기준 +6~8%

손절가
현재가 기준 -3%

출력 형식 (반드시 동일)

종목명
목표가: 숫자
손절가: 숫자
분석: 2~3줄 설명

특수문자 * # 사용 금지

종목 목록
{stock_list}
"""

    res = client.models.generate_content(
        model=model,
        contents=prompt
    )

    text = res.text.replace("*","").replace("#","")

    result = {}

    lines = text.split("\n")

    current=None
    data={}

    for line in lines:

        line=line.strip()

        if not line:
            continue

        if line in [s["name"] for s in stocks]:

            if current:
                result[current]=data

            current=line
            data={}

        elif "목표가" in line:

            data["tp"]=int(line.split(":")[1].replace(",",""))

        elif "손절가" in line:

            data["sl"]=int(line.split(":")[1].replace(",",""))

        elif "분석" in line:

            data["analysis"]=line.split(":",1)[1]

        else:

            if "analysis" in data:
                data["analysis"]+=" "+line

    if current:
        result[current]=data

    return result


def send_telegram(text):

    url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload={
        "chat_id":CHAT_ID,
        "text":text,
        "parse_mode":"HTML"
    }

    try:

        r=requests.post(url,json=payload,timeout=10)

        return r.status_code==200

    except:

        return False


def make_message(name,price,tp,sl,analysis):

    today=datetime.now().strftime("%m월 %d일")

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


if __name__=="__main__":

    client=genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={"api_version":"v1beta"}
    )

    model=find_best_model(client)

    stocks=get_stocks()

    symbols=[s["symbol"] for s in stocks]

    prices=load_prices(symbols)

    print("📊 AI 전체 분석 시작")

    analysis=analyze_all(client,model,stocks,prices)

    trades=[]

    today=datetime.now().strftime("%m월 %d일")

    for s in stocks:

        name=s["name"]
        symbol=s["symbol"]

        if symbol not in prices:
            continue

        price=prices[symbol]

        data=analysis.get(name,{})

        tp=data.get("tp",int(price*1.07))
        sl=data.get("sl",int(price*0.97))
        text=data.get("analysis","분석 데이터 없음")

        msg=make_message(name,price,tp,sl,text)

        if send_telegram(msg):

            print("✅ 전송:",name)

            trades.append({
                "date":today,
                "name":name,
                "symbol":symbol,
                "buy":price,
                "tp":tp,
                "sl":sl
            })

        time.sleep(8)

    with open(TRADES_FILE,"w",encoding="utf-8") as f:

        json.dump(trades,f,ensure_ascii=False,indent=4)
