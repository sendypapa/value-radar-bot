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
    """2026년 최신 문법으로 모든 Flash-Lite 후보군을 검색합니다."""
    try:
        # 1. 현재 주문 가능한 모델 리스트 싹 긁어오기
        available = [m.name for m in client.models.list() if 'generateContent' in m.supported_actions]
        
        # [노부장님 추천 적용] 2.5 Flash Lite까지 포함한 우선순위 리스트
        # 한도가 가장 넉넉한 3.1부터 순서대로 찾습니다.
        priorities = [
            'gemini-3.1-flash-lite', 
            'gemini-3.1-flash', 
            'gemini-3-flash-lite', 
            'gemini-2.5-flash-lite', # 노부장님 추천 종목 추가!
            'gemini-2.5-flash'
        ]
        
        for priority in priorities:
            target = [name for name in available if priority in name]
            if target:
                print(f"🎯 최적의 엔진 발견: {target[0]}")
                return target[0]
        
        return available[0] if available else "gemini-2.0-flash"
    except Exception as e:
        print(f"🚨 모델 검색 중 오류: {e}")
        return "gemini-2.0-flash"

from datetime import datetime

def generate_report(client, model_name, name, price):
    # 1. 파이썬에서 오늘 날짜 확정
    today_date = datetime.now().strftime('%m월 %d일')
    
    # 2. AI에게는 '알맹이'만 작성하도록 프롬프트 최적화
    # 특수문자(*, _, #)를 쓰지 말고 순수 텍스트로만 달라고 명시합니다.
    prompt = f"""
    당신은 전문 주식 애널리스트입니다. 
    종목명: {name}, 전일 종가: {price:,.0f}원
    
    [작성 지침]
    - 반드시 정중하고 따뜻한 존댓말로 작성할 것.
    - 1~3일 단기 매매 관점에서 '매수의견, 투자비중, 매수타점, 익절가, 손절가'를 핵심만 작성할 것.
    - 마크다운 기호(예: **, _, #)를 절대 사용하지 말고 순수 텍스트와 줄바꿈으로만 구성할 것.
    - 전체 분량은 6~7줄 이내로 아주 간결하게 작성할 것.
    """
    
    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        ai_content = response.text
        
        # 3. 노부장님이 원하시는 고정 문구를 앞뒤로 결합 (안정성 100%)
        # HTML 태그 <b>(굵게) 등을 활용해 깔끔하게 정리합니다.
        final_report = (
            f"안녕하세요 밸류레이더 노부장입니다.\n"
            f"{today_date} 금일 단기 공략주 공유드립니다.\n\n"
            f"📌 [{name} 분석 리포트]\n"
            f"{ai_content}\n\n"
            f"반드시 1~5일 지켜봐주시기 바랍니다.\n"
            f"별도 매도신호는 나가지 않습니다.\n"
            f"단기 추천 종목인 만큼 3~5% 이상 수익이 나시면\n"
            f"익절로 대응하시는 걸 추천드립니다.\n"
            f"오늘도 성투를 빌겠습니다."
        )
        return final_report
        
    except Exception as e:
        print(f"AI 리포트 생성 실패: {e}")
        return f"리포트 생성 중 오류가 발생했습니다. (종목: {name})"
        
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
