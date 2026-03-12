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
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    return filtered.sort_values(by='Amount', ascending=False).head(10)

def find_best_model(client):
    """현재 API 키로 사용 가능한 최적의 모델명을 자동으로 찾습니다."""
    print("🔍 사용 가능한 모델 리스트 검색 중...")
    try:
        # 지원하는 모델 목록 가져오기
        models = [m.name for m in client.models.list() if 'generateContent' in m.supported_methods]
        
        # 3.1 -> 3 -> 2.5 순서로 좋은 모델 찾기
        for priority in ['gemini-3.1', 'gemini-3', 'gemini-2.5', 'gemini-2']:
            target = [m for m in models if priority in m and 'flash' in m]
            if target:
                selected = target[0] # 가장 첫 번째 매칭되는 모델 선택
                print(f"🎯 최적 모델 발견: {selected}")
                return selected
        
        # 만약 없으면 리스트 중 첫 번째 사용
        print(f"⚠️ 우선순위 모델이 없어 첫 번째 모델({models[0]})을 선택합니다.")
        return models[0]
    except Exception as e:
        print(f"🚨 모델 리스트 확인 실패: {e}")
        return "models/gemini-1.5-flash" # 최후의 보루

def generate_opinion(client, model_name, name, price):
    prompt = f"너는 주식 전문가 노부장이야. 종목 {name}(종가 {price:,.0f}원)의 1~3일 단타 매수의견, 비중, 타점을 아주 구체적으로 전문가답게 작성해줘."
    
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
        # 1. 클라이언트 생성 (정식/실험용 도로 자동 대응을 위해 기본 설정 사용)
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # 2. 내 계정에서 지금 '진짜' 쓸 수 있는 모델 찾기
        target_model = find_best_model(client)
        
        # 3. 종목 가져오기
        stocks = get_target_stocks()
        print(f"🚀 [밸류레이더] 엔진({target_model}) 가동! 10개 종목 분석 시작 ---")
        
        for i, (_, row) in enumerate(stocks.iterrows()):
            name = row['Name']
            price = row['Close']
            try:
                # RPM 한도 보호 (12초 간격)
                if i > 0:
                    print(f"안전 대기 중... ({i+1}/10) 12초 뒤 분석")
                    time.sleep(12) 
                
                opinion = generate_opinion(client, target_model, name, price)
                message = f"🚀 **단기 공략주: {name}**\n- **전일 종가**: {price:,.0f}원\n\n{opinion}"
                send_telegram(message)
                print(f"✅ {name} 전송 성공!")
                
            except Exception as e:
                print(f"❌ {name} 실패: {e}")
                time.sleep(20)
                
    except Exception as e:
        print(f"🚨 시스템 치명적 오류: {e}")
