from google import genai
import FinanceDataReader as fdr
import requests
import os
import time

# 시크릿 로드
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_target_stocks():
    # 코스닥 중소형주 (시총 1,000억~6,000억)
    df = fdr.StockListing('KOSDAQ')
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    return filtered.sort_values(by='Amount', ascending=False).head(20)

def generate_opinion(name, price):
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"주식 전문가 노부장 말투로, {name}(종가 {price:,.0f}원)의 1~3일 단타 매수의견, 비중, 타점을 아주 구체적으로 작성해줘."
    
    # [핵심 변경] 쿼터가 살아있는 최신형 'gemini-3-flash' 모델 사용
    response = client.models.generate_content(
        model='gemini-3-flash',
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
        print(f"--- [밸류레이더] 최신 3세대 엔진 가동: {len(stocks)}개 ---")
        
        for i, (_, row) in enumerate(stocks.iterrows()):
            name = row['Name']
            price = row['Close']
            try:
                # [중요] RPM 5 한도를 지키기 위해 12초마다 하나씩 처리 (1분당 5개)
                if i > 0:
                    print(f"안전한 전송을 위해 12초 대기 중... ({i+1}/20)")
                    time.sleep(12) 
                
                opinion = generate_opinion(name, price)
                message = f"🚀 **단기 공략주: {name}**\n- **전일 종가**: {price:,.0f}원\n\n{opinion}"
                send_telegram(message)
                print(f"✅ {name} 전송 성공!")
                
            except Exception as e:
                print(f"❌ {name} 실패: {e}")
                time.sleep(15) # 에러 발생 시 쿼터 회복 대기
                
    except Exception as e:
        print(f"🚨 시스템 오류: {e}")
