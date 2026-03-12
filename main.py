from google import genai
import FinanceDataReader as fdr
import requests
import os
import time

# 깃허브 금고 열기
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def get_target_stocks():
    # 코스닥 중소형주 추출
    df = fdr.StockListing('KOSDAQ')
    filtered = df[(df['Marcap'] >= 100000000000) & (df['Marcap'] <= 600000000000)]
    return filtered.sort_values(by='Amount', ascending=False).head(20)

def generate_opinion(name, price):
    # [핵심] 정식 도로(v1) 주소를 강제로 설정합니다.
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={'api_version': 'v1'} # 여기가 바로 정식 고속도로 진입점입니다!
    )
    
    prompt = f"너는 주식 전문가 노부장이야. 종목 {name}(전일종가 {price:,.0f}원)의 1~3일 단타 매수의견, 비중, 타점을 아주 구체적으로 전문가답게 작성해줘."
    
    # [수정] 정식 도로에서 가장 안정적인 'gemini-2.0-flash'를 사용합니다.
    # 만약 메뉴판에 2.0이 없다면 자동으로 1.5로 시도하게 안전장치를 걸었습니다.
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
    except:
        response = client.models.generate_content(
            model='gemini-1.5-flash', 
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
        print(f"🚀 [밸류레이더] 정식 고속도로(v1) 진입 성공! 분석 시작: {len(stocks)}개 ---")
        
        for i, (_, row) in enumerate(stocks.iterrows()):
            name = row['Name']
            price = row['Close']
            try:
                # 무료 티어는 '천천히'가 생명입니다. 15초 간격으로 안전하게!
                if i > 0:
                    print(f"안전 운행 중... ({i+1}/20) 15초 뒤 다음 종목")
                    time.sleep(15) 
                
                opinion = generate_opinion(name, price)
                message = f"🚀 **단기 공략주: {name}**\n- **전일 종가**: {price:,.0f}원\n\n{opinion}"
                send_telegram(message)
                print(f"✅ {name} 배달 완료!")
                
            except Exception as e:
                print(f"❌ {name} 에러: {e}")
                time.sleep(20) # 에러 나면 더 길게 휴식
                
    except Exception as e:
        print(f"🚨 시스템 점검 필요: {e}")
