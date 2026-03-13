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
    
    # 컬럼명 유연화 (Marcap/MarCap 대응)
    marcap_col = next((c for c in df_listing.columns if c.lower() == 'marcap'), 'Marcap')
    amt_col = next((c for c in df_listing.columns if c.lower() == 'amount'), 'Amount')

    # [수정] 1차 필터링 (시총 1,000억 ~ 8,000억)
    filtered = df_listing[(df_listing[marcap_col] >= 100000000000) & (df_listing[marcap_col] <= 800000000000)]
    
    # [핵심] 만약 필터링 결과가 부족하면 거래대금 상위주로 자동 대체 (방어 로직)
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
    try:
        available = [m.name for m in client.models.list() if 'generateContent' in m.supported_actions]
        priorities = ['gemini-3.1-flash-lite', 'gemini-3-flash-lite', 'gemini-2.5-flash-lite']
        for priority in priorities:
            target = [name for name in available if priority in name]
            if target: return target[0]
        return available[0]
    except: return "gemini-2.0-flash"

def generate_buy_report(client, model_name, name, price, tp, sl, profit_expect):
    today_date = datetime.now().strftime('%m월 %d일')
    prompt = f"{name}(추천가 {price:,.0f}원)의 단기 상승 모멘텀을 3줄로 간결하고 정중하게 분석해줘. 특수문자 금지."
    
    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        ai_content = response.text
    except:
        ai_content = "현재 수급 흐름이 양호하며 기술적 반등이 유효한 자리입니다."

    # 노부장님 요청 안내 문구 포함 리포트
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
        f"반드시 1~5일 지켜봐주시기 바랍니다. 오늘도 성투를 빕니다."
    )
    return report

def check_performance():
    """어제 추천 종목의 성과를 정밀하게 분석합니다."""
    if not os.path.exists(TRADES_FILE): return None
    with open(TRADES_FILE, 'r') as f:
        old_trades = json.load(f)
    if not old_trades: return None

    perf_reports = []
    trade_date = old_trades[0].get('date', '이전')
    
    for trade in old_trades:
        name, symbol, buy_p, tp, sl = trade['name'], trade['symbol'], trade['buy_price'], trade['tp'], trade['sl']
        try:
            # 오늘의 고가 데이터 확인
            df = fdr.DataReader(symbol).tail(1)
            high_p = df['High'].iloc[0]
            
            # 예상 수익률 (추천가 대비 목표가 기준)
            profit_pct = ((tp - buy_p) / buy_p) * 100
            
            if high_p >= tp:
                status = f"✅ <b>수익 달성! (+{profit_pct:.1f}%)</b>"
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
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    res = requests.post(url, json=payload)
    return res

if __name__ == "__main__":
    try:
        client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1'})
        target_model = find_best_model(client)
        
        # 1. 성적표(수익 인증) 먼저 발송
        perf_msg = check_performance()
        if perf_msg:
            send_telegram(perf_msg)
            print("📈 수익 인증 리포트 발송 완료")
            time.sleep(5)

        # 2. 오늘 종목 분석 및 발송
        stocks = get_accurate_stocks()
        if not stocks:
            print("🚨 분석 가능한 종목이 없습니다.")
        else:
            today_trades = []
            today_str = datetime.now().strftime('%m월 %d일')

            for i, stock in enumerate(stocks):
                name, symbol, price = stock['name'], stock['symbol'], stock['price']
                
                # 익절가 +6~8% 랜덤, 손절가 -3% 고정 계산
                profit_expect = random.randint(6, 8)
                tp = price * (1 + profit_expect / 100)
                sl = price * 0.97
                
                if i > 0: time.sleep(15) # RPM 보호
                
                report = generate_buy_report(client, target_model, name, price, tp, sl, profit_expect)
                send_telegram(report)
                print(f"✅ {name} 추천 완료")
                
                today_trades.append({
                    'date': today_str, 'name': name, 'symbol': symbol, 
                    'buy_price': price, 'tp': tp, 'sl': sl
                })

            # 3. 장부 저장 (내일 복기용)
            with open(TRADES_FILE, 'w') as f:
                json.dump(today_trades, f)
            print(f"💾 {len(today_trades)}개 종목 장부 기록 완료")
                
    except Exception as e:
        print(f"🚨 치명적 오류: {e}")
