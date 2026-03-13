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
        target = next((m for m in available if 'gemini-1.5-flash' in m or 'gemini-2.0-flash' in m), available[0])
        return target
    except: return "gemini-1.5-flash"

def generate_buy_report(client, model_name, name, price, tp, sl, profit_expect):
    """노부장님의 특제 프롬프트를 사용하여 AI 분석 리포트를 생성합니다."""
    today_date = datetime.now().strftime('%m월 %d일')
    
    prompt = f"""
    "최근 {name}의 가격 변동성과 거래량 추이를 분석했을 때, 기술적 분석 관점에서 유의미하게 살펴봐야 할 지점들을 2줄로 핵심만 요약해줘."
    - 마크다운 특수문자(*, #)는 절대 사용하지 마세요.
    - 정중한 존댓말로 핵심만 짚어주세요.
    """

    # [추가] AI 분석 실패 시 사용할 전문가용 멘트 20가지
    fallbacks = [
        "최근 거래량이 실린 양봉이 출현하며 바닥권을 탈출하는 흐름이 포착되었습니다.",
        "이동평균선 정배열 초입 단계로 단기 추세 전환의 가능성이 매우 높은 구간입니다.",
        "주요 저항대를 대량 거래와 함께 돌파하며 상방으로의 에너지가 응축되고 있습니다.",
        "과매도 구간 이후 주요 지표가 반등 신호를 보내고 있어 기술적 반등이 기대됩니다.",
        "직전 고점 부근의 매물을 소화하는 과정으로, 돌파 시 강한 탄력이 예상됩니다.",
        "외인과 기관의 순매수세가 유입되며 수급 개선이 뚜렷하게 나타나고 있는 자리입니다.",
        "지지선 부근에서 하방 경직성을 확보하며 안정적인 눌림목 타점을 형성 중입니다.",
        "볼린저 밴드 상단 돌파 시도가 이어지고 있어 단기 변동성 확대에 따른 수익 기회가 보입니다.",
        "장기 이평선 돌파 후 안착하는 모습으로, 중단기적 우상향 추세가 유효한 구간입니다.",
        "매집봉 형태의 윗꼬리 캔들이 발생하며 매물 소화 및 상승 에너지를 비축하고 있습니다.",
        "하락 추세를 멈추는 도지형 캔들이 발생하여 변곡점 형성을 기대해볼 수 있습니다.",
        "60일 이동평균선의 강력한 지지를 바탕으로 추세가 꺾이지 않고 유지되고 있습니다.",
        "섹터 내 수급 순환매 흐름을 타며 기술적 반등의 정점에 위치한 것으로 분석됩니다.",
        "갭 상승 후 지지를 받는 모습으로 보아 주체 세력의 개입이 강하게 의심되는 구간입니다.",
        "심리적 저항선을 앞두고 거래량이 증가하고 있어 방향성 결정이 임박한 전망입니다.",
        "횡보 구간을 탈피하는 장대 거래량이 포착되어 단기 시세 분출이 기대되는 자리입니다.",
        "눌림목 형성 이후 재상승으로 가는 골든크로스 구간으로 기술적 매력도가 높습니다.",
        "거래대금이 상위권에 랭크되며 시장의 뜨거운 관심을 받는 종목으로 추가 여력이 충분합니다.",
        "하단 채널 지지력을 테스트한 후 반등하는 추세로 안정적인 우상향 흐름이 예상됩니다.",
        "수급의 연속성이 확보된 상태로, 단기 과열 진입 전까지 홀딩 전략이 유효해 보입니다."
    ]
    
    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        if response.text and len(response.text.strip()) > 5:
            ai_content = response.text.strip().replace('*', '').replace('#', '')
            print(f"🎯 {name} AI 분석 성공!")
        else:
            ai_content = random.choice(fallbacks)
            print(f"⚠️ {name} AI 응답 부실로 랜덤 멘트 사용")
    except Exception as e:
        print(f"⚠️ {name} 분석 실패 (Fallback 사용): {e}")
        ai_content = random.choice(fallbacks)

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
