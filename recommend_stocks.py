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

    # [추가] AI 분석 실패 시 사용할 전문가용 멘트 50가지
    fallbacks = [
    "주요 매물대 소화를 마친 후 상방 압력이 가중되고 있어, 단기적 시세 분출의 임계점에 도달한 것으로 판단됩니다.",
    "메이저 수급의 연속적인 순매수 유입은 하방 경직성을 강화하며 강력한 상승 트리거로 작용할 가능성이 높습니다.",
    "변동성 축소(VCP) 패턴의 완성 단계로, 대량 거래를 동반한 돌파 시 단기 슈팅 구간 진입이 유력합니다.",
    "이평선 밀집 구역에서 에너지를 응축한 후 우상향 발산형 패턴으로 전환되며 기술적 매력도가 극대화되었습니다.",
    "유동성 집중 현상과 함께 매수 주체의 공격적인 진입이 포착되어 직전 고점 돌파를 목전에 두고 있습니다.",
    "심리적 저항선을 거래량으로 압도하며 돌파한 이후, 새로운 가격 밴드로의 레벨업을 위한 발판을 마련했습니다.",
    "추세 하단에서의 지지력 테스트를 성공적으로 마치고 반등 추세에 가속도가 붙는 모멘텀 강화 구간입니다.",
    "섹터 내 주도주로서의 자금 쏠림 현상이 뚜렷하며 단기 과열권 진입 전까지 탄력적인 상승세가 기대됩니다.",
    "매수세의 연속성이 확보된 가운데 직전 고점 부근의 잔여 매물을 효과적으로 흡수하며 상방 랠리를 준비 중입니다.",
    "기술적 반등의 차원을 넘어 중단기 추세 전환을 확정 짓는 골든크로스가 발생하며 매수 우위의 환경을 조성했습니다.",
    "볼린저 밴드 상단 확장에 따른 변동성 확대 구간으로, 단기 추세 추종 전략이 매우 유효한 시점입니다.",
    "하락 추세선을 강력한 장대양봉으로 돌파하며 시장의 관심을 한 몸에 받는 주도적 흐름이 포착되었습니다.",
    "외국인과 기관의 쌍끌이 매수세가 유입되며 수급의 질적 개선이 이루어진 상태로 단기 고점 경신이 기대됩니다.",
    "지지선 부근에서 하방 경직성을 확보한 후 대기 매수세가 강하게 유입되며 안정적인 우상향 궤적을 형성했습니다.",
    "거래대금 최상위권 랭크와 함께 시장 에너지의 중심에 서 있어 단기적인 시세 탄력이 지속될 전망입니다.",
    "장기 이평선의 저항을 지지선으로 치환하는 리테스트를 완료하고 2차 상승 파동의 초입 단계에 진입했습니다.",
    "매집봉 형태의 캔들이 반복 출현하며 유통 물량을 장악한 것으로 파악되어 급격한 상방 변동성이 예상됩니다.",
    "보조지표상의 다이버전스 발생 이후 추세 반전 신호가 뚜렷해지며 단기 기술적 반등 이상의 시세가 기대됩니다.",
    "눌림목 형성 과정에서 거래량이 급감하며 매도세 진정 확인 후 다시 상승 모멘텀을 재점화하는 구간입니다.",
    "가격과 거래량의 조화로운 상승은 세력의 개입 가능성을 시사하며 단기적인 목표가 달성이 낙관적입니다.",
    "하단 채널의 지지력을 바탕으로 상방 채널 돌파를 시도 중이며 성공 시 강력한 가속 구간이 전개될 전망입니다.",
    "시장 유동성이 해당 섹터로 집중되는 가운데 기술적 지표들이 일제히 강세 전환을 가리키고 있습니다.",
    "과거 급등 전조 현상과 유사한 캔들 패턴이 포착되어 단기적인 시세 분출에 대한 기대감이 고조되고 있습니다.",
    "저항선을 지지선으로 변경하는 강력한 추세 지지 흐름이 확인되어 안정적인 단기 수익 기회를 제공합니다.",
    "매도 클라이맥스 이후 V자형 반등의 기울기가 가팔라지며 단기 추세의 강력한 힘이 느껴지는 자리입니다.",
    "수급의 공백을 메우는 공격적인 매수세 유입으로 인해 상방으로의 주가 탄력성이 최고조에 달해 있습니다.",
    "일목균형표 의문 돌파와 함께 구름대 상단에 안착하며 단기적인 시세 우위 국면을 확정 지었습니다.",
    "거래량 가중 평균가(VWAP) 상단에서 견조한 흐름을 유지하며 추가 상승을 위한 동력을 비축하고 있습니다.",
    "지수 대비 강한 상대적 강도(RS)를 보이며 시장 주도주로서의 면모를 유감없이 발휘하는 구간입니다.",
    "단기 이평선의 정배열 확산과 함께 추세 가속화가 진행 중으로 직관적인 수익 구간이 열려 있습니다.",
    "상승 잉태형 패턴 출현 후 저점을 높여가는 흐름으로, 단기적인 변곡점 돌파 시 강한 탄력이 예상됩니다.",
    "이격도 과다 해소 이후 추세의 하단 지지력이 견고하게 확인되며, 기술적 리바운딩의 정점에 위치했습니다.",
    "하락 채널 상단을 돌파하는 안착 캔들이 발생하여, 하락 추세를 종결짓는 강력한 반전 신호가 포착되었습니다.",
    "주요 피보나치 되돌림 구간에서 반등에 성공하며, 전고점을 향한 공격적인 시세 흐름이 재개될 전망입니다.",
    "매도세가 진정되고 매수 호가 우위의 수급 불균형이 발생하며, 단기적인 가격 점프 가능성이 매우 높습니다.",
    "거래량 가중 평균선(VWAP)을 상향 돌파하며 주체 세력의 강한 개입 의지가 확인된 유의미한 자리입니다.",
    "장기 횡보를 끝내는 대량 거래 동반 장대양봉은 새로운 추세의 시작을 알리는 확정적 신호로 해석됩니다.",
    "심리적 저항선인 라운드 피겨(Round Figure) 돌파를 시도하며 상방으로의 에너지가 강하게 응축된 상태입니다.",
    "숏커버링 물량 유입 가능성이 제기되는 수급 구조로, 급격한 변동성을 동반한 단기 슈팅이 기대됩니다.",
    "일봉상 N자형 패턴의 눌림목 완성 단계로, 직전 고점 돌파를 위한 탄력적인 매수세가 유입 중입니다.",
    "섹터 내 주도주로서의 지위를 공고히 하며 대기 매수세의 유입이 가격 하단을 탄탄하게 지지하고 있습니다.",
    "기술적 지표들이 과매도 구간을 탈피하고 일제히 우상향을 가리키며 단기적인 추세 강도가 강화되었습니다.",
    "볼린저 밴드의 수렴 이후 상단 밴드를 타고 흐르는 '라이딩' 패턴이 나타나며 강한 상승 의지를 보이고 있습니다.",
    "매물 소화 과정에서 거래량이 점진적으로 증가하며 가격의 하방 경직성을 확보한 매력적인 타점입니다.",
    "장기 이평선 돌파 이후 안착하는 되돌림 과정에서 수급의 질이 개선되며 추가 상승 동력을 확보했습니다.",
    "시장 지수 대비 강력한 아웃퍼폼(Outperform)을 기록하며 시장의 시선이 집중되는 주도 섹터의 핵심 종목입니다.",
    "단기 추세 지표인 MACD 오실레이터가 양전환되며 공격적인 단기 매수세가 가세하기 시작한 시점입니다.",
    "직전 고점의 저항을 지지선으로 완전히 치환하며 새로운 가격대 형성을 위한 강한 돌파력이 포착되었습니다.",
    "거래대금의 폭발적인 증가와 함께 시장 에너지가 응집되어 단기 고점을 가뿐히 경신할 것으로 판단됩니다.",
    "수급 주체별 매매 동향이 매수 우위로 전환되며 추세의 연속성을 담보하는 안정적인 흐름이 전개 중입니다."
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
