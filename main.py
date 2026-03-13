from google import genai
import FinanceDataReader as fdr
import requests
import os
import time
import json
import random
from datetime import datetime, timedelta

# 깃허브 시크릿 데이터
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

TRADES_FILE = "trades.json"

def get_accurate_stocks():
    """코스닥 종목 중 필터링을 통해 추천주 10개를 정확히 뽑아냅니다."""
    print("🔍 [단계 1] 코스닥 종목 리스트 불러오는 중...")
    df_listing = fdr.StockListing('KOSDAQ')
    
    # [수정] 컬럼명 대소문자 문제 완벽 해결
    # Marcap, MarCap, MARCAP 어떤 이름이든 찾아냅니다.
    target_col = next((c for c in df_listing.columns if c.lower() == 'marcap'), None)
    
    if not target_col:
        print("🚨 에러: 시가총액 컬럼을 찾을 수 없습니다!")
        return []

    # [수정] 필터링 조건 최적화 (시총 1,000억 ~ 8,000억으로 확대)
    filtered = df_listing[(df_listing[target_col] >= 100000000000) & (df_listing[target_col] <= 800000000000)]
    
    # 거래대금(Amount) 순으로 정렬 (거래 활발한 종목 우선)
    amt_col = next((c for c in df_listing.columns if c.lower() == 'amount'), target_col)
    top_candidates = filtered.sort_values(by=amt_col, ascending=False).head(20) # 20개 먼저 뽑음
    
    print(f"📊 후보 종목 {len(top_candidates)}개 발견! 정밀 분석 시작...")
    
    stock_data = []
    for _, row in top_candidates.iterrows():
        if len(stock_data) >= 10: break # 딱 10개만 채우면 종료
        
        symbol = row['Code']
        name = row['Name']
        try:
            # 실시간 가격(또는 전일 종가) 수집
            price_history = fdr.DataReader(symbol).tail(1)
            if price_history.empty: continue
            
            actual_close = price_history['Close'].iloc[0]
            stock_data.append({'name': name, 'symbol': symbol, 'price': actual_close})
            print(f"✅ 선정 완료: {name}({actual_close:,.0f}원)")
        except:
            continue
            
    return stock_data

def find_best_model(client):
    try:
        available = [m.name for m in client.models.list() if 'generateContent' in m.supported_actions]
        priorities = ['gemini-3.1-flash-lite', 'gemini-3-flash-lite', 'gemini-2.5-flash-lite']
        for priority in priorities:
            target = [name for name in available if priority in name]
            if target: return target[0]
        return available[0] if available else "gemini-2.0-flash"
    except: return "gemini-2.0-flash"

def generate_buy_report(client, model_name, name, price, tp, sl, profit_expect):
    today_date = datetime.now().strftime('%m월 %d일')
    
    prompt = f"""
    당신은 전문 주식 애널리스트입니다. 종목명: {name}, 추천가: {price:,.0f}원
    이 종목의 단기 상승 모멘텀을 분석하여 정중하게 설명하세요.
    
    [작성 지침]

    - 반드시 정중하고 따뜻한 존댓말로 작성할 것.

    - 1~3일 단기 매매 관점에서 '매수의견, 투자비중, 매수타점, 익절가, 손절가'를 핵심만 작성할 것.

    - 마크다운 기호(예: **, _, #)를 절대 사용하지 말고 순수 텍스트와 줄바꿈으로만 구성할 것.

    - 전체 분량은 6~7줄 이내로 아주 간결하게 작성할 것.
    """
    
    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        ai_content = response.text
    except:
        ai_content = "현재 시장 수급 흐름상 단기 반등이 기대되는 구간입니다."

    report = (
        f"안녕하세요 밸류레이더 노부장입니다.\n"
        f"{today_date} 금일 단기 공략주 공유드립니다.\n\n"
        f"📌 [{name} 분석 리포트]\n"
        f"• 매수 타점: <b>{price:,.0f}원</b> (전일 종가 부근)\n"
        f"• 예상 수익률: <b>약 {profit_expect}%</b>\n"
        f"• 투자 비중: <b>10~15% 내외</b>\n\n"
        f"✅ 조건부 매도 추천가\n"
        f"• 익절 목표가: <b>{tp:,.0f}원\n"
        f"• 손절 대응가: <b>{sl:,.0f}원\n\n"
        f"📖 분석 포인트\n{ai_content}\n\n"
        f"⚠️ 노부장의 안내사항\n"
        f"1분 1초마다 바뀌는 장 특성상 사인을 보고 매도를 하시면 늦습니다. "
        f"조건부 매도 세팅을 통해 안정적인 매매 세팅을 하시는 것을 권고드립니다.\n\n"
        f"반드시 1~5일 지켜봐주시기 바랍니다. 오늘도 성투를 빌겠습니다."
    )
    return report

