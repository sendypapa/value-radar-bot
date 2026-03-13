import FinanceDataReader as fdr
import requests
import os
import json
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TRADES_FILE = "trades.json"


# ==========================
# 텔레그램 전송
# ==========================
def send_telegram(text):

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        requests.post(url, json=payload, timeout=10)
    except:
        print("🚨 텔레그램 전송 실패")


# ==========================
# 장부 로드
# ==========================
def load_trades():

    if not os.path.exists(TRADES_FILE):
        return []

    try:
        with open(TRADES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        print("🚨 장부 파일 읽기 실패")
        return []


# ==========================
# 오늘 가격 데이터 조회
# ==========================
def load_market_data(symbols):

    market = {}

    for s in symbols:

        try:

            df = fdr.DataReader(s).tail(1)

            if not df.empty:

                market[s] = {
                    "high": df["High"].iloc[0],
                    "low": df["Low"].iloc[0]
                }

        except:
            continue

    return market


# ==========================
# 월간 성과 계산
# ==========================
def calculate_month_stats(trades, market):

    current_month = datetime.now().strftime("%m")

    profits = []
    success_count = 0

    for trade in trades:

        date = trade.get("date", "")

        if not date.startswith(current_month):
            continue

        symbol = trade.get("symbol")

        if symbol not in market:
            continue

        buy = trade.get("buy_price")
        tp = trade.get("tp")
        sl = trade.get("sl")

        if not all([buy, tp, sl]):
            continue

        high = market[symbol]["high"]
        low = market[symbol]["low"]

        if high >= tp and low > sl:

            profit = ((tp - buy) / buy) * 100

            profits.append(profit)
            success_count += 1

    avg_profit = sum(profits) / len(profits) if profits else 0
    total_profit = sum(profits) if profits else 0

    return avg_profit, total_profit, success_count


# ==========================
# 성과 리포트
# ==========================
def run_performance_check():

    trades = load_trades()

    if not trades:
        print("📝 장부 데이터 없음")
        return

    today = datetime.now().strftime("%m월 %d일")

    header = f"📢 <b>{today} 매매 결과 리포트</b>\n------------------------\n"

    symbols = list({t["symbol"] for t in trades if "symbol" in t})

    market = load_market_data(symbols)

    report_body = ""
    success_count = 0

    for trade in trades:

        name = trade.get("name")
        symbol = trade.get("symbol")

        if symbol not in market:
            continue

        buy_p = trade.get("buy_price")
        tp = trade.get("tp")
        sl = trade.get("sl")

        if not all([name, buy_p, tp, sl]):
            continue

        high_p = market[symbol]["high"]
        low_p = market[symbol]["low"]

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

    if success_count > 0:

        avg_profit, total_profit, month_success = calculate_month_stats(trades, market)

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
            + f"🎉 오늘 총 {success_count}개 종목이 목표가에 도달했습니다!\n"
            + summary
        )

        send_telegram(final_report)

        print(f"✅ 수익 인증 리포트 전송 완료 ({success_count}건)")

    else:

        print("⏳ 오늘은 목표가 달성 종목이 없습니다.")


# ==========================
# 실행
# ==========================
if __name__ == "__main__":
    run_performance_check()
