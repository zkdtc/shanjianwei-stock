"""
radar_rules.py
核心分析引擎：技术指标、江恩价格轴、相对强弱、操作评分
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json


# ─────────────────────────────────────────────
#  数据获取
# ─────────────────────────────────────────────

def fetch_price_data(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """下载历史行情数据"""
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return pd.DataFrame()
        # flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        return pd.DataFrame()


def fetch_current_price(ticker: str) -> float:
    """获取最新价格"""
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        return round(float(info.last_price), 2)
    except Exception:
        return 0.0


# ─────────────────────────────────────────────
#  技术指标计算
# ─────────────────────────────────────────────

def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calc_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def calc_indicators(df: pd.DataFrame) -> dict:
    """计算所有技术指标，返回最新值"""
    if df.empty or len(df) < 2:
        return {}

    # For very thin data (< 20 rows), return basic price info only
    if len(df) < 20:
        price_now = float(df["Close"].iloc[-1])
        return {
            "price": round(price_now, 2),
            "rsi_14": 50.0,
            "ema_20": price_now,
            "ema_50": price_now,
            "sma_200": None,
            "atr_14": 0.0,
            "vol_ratio": 1.0,
            "high_52w": price_now,
            "low_52w": price_now,
            "dist_from_52w_high": 0.0,
            "momentum_10d": 0.0,
            "momentum_20d": 0.0,
            "above_ema20": True,
            "above_ema50": True,
            "above_sma200": None,
            "ema20_above_ema50": True,
        }

    close = df["Close"]
    volume = df["Volume"]

    rsi_14 = calc_rsi(close, 14)
    ema_20 = calc_ema(close, 20)
    ema_50 = calc_ema(close, 50)
    sma_200 = calc_sma(close, 200)
    atr_14 = calc_atr(df, 14)

    price_now = float(close.iloc[-1])
    ema20_now = float(ema_20.iloc[-1])
    ema50_now = float(ema_50.iloc[-1])
    sma200_now = float(sma_200.iloc[-1]) if len(df) >= 200 else None
    rsi_now = float(rsi_14.iloc[-1])
    atr_now = float(atr_14.iloc[-1])

    # Volume analysis
    vol_ma20 = float(volume.rolling(20).mean().iloc[-1])
    vol_now = float(volume.iloc[-1])
    vol_ratio = vol_now / vol_ma20 if vol_ma20 > 0 else 1.0

    # 52-week high/low
    high_52 = float(close.rolling(252).max().iloc[-1]) if len(df) >= 50 else float(close.max())
    low_52 = float(close.rolling(252).min().iloc[-1]) if len(df) >= 50 else float(close.min())
    dist_from_high = (price_now - high_52) / high_52 * 100

    # Recent momentum (10-day return)
    momentum_10d = float((close.iloc[-1] / close.iloc[-11] - 1) * 100) if len(df) >= 11 else 0.0
    momentum_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(df) >= 21 else 0.0

    return {
        "price": round(price_now, 2),
        "rsi_14": round(rsi_now, 1),
        "ema_20": round(ema20_now, 2),
        "ema_50": round(ema50_now, 2),
        "sma_200": round(sma200_now, 2) if sma200_now else None,
        "atr_14": round(atr_now, 2),
        "vol_ratio": round(vol_ratio, 2),
        "high_52w": round(high_52, 2),
        "low_52w": round(low_52, 2),
        "dist_from_52w_high": round(dist_from_high, 1),
        "momentum_10d": round(momentum_10d, 1),
        "momentum_20d": round(momentum_20d, 1),
        "above_ema20": price_now > ema20_now,
        "above_ema50": price_now > ema50_now,
        "above_sma200": price_now > sma200_now if sma200_now else None,
        "ema20_above_ema50": ema20_now > ema50_now,
    }


# ─────────────────────────────────────────────
#  江恩价格轴分析
# ─────────────────────────────────────────────

def gann_analysis(price: float, gann_levels: dict) -> dict:
    """基于预设江恩水平分析当前价格位置"""
    s1 = gann_levels.get("s1", 0)
    s2 = gann_levels.get("s2", 0)
    r1 = gann_levels.get("r1", 0)
    r2 = gann_levels.get("r2", 0)

    if price <= 0:
        return {}

    # 确定当前价格区间
    if price < s2:
        zone = "超跌区（s2以下）"
        zone_color = "🟢"
        zone_signal = "极度超跌，关注反弹机会"
    elif price < s1:
        zone = "支撑区（s2~s1）"
        zone_color = "🟢"
        zone_signal = "支撑区间，可考虑建仓/加仓"
    elif price < r1:
        zone = "中性区（s1~r1）"
        zone_color = "🟡"
        zone_signal = "中性区间，持仓观察"
    elif price < r2:
        zone = "压力区（r1~r2）"
        zone_color = "🟠"
        zone_signal = "接近压力位，注意减仓/止盈"
    else:
        zone = "超买区（r2以上）"
        zone_color = "🔴"
        zone_signal = "高位超买区，警惕回调"

    # 距离各水平的百分比
    dist_s1 = (price - s1) / s1 * 100 if s1 > 0 else 0
    dist_r1 = (r1 - price) / price * 100 if price > 0 else 0

    return {
        "zone": zone,
        "zone_color": zone_color,
        "zone_signal": zone_signal,
        "s2": s2,
        "s1": s1,
        "r1": r1,
        "r2": r2,
        "dist_to_s1_pct": round(dist_s1, 1),
        "dist_to_r1_pct": round(dist_r1, 1),
    }


# ─────────────────────────────────────────────
#  相对强弱（vs SPY / vs QQQ）
# ─────────────────────────────────────────────

_benchmark_cache = {}

def get_benchmark_return(ticker: str, days: int = 20) -> float:
    """获取基准指数过去N天回报"""
    if ticker in _benchmark_cache:
        return _benchmark_cache[ticker]
    try:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < days:
            return 0.0
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        ret = float((df["Close"].iloc[-1] / df["Close"].iloc[-days] - 1) * 100)
        _benchmark_cache[ticker] = round(ret, 2)
        return _benchmark_cache[ticker]
    except Exception:
        return 0.0


def calc_relative_strength(stock_return_20d: float, spy_return: float, qqq_return: float) -> dict:
    """计算相对强弱"""
    rs_vs_spy = stock_return_20d - spy_return
    rs_vs_qqq = stock_return_20d - qqq_return

    if rs_vs_qqq > 10:
        rs_label = "🔥 极强（远超QQQ）"
        rs_score = 5
    elif rs_vs_qqq > 4:
        rs_label = "✅ 强势（跑赢QQQ）"
        rs_score = 4
    elif rs_vs_qqq > 0:
        rs_label = "🟡 略强（小幅跑赢）"
        rs_score = 3
    elif rs_vs_qqq > -5:
        rs_label = "🟠 弱势（跑输QQQ）"
        rs_score = 2
    else:
        rs_label = "🔴 极弱（大幅跑输）"
        rs_score = 1

    return {
        "rs_vs_spy": round(rs_vs_spy, 1),
        "rs_vs_qqq": round(rs_vs_qqq, 1),
        "rs_label": rs_label,
        "rs_score": rs_score,
    }


# ─────────────────────────────────────────────
#  技术状态评分
# ─────────────────────────────────────────────

def tech_state_score(indicators: dict) -> dict:
    """综合技术状态评分（0-100）"""
    if not indicators:
        return {"score": 0, "label": "数据不足", "signals": []}

    score = 50
    signals = []

    # RSI
    rsi = indicators.get("rsi_14", 50)
    if rsi < 30:
        score += 15
        signals.append("RSI极度超卖(<30) +15")
    elif rsi < 45:
        score += 8
        signals.append("RSI偏超卖(<45) +8")
    elif rsi > 75:
        score -= 12
        signals.append("RSI超买(>75) -12")
    elif rsi > 65:
        score -= 5
        signals.append("RSI偏超买(>65) -5")

    # 均线结构
    if indicators.get("above_ema20") and indicators.get("above_ema50"):
        score += 10
        signals.append("价格在EMA20/50上方 +10")
    elif indicators.get("above_ema20"):
        score += 5
        signals.append("价格在EMA20上方 +5")
    elif not indicators.get("above_ema20") and not indicators.get("above_ema50"):
        score -= 10
        signals.append("价格在EMA20/50下方 -10")

    if indicators.get("ema20_above_ema50"):
        score += 5
        signals.append("EMA20>EMA50(多头排列) +5")
    else:
        score -= 5
        signals.append("EMA20<EMA50(空头排列) -5")

    # 距52周高点
    dist = indicators.get("dist_from_52w_high", 0)
    if dist > -5:
        score -= 8
        signals.append(f"接近52周高点({dist:.1f}%) -8")
    elif dist < -30:
        score += 8
        signals.append(f"远离52周高点({dist:.1f}%) +8")

    # 成交量
    vol_ratio = indicators.get("vol_ratio", 1.0)
    mom = indicators.get("momentum_10d", 0)
    if vol_ratio > 1.5 and mom > 0:
        score += 8
        signals.append("放量上涨 +8")
    elif vol_ratio > 1.5 and mom < 0:
        score -= 8
        signals.append("放量下跌 -8")

    # 动量
    if mom > 15:
        score += 5
        signals.append(f"10日涨幅>{mom:.1f}% +5")
    elif mom < -15:
        score -= 5
        signals.append(f"10日跌幅>{mom:.1f}% -5")

    score = max(0, min(100, score))

    if score >= 75:
        label = "🟢 强势"
    elif score >= 60:
        label = "🟡 偏强"
    elif score >= 40:
        label = "🟠 中性"
    elif score >= 25:
        label = "🔴 偏弱"
    else:
        label = "⛔ 极弱"

    return {"score": score, "label": label, "signals": signals}


# ─────────────────────────────────────────────
#  估值状态
# ─────────────────────────────────────────────

def valuation_state(price: float, bottom_val: float, consensus_val: float) -> dict:
    """基于段永平式底线估值+市场共识估值判断当前价格位置"""
    if price <= 0 or bottom_val <= 0 or consensus_val <= 0:
        return {}

    pct_above_bottom = (price - bottom_val) / bottom_val * 100
    pct_vs_consensus = (price - consensus_val) / consensus_val * 100
    upside_to_consensus = (consensus_val - price) / price * 100

    if price < bottom_val:
        val_zone = "🟢 极度低估（低于底线估值）"
        val_signal = "安全边际极高，考虑重仓"
    elif price < bottom_val * 1.15:
        val_zone = "🟢 低估区间"
        val_signal = "安全边际充足，可积极建仓"
    elif price < consensus_val * 0.90:
        val_zone = "🟡 合理偏低"
        val_signal = "估值合理，适合建仓"
    elif price < consensus_val * 1.10:
        val_zone = "🟡 合理区间"
        val_signal = "估值合理，持仓观察"
    elif price < consensus_val * 1.25:
        val_zone = "🟠 偏高（高于共识15%+）"
        val_signal = "估值偏贵，减少新仓"
    else:
        val_zone = "🔴 高估（远超共识估值）"
        val_signal = "估值极贵，警惕回调"

    return {
        "val_zone": val_zone,
        "val_signal": val_signal,
        "bottom_valuation": bottom_val,
        "consensus_valuation": consensus_val,
        "upside_to_consensus_pct": round(upside_to_consensus, 1),
        "pct_above_bottom": round(pct_above_bottom, 1),
        "pct_vs_consensus": round(pct_vs_consensus, 1),
    }


# ─────────────────────────────────────────────
#  操作建议生成
# ─────────────────────────────────────────────

def generate_action_plan(
    stock_meta: dict,
    indicators: dict,
    gann: dict,
    rs: dict,
    tech: dict,
    val: dict,
) -> dict:
    """生成三层操作建议"""

    price = indicators.get("price", 0)
    rsi = indicators.get("rsi_14", 50)
    beta_type = stock_meta.get("beta_type", "")
    rs_score = rs.get("rs_score", 3)
    tech_score = tech.get("score", 50)
    zone = gann.get("zone", "")

    # ─── 综合评分 ───
    # 基础：技术(40%) + 相对强弱(30%) + 起点50
    composite = 30 + (tech_score * 0.4) + (rs_score * 10 * 0.3)
    val_zone = val.get("val_zone", "")
    # 估值调整（幅度缩小，避免高估值强势股被过度惩罚）
    if "极度低估" in val_zone:
        composite += 12
    elif "低估" in val_zone:
        composite += 7
    elif "合理偏低" in val_zone:
        composite += 3
    elif "远超共识" in val_zone or "高估" in val_zone:
        composite -= 5   # 高估只小幅扣分，趋势更重要
    # 江恩区间调整
    if "超跌" in zone:
        composite += 10
    elif "支撑" in zone:
        composite += 5
    elif "超买" in zone:
        composite -= 3   # 超买只轻微扣分
    composite = max(0, min(100, composite))

    # ─── 短线（1-3天）───
    if composite >= 70 and rsi < 65 and indicators.get("above_ema20"):
        short_action = "🟢 进攻"
        short_desc = "技术强势+估值合理，可短线追入或加仓"
        short_trigger = f"站稳 EMA20（{indicators.get('ema_20', 0):.2f}）持续"
        short_stop = f"跌破 EMA20 止损"
    elif composite >= 55:
        short_action = "🟡 持有"
        short_desc = "结构偏健康，持仓观察，等待更明确信号"
        short_trigger = "RSI回调至50-55区间可加仓"
        short_stop = f"跌破江恩S1（{gann.get('s1',0):.2f}）减仓"
    elif composite >= 40:
        short_action = "🟠 观察"
        short_desc = "结构中性，暂不新仓，等待方向确认"
        short_trigger = "放量突破近期高点后可进"
        short_stop = "跌破支撑止损"
    else:
        short_action = "🔴 回避"
        short_desc = "技术偏弱或估值过高，不宜追入"
        short_trigger = "等待RSI回到40-50区间再观察"
        short_stop = "严格控仓"

    # ─── 中线（1-2周）───
    if rs_score >= 4 and indicators.get("ema20_above_ema50"):
        mid_action = "🟢 趋势持有"
        mid_desc = "相对强弱领先+均线多头，中线趋势完好"
        mid_trigger = f"守住EMA50（{indicators.get('ema_50', 0):.2f}）"
        mid_exit = "EMA50失守或RS开始走弱则减仓"
    elif rs_score >= 3:
        mid_action = "🟡 持仓为主"
        mid_desc = "中线结构偏健康，持仓为主，高位注意节奏"
        mid_trigger = "财报/重大催化剂前后注意调仓"
        mid_exit = "跌破江恩S1减仓"
    else:
        mid_action = "🟠 轻仓或观察"
        mid_desc = "中线相对强弱走弱，建议轻仓或观察"
        mid_trigger = "等待RS重新领先大盘"
        mid_exit = "保持轻仓，等待机会"

    # ─── 长线（1-2月）───
    upside = val.get("upside_to_consensus_pct", 0)
    discount_horizon = stock_meta.get("discount_horizon", "")
    bottom_val = val.get("bottom_valuation", 0)

    if "低估" in val.get("val_zone", "") or upside > 20:
        long_action = "🟢 核心仓建立"
        long_desc = f"段永平底线估值（{bottom_val:.2f}）以上，上行空间{upside:.1f}%，可建立核心仓"
        long_note = f"折现窗口：{discount_horizon}，乘时代主线"
    elif upside > 5:
        long_action = "🟡 持有核心仓"
        long_desc = f"估值合理，上行空间{upside:.1f}%，坚持持有核心仓"
        long_note = f"折现窗口：{discount_horizon}"
    else:
        long_action = "🟠 控制仓位"
        long_desc = "当前价位已接近共识估值，长线需等待回调再加仓"
        long_note = f"底线估值支撑：{bottom_val:.2f}"

    return {
        "composite_score": round(composite, 1),
        "short": {
            "action": short_action,
            "desc": short_desc,
            "trigger": short_trigger,
            "stop": short_stop,
        },
        "mid": {
            "action": mid_action,
            "desc": mid_desc,
            "trigger": mid_trigger,
            "exit": mid_exit,
        },
        "long": {
            "action": long_action,
            "desc": long_desc,
            "note": long_note,
        },
    }


# ─────────────────────────────────────────────
#  主入口：分析单只股票
# ─────────────────────────────────────────────

def analyze_stock(stock_meta: dict, spy_ret: float = 0.0, qqq_ret: float = 0.0) -> dict:
    """完整分析一只股票，返回雷达报告"""
    ticker = stock_meta["ticker"]

    df = fetch_price_data(ticker, period="1y")
    indicators = calc_indicators(df)

    if not indicators:
        return {
            "ticker": ticker,
            "name": stock_meta.get("name", ticker),
            "error": "数据获取失败，请检查网络或ticker",
        }

    price = indicators["price"]

    gann = gann_analysis(price, stock_meta.get("gann_levels", {}))
    rs = calc_relative_strength(indicators.get("momentum_20d", 0), spy_ret, qqq_ret)
    tech = tech_state_score(indicators)
    val = valuation_state(
        price,
        stock_meta.get("bottom_valuation", 0),
        stock_meta.get("consensus_valuation", 0),
    )
    plan = generate_action_plan(stock_meta, indicators, gann, rs, tech, val)

    return {
        "ticker": ticker,
        "name": stock_meta.get("name", ticker),
        "market_identity": stock_meta.get("market_identity", ""),
        "mainline_layer": stock_meta.get("mainline_layer", ""),
        "mainline_position": stock_meta.get("mainline_position", ""),
        "discount_horizon": stock_meta.get("discount_horizon", ""),
        "beta_type": stock_meta.get("beta_type", ""),
        "notes": stock_meta.get("notes", ""),
        "indicators": indicators,
        "gann": gann,
        "rs": rs,
        "tech": tech,
        "val": val,
        "plan": plan,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def analyze_all(watchlist_path: str = "watchlist.json") -> list:
    """分析watchlist中所有股票"""
    with open(watchlist_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    stocks = data["stocks"]

    # 获取基准指数回报（只请求一次）
    spy_ret = get_benchmark_return("SPY", 20)
    qqq_ret = get_benchmark_return("QQQ", 20)

    results = []
    for s in stocks:
        result = analyze_stock(s, spy_ret, qqq_ret)
        results.append(result)

    return results, data.get("market_context", {})
