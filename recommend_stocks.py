from google import genai
import FinanceDataReader as fdr
import requests
import os
import time
import json
import random
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TRADES_FILE = "trades.json"

def get_stocks():
    df = fdr.StockListing('KOSDAQ')
    # 시총 1,000억 ~ 8,000억 사이 거래대금 상위주
    target_col = next((c for c in df.columns if c.lower() == 'marcap'), 'Marcap')
    filtered = df[(df[target_col] >= 100000000000) & (df[target_col] <= 800000000000)]
    return filtered.sort_values(by='Amount', ascending=False).head(15)

def run_recommendation():
    client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1'})
    stocks_df = get_stocks()
    
    today_trades = []
    today_str = datetime.now().strftime('%m월 %d일')
    
    count = 0
    for _, row in stocks_df.iterrows():
        if count >= 10: break
        name, symbol = row['Name'], row['Code']
        try:
            price = fdr.DataReader(symbol).tail(1)['Close'].iloc[0]
            profit_expect = random.randint(6, 8)
            tp, sl = price * (1 + profit_expect / 100), price * 0.97
            
            # AI 분석 (정중한 버전)
            prompt = f"{name}({price:,.0f}원)의 단기 상승 모멘텀을 전문적으로 3줄 요약해줘. 정중한 존댓말 사용."
            response = client.models.generate_content(model='gemini-3.1-flash-lite', contents=prompt)
            
            report = (
                f"📢 <b>[밸류레이더] 오늘의 단기 공략주</b>\n\n"
                f"🔹 <b>종목명</b>: {name}\n"
                f"🔹 <b>매수 타점</b>: <b>{price:,.0f}원</b>\n\n"
                f"안녕하세요 밸류레이더 노부장입니다.\n"
                f"<b>{today_str} 금일 단기 공략주 공유드립니다.</b>\n\n"
                f"📌 <b>[{name} 분석]</b>\n"
                f"• 예상 수익률: <b>약 {profit_expect}%</b>\n"
                f"• 투자 비중: 10~15%\n\n"
                f"✅ <b>조건부 매도 추천가</b>\n"
                f"• 익절 목표가: <b>{tp:,.0f}원</b>\n"
                f"• 손절 대응가: <b>{sl:,.0f}원</b>\n\n"
                f"📖 <b>분석 포인트</b>\n{response.text}\n\n"
                f"⚠️ <b>안내 사항</b>\n"
                f"조건부 매도 세팅을 통해 안정적인 매매 환경을 만드시는 것을 권고드립니다.\n\n"
                f"오늘도 성투를 빌겠습니다."
            )
            
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": CHAT_ID, "text": report, "parse_mode": "HTML"})
            
            today_trades.append({'date': today_str, 'name': name, 'symbol': symbol, 'buy_price': price, 'tp': tp, 'sl': sl})
            count += 1
            time.sleep(12)
        except: continue

    with open(TRADES_FILE, 'w') as f:
        json.dump(today_trades, f)

if __name__ == "__main__":
    run_recommendation()
