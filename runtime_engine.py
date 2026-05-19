"""
AMOS Runtime Engine
====================
Market Regime · Narrative Heatmap · Leadership Board · Opportunity/Danger Radars
Attention Map · Market Memory · Cognitive State
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
import yfinance as yf


# ─────────────────────────────────────────────
# 1. MARKET REGIME (顶部全球 Runtime)
# ─────────────────────────────────────────────
def fetch_macro_signals() -> Dict[str, Any]:
    """Fetch macro signals: VIX, rates, BTC, NVDA leadership, dollar."""
    tickers = {
        "VIX": "^VIX",
        "TNX": "^TNX",   # 10-yr yield
        "BTC": "BTC-USD",
        "NVDA": "NVDA",
        "SPY": "SPY",
        "QQQ": "QQQ",
        "DXY": "DX-Y.NYB",
    }
    out = {}
    for label, sym in tickers.items():
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="3mo")
            if hist.empty:
                continue
            price = float(hist["Close"].iloc[-1])
            chg_1d = float((hist["Close"].iloc[-1] / hist["Close"].iloc[-2] - 1) * 100) if len(hist) > 1 else 0
            chg_20d = float((hist["Close"].iloc[-1] / hist["Close"].iloc[-20] - 1) * 100) if len(hist) > 20 else 0
            sma20 = float(hist["Close"].rolling(20).mean().iloc[-1])
            out[label] = {
                "price": price, "chg_1d": chg_1d, "chg_20d": chg_20d,
                "sma20": sma20, "above_sma20": price > sma20,
            }
        except Exception:
            continue
    return out


def classify_regime(macro: Dict[str, Any]) -> Dict[str, str]:
    """Classify market regime based on macro signals."""
    vix = macro.get("VIX", {}).get("price", 18)
    tnx = macro.get("TNX", {}).get("price", 4.0)
    nvda = macro.get("NVDA", {})
    qqq = macro.get("QQQ", {})
    btc = macro.get("BTC", {})

    # Risk appetite
    if vix < 15:
        risk_app = "Risk-On (vix低)"
    elif vix < 20:
        risk_app = "Selective (中性)"
    elif vix < 28:
        risk_app = "Cautious (谨慎)"
    else:
        risk_app = "Risk-Off (恐慌)"

    # Liquidity
    if tnx >= 4.5:
        liquidity = "Tightening (利率压制)"
    elif tnx >= 4.0:
        liquidity = "Neutral (中性)"
    else:
        liquidity = "Loosening (宽松)"

    # Regime
    nvda_above = nvda.get("above_sma20", False)
    qqq_above = qqq.get("above_sma20", False)
    qqq_20d = qqq.get("chg_20d", 0)

    if nvda_above and qqq_above and qqq_20d > 3 and vix < 20:
        regime = "AI Expansion"
    elif nvda_above and not qqq_above:
        regime = "AI Expansion → Compression"
    elif not nvda_above and qqq_above:
        regime = "Rotation (主线动摇)"
    elif vix > 25:
        regime = "Risk Compression"
    else:
        regime = "Neutral Consolidation"

    # Leadership
    leadership = "NVDA intact" if nvda_above else "NVDA wobbling ⚠️"

    # Current Risk
    risks = []
    if vix > 22:
        risks.append("VIX上升")
    if tnx > 4.5:
        risks.append("利率压制估值")
    if not nvda_above:
        risks.append("龙头走弱")
    if qqq.get("chg_1d", 0) < -1.5:
        risks.append("当日大跌")
    current_risk = "High-beta volatility" if risks else "Manageable"
    if risks:
        current_risk = " · ".join(risks)

    return {
        "regime": regime,
        "liquidity": liquidity,
        "risk_appetite": risk_app,
        "vix_level": f"{vix:.1f} {'↑' if vix > 20 else '↓'}",
        "rates_level": f"{tnx:.2f}% {'高' if tnx > 4.3 else '中性'}",
        "btc_trend": "Hold Risk Sentiment" if btc.get("above_sma20") else "Weakening",
        "leadership": leadership,
        "current_risk": current_risk,
    }


def regime_chinese_narrative(regime: Dict[str, str]) -> str:
    """Generate connected Chinese narrative for the regime."""
    parts = []
    if "Expansion → Compression" in regime["regime"]:
        parts.append("当前AI主线仍然存在，但高Beta股票开始进入压缩阶段。")
    elif "Expansion" in regime["regime"]:
        parts.append("AI主线扩张延续，风险资产承接力良好。")
    elif "Compression" in regime["regime"]:
        parts.append("市场处于compression阶段，高波动是主基调。")
    elif "Rotation" in regime["regime"]:
        parts.append("AI龙头出现动摇，资金可能正在寻找新主线。")
    else:
        parts.append("市场处于过渡/震荡阶段。")

    if "Tightening" in regime["liquidity"]:
        parts.append("流动性偏紧，更适合精选机会，而不是全面risk-on。")
    elif "Loosening" in regime["liquidity"]:
        parts.append("流动性宽松，风险偏好有支撑。")

    if "intact" in regime["leadership"]:
        parts.append("NVDA龙头结构完整，更像中期compression而非Narrative collapse。")
    elif "wobbling" in regime["leadership"]:
        parts.append("⚠️ NVDA龙头开始动摇，警惕主线切换风险。")

    return " ".join(parts)


# ─────────────────────────────────────────────
# 2. NARRATIVE HEATMAP
# ─────────────────────────────────────────────
# Narrative定义：层级 + 关键龙头
NARRATIVES = {
    "AI Infra (GPU/Compute)": {
        "tickers": ["NVDA", "AVGO", "AMD", "TSM"],
        "layer": "基础设施层",
    },
    "AI Networking/Optics": {
        "tickers": ["CRDO", "LITE", "COHR", "ANET"],
        "layer": "基础设施层",
    },
    "AI Platform/Cloud": {
        "tickers": ["MSFT", "GOOG", "AMZN", "ORCL"],
        "layer": "平台层",
    },
    "AI Application/SaaS": {
        "tickers": ["PLTR", "NET", "CRWD", "PANW"],
        "layer": "应用层",
    },
    "BTC Miners/AI Datacenter": {
        "tickers": ["IREN", "MARA", "CLSK", "CIFR"],
        "layer": "基础设施层",
    },
    "AI Healthcare": {
        "tickers": ["TEM", "RXRX", "SDGR"],
        "layer": "应用层",
    },
    "Robotics/Autonomy": {
        "tickers": ["TSLA", "ISRG", "PATH"],
        "layer": "应用层",
    },
    "Fintech/Crypto-Adjacent": {
        "tickers": ["HOOD", "COIN", "SQ"],
        "layer": "应用层",
    },
}


def _ticker_perf(sym: str, period: str = "1mo") -> Optional[Dict[str, float]]:
    try:
        h = yf.Ticker(sym).history(period=period)
        if h.empty or len(h) < 5:
            return None
        c = h["Close"]
        v = h["Volume"]
        return {
            "price": float(c.iloc[-1]),
            "chg_5d": float((c.iloc[-1] / c.iloc[-5] - 1) * 100) if len(c) >= 5 else 0,
            "chg_20d": float((c.iloc[-1] / c.iloc[-20] - 1) * 100) if len(c) >= 20 else 0,
            "vol_ratio": float(v.iloc[-1] / v.tail(20).mean()) if len(v) >= 20 else 1.0,
            "sma20": float(c.rolling(20).mean().iloc[-1]) if len(c) >= 20 else float(c.iloc[-1]),
        }
    except Exception:
        return None


def compute_narrative_heatmap() -> List[Dict[str, Any]]:
    """For each narrative, compute aggregate strength signal."""
    results = []
    for name, info in NARRATIVES.items():
        perfs = []
        for t in info["tickers"]:
            p = _ticker_perf(t)
            if p:
                perfs.append(p)
        if not perfs:
            continue
        avg_5d = sum(p["chg_5d"] for p in perfs) / len(perfs)
        avg_20d = sum(p["chg_20d"] for p in perfs) / len(perfs)
        avg_vol = sum(p["vol_ratio"] for p in perfs) / len(perfs)
        above_sma = sum(1 for p in perfs if p["price"] > p["sma20"]) / len(perfs)

        # Classify state
        if avg_20d > 8 and above_sma > 0.7:
            state = "🔥 HOT EXPANSION"
            color = "#dc3545"
        elif avg_20d > 3 and above_sma > 0.5:
            state = "📈 EXPANSION"
            color = "#fd7e14"
        elif avg_20d > 0 and avg_5d < -3:
            state = "⚠️ HOT but COMPRESSING"
            color = "#ffc107"
        elif avg_5d < -5 and avg_vol > 1.5:
            state = "📉 PANIC COMPRESSION"
            color = "#0d6efd"
        elif avg_5d > 3 and avg_20d < -3:
            state = "🔄 RE-ACCELERATING"
            color = "#20c997"
        elif avg_20d < -5:
            state = "❄️ COLD"
            color = "#6c757d"
        else:
            state = "➖ NEUTRAL"
            color = "#adb5bd"

        results.append({
            "name": name,
            "layer": info["layer"],
            "state": state,
            "color": color,
            "avg_5d": round(avg_5d, 2),
            "avg_20d": round(avg_20d, 2),
            "vol_ratio": round(avg_vol, 2),
            "above_sma_pct": round(above_sma * 100, 0),
            "tickers": info["tickers"],
            "leaders": [t for t in info["tickers"] if (p := _ticker_perf(t)) and p["chg_20d"] > avg_20d][:3],
        })
    # Sort by avg_20d
    results.sort(key=lambda x: x["avg_20d"], reverse=True)
    return results


# ─────────────────────────────────────────────
# 3. LEADERSHIP BOARD
# ─────────────────────────────────────────────
CORE_LEADERS = {
    "NVDA": "AI Compute Leadership",
    "MSFT": "AI Platform Anchor",
    "GOOG": "AI Agent Ecosystem",
    "TSLA": "Robotics/FSD Narrative",
    "BTC-USD": "Cross-Asset Risk Proxy",
    "HOOD": "Retail Risk Appetite Gauge",
}
HIGH_BETA_LEADERS = {
    "CRDO": "AI Networking Panic Compression",
    "IREN": "BTC + AI Infra Expansion",
    "TEM": "Event-Driven AI Healthcare",
    "PLTR": "AI Software Commercialization",
    "AVGO": "AI ASIC/Networking",
    "COIN": "Crypto Beta",
}


def compute_leadership_board() -> Dict[str, List[Dict[str, Any]]]:
    """Generate leadership board with current state."""
    def _build(d):
        out = []
        for sym, role in d.items():
            p = _ticker_perf(sym)
            if not p:
                continue
            # State
            if p["chg_20d"] > 10 and p["price"] > p["sma20"]:
                state = "🟢 Leading"
            elif p["chg_20d"] > 0 and p["price"] > p["sma20"]:
                state = "🟢 Intact"
            elif p["chg_5d"] < -8:
                state = "🔴 Panic Compression"
            elif p["chg_20d"] < -5:
                state = "🟠 Weakening"
            else:
                state = "🟡 Consolidating"
            out.append({
                "ticker": sym, "role": role, "state": state,
                "price": p["price"], "chg_5d": p["chg_5d"], "chg_20d": p["chg_20d"],
            })
        return out
    return {
        "core": _build(CORE_LEADERS),
        "high_beta": _build(HIGH_BETA_LEADERS),
    }


# ─────────────────────────────────────────────
# 4. OPPORTUNITY RADAR / DANGER RADAR / ATTENTION MAP
# ─────────────────────────────────────────────
def detect_opportunities(watchlist_path: str = "watchlist.json") -> List[Dict[str, Any]]:
    """Detect high-confluence opportunities from watchlist."""
    try:
        with open(watchlist_path, "r", encoding="utf-8") as f:
            wl = json.load(f)
    except Exception:
        return []

    opps = []
    for stock in wl.get("stocks", []):
        sym = stock["ticker"]
        p = _ticker_perf(sym, "3mo")
        if not p:
            continue

        # Check confluences
        confluences = []
        # Panic compression: -8% in 5d, +20d still positive (i.e. high-beta dip in bull trend)
        if p["chg_5d"] < -8 and p["chg_20d"] > 0:
            confluences.append("📉 High-Beta Panic Dip")
        # Approaching bottom valuation
        bv = stock.get("bottom_valuation", 0)
        if bv and p["price"] <= bv * 1.1:
            confluences.append("💎 接近底线估值")
        # Approaching Gann support
        gann_s1 = stock.get("gann_levels", {}).get("s1", 0)
        if gann_s1 and abs(p["price"] - gann_s1) / p["price"] < 0.03:
            confluences.append("📐 触及江恩S1支撑")
        # Strong relative strength
        if p["chg_20d"] > 15 and p["vol_ratio"] > 1.3:
            confluences.append("🚀 强势放量")
        # Oversold extreme
        try:
            h = yf.Ticker(sym).history(period="3mo")
            close = h["Close"]
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss
            rsi = float((100 - 100 / (1 + rs)).iloc[-1])
            if rsi < 30:
                confluences.append(f"📊 RSI极度超卖 ({rsi:.0f})")
            elif rsi > 75:
                confluences.append(f"⚠️ RSI超买 ({rsi:.0f})")
        except Exception:
            rsi = 50

        if len(confluences) >= 2:
            grade = "🔥 A-GRADE" if len(confluences) >= 3 else "⭐ B-GRADE"
            # Determine type
            if "Panic Dip" in str(confluences) or "超卖" in str(confluences):
                opp_type = "High-Beta Panic Compression Repair"
            elif "底线估值" in str(confluences):
                opp_type = "Value Floor Bounce"
            elif "强势放量" in str(confluences):
                opp_type = "Breakout Confirmation"
            else:
                opp_type = "Confluence Setup"
            opps.append({
                "ticker": sym,
                "name": stock.get("name", sym),
                "grade": grade,
                "type": opp_type,
                "confluences": confluences,
                "price": p["price"],
                "chg_5d": p["chg_5d"],
                "chg_20d": p["chg_20d"],
                "rsi": rsi,
                "narrative": stock.get("market_identity", ""),
                "risk": "High Volatility" if p["vol_ratio"] > 1.5 else "Moderate",
                "execution_state": "TACTICAL" if "Panic" in opp_type else "STRATEGIC",
            })

    opps.sort(key=lambda x: len(x["confluences"]), reverse=True)
    return opps[:8]


def detect_dangers(watchlist_path: str = "watchlist.json") -> List[Dict[str, Any]]:
    """Detect deteriorating setups → warnings."""
    try:
        with open(watchlist_path, "r", encoding="utf-8") as f:
            wl = json.load(f)
    except Exception:
        return []

    dangers = []
    for stock in wl.get("stocks", []):
        sym = stock["ticker"]
        p = _ticker_perf(sym, "3mo")
        if not p:
            continue

        flags = []
        # Failed rally / breaking trend
        if p["chg_20d"] > 5 and p["price"] < p["sma20"] and p["chg_5d"] < -3:
            flags.append("📉 跌破SMA20，趋势开始动摇")
        # 利好不涨 proxy: high vol_ratio but flat/down price
        if p["vol_ratio"] > 1.4 and p["chg_5d"] < 1:
            flags.append("⚠️ 放量不涨（潜在利好不涨）")
        # Near consensus valuation (overextended)
        cv = stock.get("consensus_valuation", 0)
        if cv and p["price"] > cv * 1.15:
            flags.append(f"🎯 价格已远超共识估值 ${cv}")
        # Gann R2 hit (overbought)
        gann_r2 = stock.get("gann_levels", {}).get("r2", 0)
        if gann_r2 and p["price"] > gann_r2:
            flags.append(f"⚡ 突破江恩R2 ${gann_r2}（超买）")
        # Bottom valuation breach
        bv = stock.get("bottom_valuation", 0)
        if bv and p["price"] < bv:
            flags.append(f"💀 跌破底线估值 ${bv}")

        if len(flags) >= 1:
            severity = "🔴 HIGH" if len(flags) >= 2 else "🟡 MED"
            dangers.append({
                "ticker": sym, "name": stock.get("name", sym),
                "severity": severity, "flags": flags,
                "price": p["price"], "chg_5d": p["chg_5d"], "chg_20d": p["chg_20d"],
            })

    # Sort by severity
    dangers.sort(key=lambda x: (-len(x["flags"]), x["chg_5d"]))
    return dangers[:8]


def attention_map(watchlist_path: str = "watchlist.json") -> Dict[str, List[str]]:
    """Generate today's attention priority (HIGH/WATCH/LOW/MUTED)."""
    try:
        with open(watchlist_path, "r", encoding="utf-8") as f:
            wl = json.load(f)
    except Exception:
        return {"high": [], "watch": [], "low": [], "muted": []}

    high, watch, low, muted = [], [], [], []
    for stock in wl.get("stocks", []):
        sym = stock["ticker"]
        p = _ticker_perf(sym)
        if not p:
            muted.append(sym)
            continue
        abs_5d = abs(p["chg_5d"])
        # HIGH PRIORITY: big moves OR near key levels OR high volume
        bv = stock.get("bottom_valuation", 0)
        cv = stock.get("consensus_valuation", 0)
        near_bv = bv and abs(p["price"] - bv) / p["price"] < 0.08
        near_cv = cv and abs(p["price"] - cv) / p["price"] < 0.05
        high_vol = p["vol_ratio"] > 1.6
        big_move = abs_5d > 8

        if big_move or high_vol or near_bv or near_cv:
            high.append(sym)
        elif abs_5d > 4 or p["vol_ratio"] > 1.2:
            watch.append(sym)
        elif abs_5d > 1:
            low.append(sym)
        else:
            muted.append(sym)
    return {"high": high, "watch": watch, "low": low, "muted": muted}


