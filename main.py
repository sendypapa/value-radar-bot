import FinanceDataReader as fdr
import google.generativeai as genai
import requests
import os
import time

# 깃허브 시크릿에서 정보 가져오기
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

def get_target_stocks():
    # 코스닥 종목 리스트 가져오기
    df = fdr.StockListing('KOSDAQ')
    # 필터: 시총 1,000억 ~ 6,000억 사이 중소형주
    filtered = df[(df['MarketCap'] >= 100000000000) & (df['MarketCap'] <= 600000000000)]
    # 거래대금 상위 20개 선정
    top_20 = filtered.sort_values(by='Amount', ascending=False).head(20)
    return top_20

def generate_opinion(name, price):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    너는 주식 전문가 노부장이야. 
    종목명: {name}, 전일종가: {price:,.0f}원. 
    1~3일 보유 단타 관점에서 매수의견, 권장비중, 매수타점을 아주 구체적이고 길게 전문가처럼 작성해줘. 
    '1/20' 같은 순번은 절대 넣지마. 텔레그램 메시지 한 개 분량으로 작성해.
    """
    response = model.generate_content(prompt)
    return response.text

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    stocks = get_target_stocks()
    for _, row in stocks.iterrows():
        try:
            opinion = generate_opinion(row['Name'], row['Close'])
            message = f"🚀 **단기 공략주: {row['Name']}**\n- **전일 종가**: {row['Close']:,.0f}원\n\n{opinion}"
            send_telegram(message)
            time.sleep(1) # 텔레그램 방화벽 방지용 1초 휴식
        except Exception as e:
            print(f"에러 발생({row['Name']}): {e}")