def check_performance():
    """어제 추천한 종목들의 성과를 분석하여 리포트를 만듭니다."""
    if not os.path.exists(TRADES_FILE): return None
    
    with open(TRADES_FILE, 'r') as f:
        old_trades = json.load(f)
    if not old_trades: return None

    perf_reports = []
    trade_date = old_trades[0].get('date', '이전')
    
    for trade in old_trades:
        name, symbol, buy_p, tp, sl = trade['name'], trade['symbol'], trade['buy_price'], trade['tp'], trade['sl']
        try:
            # 어제(혹은 최근) 하루치 데이터 조회
            df = fdr.DataReader(symbol).tail(1)
            high_p = df['High'].iloc[0]
            close_p = df['Close'].iloc[0]
            
            # 수익률 계산 (매수추천가 대비 익절가 도달 여부)
            if high_p >= tp:
                actual_profit = ((tp - buy_p) / buy_p) * 100
                status = f"✅ <b>축하드립니다! 수익 달성! (+{actual_profit:.1f}%)</b>"
            elif high_p <= sl:
                status = "❌ <b>손절 처리</b>"
            else:
                status = "⏳ <b>관망 (보유 중)</b>"

            perf_reports.append(
                f"종목명 : {name}\n"
                f"매수추천가 : {buy_p:,.0f}원\n"
                f"조건부매매 추천가 : 익절 {tp:,.0f} / 손절 {sl:,.0f}\n"
                f"장중 최고가 : {high_p:,.0f}원\n"
                f"결과 : {status}\n"
            )
        except: continue

    if not perf_reports: return None
    
    header = f"📢 <b>{trade_date} 매매 결과 리포트</b>\n------------------------\n"
    return header + "\n".join(perf_reports)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    # HTML 모드가 더 안정적이어서 HTML로 발송합니다.
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    requests.post(url, json=payload)

if __name__ == "__main__":
    try:
        client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1'})
        target_model = find_best_model(client)
        
        # 1. 어제 성적표 먼저 발송
        perf_msg = check_performance()
        if perf_msg:
            send_telegram(perf_msg)
            time.sleep(5) # 메시지 섞임 방지

        # 2. 오늘 종목 분석 및 발송
        stocks = get_accurate_stocks()
        print(f"🚀 [밸류레이더] {target_model} 엔진 가동")
        
        today_trades = []
        today_str = datetime.now().strftime('%m월 %d일')

        for i, stock in enumerate(stocks):
            name, symbol, price = stock['name'], stock['symbol'], stock['price']
            
            # [수정] 익절가 +6~8% 랜덤, 손절가 -3% 고정 계산
            profit_expect = random.randint(6, 8)
            tp = price * (1 + profit_expect / 100)
            sl = price * 0.97
            
            if i > 0: time.sleep(15)
            
            report = generate_buy_report(client, target_model, name, price, tp, sl, profit_expect)
            send_telegram(report)
            print(f"✅ {name} 전송 성공!")
            
            # 장부에 기록
            today_trades.append({
                'date': today_str, 'name': name, 'symbol': symbol, 
                'buy_price': price, 'tp': tp, 'sl': sl
            })

        # 3. 오늘 추천한 종목을 파일로 저장 (내일 복기용)
        with open(TRADES_FILE, 'w') as f:
            json.dump(today_trades, f)
                
    except Exception as e:
        print(f"🚨 시스템 오류: {e}")