def market_memory() -> Dict[str, str]:
    """Generate market memory: 'what does today look like historically?'"""
    macro = fetch_macro_signals()
    regime = classify_regime(macro)
    nvda = macro.get("NVDA", {})
    vix = macro.get("VIX", {}).get("price", 18)
    tnx = macro.get("TNX", {}).get("price", 4)

    if nvda.get("above_sma20") and vix < 22 and tnx > 4.2:
        most_similar = "2023 H2 AI Infra Expansion (利率高但AI主线扩张)"
        not_yet = "2022 Growth Collapse (主线尚未死亡)"
        key_diff = "当前利率环境与2023类似，但AI Capex周期更成熟。"
    elif vix > 25:
        most_similar = "2022 Q2/Q3 Compression"
        not_yet = "2020 Risk-Off Capitulation"
        key_diff = "目前VIX上升但流动性未恶化到2022水平。"
    elif not nvda.get("above_sma20"):
        most_similar = "2024 Q2 AI Cooling Phase"
        not_yet = "Full Narrative Death"
        key_diff = "AI龙头走弱但流动性结构仍存。"
    else:
        most_similar = "Mid-cycle Consolidation"
        not_yet = "Major Reversal"
        key_diff = "市场处于中段消化阶段。"

    return {
        "most_similar": most_similar,
        "not_yet": not_yet,
        "key_diff": key_diff,
    }


def cognitive_panel_default() -> Dict[str, Any]:
    """Default user cognitive state (could be persisted later)."""
    return {
        "improving": ["panic recognition", "leadership sensitivity", "time-price awareness"],
        "weakness": ["late-stage exits", "emotional attachment"],
        "focus": "profit protection structures (锁利结构)",
    }


# ─────────────────────────────────────────────
# COMPILE ALL
# ─────────────────────────────────────────────
def compile_market_runtime(watchlist_path: str = "watchlist.json") -> Dict[str, Any]:
    """One-stop call: returns the complete market command center state."""
    macro = fetch_macro_signals()
    regime = classify_regime(macro)
    return {
        "compiled_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "macro": macro,
        "regime": regime,
        "regime_narrative": regime_chinese_narrative(regime),
        "narratives": compute_narrative_heatmap(),
        "leadership": compute_leadership_board(),
        "opportunities": detect_opportunities(watchlist_path),
        "dangers": detect_dangers(watchlist_path),
        "attention": attention_map(watchlist_path),
        "memory": market_memory(),
        "cognitive": cognitive_panel_default(),
    }
