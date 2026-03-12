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
    # 코스닥 중소형주 (시총 1,000억 ~ 6,000억)
    df = fdr.StockListing('KOSDAQ')
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    return filtered.sort_values(by='Amount', ascending=False).head(20)

def generate_opinion(name, price):
    # 2026년 최신 클라이언트 세팅
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"너는 주식 전문가 노부장이야. 종목 {name}(종가 {price:,.0f}원)의 1~3일 단타 매수의견, 비중, 타점을 전문가답게 아주 구체적으로 작성해줘."
    
    # [수정] 쿼터 화면에서 확인한 최신 모델 'gemini-3.1-flash-lite' 사용
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite', 
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
        print(f"🚀 [밸류레이더] 2026년 3.1세대 엔진 가동: {len(stocks)}개 종목 ---")
        
        for i, (_, row) in enumerate(stocks.iterrows()):
            name = row['Name']
            price = row['Close']
            try:
                # [수정] RPM 15 한도를 고려하여 5초마다 하나씩 처리
                if i > 0:
                    print(f"API 한도 보호 중... ({i+1}/20) 5초 대기")
                    time.sleep(5) 
                
                opinion = generate_opinion(name, price)
                message = f"🚀 **단기 공략주: {name}**\n- **전일 종가**: {price:,.0f}원\n\n{opinion}"
                send_telegram(message)
                print(f"✅ {name} 전송 성공!")
                
            except Exception as e:
                print(f"❌ {name} 실패: {e}")
                time.sleep(10) # 에러 시 잠시 휴식
                
    except Exception as e:
        print(f"🚨 시스템 오류: {e}")
