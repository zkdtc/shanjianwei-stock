"""
money_flow.py
资金流向分析（基于K线 + 成交量代理 — 不依赖level-2数据）
- 大单/中单/小单近似（按当日成交量分位）
- 主力意图（高位换手 vs 低位放量）
- 换手率
- OBV (能量潮)
- A/D Line
- 净流入估算
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime


def calc_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume"""
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def calc_ad_line(df: pd.DataFrame) -> pd.Series:
    """累积分配线"""
    money_flow_mult = ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / \
                      (df["High"] - df["Low"]).replace(0, 1)
    money_flow_vol = money_flow_mult * df["Volume"]
    return money_flow_vol.cumsum()


def analyze_money_flow(ticker: str, lookback_days: int = 60) -> dict:
    """资金流分析"""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        hist = t.history(period=f"{lookback_days + 30}d", interval="1d")
        if hist.empty:
            return {"error": "无数据"}

        df = hist.tail(lookback_days).copy()

        # ── 基础指标 ──
        df["price_change"] = df["Close"].pct_change() * 100
        df["amount"] = df["Close"] * df["Volume"]  # 成交额
        avg_amount = float(df["amount"].mean())

        # 当日成交量分位
        df["vol_pct"] = df["Volume"].rank(pct=True)

        # ── 大单/中单/小单近似 ──
        # 用成交量分位数 + 价格变动方向作为代理
        # 大单：成交量>80分位（机构）
        # 小单：成交量<30分位（散户/做市商）
        large_days = df[df["vol_pct"] > 0.8]
        small_days = df[df["vol_pct"] < 0.3]

        large_net = float((large_days["price_change"] * large_days["amount"]).sum())
        small_net = float((small_days["price_change"] * small_days["amount"]).sum())

        # 高位/低位区分
        median_price = float(df["Close"].median())
        high_zone = df[df["Close"] > median_price]
        low_zone = df[df["Close"] <= median_price]

        high_zone_large_outflow = float(
            high_zone[high_zone["price_change"] < 0]["amount"].sum() -
            high_zone[high_zone["price_change"] > 0]["amount"].sum()
        )
        low_zone_large_inflow = float(
            low_zone[low_zone["price_change"] > 0]["amount"].sum() -
            low_zone[low_zone["price_change"] < 0]["amount"].sum()
        )

        # ── OBV ──
        obv = calc_obv(df["Close"], df["Volume"])
        obv_now = float(obv.iloc[-1])
        obv_20_ago = float(obv.iloc[-21]) if len(obv) >= 21 else float(obv.iloc[0])
        obv_chg = obv_now - obv_20_ago
        price_chg_20d = float((df["Close"].iloc[-1] / df["Close"].iloc[-21] - 1) * 100) if len(df) >= 21 else 0

        # OBV 背离检测
        if price_chg_20d > 3 and obv_chg < 0:
            divergence = "🔴 顶背离：价格上涨但OBV下降 → 量价背离，警惕回调"
        elif price_chg_20d < -3 and obv_chg > 0:
            divergence = "🟢 底背离：价格下跌但OBV上升 → 主力暗中吸筹"
        elif price_chg_20d > 0 and obv_chg > 0:
            divergence = "🟢 量价齐升：健康上涨"
        elif price_chg_20d < 0 and obv_chg < 0:
            divergence = "🔴 量价齐跌：抛压持续"
        else:
            divergence = "🟡 量价平衡"

        # ── A/D Line ──
        ad = calc_ad_line(df)
        ad_now = float(ad.iloc[-1])
        ad_20_ago = float(ad.iloc[-21]) if len(ad) >= 21 else float(ad.iloc[0])
        ad_chg = ad_now - ad_20_ago

        if ad_chg > 0:
            ad_signal = "🟢 A/D Line上升 → 累积阶段（机构在收集筹码）"
        else:
            ad_signal = "🔴 A/D Line下降 → 派发阶段（机构在出货）"

        # ── 换手率 ──
        shares_outstanding = info.get("sharesOutstanding") or info.get("floatShares") or 0
        if shares_outstanding > 0:
            avg_turnover = float(df["Volume"].mean()) / shares_outstanding * 100
            last_turnover = float(df["Volume"].iloc[-1]) / shares_outstanding * 100
        else:
            avg_turnover = None
            last_turnover = None

        # ── 主力意图判断 ──
        main_intent = []
        if high_zone_large_outflow > avg_amount * 5:
            main_intent.append("📤 高位明显有大单流出 → 部分资金锁利离场")
        if low_zone_large_inflow > avg_amount * 5:
            main_intent.append("📥 低位有大单流入 → 主力承接意愿强")
        if avg_turnover and avg_turnover > 5:
            main_intent.append(f"🌪️ 换手率高（{avg_turnover:.1f}%）→ 高位剧烈洗盘，浮筹被洗")
        elif avg_turnover and avg_turnover < 1:
            main_intent.append(f"💤 换手率低（{avg_turnover:.1f}%）→ 筹码锁定，关注突破")
        if not main_intent:
            main_intent.append("⚖️ 资金流向平衡，无明显主力意图")

        # 近5天成交量趋势
        recent5 = df.tail(5)
        recent5_vol_avg = float(recent5["Volume"].mean())
        prior_avg = float(df["Volume"].iloc[-20:-5].mean()) if len(df) >= 20 else recent5_vol_avg
        recent_vol_trend = "🔥 近5日放量" if recent5_vol_avg > prior_avg * 1.3 else \
                           "💤 近5日缩量" if recent5_vol_avg < prior_avg * 0.7 else \
                           "📊 近5日量能持平"

        return {
            "ticker": ticker,
            "lookback_days": lookback_days,
            "avg_daily_amount": round(avg_amount, 0),
            "shares_outstanding": shares_outstanding,
            "avg_turnover_pct": round(avg_turnover, 2) if avg_turnover else None,
            "last_turnover_pct": round(last_turnover, 2) if last_turnover else None,
            "high_zone_large_outflow": round(high_zone_large_outflow, 0),
            "low_zone_large_inflow": round(low_zone_large_inflow, 0),
            "obv_change_20d": round(obv_chg, 0),
            "price_change_20d_pct": round(price_chg_20d, 2),
            "obv_divergence": divergence,
            "ad_change_20d": round(ad_chg, 0),
            "ad_signal": ad_signal,
            "recent_vol_trend": recent_vol_trend,
            "main_intent": main_intent,
            "compiled_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        return {"error": str(e)}
