from google import genai
import FinanceDataReader as fdr
import requests
import os
import time

# 깃허브 시크릿 데이터
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_target_stocks():
    df = fdr.StockListing('KOSDAQ')
    # 시총 1,000억 ~ 6,000억 사이 필터링 (10개 종목 집중)
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    return filtered.sort_values(by='Amount', ascending=False).head(10)

def find_best_model(client):
    """2026년 최신 문법으로 사용 가능한 모델을 검색합니다."""
    print("🔍 노부장님의 전용 모델 리스트 검색 중...")
    try:
        # [2026년형 문법] supported_actions를 확인하여 사용 가능한 모델 추출
        available_models = []
        for m in client.models.list():
            if hasattr(m, 'supported_actions') and 'generateContent' in m.supported_actions:
                available_models.append(m.name)
        
        # 3.1 -> 3 -> 2.5 순서로 가장 좋은 모델 선택
        for priority in ['gemini-3.1', 'gemini-3', 'gemini-2.5', 'gemini-2']:
            for name in available_models:
                if priority in name and 'flash' in name:
                    print(f"🎯 최적 엔진 발견: {name}")
                    return name
        
        if available_models:
            print(f"⚠️ 우선순위 모델이 없어 {available_models[0]}을(를) 선택합니다.")
            return available_models[0]
        return "models/gemini-2.0-flash" # 최후의 보루
    except Exception as e:
        print(f"🚨 리스트 검색 중 오류(v1 고수): {e}")
        return "gemini-2.0-flash"

def generate_opinion(client, model_name, name, price):
    prompt = f"주식 전문가 노부장 말투로, {name}(종가 {price:,.0f}원)의 1~3일 단타 매수의견, 비중, 타점을 아주 구체적으로 작성해줘."
    
    # 2026년형 표준 호출
    response = client.models.generate_content(
        model=model_name,
        contents=prompt
    )
    return response.text

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    try:
        # 정식 도로(v1)로 접속
        client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1'})
        
        # 내 계정에 상장된 최적의 모델 찾기
        target_model = find_best_model(client)
        
        stocks = get_target_stocks()
        print(f"🚀 [밸류레이더] {target_model} 엔진으로 10개 종목 분석 시작!")
        
        for i, (_, row) in enumerate(stocks.iterrows()):
            name = row['Name']
            price = row['Close']
            try:
                # 15초 간격으로 429 에러 완벽 차단
                if i > 0:
                    print(f"안전 수익 구간 대기 중... ({i+1}/10) 15초 뒤 분석")
                    time.sleep(15) 
                
                opinion = generate_opinion(client, target_model, name, price)
                message = f"🚀 **단기 공략주: {name}**\n- **전일 종가**: {price:,.0f}원\n\n{opinion}"
                send_telegram(message)
                print(f"✅ {name} 전송 성공!")
                
            except Exception as e:
                print(f"❌ {name} 에러: {e}")
                time.sleep(20)
                
    except Exception as e:
        print(f"🚨 시스템 오류: {e}")
