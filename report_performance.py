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

    try:
        with open(TRADES_FILE, 'r', encoding='utf-8') as f:
            trades = json.load(f)
    except:
        print("🚨 장부 파일 읽기 실패.")
        return

    if not trades: return

    trade_date = trades[0].get('date', '이전')
    
    # 기존과 동일한 헤더 폼
    header = f"📢 <b>{trade_date} 매매 결과 리포트</b>\n------------------------\n"
    report_body = ""
    success_count = 0

    for trade in trades:
        name, symbol, buy_p, tp, sl = trade['name'], trade['symbol'], trade['buy_price'], trade['tp'], trade['sl']
        try:
            # 당일 고가 확인
            df = fdr.DataReader(symbol).tail(1)
            high_p = df['High'].iloc[0]
            
            # [핵심] 익절가(tp)에 도달한 경우만 기존 폼 그대로 리포트에 추가
            if high_p >= tp:
                expected_profit = ((tp - buy_p) / buy_p) * 100
                success_count += 1
                
                # 기존 메시지 폼과 100% 동일하게 구성
                report_body += (
                    f"<b>종목명 : {name}</b>\n"
                    f"매수추천가 : {buy_p:,.0f}원\n"
                    f"조건부매매 : 익절 {tp:,.0f} / 손절 {sl:,.0f}\n"
                    f"장중 최고가 : {high_p:,.0f}원\n"
                    f"결과 : ✅ <b>축하합니다 수익 달성! (+{expected_profit:.1f}%)</b>\n\n"
                )
            else:
                # 손절이나 관망은 리포트에 넣지 않고 패스합니다.
                continue
        except: continue

    # 수익 달성 종목이 하나라도 있을 때만 메시지 발송
    if success_count > 0:
        # 기존 폼: 헤더 + 바디 + 푸터
        final_report = header + report_body + f"🎉 오늘 총 {success_count}개 종목이 목표가에 도달했습니다!"
        send_telegram(final_report)
        print(f"✅ 수익 인증 리포트 전송 완료 ({success_count}건)")
    else:
        print("⏳ 오늘은 목표가에 도달한 수익 종목이 없어 메시지를 보내지 않습니다.")

if __name__ == "__main__":
    run_performance_check()
