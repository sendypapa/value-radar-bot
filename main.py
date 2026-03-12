import FinanceDataReader as fdr
import google.generativeai as genai
import requests
import os
import time

# 시크릿 정보 로드
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_target_stocks():
    # 코스닥 중소형주 추출
    df = fdr.StockListing('KOSDAQ')
    # 시총 1,000억 ~ 6,000억 사이 필터링 (Marcap)
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    # 거래대금 상위 20개
    top_20 = filtered.sort_values(by='Amount', ascending=False).head(20)
    return top_20

def generate_opinion(name, price):
    # API 설정 및 모델 생성
    genai.configure(api_key=GEMINI_API_KEY)
    # 모델명을 명확하게 지정 (gemini-1.5-flash)
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
        print(f"총 {len(stocks)}개 종목 분석 시작...")
        
        for _, row in stocks.iterrows():
            name = row['Name']
            price = row['Close']
            try:
                opinion = generate_opinion(name, price)
                message = f"🚀 **단기 공략주: {name}**\n- **전일 종가**: {price:,.0f}원\n\n{opinion}"
                send_telegram(message)
                print(f"{name} 전송 성공!")
                time.sleep(2) # 텔레그램 도배 방지
            except Exception as e:
                print(f"{name} 분석 중 에러: {e}")
                
    except Exception as e:
        print(f"시스템 오류: {e}")
