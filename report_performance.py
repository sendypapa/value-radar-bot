import FinanceDataReader as fdr
import requests
import os
import json
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TRADES_FILE = "trades.json"
PERFORMANCE_FILE = "performance_history.json"


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code != 200:
            print("🚨 텔레그램 전송 실패:", r.text)
    except Exception as e:
        print("🚨 텔레그램 전송 실패:", e)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def load_trades():
    return load_json(TRADES_FILE, [])


def load_performance_history():
    return load_json(PERFORMANCE_FILE, [])


def save_performance_history(data):
    save_json(PERFORMANCE_FILE, data)


def parse_trade_date(date_str):
    try:
        today = datetime.now()
        d = datetime.strptime(date_str, "%m월 %d일")
        return d.replace(year=today.year)
    except:
        return None


def get_latest_trade_date(trades):
    dates = []
    for t in trades:
        d = parse_trade_date(t.get("date", ""))
        if d:
            dates.append(d)
    return max(dates) if dates else None


_market_cache = {}

def get_market_data(symbol):
    if symbol in _market_cache:
        return _market_cache[symbol]

    try:
        df = fdr.DataReader(symbol).tail(1)
        if df.empty:
            return None

        row = df.iloc[-1]
        data = {
            "high": float(row["High"]),
            "low": float(row["Low"])
        }
        _market_cache[symbol] = data
        return data
    except:
        return None


def calculate_month_stats(history):
    current_month = datetime.now().strftime("%m")
    monthly = [x for x in history if x.get("date", "").startswith(current_month)]

    profits = [float(x.get("profit", 0)) for x in monthly]

    avg_profit = sum(profits) / len(profits) if profits else 0
    total_profit = sum(profits) if profits else 0
    success_count = len(monthly)

    return avg_profit, total_profit, success_count


def merge_today_results(history, today_results):
    existing_keys = {
        (x.get("date"), x.get("symbol"), round(float(x.get("profit", 0)), 1))
        for x in history
    }

    for item in today_results:
        key = (item.get("date"), item.get("symbol"), round(float(item.get("profit", 0)), 1))
        if key not in existing_keys:
            history.append(item)

    return history


def run_performance_check():
    trades = load_trades()

    if not trades:
        print("📝 장부 데이터 없음")
        return

    today = datetime.now().strftime("%m월 %d일")
    header = f"📢 <b>{today} 매매 결과 리포트</b>\n------------------------\n"

    latest_trade_date = get_latest_trade_date(trades)
    if not latest_trade_date:
        print("📝 유효한 추천 날짜 없음")
        return

    latest_trade_str = latest_trade_date.strftime("%m월 %d일")

    # 본문은 직전 추천일 종목만
    target_trades = [t for t in trades if t.get("date") == latest_trade_str]

    report_body = ""
    success_count = 0
    today_results = []

    for trade in target_trades:
        name = trade.get("name")
        symbol = trade.get("symbol")
        buy_p = trade.get("buy_price") or trade.get("buy")
        tp = trade.get("tp")
        sl = trade.get("sl")

        if not all([name, symbol, buy_p, tp, sl]):
            continue

        market = get_market_data(symbol)
        if not market:
            continue

        high_p = market["high"]
        low_p = market["low"]

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

            today_results.append({
                "date": today,
                "name": name,
                "symbol": symbol,
                "profit": round(expected_profit, 1)
            })

    if success_count > 0:
        history = load_performance_history()
        history = merge_today_results(history, today_results)
        save_performance_history(history)

        avg_profit, total_profit, month_success = calculate_month_stats(history)

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


if __name__ == "__main__":
    run_performance_check()
