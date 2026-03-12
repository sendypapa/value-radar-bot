from google import genai
import FinanceDataReader as fdr
import requests
import os
import time

# 깃허브 시크릿 데이터
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_accurate_stocks():
    """정확한 실시간 종가를 포함한 상위 10개 종목을 가져옵니다."""
    df_listing = fdr.StockListing('KOSDAQ')
    # 시총 1,000억 ~ 6,000억 사이 필터링
    filtered = df_listing[(df_listing['Marcap'] >= 100000000000) & (df_listing['Marcap'] <= 600000000000)]
    top_10 = filtered.sort_values(by='Amount', ascending=False).head(10)
    
    stock_data = []
    for _, row in top_10.iterrows():
        symbol = row['Code']
        name = row['Name']
        # [수정] DataReader를 사용하여 가장 최신의 정확한 종가를 가져옵니다.
        price_history = fdr.DataReader(symbol).tail(1)
        actual_close = price_history['Close'].iloc[0]
        stock_data.append({'name': name, 'price': actual_close})
    
    return stock_data

def find_best_model(client):
    """2026년 최신 문법으로 사용 가능한 최적의 모델을 찾습니다."""
    try:
        # 지원하는 액션 중 generateContent가 있는 모델만 추출
        available = [m.name for m in client.models.list() if 'generateContent' in m.supported_actions]
        # 3.1 -> 3 -> 2.5 순서로 검색
        for priority in ['gemini-3.1', 'gemini-3', 'gemini-2.5']:
            target = [name for name in available if priority in name and 'flash' in name]
            if target:
                return target[0]
        return available[0] if available else "gemini-2.0-flash"
    except:
        return "gemini-2.0-flash"

def generate_report(client, model_name, name, price):
    # [수정] 정중하고 간결한 리포트를 위한 프롬프트
    prompt = f"""
    당신은 전문 주식 애널리스트입니다. 종목명 {name}, 전일 확정 종가 {price:,.0f}원에 대해 리포트를 작성하세요.
    
    [작성 가이드라인]
    1. 반드시 정중한 존댓말을 사용할 것.
    2. 1~3일 단기 매매 관점에서 핵심 매수 전략만 제안할 것.
    3. 매수의견, 비중, 구체적인 타점(매수/익절/손절)을 불렛포인트로 요약할 것.
    4. 전체 분량은 8~10줄 내외로 아주 간결하게 작성할 것.
    5. '자네', '껄껄' 등 비격식적인 표현은 절대 금지.
    """
    
    response = client.models.generate_content(model=model_name, contents=prompt)
    return response.text

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    try:
        # 정식 버전(v1) 접속
        client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1'})
        target_model = find_best_model(client)
        
        stocks = get_accurate_stocks()
        print(f"🚀 [밸류레이더] {target_model} 엔진 가동: {len(stocks)}개 정밀 분석 시작")
        
        for i, stock in enumerate(stocks):
            name = stock['name']
            price = stock['price']
            try:
                # RPM 한도 준수를 위해 15초 대기
                if i > 0:
                    print(f"안전 대기 중... ({i+1}/10) 15초 뒤 분석")
                    time.sleep(15) 
                
                report = generate_report(client, target_model, name, price)
                
                # 메시지 레이아웃 구성
                message = f"📢 **[밸류레이더] 오늘의 단기 공략주**\n\n🔹 **종목명**: {name}\n🔹 **전일 종가**: {price:,.0f}원\n\n{report}"
                send_telegram(message)
                print(f"✅ {name} (종가: {price:,.0f}) 전송 성공!")
                
            except Exception as e:
                print(f"❌ {name} 에러: {e}")
                time.sleep(20)
                
    except Exception as e:
        print(f"🚨 시스템 오류: {e}")
