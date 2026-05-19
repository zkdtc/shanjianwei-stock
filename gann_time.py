"""
gann_time.py
江恩时间窗口 + 财报日历
- 财报日期（用yfinance的calendar/earnings_dates）
- 江恩重要时间周期：30/45/60/90/120/180天循环
- 距财报天数和操作建议
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, date
import json
import os


# ─────────────────────────────────────────────
#  财报日期
# ─────────────────────────────────────────────

def get_next_earnings(ticker: str) -> dict:
    """获取下一次财报日期。返回 {date, days_until, time_of_day}"""
    try:
        t = yf.Ticker(ticker)

        # 优先用 calendar
        cal = t.calendar
        earnings_date = None
        if cal is not None:
            if isinstance(cal, dict):
                # newer yfinance returns dict
                ed = cal.get("Earnings Date")
                if ed:
                    if isinstance(ed, (list, tuple)):
                        earnings_date = ed[0] if ed else None
                    else:
                        earnings_date = ed
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                if "Earnings Date" in cal.index:
                    val = cal.loc["Earnings Date"].values[0]
                    earnings_date = val

        # fallback: earnings_dates
        if not earnings_date:
            try:
                ed_df = t.earnings_dates
                if ed_df is not None and not ed_df.empty:
                    # 找下一个未来日期
                    now = pd.Timestamp.now(tz=ed_df.index.tz)
                    future = ed_df[ed_df.index > now]
                    if not future.empty:
                        earnings_date = future.index.min().to_pydatetime()
            except Exception:
                pass

        if not earnings_date:
            return {"error": "无可用财报日期"}

        # 标准化日期
        if isinstance(earnings_date, pd.Timestamp):
            earnings_date = earnings_date.to_pydatetime()
        if isinstance(earnings_date, datetime):
            ed_date = earnings_date.date()
        elif isinstance(earnings_date, date):
            ed_date = earnings_date
        else:
            ed_date = pd.Timestamp(earnings_date).date()

        days_until = (ed_date - date.today()).days

        return {
            "date": ed_date.strftime("%Y-%m-%d"),
            "weekday": ed_date.strftime("%A"),
            "days_until": days_until,
            "is_past": days_until < 0,
        }
    except Exception as e:
        return {"error": f"获取失败: {e}"}


def earnings_window_advice(days_until: int) -> dict:
    """根据距财报天数给出操作建议"""
    if days_until is None:
        return {"phase": "—", "advice": "无财报数据", "color": "🟡"}
    if days_until < 0:
        return {
            "phase": "财报已过",
            "advice": f"财报已过{-days_until}天，关注后续走势",
            "color": "⚪",
        }
    if days_until == 0:
        return {
            "phase": "🚨 财报日",
            "advice": "盘后/盘前财报，建议提前减仓至少50%或买保护性Put",
            "color": "🔴",
        }
    if days_until <= 3:
        return {
            "phase": "财报前 (≤3天)",
            "advice": "极高IV风险期。若持仓，提前减仓1/3-1/2；若空仓，不要追入",
            "color": "🔴",
        }
    if days_until <= 7:
        return {
            "phase": "财报前 (≤7天)",
            "advice": "IV开始急速上升，期权变贵。波段仓位应该开始降低",
            "color": "🟠",
        }
    if days_until <= 14:
        return {
            "phase": "财报前 (≤14天)",
            "advice": "进入财报敏感期，注意机构调仓动作（量价异动）",
            "color": "🟡",
        }
    if days_until <= 30:
        return {
            "phase": "财报前 (≤30天)",
            "advice": "正常波动期。可以正常操作，关注盘面预期变化",
            "color": "🟢",
        }
    return {
        "phase": f"财报前 ({days_until}天)",
        "advice": "距离财报较远，正常操作",
        "color": "🟢",
    }


# ─────────────────────────────────────────────
#  江恩时间循环
# ─────────────────────────────────────────────

GANN_CYCLES = [
    (30, "30天小循环"),
    (45, "45天江恩转折"),
    (60, "60天中循环"),
    (90, "90天季度循环（重要）"),
    (120, "120天江恩中周期"),
    (144, "144天江恩主循环"),
    (180, "180天半年循环（重要）"),
    (270, "270天循环"),
    (360, "360天年度循环（重要）"),
]


def find_anchor_date(ticker: str, period: str = "2y") -> dict:
    """
    寻找近期最重要的锚点日期：
    - 最近的52周高点
    - 最近的52周低点
    - 最近的明显放量异动日
    """
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period)
        if df.empty:
            return {}

        # 52周高点和低点（精确日期）
        high_idx = df["High"].idxmax()
        low_idx = df["Low"].idxmin()

        # 最近放量日（成交量为均量2x以上）
        vol_ma = df["Volume"].rolling(20).mean()
        spike = df[df["Volume"] > vol_ma * 2.0]
        recent_spike = spike.index.max() if not spike.empty else None

        return {
            "52w_high_date": high_idx.date(),
            "52w_high_price": float(df.loc[high_idx, "High"]),
            "52w_low_date": low_idx.date(),
            "52w_low_price": float(df.loc[low_idx, "Low"]),
            "recent_spike_date": recent_spike.date() if recent_spike is not None else None,
        }
    except Exception:
        return {}


def gann_time_windows(anchor_date: date, lookback_days: int = 30, lookforward_days: int = 90) -> list:
    """从锚点日期计算未来江恩时间窗口"""
    if not anchor_date:
        return []

    today = date.today()
    out = []
    for days, label in GANN_CYCLES:
        target = anchor_date + timedelta(days=days)
        days_from_today = (target - today).days
        if -lookback_days <= days_from_today <= lookforward_days:
            out.append({
                "anchor_date": anchor_date.strftime("%Y-%m-%d"),
                "cycle": label,
                "cycle_days": days,
                "target_date": target.strftime("%Y-%m-%d"),
                "days_from_today": days_from_today,
                "is_past": days_from_today < 0,
                "is_imminent": -2 <= days_from_today <= 7,
            })
    return out


def compile_time_axis(ticker: str) -> dict:
    """编译完整时间轴：财报 + 锚点 + 江恩时间窗口"""
    earnings = get_next_earnings(ticker)
    earnings_advice = earnings_window_advice(earnings.get("days_until"))

    anchors = find_anchor_date(ticker)

    windows = []
    if anchors.get("52w_high_date"):
        for w in gann_time_windows(anchors["52w_high_date"]):
            w["anchor_type"] = f"52周高点 (${anchors['52w_high_price']:.2f})"
            windows.append(w)
    if anchors.get("52w_low_date"):
        for w in gann_time_windows(anchors["52w_low_date"]):
            w["anchor_type"] = f"52周低点 (${anchors['52w_low_price']:.2f})"
            windows.append(w)
    if anchors.get("recent_spike_date"):
        for w in gann_time_windows(anchors["recent_spike_date"]):
            w["anchor_type"] = "近期放量异动日"
            windows.append(w)

    # 按距今天数排序
    windows.sort(key=lambda x: abs(x["days_from_today"]))

    # 找最近的关键窗口
    upcoming = [w for w in windows if 0 <= w["days_from_today"] <= 30]
    upcoming.sort(key=lambda x: x["days_from_today"])

    return {
        "ticker": ticker,
        "earnings": earnings,
        "earnings_advice": earnings_advice,
        "anchors": anchors,
        "all_windows": windows,
        "upcoming_windows": upcoming[:5],  # 接下来5个最近的窗口
        "compiled_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def compile_all_time_axis(watchlist_path: str = "watchlist.json") -> list:
    """编译watchlist里所有股票的时间轴"""
    with open(watchlist_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []
    for s in data["stocks"]:
        try:
            ta = compile_time_axis(s["ticker"])
            ta["name"] = s.get("name", s["ticker"])
            results.append(ta)
        except Exception as e:
            results.append({
                "ticker": s["ticker"],
                "name": s.get("name", s["ticker"]),
                "error": str(e),
            })
    return results
