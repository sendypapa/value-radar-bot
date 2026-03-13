from google import genai
from google.genai import types
import FinanceDataReader as fdr
import requests
import os
import time
import json
import random
from datetime import datetime

# 깃허브 시크릿 데이터
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

TRADES_FILE = "trades.json"

def get_accurate_stocks():
    """코스닥 종목 중 필터링을 통해 추천주 10개를 정확히 뽑아냅니다."""
    print("🔍 [단계 1] 종목 스캐닝 엔진 가동...")
    df_listing = fdr.StockListing('KOSDAQ')
    marcap_col = next((c for c in df_listing.columns if c.lower() == 'marcap'), 'Marcap')
    amt_col = next((c for c in df_listing.columns if c.lower() == 'amount'), 'Amount')
    filtered = df_listing[(df_listing[marcap_col] >= 100000000000) & (df_listing[marcap_col] <= 800000000000)]
    
    if len(filtered) < 5:
        top_candidates = df_listing.sort_values(by=amt_col, ascending=False).head(15)
    else:
        top_candidates = filtered.sort_values(by=amt_col, ascending=False).head(15)
    
    stock_data = []
    for _, row in top_candidates.iterrows():
        if len(stock_data) >= 10: break
        symbol, name = row['Code'], row['Name']
        try:
            price_history = fdr.DataReader(symbol).tail(1)
            if price_history.empty: continue
            # [수정] JSON 저장을 위해 반드시 일반 정수(int)로 변환
            actual_close = int(price_history['Close'].iloc[0])
            stock_data.append({'name': name, 'symbol': symbol, 'price': actual_close})
            print(f"✅ 선정: {name}({actual_close:,.0f}원)")
        except: continue
    return stock_data

def generate_buy_report(client, model_name, name, price, tp, sl, profit_expect):
    """400 에러를 방지하기 위해 매개변수 형식을 표준화한 버전입니다."""
    today_date = datetime.now().strftime('%m월 %d일')
    
    # [수정] 모델 이름에 models/ 가 없다면 붙여주는 안전장치
    full_model_name = model_name if model_name.startswith("models/") else f"models/{model_name}"
    
    # 노부장님의 필터 우회형 프롬프트 (이슈 + 차트분석 요청)
    prompt = f"""
    너는 주식전문가 밸류레이더 소속의 노부장이야. 
    종목명: {name}, 전일종가: {price:,.0f}원. 
    1~3일 보유 단타 관점에서 종목에대한 이슈와 차트분석을 간단하게 2~3줄로 전문가처럼 작성해줘.
    - 마크다운 특수문자(*, #)는 절대 사용하지 마세요.
    - 정중한 존댓말로 핵심만 짚어주세요.
    """
    
    # [수정] 400 에러를 방지하기 위해 카테고리 명칭을 최신 표준으로 정리
    safety_settings = [
        types.SafetySetting(category="HATE_SPEECH", threshold="OFF"),
        types.SafetySetting(category="HARASSMENT", threshold="OFF"),
        types.SafetySetting(category="DANGEROUS_CONTENT", threshold="OFF"),
        types.SafetySetting(category="SEXUALLY_EXPLICIT", threshold="OFF"),
    ]

    try:
        # [수정] config 구조를 명확히 전달
        response = client.models.generate_content(
            model=full_model_name, 
            contents=prompt,
            config=types.GenerateContentConfig(safety_settings=safety_settings)
        )
        
        if response.text and len(response.text.strip()) > 5:
            ai_content = response.text.strip().replace('*', '').replace('#', '')
            print(f"🎯 {name} AI 정밀 분석 성공!")
        else:
            ai_content = "⚠️ 현재 해당 종목에 대한 AI 정밀 분석 데이터를 불러올 수 없습니다."
            print(f"🚨 {name} AI 분석 거절됨 (Safety Filter)")

    except Exception as e:
        # [디버깅] 에러 원인을 더 정확히 파악하기 위해 로그 출력 강화
        print(f"⚠️ {name} AI 분석 에러 발생: {e}")
        ai_content = "분석포인트 별도 전달드리겠습니다."

    return (
        f"📢 <b>[밸류레이더] 오늘의 단기 공략주</b>\n\n"
        f"🔹 <b>종목명</b>: {name}\n"
        f"🔹 <b>매수 타점</b>: <b>{price:,.0f}원</b>\n\n"
        f"안녕하세요 밸류레이더 노부장입니다.\n"
        f"<b>{today_date} 금일 단기 공략주 공유드립니다.</b>\n\n"
        f"📌 <b>[{name} 분석 리포트]</b>\n"
        f"• 예상 수익률: 약 {profit_expect}%\n"
        f"• 투자 비중: 10~15% 내외\n\n"
        f"✅ <b>조건부 매도 추천가</b>\n"
        f"• 익절 목표가: <b>{tp:,.0f}원</b>\n"
        f"• 손절 대응가: <b>{sl:,.0f}원</b>\n\n"
        f"📖 <b>분석 포인트</b>\n{ai_content}\n\n"
        f"⚠️ <b>노부장의 안내사항</b>\n"
        f"1분 1초마다 바뀌는 장 특성상 사인을 보고 매도를 하시면 늦습니다. "
        f"조건부 매도 세팅을 통해 안정적인 매매 환경을 만드시는 것을 권고드립니다.\n\n"
        f"오늘도 노부장과 함께 행복한 하루되세요!\n\n"
        f"밸류레이더에서 빠른 종목 분석과 대응 시나리오를 만나보실 수 있습니다."
    )

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    return requests.post(url, json=payload)

if __name__ == "__main__":
    try:
        client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1'})
        target_model = "gemini-1.5-flash" 
        
        stocks = get_accurate_stocks()
        today_trades = []
        today_str = datetime.now().strftime('%m월 %d일')

        for i, stock in enumerate(stocks):
            name, symbol, price = stock['name'], stock['symbol'], stock['price']
            profit_expect = random.randint(6, 8)
            tp = int(price * (1 + profit_expect / 100))
            sl = int(price * 0.97)
            
            if i > 0: time.sleep(15) 
            
            try:
                report = generate_buy_report(client, target_model, name, price, tp, sl, profit_expect)
                res = send_telegram(report)
                
                # [중요] 텔레그램 전송이 성공했을 때만 장부에 기록합니다.
                if res.status_code == 200:
                    today_trades.append({
                        'date': today_str, 
                        'name': name, 
                        'symbol': symbol, 
                        'buy_price': price, 
                        'tp': tp, 
                        'sl': sl
                    })
                    
                    # [백업 보장] 루프 안에서 매번 파일을 저장하여 데이터 유실을 방지합니다.
                    with open(TRADES_FILE, 'w', encoding='utf-8') as f:
                        json.dump(today_trades, f, ensure_ascii=False, indent=4)
                    print(f"✅ {name} 발송 및 장부 기록 완료")
                    
            except Exception as e:
                print(f"⚠️ {name} 처리 중 오류: {e}")
                continue
                
    except Exception as e:
        print(f"🚨 치명적 오류: {e}")
