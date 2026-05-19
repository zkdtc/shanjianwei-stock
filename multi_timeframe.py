"""
multi_timeframe.py
多周期（周线 / 日线 / 1小时）技术指标分析
- 均线系统（MA5/10/20/50/200, EMA）
- MACD
- RSI (14)
- 布林带 (Boll)
- 成交量结构
- 筹码分布（Volume Profile）
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime


# ─────────────────────────────────────────────
#  通用指标函数
# ─────────────────────────────────────────────

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast).mean()
    ema_slow = series.ewm(span=slow).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal).mean()
    hist = (dif - dea) * 2
    return dif, dea, hist


def boll(series, period=20, k=2):
    mid = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = mid + std * k
    lower = mid - std * k
    return upper, mid, lower


def volume_profile(df, n_bins=24):
    """筹码分布：按价格区间统计成交量"""
    if df.empty:
        return []
    lo, hi = df["Low"].min(), df["High"].max()
    bins = np.linspace(lo, hi, n_bins + 1)
    profile = []
    for i in range(n_bins):
        mask = (df["Close"] >= bins[i]) & (df["Close"] < bins[i + 1])
        vol = float(df.loc[mask, "Volume"].sum())
        if vol > 0:
            profile.append({
                "price_low": round(float(bins[i]), 2),
                "price_high": round(float(bins[i + 1]), 2),
                "price_mid": round(float((bins[i] + bins[i + 1]) / 2), 2),
                "volume": vol,
            })
    # POC (Point of Control) = 成交量最大区间
    if profile:
        profile.sort(key=lambda x: -x["volume"])
        poc = profile[0]
        # value area (70% volume)
        total = sum(p["volume"] for p in profile)
        cumvol = 0
        val_area = []
        for p in profile:
            cumvol += p["volume"]
            val_area.append(p)
            if cumvol >= total * 0.7:
                break
        profile.sort(key=lambda x: x["price_mid"])
        return {
            "all_bins": profile,
            "poc": poc,
            "value_area_high": max(p["price_high"] for p in val_area),
            "value_area_low": min(p["price_low"] for p in val_area),
        }
    return None


# ─────────────────────────────────────────────
#  单周期分析
# ─────────────────────────────────────────────

def analyze_timeframe(df: pd.DataFrame, label: str) -> dict:
    """对一个周期的K线做完整分析"""
    if df.empty or len(df) < 30:
        return {"error": f"{label}数据不足"}

    close = df["Close"]
    price = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    chg_pct = (price - prev) / prev * 100

    # ── 均线系统 ──
    ma5 = close.rolling(5).mean().iloc[-1]
    ma10 = close.rolling(10).mean().iloc[-1]
    ma20 = close.rolling(20).mean().iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
    ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

    ema12 = close.ewm(span=12).mean().iloc[-1]
    ema26 = close.ewm(span=26).mean().iloc[-1]

    # 多头/空头排列
    if ma5 > ma10 > ma20:
        ma_arr = "🟢 完美多头排列 (MA5>MA10>MA20)"
    elif ma5 < ma10 < ma20:
        ma_arr = "🔴 完美空头排列 (MA5<MA10<MA20)"
    else:
        ma_arr = "🟡 均线交织（无方向）"

    # ── MACD ──
    dif, dea, hist = macd(close)
    macd_dif = float(dif.iloc[-1])
    macd_dea = float(dea.iloc[-1])
    macd_hist = float(hist.iloc[-1])
    macd_prev = float(hist.iloc[-2]) if len(hist) >= 2 else 0

    if macd_dif > 0 and macd_dea > 0 and macd_hist > macd_prev:
        macd_signal = "🟢 零轴上方多头发散（强势）"
    elif macd_dif > 0 and macd_hist < macd_prev:
        macd_signal = "🟡 零轴上方但柱状缩短（高位钝化警报）"
    elif macd_dif < 0 and macd_hist > macd_prev:
        macd_signal = "🟡 零轴下方但柱状收窄（底部修复中）"
    elif macd_dif < 0 and macd_dea < 0 and macd_hist < macd_prev:
        macd_signal = "🔴 零轴下方空头发散（弱势）"
    else:
        macd_signal = "🟡 MACD震荡"

    # ── RSI ──
    rsi14 = float(rsi(close).iloc[-1])
    if rsi14 > 80:
        rsi_signal = "🔴 严重超买（>80）"
    elif rsi14 > 70:
        rsi_signal = "🟠 超买"
    elif rsi14 < 20:
        rsi_signal = "🟢 严重超卖（<20，反弹机会）"
    elif rsi14 < 30:
        rsi_signal = "🟢 超卖"
    elif rsi14 > 50:
        rsi_signal = "🟡 多头中性"
    else:
        rsi_signal = "🟡 空头中性"

    # ── 布林带 ──
    bup, bmid, blow = boll(close)
    bup_v, bmid_v, blow_v = float(bup.iloc[-1]), float(bmid.iloc[-1]), float(blow.iloc[-1])
    bb_width_pct = (bup_v - blow_v) / bmid_v * 100

    if price > bup_v:
        boll_signal = "🔴 突破布林上轨（超买/动量极强）"
    elif price < blow_v:
        boll_signal = "🟢 跌破布林下轨（超卖/动量极弱）"
    elif price > bmid_v:
        boll_signal = "🟡 中轨上方（多头主导）"
    else:
        boll_signal = "🟡 中轨下方（空头主导）"

    # ── 成交量 ──
    vol = df["Volume"]
    vol_now = float(vol.iloc[-1])
    vol_ma = float(vol.rolling(20).mean().iloc[-1])
    vol_ratio = vol_now / vol_ma if vol_ma > 0 else 1.0

    if vol_ratio > 2 and chg_pct > 0:
        vol_signal = "🔥 放巨量上涨（资金强烈买入）"
    elif vol_ratio > 2 and chg_pct < 0:
        vol_signal = "🔥 放巨量下跌（恐慌抛售）"
    elif vol_ratio > 1.5:
        vol_signal = "🟢 放量"
    elif vol_ratio < 0.6:
        vol_signal = "🟡 缩量（观望情绪）"
    else:
        vol_signal = "🟡 正常量能"

    return {
        "label": label,
        "rows": len(df),
        "price": round(price, 2),
        "chg_pct": round(chg_pct, 2),

        "ma5": round(float(ma5), 2),
        "ma10": round(float(ma10), 2),
        "ma20": round(float(ma20), 2),
        "ma50": round(float(ma50), 2) if ma50 else None,
        "ma200": round(float(ma200), 2) if ma200 else None,
        "ema12": round(float(ema12), 2),
        "ema26": round(float(ema26), 2),
        "ma_arrangement": ma_arr,

        "macd_dif": round(macd_dif, 3),
        "macd_dea": round(macd_dea, 3),
        "macd_hist": round(macd_hist, 3),
        "macd_signal": macd_signal,

        "rsi_14": round(rsi14, 1),
        "rsi_signal": rsi_signal,

        "boll_upper": round(bup_v, 2),
        "boll_mid": round(bmid_v, 2),
        "boll_lower": round(blow_v, 2),
        "boll_width_pct": round(bb_width_pct, 2),
        "boll_signal": boll_signal,

        "vol_now": int(vol_now),
        "vol_ma20": int(vol_ma),
        "vol_ratio": round(vol_ratio, 2),
        "vol_signal": vol_signal,
    }


# ─────────────────────────────────────────────
#  多周期组合分析
# ─────────────────────────────────────────────

def multi_timeframe_analysis(ticker: str) -> dict:
    """周线 + 日线 + 1小时 三周期分析"""
    try:
        t = yf.Ticker(ticker)

        # 周线
        wk_df = t.history(period="2y", interval="1wk")
        wk = analyze_timeframe(wk_df, "周线")

        # 日线
        d_df = t.history(period="1y", interval="1d")
        daily = analyze_timeframe(d_df, "日线")

        # 1小时（最多60天）
        h_df = t.history(period="60d", interval="1h")
        hourly = analyze_timeframe(h_df, "1小时")

        # 筹码分布（用日线）
        vp = volume_profile(d_df, n_bins=24) if not d_df.empty else None

        # 综合判断：周日小时三共振
        signals = []
        # MA arrangement consensus
        ma_consensus = sum(1 for tf in [wk, daily, hourly]
                           if "多头" in tf.get("ma_arrangement", ""))
        if ma_consensus == 3:
            signals.append("🟢 周/日/时三周期全部多头排列 — 主升浪结构完美")
        elif ma_consensus == 0:
            signals.append("🔴 周/日/时三周期全部空头 — 趋势性下跌")
        elif ma_consensus == 2:
            signals.append("🟡 两周期多头一周期空头 — 趋势仍在但有分歧")

        # RSI共振
        if all("超卖" in tf.get("rsi_signal", "") for tf in [daily, hourly]):
            signals.append("🟢 日线+小时线双双超卖 — 短线反弹概率高")
        if all("超买" in tf.get("rsi_signal", "") for tf in [daily, hourly]):
            signals.append("🔴 日线+小时线双双超买 — 短线回调风险")

        # 周线MACD背离/钝化
        if wk.get("macd_signal", "").startswith("🟡 零轴上方"):
            signals.append("⚠️ 周线MACD高位钝化 — 大周期可能进入震荡期")

        # 布林共振
        if "突破布林上轨" in daily.get("boll_signal", "") and \
           "突破布林上轨" in hourly.get("boll_signal", ""):
            signals.append("🔥 日线+小时线双双突破布林上轨 — 极端动量")

        return {
            "ticker": ticker,
            "weekly": wk,
            "daily": daily,
            "hourly": hourly,
            "volume_profile": vp,
            "cross_signals": signals,
            "compiled_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        return {"error": str(e)}
