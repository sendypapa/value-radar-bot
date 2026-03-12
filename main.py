from google import genai
import FinanceDataReader as fdr
import requests
import os
import time

# 깃허브 시크릿 데이터 (절대 오타 없어야 함!)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_target_stocks():
    # 코스닥 중소형주 (시총 1,000억 ~ 6,000억)
    df = fdr.StockListing('KOSDAQ')
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    return filtered.sort_values(by='Amount', ascending=False).head(20)

def generate_opinion(name, price):
    # 2026년형 최신 클라이언트 세팅
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"너는 주식 전문가 노부장이야. 종목 {name}(종가 {price:,.0f}원)에 대해 1~3일 단타 매수의견, 비중, 타점을 전문가답게 구체적으로 써줘."
    
    # [핵심] 2026년형 메인 모델 'gemini-2.0-flash' 사용
    # 만약 이것도 404가 뜨면 구글이 모델명을 바꾼 것이므로 목록을 뽑아야 함
    response = client.models.generate_content(
        model='gemini-2.0-flash', 
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
        print(f"--- [밸류레이더] 2026년형 엔진 가동: {len(stocks)}개 ---")
        
        for _, row in stocks.iterrows():
            name = row['Name']
            price = row['Close']
            try:
                opinion = generate_opinion(name, price)
                # 메시지 조립
                message = f"🚀 **단기 공략주: {name}**\n- **전일 종가**: {price:,.0f}원\n\n{opinion}"
                send_telegram(message)
                print(f"✅ {name} 전송 완료")
                time.sleep(2.5) # 안전하게 2.5초씩 휴식
            except Exception as e:
                print(f"❌ {name} 분석 실패: {e}")
                
    except Exception as e:
        print(f"🚨 치명적 시스템 에러: {e}")
