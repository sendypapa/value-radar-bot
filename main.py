import google.generativeai as genai
import FinanceDataReader as fdr
import requests
import os
import time

# 시크릿 데이터 로드
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_target_stocks():
    # 코스닥 중소형주 (시총 1,000억 ~ 6,000억)
    df = fdr.StockListing('KOSDAQ')
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    return filtered.sort_values(by='Amount', ascending=False).head(20)

def generate_opinion(name, price):
    # API 설정 및 모델 초기화
    genai.configure(api_key=GEMINI_API_KEY)
    
    # 2026년 현재 가장 표준적인 모델 호출 방식
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"주식 전문가 노부장의 말투로, 종목 {name}(전일종가 {price:,.0f}원)의 1~3일 단타 매수의견, 비중, 타점을 아주 길고 구체적으로 써줘."
    
    # 에러 방지를 위해 단순 호출
    response = model.generate_content(prompt)
    return response.text

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    try:
        stocks = get_target_stocks()
        print(f"--- 분석 시작: {len(stocks)}개 종목 ---")
        
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
                print(f"❌ {name} 실패: {e}")
                
    except Exception as e:
        print(f"🚨 시스템 오류: {e}")
