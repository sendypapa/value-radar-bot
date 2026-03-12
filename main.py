from google import genai
import FinanceDataReader as fdr
import requests
import os
import time
from datetime import datetime

# 깃허브 시크릿 데이터
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_accurate_stock_data():
    """코스닥 상위 10개 종목의 정확한 전일 종가를 가져옵니다."""
    df_list = fdr.StockListing('KOSDAQ')
    # 시총 1,000억 ~ 6,000억 사이 필터링
    filtered = df_list[(df_list['Marcap'] >= 100000000000) & (df_list['Marcap'] <= 600000000000)]
    top_10 = filtered.sort_values(by='Amount', ascending=False).head(10)
    
    result = []
    for _, row in top_10.iterrows():
        symbol = row['Code']
        name = row['Name']
        # DataReader를 통해 가장 최근의 정확한 종가 한 줄을 가져옵니다.
        price_df = fdr.DataReader(symbol).tail(1)
        close_price = price_df['Close'].iloc[0]
        result.append({'name': name, 'price': close_price})
    return result

def generate_opinion(name, price):
    client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1'})
    
    # [수정] 정중한 말투와 간결한 분량을 요구하는 프롬프트
    prompt = f"""
    너는 전문 주식 애널리스트야. 종목명 {name}, 전일 확정 종가 {price:,.0f}원에 대해 리포트를 작성해줘.
    
    [작성 규칙]
    1. 반드시 정중한 존댓말을 사용할 것.
    2. 1~3일 단기 매매 관점으로 작성할 것.
    3. 매수 의견, 비중, 구체적인 타점(매수/익절/손절)을 핵심만 간결하게 불렛포인트로 작성할 것.
    4. 전체 분량은 10줄 내외로 짧게 요약할 것.
    5. '자네', '껄껄' 같은 표현은 절대 사용하지 말 것.
    """
    
    response = client.models.generate_content(
        model='models/gemini-3.1-flash-lite', 
        contents=prompt
    )
    return response.text

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    try:
        stocks = get_accurate_stock_data()
        print(f"🚀 [밸류레이더] 정밀 분석 시작: {len(stocks)}개 종목 ---")
        
        for i, stock in enumerate(stocks):
            name = stock['name']
            price = stock['price']
            try:
                # RPM 15 한도 준수를 위한 12초 대기
                if i > 0:
                    time.sleep(12) 
                
                opinion = generate_opinion(name, price)
                # 메시지 레이아웃 정리
                message = f"📢 **[밸류레이더] 오늘의 단기 공략주**\n\n🔹 **종목명**: {name}\n🔹 **전일 종가**: {price:,.0f}원\n\n{opinion}"
                send_telegram(message)
                print(f"✅ {name} (종가: {price:,.0f}) 전송 성공!")
                
            except Exception as e:
                print(f"❌ {name} 실패: {e}")
                time.sleep(15)
                
    except Exception as e:
        print(f"🚨 시스템 오류: {e}")
