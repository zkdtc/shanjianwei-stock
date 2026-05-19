"""
AMOS AI Market Language Engine
================================
Convert structured signals into coherent Chinese runtime prose.
This is the "认知翻译层" — turns raw indicators into market narrative.
"""
from __future__ import annotations
from typing import Any, Dict, List


def translate_hero(hero: Dict, nar_state: Dict) -> str:
    """Hero runtime → connected Chinese sentence(s)."""
    ticker = hero.get("ticker", "")
    identity = hero.get("identity", "")
    reg = hero.get("current_regime", "")
    phase = nar_state.get("phase", "")
    lto = nar_state.get("long_term_outlook", "")
    exec_st = hero.get("execution_state", "")
    risk = hero.get("current_risk", "")
    lead = hero.get("leadership_dependency", "")

    parts = []
    # Identity opener
    parts.append(f"{ticker} 当前更像：{identity} 中的「{reg}」阶段。")
    # Narrative phase
    if "Compression" in phase or "Late" in phase:
        parts.append(f"Narrative 正在 {phase}，但并未死亡。")
    elif "Expansion" in phase:
        parts.append(f"Narrative 处于 {phase}，资金风险偏好支持当前结构。")
    else:
        parts.append(f"Narrative 阶段：{phase}。")
    # Long-term outlook
    parts.append(f"长期判断：{lto}")
    # Leadership
    if "Strong" in lead:
        parts.append("由于 NVDA 龙头未坏，当前更像中期 compression 而非 collapse。")
    elif "Wobbling" in lead:
        parts.append("⚠️ NVDA 龙头出现动摇，需提高对结构切换的警惕。")
    # Execution
    parts.append(f"执行状态：{exec_st} — {hero.get('execution_desc','')}")
    # Risk
    if risk and risk != "可控":
        parts.append(f"当前主要风险：{risk}。")
    return " ".join(parts)


def translate_valuation(val: Dict, meta: Dict) -> str:
    """Valuation stack → narrative explanation."""
    if not val:
        return "估值数据不可用。"
    zone = val.get("zone", "")
    discount = val.get("discount_narrative", "")
    cv = val.get("conservative")
    base = val.get("base")
    bull = val.get("bull")
    eup = val.get("euphoria")
    cp = val.get("current_price")
    parts = []
    parts.append(f"当前价 ${cp:.2f} 处于：{zone}")
    parts.append(f"估值堆叠：Conservative ${cv} | Base ${base} | Bull ${bull} | Euphoria ${eup}。")
    parts.append(discount + "。")

    if "Conservative" in zone or "💎" in zone or "💀" in zone:
        parts.append("核心矛盾不在业务，而在市场是否愿意继续相信底线估值之上的 Narrative。"
                     " 任何 Narrative 修复都可能带来估值快速恢复。")
    elif "Bull" in zone or "Euphoria" in zone:
        parts.append("当前估值压力主要来自 Narrative 扩张溢价，市场对未来兑现速度的要求会越来越高。"
                     " 此阶段需特别警惕「利好不涨」。")
    else:
        parts.append("当前估值合理，市场尚未给出过度溢价或过度压制。")
    return " ".join(parts)


def translate_time_price(gann: Dict, ind: Dict) -> str:
    """Gann + time-price → narrative."""
    if not gann or "error" in gann:
        return "时间-价格数据不可用。"
    price = ind.get("price", 0)
    rsi = ind.get("rsi_14", 50)

    # Find closest support/resistance
    closest = gann.get("closest_levels", {})
    nr = closest.get("next_resistances", [])
    ns = closest.get("next_supports_from_top", [])

    parts = []
    # Time-price alignment
    res_str = f"${nr[0]['target']:.2f} ({nr[0]['degrees']}°)" if nr else "—"
    sup_str = f"${ns[0]['target']:.2f} ({ns[0]['degrees']}°)" if ns else "—"
    parts.append(f"江恩结构：上方阻力 {res_str}，下方支撑 {sup_str}。")

    # Resonance
    if gann.get("time_resonance_days"):
        d = gann["time_resonance_days"][0]
        parts.append(f"🔥 时间共振日：{d['date']} (距今 {d['days_from_today']}天) — 多周期重合的高变盘概率日。")

    # RSI + structure read
    if rsi < 30:
        parts.append("当前 RSI 极度超卖，叠加江恩支撑常引发短线反弹。")
    elif rsi > 75:
        parts.append("RSI 超买，结构进入「时间敏感阶段」，下一次震荡的概率上升。")

    # Critical upcoming
    upcoming = gann.get("upcoming_windows", [])
    crit = [w for w in upcoming if w.get("is_critical")][:2]
    if crit:
        parts.append("关键时间窗：" + " · ".join([f"{w['target_date']} ({w['cycle_label']})" for w in crit]))
    return " ".join(parts)


