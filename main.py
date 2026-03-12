from google import genai
import FinanceDataReader as fdr
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
    # 시총 1,000억 ~ 6,000억 사이 중소형주 필터링 (Marcap 기준)
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    # 거래대금(Amount) 상위 20개 선정
    top_20 = filtered.sort_values(by='Amount', ascending=False).head(20)
    return top_20

def generate_opinion(name, price):
    # 최신 SDK 클라이언트 설정
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    너는 주식 전문가 노부장이야. 
    종목명: {name}, 전일종가: {price:,.0f}원. 
    1~3일 보유 단타 관점에서 매수의견, 권장비중, 매수타점을 구체적이고 길게 전문가처럼 작성해줘. 
    순번이나 '1/20' 같은 표시는 절대 넣지 말고 텍스트로만 줘.
    """
    
    # 최신 호출 방식 (gemini-1.5-flash 모델 지정)
    response = client.models.generate_content(
        model='gemini-1.5-flash',
        contents=prompt
    )
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
                opinion = generate_opinion(row['Name'], row['Close'])
                message = f"🚀 **단기 공략주: {row['Name']}**\n- **전일 종가**: {row['Close']:,.0f}원\n\n{opinion}"
                send_telegram(message)
                time.sleep(2) # 텔레그램 안전 전송을 위해 2초 쉼
                print(f"{row['Name']} 전송 성공")
            except Exception as e:
                print(f"{row['Name']} 처리 중 에러: {e}")
    except Exception as e:
        print(f"데이터 수집 중 치명적 에러: {e}")
