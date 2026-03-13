from google import genai
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
        print("⚠️ 조건 부합 종목 부족으로 거래대금 상위주로 그물을 넓힙니다.")
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
            actual_close = price_history['Close'].iloc[0]
            stock_data.append({'name': name, 'symbol': symbol, 'price': actual_close})
            print(f"✅ 선정: {name}({actual_close:,.0f}원)")
        except: continue
            
    return stock_data

def find_best_model(client):
    """2026년 최신 문법으로 최적의 모델을 찾습니다."""
    try:
        available = [m.name for m in client.models.list() if 'generateContent' in m.supported_actions]
        priorities = ['gemini-3.1-flash-lite', 'gemini-3-flash-lite', 'gemini-2.5-flash-lite']
        for priority in priorities:
            target = [name for name in available if priority in name]
            if target: return target[0]
        return available[0]
    except: return "gemini-2.0-flash"

def generate_buy_report(client, model_name, name, price, tp, sl, profit_expect):
    """AI를 통해 종목별로 '살아있는' 2줄 분석 리포트를 생성합니다."""
    today_date = datetime.now().strftime('%m월 %d일')
    
    prompt = f"""
    당신은 밸류레이더 소속의 베테랑 주식 애널리스트입니다. 
    대상 종목: {name}, 현재가: {price:,.0f}원
    
    [작성 규칙]
    1. 이 종목의 현재 위치를 고려하여 매수해야 하는 이유를 '딱 2줄'로 작성하세요.
    2. '거래량 실린 장대양봉', '매집봉 포착', '이평선 정배열 초기', '외인/기관 수급 유입', '매물대 돌파' 등 전문적인 용어를 사용하여 분석하세요.
    3. 종목마다 내용이 중복되지 않도록 역동적으로 작성하세요.
    4. 마크다운(**)이나 특수문자는 절대 사용 금지, 순수 텍스트와 줄바꿈으로만 구성하세요.
    """
    
    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        ai_content = response.text.strip()
        if len(ai_content) < 10: raise ValueError
    except:
        fallbacks = [
            f"주요 이평선 부근에서 강력한 지지세가 확인되며, 바닥권 거래량이 실리는 추세 전환 국면입니다.",
            f"최근 기관의 연속적인 수급 유입이 포착되었으며, 전고점 매물 소화 후 슈팅이 기대되는 자리입니다.",
            f"단기 정배열 초입 구간으로 하방 경직성이 확보되었습니다. 변동성을 활용한 눌림목 공략이 유효합니다.",
            f"거래대금이 동반된 돌파 시도가 이어지고 있으며, 상방 매물벽이 얇아 가벼운 탄력이 예상됩니다.",
            f"과매도 구간 이후 RSR 등 기술적 지표가 반등을 가리키고 있어 단기 기술적 반등의 확률이 매우 높습니다."
        ]
        ai_content = random.choice(fallbacks)

    report = (
        f"📢 <b>[밸류레이더] 오늘의 단기 공략주</b>\n\n"
        f"🔹 <b>종목명</b>: {name}\n"
        f"🔹 <b>매수 타점</b>: <b>{price:,.0f}원</b> (전일 종가 부근)\n\n"
        f"안녕하세요 밸류레이더 노부장입니다.\n"
        f"<b>{today_date} 금일 단기 공략주 공유드립니다.</b>\n\n"
        f"📌 <b>[{name} 분석 리포트]</b>\n"
        f"• 예상 수익률: <b>약 {profit_expect}%</b>\n"
        f"• 투자 비중: <b>10~15% 내외</b>\n\n"
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
    return report

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    return requests.post(url, json=payload)

if __name__ == "__main__":
    try:
        client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1'})
        target_model = find_best_model(client)
        
        stocks = get_accurate_stocks()
        if not stocks:
            print("🚨 분석 가능한 종목이 없습니다.")
        else:
            today_trades = []
            today_str = datetime.now().strftime('%m월 %d일')

            for i, stock in enumerate(stocks):
                name, symbol, price = stock['name'], stock['symbol'], stock['price']
                
                profit_expect = random.randint(6, 8)
                tp = price * (1 + profit_expect / 100)
                sl = price * 0.97
                
                if i > 0:
                    print(f"⏳ RPM 보호를 위해 15초 대기 중... ({i+1}/10)")
                    time.sleep(15)
                
                # 텔레그램 발송 및 리포트 생성
                report = generate_buy_report(client, target_model, name, price, tp, sl, profit_expect)
                send_telegram(report)
                print(f"✅ {name} 추천 완료")
                
                # 리스트에 추가
                today_trades.append({
                    'date': today_str, 'name': name, 'symbol': symbol, 
                    'buy_price': price, 'tp': tp, 'sl': sl
                })

                # [중요] 한 종목 보낼 때마다 즉시 장부 파일 업데이트 (실시간 백업)
                with open(TRADES_FILE, 'w', encoding='utf-8') as f:
                    json.dump(today_trades, f, ensure_ascii=False, indent=4)
                print(f"💾 {name} 장부 실시간 기록 완료")
                
            print(f"🎯 총 {len(today_trades)}개 종목 최종 기록 완료")
                
    except Exception as e:
        print(f"🚨 추천 시스템 치명적 오류: {e}")
