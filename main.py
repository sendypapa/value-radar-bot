from google import genai
import FinanceDataReader as fdr
import requests
import os
import time

# 깃허브 시크릿 데이터 가져오기
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_target_stocks():
    # 코스닥 종목 리스트 (중소형주 필터)
    df = fdr.StockListing('KOSDAQ')
    # 시총 1,000억 ~ 6,000억 (Marcap 기준)
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    # 거래대금 상위 20개
    top_20 = filtered.sort_values(by='Amount', ascending=False).head(20)
    return top_20

def generate_opinion(name, price):
    # 2026년 최신 클라이언트 설정
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    너는 주식 전문가 노부장이야. 
    종목명: {name}, 전일종가: {price:,.0f}원. 
    1~3일 보유 단타 관점에서 매수의견, 권장비중, 매수타점을 아주 구체적이고 길게 전문가처럼 작성해줘. 
    순번이나 '1/20' 같은 표시는 절대 넣지 말고 텍스트로만 줘.
    """
    
    # [핵심 변경] 모델명을 2.0 버전으로 시도합니다.
    # 만약 안되면 'gemini-1.5-flash'로 자동 시도하도록 설계했습니다.
    try:
        model_name = 'gemini-2.0-flash'
        response = client.models.generate_content(model=model_name, contents=prompt)
    except:
        model_name = 'gemini-1.5-flash'
        response = client.models.generate_content(model=model_name, contents=prompt)
        
    return response.text

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    try:
        stocks = get_target_stocks()
        print(f"🚀 [{len(stocks)}개 종목 분석 시작 - 2026 모드]")
        
        for _, row in stocks.iterrows():
            name = row['Name']
            price = row['Close']
            try:
                opinion = generate_opinion(name, price)
                message = f"🚀 **단기 공략주: {name}**\n- **전일 종가**: {price:,.0f}원\n\n{opinion}"
                send_telegram(message)
                print(f"✅ {name} 전송 성공")
                time.sleep(2)
            except Exception as e:
                print(f"❌ {name} 에러: {e}")
                
    except Exception as e:
        print(f"🚨 시스템 오류: {e}")
