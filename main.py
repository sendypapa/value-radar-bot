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
    # 코스닥 중소형주 10개 추출
    df = fdr.StockListing('KOSDAQ')
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    return filtered.sort_values(by='Amount', ascending=False).head(10)

def generate_opinion(name, price):
    # [수정] 3.1 모델이 있는 'v1beta' 통로로 접속합니다.
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={'api_version': 'v1beta'}
    )
    
    prompt = f"너는 주식 전문가 노부장이야. 종목 {name}(전일종가 {price:,.0f}원)의 1~3일 단타 매수의견, 비중, 타점을 전문가답게 아주 구체적으로 작성해줘."
    
    # [수정] 메뉴판에서 확인한 정확한 이름 사용
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
        print(f"🚀 [밸류레이더] 2026년형 3.1 Flash Lite 엔진 가동: {len(stocks)}개 ---")
        
        for i, (_, row) in enumerate(stocks.iterrows()):
            name = row['Name']
            price = row['Close']
            try:
                # RPM 15이므로 10초 대기면 차트 분석 속도로는 아주 안정적입니다.
                if i > 0:
                    print(f"안전 수익 구간 확보 중... ({i+1}/10) 10초 대기")
                    time.sleep(10) 
                
                opinion = generate_opinion(name, price)
                message = f"🚀 **단기 공략주: {name}**\n- **전일 종가**: {price:,.0f}원\n\n{opinion}"
                send_telegram(message)
                print(f"✅ {name} 배달 완료!")
                
            except Exception as e:
                print(f"❌ {name} 실패: {e}")
                time.sleep(15) # 에러 시 잠시 휴식
                
    except Exception as e:
        print(f"🚨 시스템 점검 필요: {e}")
