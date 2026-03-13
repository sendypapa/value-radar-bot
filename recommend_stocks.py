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
            actual_close = int(price_history['Close'].iloc[0])
            stock_data.append({'name': name, 'symbol': symbol, 'price': actual_close})
            print(f"✅ 선정: {name}({actual_close:,.0f}원)")
        except: continue
    return stock_data

def find_best_model(client):
    try:
        available = [m.name for m in client.models.list() if 'generateContent' in m.supported_actions]
        # models/ 접두사 제거 로직 추가
        target = next((m for m in available if 'gemini-1.5-flash' in m or 'gemini-2.0-flash' in m), available[0])
        return target
    except: return "gemini-1.5-flash"

def generate_buy_report(client, model_name, name, price, tp, sl, profit_expect):
    """노부장님의 특제 프롬프트를 사용하여 AI 분석 리포트를 생성합니다."""
    today_date = datetime.now().strftime('%m월 %d일')
    
    # [수정] 노부장님의 아이디어를 반영한 '필터 우회형' 전문 분석 프롬프트
    prompt = f"""
    너는 주식 전문 애널리스트입니다. 
    현재 {name}의 가격은 {price:,.0f}원인데, 투자 전문가로서의 관점과 기술적 분석 부분의 관점으로 보았을 때의 단기주가전망에 대한 분석을 2줄로 요약해서 만들어주세요.
    - 마크다운 특수문자(*, #)는 절대 사용하지 마세요.
    - 정중한 존댓말로 핵심만 짚어주세요.
    """
    
    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        if response.text:
            # AI가 혹시나 넣었을지 모를 마크다운 기호를 한 번 더 제거합니다.
            ai_content = response.text.strip().replace('*', '').replace('#', '')
        else:
            ai_content = "현재 기술적 지표상 반등 에너지가 응축된 구간으로 단기 수익 실현 가능성이 높은 자리입니다."
        print(f"🎯 {name} 분석 성공!")
    except Exception as e:
        print(f"⚠️ {name} 분석 실패 (Fallback 사용): {e}")
        ai_content = "현재 수급 흐름이 양호하며 주요 지지선에서의 기술적 반등이 유효한 구간입니다."

    return (
        f"📢 <b>[밸류레이더] 오늘의 단기 공략주</b>\n\n"
        f"🔹 <b>종목명</b>: {name}\n"
        f"🔹 <b>매수 타점</b>: <b>{price:,.0f}원</b> (전일 종가 부근)\n\n"
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
        target_model = find_best_model(client)
        print(f"🚀 분석 엔진 가동: {target_model}")
        
        stocks = get_accurate_stocks()
        today_trades = []
        today_str = datetime.now().strftime('%m월 %d일')

        for i, stock in enumerate(stocks):
            name, symbol, price = stock['name'], stock['symbol'], stock['price']
            profit_expect = random.randint(6, 8)
            tp = int(price * (1 + profit_expect / 100))
            sl = int(price * 0.97)
            
            if i > 0: time.sleep(15) # RPM 보호
            
            try:
                report = generate_buy_report(client, target_model, name, price, tp, sl, profit_expect)
                res = send_telegram(report)
                
                if res.status_code == 200:
                    today_trades.append({
                        'date': today_str, 'name': name, 'symbol': symbol, 
                        'buy_price': price, 'tp': tp, 'sl': sl
                    })
                    # 매 종목마다 즉시 저장 (백업 보장)
                    with open(TRADES_FILE, 'w', encoding='utf-8') as f:
                        json.dump(today_trades, f, ensure_ascii=False, indent=4)
                    print(f"✅ {name} 발송 및 장부 기록 완료")
                else:
                    print(f"❌ {name} 전송 실패: {res.text}")
            except Exception as e:
                print(f"⚠️ {name} 개별 처리 중 오류: {e}")
                continue
                
    except Exception as e:
        print(f"🚨 시스템 치명적 오류: {e}")
