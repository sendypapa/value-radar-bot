from google import genai
import FinanceDataReader as fdr
import requests
import os
import time

# 깃허브 금고 데이터 로드
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_target_stocks():
    # 코스닥 종목 리스트 가져오기
    df = fdr.StockListing('KOSDAQ')
    # 시총 1,000억 ~ 6,000억 사이 중소형주 필터링 (Marcap 기준)
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    
    # [노부장님 전략 적용] 종목 수를 20개에서 10개로 집중합니다.
    top_10 = filtered.sort_values(by='Amount', ascending=False).head(10)
    return top_10

def generate_opinion(name, price):
    # 정식 도로(v1)로 강제 접속하여 404 에러를 방지합니다.
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={'api_version': 'v1'}
    )
    
    prompt = f"너는 주식 전문가 노부장이야. 종목 {name}(전일종가 {price:,.0f}원)의 1~3일 단타 매수의견, 비중, 타점을 아주 구체적으로 전문가답게 작성해줘."
    
    # 2026년 정식 버전에서 가장 확실한 모델 사용
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
        print(f"🚀 [밸류레이더] 선택과 집중! 우량 중소형주 {len(stocks)}개 분석 시작 ---")
        
        for i, (_, row) in enumerate(stocks.iterrows()):
            name = row['Name']
            price = row['Close']
            try:
                # [노부장님 전략 적용] 종목당 15초씩 휴식하여 429 에러를 완벽 차단합니다.
                if i > 0:
                    print(f"안정적인 수익 구간 확보 중... ({i+1}/10) 15초 뒤 분석")
                    time.sleep(15) 
                
                opinion = generate_opinion(name, price)
                message = f"🚀 **단기 공략주: {name}**\n- **전일 종가**: {price:,.0f}원\n\n{opinion}"
                send_telegram(message)
                print(f"✅ {name} 분석 완료 및 전송 성공!")
                
            except Exception as e:
                print(f"❌ {name} 처리 중 작은 장애 발생: {e}")
                time.sleep(20) # 에러 시에는 조금 더 길게 휴식
                
    except Exception as e:
        print(f"🚨 시스템 점검이 필요합니다: {e}")