def translate_technical_regime(mtf: Dict) -> str:
    """Multi-timeframe → narrative."""
    if not mtf or "error" in mtf:
        return "多周期数据不可用。"
    w = mtf.get("weekly", {})
    d = mtf.get("daily", {})
    h = mtf.get("hourly", {})
    parts = []
    # Weekly
    wt = w.get("ma_arrangement", "")
    if "多头排列" in wt:
        parts.append("周线趋势完整，长周期多头结构未坏。")
    elif "空头" in wt:
        parts.append("⚠️ 周线进入空头排列，长周期结构受损。")
    # Daily
    rsi_d = d.get("rsi_14", 50)
    if rsi_d < 35:
        parts.append("日线进入超卖，开始呈现 panic 后平衡阶段。")
    elif rsi_d > 70:
        parts.append("日线 RSI 超买，警惕高位震荡。")
    # Hourly
    rsi_h = h.get("rsi_14", 50)
    if rsi_h < 25:
        parts.append("1小时 RSI 极度超卖 — 通常引发短期技术性抽头。")
    elif rsi_h > 80:
        parts.append("1小时 RSI 超买 — 短线追涨风险高。")
    # Volume Profile
    vp = mtf.get("volume_profile", {})
    if vp:
        parts.append(f"筹码 POC 在 ${vp['poc']['price_mid']:.2f}，VA: ${vp['value_area_low']:.2f}–${vp['value_area_high']:.2f}。")
    return " ".join(parts)


def translate_options(options: Dict) -> str:
    """Options structure → narrative."""
    if not options or "error" in options:
        return "期权数据不可用。"
    iv = options.get("iv_regime", {})
    flip = options.get("flip", {})
    walls = options.get("walls", {})
    parts = []
    iv_level = iv.get("iv_level", "")
    iv_avg = iv.get("atm_iv_avg", 0)
    if iv_avg:
        parts.append(f"当前 IV={iv_avg:.0f}% ({iv_level})。")
    pcr_sig = options.get("pcr_signal", "")
    if pcr_sig:
        parts.append(pcr_sig)
    reg = flip.get("regime")
    if reg == "负Gamma":
        parts.append("Dealer Gamma 为负 — 市场波动会被放大，警惕追涨杀跌情绪。")
    elif reg == "正Gamma":
        parts.append("Dealer Gamma 为正 — 波动会被压制，区间震荡概率高。")
    if walls.get("call_wall_strike"):
        parts.append(f"Call Wall ${walls['call_wall_strike']:.2f} 是上方关键阻力，无法突破则继续震荡压缩。")
    if walls.get("put_wall_strike"):
        parts.append(f"Put Wall ${walls['put_wall_strike']:.2f} 是下方主动防御位。")
    return " ".join(parts)


def translate_flow(money: Dict) -> str:
    """Money flow → narrative."""
    if not money or "error" in money:
        return "资金流数据不可用。"
    parts = []
    obv = money.get("obv_divergence", "")
    ad = money.get("ad_signal", "")
    if obv:
        parts.append(f"OBV：{obv}")
    if ad:
        parts.append(f"A/D：{ad}")
    intent = money.get("main_intent", [])
    if intent:
        parts.append("主力意图：" + "；".join(intent[:2]))
    return " ".join(parts)


def translate_runtime(runtime: Dict) -> Dict[str, str]:
    """Return all narrative sections."""
    hero = runtime.get("hero", {})
    nar_state = runtime.get("narrative_state", {})
    val = runtime.get("valuation_stack", {})
    gann = runtime.get("gann", {})
    ind = runtime.get("indicators", {})
    mtf = runtime.get("mtf", {})
    options = runtime.get("options", {})
    money = runtime.get("money", {})
    meta = runtime.get("meta", {})

    return {
        "hero_narrative": translate_hero(hero, nar_state),
        "valuation_narrative": translate_valuation(val, meta),
        "time_price_narrative": translate_time_price(gann, ind),
        "technical_narrative": translate_technical_regime(mtf),
        "options_narrative": translate_options(options),
        "flow_narrative": translate_flow(money),
    }
