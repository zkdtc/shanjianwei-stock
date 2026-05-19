"""
gann_sq9.py
江恩九宫图（Square of 9）+ 时间共振分析
- Square of 9 价格目标位（从底部向上 / 从顶部向下）
- 50%/62.5% 黄金回调位
- 时间循环：7/14/21/30/45/60/90/120/144/180 天
- 价格-时间共振点
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import math


# ─────────────────────────────────────────────
#  寻找重要高点/低点
# ─────────────────────────────────────────────

def find_swing_points(ticker: str, period: str = "2y") -> dict:
    """寻找近期重要的swing high/low"""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist.empty:
            return {}

        # 全周期最高/最低
        all_high_idx = hist["High"].idxmax()
        all_low_idx = hist["Low"].idxmin()

        # 近6个月低点（找近期大底）
        recent_6m = hist.tail(126)
        recent_low_idx = recent_6m["Low"].idxmin()
        recent_high_idx = recent_6m["High"].idxmax()

        # 当前价
        current_price = float(hist["Close"].iloc[-1])

        return {
            "current_price": round(current_price, 2),
            "all_time_high": round(float(hist.loc[all_high_idx, "High"]), 2),
            "all_time_high_date": all_high_idx.date(),
            "all_time_low": round(float(hist.loc[all_low_idx, "Low"]), 2),
            "all_time_low_date": all_low_idx.date(),
            "recent_high": round(float(hist.loc[recent_high_idx, "High"]), 2),
            "recent_high_date": recent_high_idx.date(),
            "recent_low": round(float(hist.loc[recent_low_idx, "Low"]), 2),
            "recent_low_date": recent_low_idx.date(),
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
#  江恩九宫图 (Square of 9)
# ─────────────────────────────────────────────

def gann_sq9_from_bottom(bottom_price: float, n_rotations: int = 8) -> list:
    """
    从底部向上，每旋转45度（=0.125）计算目标位。
    一个完整圈=360度=1.0
    """
    if bottom_price <= 0:
        return []
    sqrt_base = math.sqrt(bottom_price)
    targets = []
    for r in range(1, n_rotations * 8 + 1):  # 每0.125一档
        delta = r * 0.125
        target = (sqrt_base + delta) ** 2
        degrees = r * 45
        rotations = degrees / 360
        targets.append({
            "degrees": degrees,
            "rotations": round(rotations, 3),
            "delta_sqrt": round(delta, 3),
            "target": round(target, 2),
            "gain_pct": round((target - bottom_price) / bottom_price * 100, 1),
        })
    return targets


def gann_sq9_from_top(top_price: float, n_rotations: int = 8) -> list:
    """从顶部向下，每回撤45度计算支撑位"""
    if top_price <= 0:
        return []
    sqrt_base = math.sqrt(top_price)
    supports = []
    for r in range(1, n_rotations * 8 + 1):
        delta = r * 0.125
        if sqrt_base - delta <= 0:
            break
        target = (sqrt_base - delta) ** 2
        degrees = r * 45
        rotations = degrees / 360
        supports.append({
            "degrees": degrees,
            "rotations": round(rotations, 3),
            "delta_sqrt": round(delta, 3),
            "target": round(target, 2),
            "drop_pct": round((top_price - target) / top_price * 100, 1),
        })
    return supports


def find_closest_sq9_levels(price: float, bottom: float, top: float) -> dict:
    """找出离当前价最近的Sq9关键位"""
    ups = gann_sq9_from_bottom(bottom)
    downs = gann_sq9_from_top(top)

    # 距当前价最近的上方阻力
    above = [u for u in ups if u["target"] > price]
    above.sort(key=lambda x: x["target"])
    next_resistances = above[:4] if above else []

    # 距当前价最近的下方支撑
    below = [u for u in ups if u["target"] < price]
    below.sort(key=lambda x: -x["target"])
    next_supports_up = below[:4] if below else []

    # 从顶部回撤的支撑
    below_top = [d for d in downs if d["target"] < price]
    below_top.sort(key=lambda x: -x["target"])
    next_supports_down = below_top[:4] if below_top else []

    return {
        "next_resistances": next_resistances,
        "next_supports_from_bottom": next_supports_up,
        "next_supports_from_top": next_supports_down,
    }


def check_price_resonance(price: float, bottom: float, top: float, tol_pct: float = 0.5) -> list:
    """
    检查当前价是否在某个江恩关键位的容忍度内（共振）。
    tol_pct: 容忍百分比（0.5%）
    """
    resonances = []

    # 从底部向上的目标位
    for u in gann_sq9_from_bottom(bottom):
        if abs(price - u["target"]) / price * 100 < tol_pct:
            resonances.append({
                "type": "向上目标位",
                "anchor": f"低点 ${bottom:.2f}",
                "degrees": u["degrees"],
                "target": u["target"],
                "deviation_pct": round((price - u["target"]) / u["target"] * 100, 2),
            })

    # 从顶部回撤的支撑位
    for d in gann_sq9_from_top(top):
        if abs(price - d["target"]) / price * 100 < tol_pct:
            resonances.append({
                "type": "顶部回撤支撑",
                "anchor": f"高点 ${top:.2f}",
                "degrees": d["degrees"],
                "target": d["target"],
                "deviation_pct": round((price - d["target"]) / d["target"] * 100, 2),
            })

    # 50% 黄金回调
    mid = (bottom + top) / 2
    if abs(price - mid) / price * 100 < tol_pct:
        resonances.append({
            "type": "50% 黄金回调",
            "anchor": f"区间 ${bottom:.2f}-${top:.2f}",
            "degrees": "—",
            "target": round(mid, 2),
            "deviation_pct": round((price - mid) / mid * 100, 2),
        })
    # 4/8, 5/8 江恩比例
    for ratio, label in [(0.375, "3/8 回调"), (0.625, "5/8 回调")]:
        lvl = top - (top - bottom) * ratio
        if abs(price - lvl) / price * 100 < tol_pct:
            resonances.append({
                "type": label,
                "anchor": f"区间 ${bottom:.2f}-${top:.2f}",
                "degrees": "—",
                "target": round(lvl, 2),
                "deviation_pct": round((price - lvl) / lvl * 100, 2),
            })

    return resonances


# ─────────────────────────────────────────────
#  时间循环 + 共振
# ─────────────────────────────────────────────

TIME_CYCLES = [
    (7, "7天小循环"),
    (14, "14天小循环"),
    (21, "21天循环（斐+江恩共振）"),
    (30, "30天月循环"),
    (45, "45天江恩转折"),
    (60, "60天江恩重要循环"),
    (90, "90天季度循环（极重要）"),
    (120, "120天江恩中周期"),
    (144, "144天江恩主循环（最重要）"),
    (180, "180天半年循环"),
]


def compute_time_windows(anchor_date: date, lookforward_days: int = 90) -> list:
    """从锚点日期算出未来的江恩时间窗口"""
    today = date.today()
    windows = []
    for days, label in TIME_CYCLES:
        target = anchor_date + timedelta(days=days)
        days_from_today = (target - today).days
        if -7 <= days_from_today <= lookforward_days:
            windows.append({
                "anchor_date": anchor_date.strftime("%Y-%m-%d"),
                "cycle_label": label,
                "cycle_days": days,
                "target_date": target.strftime("%Y-%m-%d"),
                "days_from_today": days_from_today,
                "is_imminent": -2 <= days_from_today <= 5,
                "is_critical": label in (
                    "60天江恩重要循环", "90天季度循环（极重要）",
                    "144天江恩主循环（最重要）", "180天半年循环"
                ),
            })
    return windows


def find_time_resonance(swings: dict) -> list:
    """
    找时间共振：多个锚点（顶/底/放量）+ 同一天附近落在重要江恩周期
    多个循环同时落在同一周期 = 极高概率变盘
    """
    all_windows = []
    if swings.get("recent_low_date"):
        for w in compute_time_windows(swings["recent_low_date"]):
            w["anchor_type"] = f"近期低点 ${swings['recent_low']:.2f}"
            all_windows.append(w)
    if swings.get("recent_high_date"):
        for w in compute_time_windows(swings["recent_high_date"]):
            w["anchor_type"] = f"近期高点 ${swings['recent_high']:.2f}"
            all_windows.append(w)

    # 按日期聚合：找哪些日期有多个窗口重合
    date_groups = {}
    for w in all_windows:
        d = w["target_date"]
        date_groups.setdefault(d, []).append(w)

    # 共振日 = 至少2个独立循环落在同一天±2天
    resonance_days = []
    for d, ws in date_groups.items():
        if len(ws) >= 2:
            resonance_days.append({
                "date": d,
                "days_from_today": ws[0]["days_from_today"],
                "windows": ws,
                "is_critical": any(w.get("is_critical") for w in ws),
            })

    resonance_days.sort(key=lambda x: x["days_from_today"])
    return resonance_days


# ─────────────────────────────────────────────
#  主入口
# ─────────────────────────────────────────────

def full_gann_analysis(ticker: str) -> dict:
    """完整的江恩分析报告"""
    swings = find_swing_points(ticker)
    if "error" in swings or not swings:
        return {"error": swings.get("error", "无价格数据")}

    price = swings["current_price"]
    bottom = swings["recent_low"]
    top = swings["recent_high"]

    sq9_from_bottom = gann_sq9_from_bottom(bottom)
    sq9_from_top = gann_sq9_from_top(top)
    closest = find_closest_sq9_levels(price, bottom, top)
    resonances = check_price_resonance(price, bottom, top, tol_pct=1.0)
    all_windows = []

    if swings.get("recent_low_date"):
        for w in compute_time_windows(swings["recent_low_date"]):
            w["anchor_type"] = f"近期低点"
            w["anchor_price"] = swings["recent_low"]
            all_windows.append(w)
    if swings.get("recent_high_date"):
        for w in compute_time_windows(swings["recent_high_date"]):
            w["anchor_type"] = f"近期高点"
            w["anchor_price"] = swings["recent_high"]
            all_windows.append(w)

    all_windows.sort(key=lambda x: x["days_from_today"])
    upcoming = [w for w in all_windows if 0 <= w["days_from_today"] <= 60]

    time_resonance = find_time_resonance(swings)

    # ─── 关键判断：当前价格是否在大江恩位置 ───
    interpretation = []
    if resonances:
        for r in resonances:
            interpretation.append(
                f"⚡ 当前价 ${price:.2f} 精准落在 **{r['type']}** "
                f"(${r['target']:.2f}, {r['anchor']}, 偏差{r['deviation_pct']:+.2f}%)"
            )
    # 距下一个关键位
    if closest["next_resistances"]:
        nr = closest["next_resistances"][0]
        interpretation.append(
            f"🔺 下一阻力 (Sq9 {nr['degrees']}°): ${nr['target']:.2f} ({(nr['target']-price)/price*100:+.1f}%)"
        )
    if closest["next_supports_from_top"]:
        ns = closest["next_supports_from_top"][0]
        interpretation.append(
            f"🔻 下一支撑 (Sq9 -{ns['degrees']}°): ${ns['target']:.2f} ({(ns['target']-price)/price*100:+.1f}%)"
        )

    return {
        "ticker": ticker,
        "swings": swings,
        "current_price": price,
        "sq9_from_bottom": sq9_from_bottom[:16],  # 显示前16档
        "sq9_from_top": sq9_from_top[:16],
        "closest_levels": closest,
        "resonances": resonances,
        "time_windows": all_windows,
        "upcoming_windows": upcoming,
        "time_resonance_days": time_resonance,
        "interpretation": interpretation,
        "compiled_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
