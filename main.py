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
    
    # [수정 포인트] 컬럼명을 'MarketCap'에서 'Marcap'으로 변경했습니다.
    # 시총 1,000억 ~ 6,000억 사이 중소형주 필터링
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    
    # 거래대금(Amount) 상위 20개 선정
    top_20 = filtered.sort_values(by='Amount', ascending=False).head(20)
    return top_20

def generate_opinion(name, price):
    genai.configure(api_key=GEMINI_API_KEY)
    # 최신 모델명으로 업데이트 (gemini-1.5-flash)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    너는 주식 전문가 노부장이야. 
    종목명: {name}, 전일종가: {price:,.0f}원. 
    1~3일 보유 단타 관점에서 매수의견, 권장비중, 매수타점을 구체적이고 길게 전문가처럼 작성해줘. 
    순번이나 '1/20' 같은 표시는 절대 넣지 말고 텍스트로만 줘.
    """
    response = model.generate_content(prompt)
    return response.text

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    try:
        stocks = get_target_stocks()
        for _, row in stocks.iterrows():
            try:
                # 'Close' 컬럼으로 전일 종가를 가져옵니다.
                opinion = generate_opinion(row['Name'], row['Close'])
                message = f"🚀 **단기 공략주: {row['Name']}**\n- **전일 종가**: {row['Close']:,.0f}원\n\n{opinion}"
                send_telegram(message)
                time.sleep(1.5) # 텔레그램 도배 방지를 위해 조금 더 여유 있게 쉼
                print(f"{row['Name']} 전송 성공")
            except Exception as e:
                print(f"{row['Name']} 처리 중 에러: {e}")
    except Exception as e:
        print(f"데이터 수집 중 치명적 에러: {e}")
