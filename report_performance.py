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
    
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        print("텔레그램 전송 실패")


def calculate_month_stats(trades):

    current_month = datetime.now().strftime("%m")

    profits = []
    success_count = 0

    for trade in trades:

        date = trade.get("date", "")

        if current_month not in date:
            continue

        buy = trade.get("buy_price") or trade.get("buy")
        tp = trade.get("tp")

        if buy and tp:

            profit = ((tp - buy) / buy) * 100

            profits.append(profit)
            success_count += 1

    avg_profit = sum(profits) / len(profits) if profits else 0
    total_profit = sum(profits) if profits else 0

    return avg_profit, total_profit, success_count


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

    if not trades:
        return

    trade_date = trades[0].get('date', '이전')

    header = f"📢 <b>{trade_date} 매매 결과 리포트</b>\n------------------------\n"

    report_body = ""
    success_count = 0

    for trade in trades:

        name = trade['name']
        symbol = trade['symbol']
        buy_p = trade['buy_price']
        tp = trade['tp']
        sl = trade['sl']

        try:

            df = fdr.DataReader(symbol).tail(1)

            high_p = df['High'].iloc[0]
            low_p = df['Low'].iloc[0]

            if high_p >= tp and low_p > sl:

                expected_profit = ((tp - buy_p) / buy_p) * 100

                success_count += 1

                report_body += (
                    f"<b>종목명 : {name}</b>\n"
                    f"매수추천가 : {buy_p:,.0f}원\n"
                    f"조건부매매 : 익절 {tp:,.0f} / 손절 {sl:,.0f}\n"
                    f"장중 최고가 : {high_p:,.0f}원\n"
                    f"결과 : ✅ <b>축하합니다 수익 달성! (+{expected_profit:.1f}%)</b>\n\n"
                )

        except:
            continue

    if success_count > 0:

        avg_profit, total_profit, month_success = calculate_month_stats(trades)

        summary = (
            "\n━━━━━━━━━━━━━━\n"
            f"📊 이달 평균 익절 수익률\n"
            f"<b>+{avg_profit:.1f}%</b>\n\n"
            f"📈 이달 누적 익절 수익률\n"
            f"<b>+{total_profit:.1f}%</b>\n\n"
            f"🏆 이달 익절 성공\n"
            f"<b>{month_success}종목</b>\n"
            "━━━━━━━━━━━━━━"
        )

        final_report = (
            header
            + report_body
            + f"🎉 오늘 총 {success_count}개 종목이 목표가에 도달했습니다!"
            + summary
        )

        send_telegram(final_report)

        print(f"✅ 수익 인증 리포트 전송 완료 ({success_count}건)")

    else:

        print("⏳ 오늘은 확실하게 목표가에 도달한 수익 종목이 없어 메시지를 보내지 않습니다.")


if __name__ == "__main__":
    run_performance_check()
