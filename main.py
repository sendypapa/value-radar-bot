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
    return filtered.sort_values(by='Amount', ascending=False).head(20)

def generate_opinion(name, price):
    # [핵심] API 버전을 'v1'(정식)으로 강제 고정합니다.
    client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1'})
    
    prompt = f"너는 주식 전문가 노부장이야. 종목 {name}(종가 {price:,.0f}원)의 1~3일 단타 매수의견, 비중, 타점을 아주 구체적으로 작성해줘."
    
    # [수정] 모델명을 'models/' 접두사를 붙여 더 정확하게 호출합니다.
    response = client.models.generate_content(
        model='models/gemini-2.0-flash', # 정식 도로(v1)에서 가장 확실한 모델
        contents=prompt
    )
    return response.text

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    try:
        # 1. 시크릿 오타 검수 (노부장님, 이거 한 번만 더 확인!)
        if not GEMINI_API_KEY or not TELEGRAM_TOKEN or not CHAT_ID:
            print("🚨 깃허브 시크릿(Secrets) 설정이 안 되어 있습니다!")
            exit()

        stocks = get_target_stocks()
        print(f"🚀 [밸류레이더] 2026년 정식 엔진 가동: {len(stocks)}개 종목 ---")
        
        for i, (_, row) in enumerate(stocks.iterrows()):
            name = row['Name']
            price = row['Close']
            try:
                # RPM 15 한도를 고려하여 안전하게 10초 대기
                if i > 0:
                    print(f"API 안정성 확보 중... ({i+1}/20) 10초 대기")
                    time.sleep(10) 
                
                opinion = generate_opinion(name, price)
                message = f"🚀 **단기 공략주: {name}**\n- **전일 종가**: {price:,.0f}원\n\n{opinion}"
                send_telegram(message)
                print(f"✅ {name} 전송 성공!")
                
            except Exception as e:
                print(f"❌ {name} 실패: {e}")
                # 만약 또 404가 뜨면 'gemini-1.5-flash'로 시도 (거의 모든 계정 허용)
                if "404" in str(e):
                    try:
                        print(f"🔄 {name} 모델 긴급 하향 조정 시도...")
                        client = genai.Client(api_key=GEMINI_API_KEY)
                        opinion = client.models.generate_content(model='models/gemini-1.5-flash', contents=prompt).text
                        send_telegram(f"🚀 **단기 공략주: {name}**\n\n{opinion}")
                        print(f"✅ {name} 긴급 복구 전송 성공!")
                    except:
                        pass
                time.sleep(5)
                
    except Exception as e:
        print(f"🚨 시스템 오류: {e}")
