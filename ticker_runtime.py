"""
AMOS Ticker Runtime
====================
Hero Runtime · Narrative Positioning · Valuation Stack (Conservative/Base/Bull/Euphoria)
Gann+Time-Price · Technical Regime · Options · Flow · Execution State
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
import yfinance as yf

from radar_rules import fetch_price_data, calc_indicators
from gann_sq9 import full_gann_analysis
from multi_timeframe import multi_timeframe_analysis
from money_flow import analyze_money_flow
from options_gamma import full_structural_analysis, get_expirations
from gann_time import get_next_earnings


# ─────────────────────────────────────────────
# 1. HERO RUNTIME — TOP STATE LINE
# ─────────────────────────────────────────────
def classify_execution_state(price: float, ind: Dict, mtf: Dict,
                             options: Dict, gann: Dict) -> Dict[str, str]:
    """
    Classify execution state:
      - LONG-TERM HOLD: trend intact + value zone + low IV
      - STRATEGIC: trend up + reasonable value
      - TACTICAL: panic compression / extreme readings → only nimble plays
      - WAIT: nothing actionable / unclear regime
      - DEFENSE: trend broken / dangerous setup
    """
    daily = mtf.get("daily", {}) if mtf else {}
    weekly = mtf.get("weekly", {}) if mtf else {}
    rsi = daily.get("rsi_14", 50)
    weekly_trend = weekly.get("ma_arrangement", "")
    daily_trend = daily.get("ma_arrangement", "")

    iv_regime = options.get("iv_regime", {}) if options else {}
    iv_level = iv_regime.get("iv_level", "")
    flip = options.get("flip", {}) if options else {}
    regime = flip.get("regime", "")

    if "多头排列" in weekly_trend and "多头排列" in daily_trend and "极低" not in iv_level and rsi < 70:
        state = "STRATEGIC"
        color = "🟢"
        desc = "趋势完整且估值合理 — 适合战略性建仓/持有"
    elif "多头" in weekly_trend and (rsi < 35 or "PANIC" in str(options.get("alerts", []))):
        state = "TACTICAL"
        color = "🟡"
        desc = "大趋势完好但短期超卖 — 适合节奏性介入"
    elif "多头" in weekly_trend and rsi > 75 and "高" in iv_level:
        state = "DEFENSE"
        color = "🟠"
        desc = "高位高IV — 锁利/卖covered call/不追高"
    elif "空头" in weekly_trend or "空头" in daily_trend:
        state = "WAIT"
        color = "🔴"
        desc = "趋势走弱 — 暂时观望，等待结构修复"
    else:
        state = "TACTICAL"
        color = "🟡"
        desc = "中性状态 — 只做高确信度战术机会"
    return {"state": state, "color": color, "desc": desc}


def hero_runtime(ticker: str, meta: Dict, ind: Dict, mtf: Dict,
                 options: Dict, gann: Dict, macro_regime: Dict) -> Dict[str, Any]:
    """Build hero runtime line."""
    price = ind.get("price", 0)
    rsi = ind.get("rsi_14", 50)

    # Narrative strength
    chg_20d = mtf.get("daily", {}).get("chg_pct", 0) if mtf else 0
    if abs(chg_20d) > 5:
        nar_strength = "Volatile but Intact"
    elif chg_20d > 0:
        nar_strength = "Intact"
    else:
        nar_strength = "Compressed"

    # Leadership dependency: if it's NVDA → none, else → dependency on AI sector
    sector = meta.get("sector", "")
    if "Infra" in sector or "AI" in sector:
        leadership_dep = "NVDA Strong" if macro_regime.get("leadership", "").startswith("NVDA intact") else "NVDA Wobbling ⚠️"
    else:
        leadership_dep = "Independent"

    # Liquidity state
    vol_ratio = ind.get("vol_ratio", 1.0)
    if vol_ratio > 1.5:
        liq_state = "Volatile (高换手)"
    elif vol_ratio > 1.1:
        liq_state = "Active"
    else:
        liq_state = "Quiet"

    # Current risk
    iv_regime = options.get("iv_regime", {}) if options else {}
    flip = options.get("flip", {}) if options else {}
    risks = []
    if iv_regime.get("atm_iv_avg", 0) > 60:
        risks.append(f"高IV ({iv_regime['atm_iv_avg']:.0f}%)")
    if flip.get("regime") == "负Gamma":
        risks.append("负Gamma")
    if rsi > 75:
        risks.append("RSI超买")
    elif rsi < 25:
        risks.append("RSI超卖")
    current_risk = " + ".join(risks) if risks else "可控"

    # Current Regime label (state-aware)
    if "Panic" in str(meta.get("notes", "")) or rsi < 30:
        cur_regime = "Tactical Repair Attempt"
    elif rsi > 75 and chg_20d > 10:
        cur_regime = "Late-stage Expansion / High Risk"
    elif chg_20d > 5:
        cur_regime = "Expansion in Progress"
    elif chg_20d < -5:
        cur_regime = "Compression"
    else:
        cur_regime = "Consolidation"

    # Identify
    identity = meta.get("market_identity", "—")

    exec_st = classify_execution_state(price, ind, mtf, options, gann)

    return {
        "ticker": ticker,
        "identity": identity,
        "current_regime": cur_regime,
        "narrative_strength": nar_strength,
        "leadership_dependency": leadership_dep,
        "liquidity_state": liq_state,
        "execution_state": exec_st["state"],
        "execution_color": exec_st["color"],
        "execution_desc": exec_st["desc"],
        "current_risk": current_risk,
        "price": price,
    }


# ─────────────────────────────────────────────
# 2. NARRATIVE POSITIONING TREE
# ─────────────────────────────────────────────
def narrative_tree(meta: Dict) -> List[str]:
    """Build narrative tree from layer + sector + ticker."""
    layer = meta.get("mainline_layer", "")
    sector = meta.get("sector", "")
    pos = meta.get("mainline_position", "")
    parts = ["AI"]
    if "Infra" in layer:
        parts.append("AI Infrastructure")
        if "Networking" in sector or "Optic" in sector or "Photonics" in sector:
            parts.append("Networking / Optics")
        elif "ASIC" in sector or "GPU" in sector:
            parts.append("GPU / ASIC Compute")
        elif "Mining" in sector or "Datacenter" in sector:
            parts.append("BTC Mining / AI Datacenter")
    elif "Platform" in layer:
        parts.append("AI Platform / Cloud")
    elif "Application" in layer:
        parts.append("AI Application")
        if "Healthcare" in sector:
            parts.append("AI Healthcare")
        elif "Cybersecurity" in sector or "Security" in sector:
            parts.append("AI Cybersecurity")
        elif "Fintech" in sector or "Crypto" in sector:
            parts.append("Fintech / Crypto-Adjacent")
        elif "Robotic" in sector or "EV" in sector:
            parts.append("Robotics / Autonomy")
    parts.append(meta.get("ticker", ""))
    return parts


def narrative_runtime_state(meta: Dict, ind: Dict, mtf: Dict,
                            narrative_state: Optional[Dict] = None) -> Dict[str, str]:
    """Describe narrative phase: expansion/compression/late-stage."""
    daily = mtf.get("daily", {}) if mtf else {}
    weekly = mtf.get("weekly", {}) if mtf else {}
    chg_w = weekly.get("chg_pct", 0)
    rsi_d = daily.get("rsi_14", 50)

    if chg_w > 5 and rsi_d < 65:
        phase = "Expansion"
    elif chg_w > 0 and rsi_d > 70:
        phase = "Expansion → Late Stage"
    elif chg_w < -3:
        phase = "Compression"
    elif chg_w < 0:
        phase = "Cooling"
    else:
        phase = "Consolidation"

    # Crowding (proxy from volume ratio and 20d momentum)
    vol_r = ind.get("vol_ratio", 1.0)
    if vol_r > 1.5 and ind.get("momentum_20d", 0) > 10:
        crowding = "High"
    elif vol_r > 1.2:
        crowding = "Moderate"
    else:
        crowding = "Low"

    # Narrative risk
    if phase == "Expansion → Late Stage":
        nar_risk = "Moderate-High"
    elif phase == "Compression":
        nar_risk = "Moderate"
    elif phase == "Expansion":
        nar_risk = "Low-Moderate"
    else:
        nar_risk = "Low"

    # Long term outlook (from discount horizon)
    horizon = meta.get("discount_horizon", "")
    if "2028" in horizon or "2030" in horizon:
        lto = "Still Structurally Bullish (长期看好)"
    elif "切换" in horizon or "1-2季度" in horizon:
        lto = "Identity-Transition Phase (身份切换中)"
    else:
        lto = "Stable / Mature"

    return {
        "phase": phase,
        "crowding": crowding,
        "narrative_risk": nar_risk,
        "long_term_outlook": lto,
    }


# ─────────────────────────────────────────────
# 3. VALUATION STACK (Conservative / Base / Bull / Euphoria)
# ─────────────────────────────────────────────
def valuation_stack(meta: Dict, ind: Dict) -> Dict[str, Any]:
    """
    Build the 4-layer valuation stack.
    - Conservative = bottom_valuation (基本面底线)
    - Base = consensus_valuation (中性预期)
    - Bull = consensus * 1.35 (Narrative扩张)
    - Euphoria = consensus * 1.75 (情绪溢价)
    """
    cv = meta.get("consensus_valuation", 0)
    bv = meta.get("bottom_valuation", 0)
    price = ind.get("price", 0)
    if not cv or not bv:
        return {}
    conservative = bv
    base = cv
    bull = round(cv * 1.35, 2)
    euphoria = round(cv * 1.75, 2)

    # Where are we?
    if price < conservative:
        zone = "💀 Below Conservative (恐慌 / 底线被破)"
    elif price < (conservative + base) / 2:
        zone = "💎 Conservative Zone (低估)"
    elif price < base:
        zone = "🟢 Below Base (合理偏低)"
    elif price < bull:
        zone = "🟡 Base → Bull (合理至乐观)"
    elif price < euphoria:
        zone = "🟠 Bull Zone (高估，Narrative扩张)"
    else:
        zone = "🔴 Euphoria Zone (情绪溢价)"

    # Discounting
    horizon = meta.get("discount_horizon", "")
    if "2028" in horizon or "2030" in horizon:
        discount = "市场正在交易 2028-2030 (远期Narrative)"
    elif "2027" in horizon:
        discount = "市场正在交易 2027 (中期Narrative)"
    elif "2026" in horizon:
        discount = "市场正在交易 2026 (近期业绩兑现)"
    elif "切换" in horizon:
        discount = "市场尚未完全接受新身份"
    else:
        discount = horizon

    return {
        "conservative": conservative,
        "base": base,
        "bull": bull,
        "euphoria": euphoria,
        "current_price": price,
        "zone": zone,
        "discount_narrative": discount,
        "distance_to_conservative_pct": round((price - conservative) / conservative * 100, 1),
        "distance_to_base_pct": round((price - base) / base * 100, 1),
    }


# ─────────────────────────────────────────────
# COMPILE ALL: TICKER RUNTIME
# ─────────────────────────────────────────────
def compile_ticker_runtime(ticker: str, watchlist_path: str = "watchlist.json",
                           macro_regime: Optional[Dict] = None) -> Dict[str, Any]:
    """One-stop call: build full ticker runtime."""
    # Load meta
    with open(watchlist_path, "r", encoding="utf-8") as f:
        wl = json.load(f)
    meta = next((s for s in wl["stocks"] if s["ticker"] == ticker), None)
    if not meta:
        return {"error": f"{ticker} not in watchlist"}

    # Indicators
    df = fetch_price_data(ticker, "1y")
    if df.empty:
        return {"error": f"No data for {ticker}"}
    ind = calc_indicators(df)

    # Sub-analyses
    gann = full_gann_analysis(ticker)
    mtf = multi_timeframe_analysis(ticker)
    money = analyze_money_flow(ticker)
    try:
        exps = get_expirations(ticker)
        opt = full_structural_analysis(ticker, exps[0]) if exps else {"error": "no exp"}
    except Exception as e:
        opt = {"error": str(e)}
    try:
        earnings = get_next_earnings(ticker)
    except Exception:
        earnings = {}

    if macro_regime is None:
        from runtime_engine import fetch_macro_signals, classify_regime
        macro_regime = classify_regime(fetch_macro_signals())

    hero = hero_runtime(ticker, meta, ind, mtf, opt, gann, macro_regime)
    tree = narrative_tree(meta)
    nar_state = narrative_runtime_state(meta, ind, mtf)
    val_stack = valuation_stack(meta, ind)

    return {
        "ticker": ticker,
        "name": meta.get("name", ticker),
        "meta": meta,
        "indicators": ind,
        "hero": hero,
        "narrative_tree": tree,
        "narrative_state": nar_state,
        "valuation_stack": val_stack,
        "gann": gann,
        "mtf": mtf,
        "money": money,
        "options": opt,
        "earnings": earnings,
        "compiled_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
