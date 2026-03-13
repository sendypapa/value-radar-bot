import FinanceDataReader as fdr
import requests
import os
import json
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TRADES_FILE = "trades.json"

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    return requests.post(url, json=payload)

def run_performance_check():
    if not os.path.exists(TRADES_FILE):
        print("📝 장부가 없습니다. 복기를 건너뜁니다.")
        return

    with open(TRADES_FILE, 'r') as f:
        trades = json.load(f)
    if not trades: return

    trade_date = trades[0].get('date', '이전')
    report = f"📢 <b>{trade_date} 매매 결과 리포트</b>\n------------------------\n"
    
    success_count = 0
    for trade in trades:
        name, symbol, buy_p, tp, sl = trade['name'], trade['symbol'], trade['buy_price'], trade['tp'], trade['sl']
        try:
            # 당일 고가 확인
            df = fdr.DataReader(symbol).tail(1)
            high_p = df['High'].iloc[0]
            
            # 수익률 계산 (추천가 대비 목표가 기준)
            expected_profit = ((tp - buy_p) / buy_p) * 100
            
            if high_p >= tp:
                status = f"✅ <b>축하합니다 수익 달성! (+{expected_profit:.1f}%)</b>"
                success_count += 1
            elif high_p <= sl:
                status = "❌ <b>손절 처리</b>"
            else:
                status = "⏳ <b>관망 (보유 중)</b>"

            report += (
                f"<b>종목명 : {name}</b>\n"
                f"매수추천가 : {buy_p:,.0f}원\n"
                f"조건부매매 : 익절 {tp:,.0f} / 손절 {sl:,.0f}\n"
                f"장중 최고가 : {high_p:,.0f}원\n"
                f"결과 : {status}\n\n"
            )
        except: continue

    if success_count > 0:
        report += f"🎉 오늘 총 {success_count}개 종목이 목표가에 도달했습니다!"
    
    send_telegram(report)
    print("✅ 수익 인증 리포트 전송 완료")

if __name__ == "__main__":
    run_performance_check()
