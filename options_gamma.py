"""
options_gamma.py
期权链 + Gamma状态追踪
- 期权链下载（call/put）
- IV / OI / Volume
- Max Pain
- Gamma Exposure（GEX）
- Put/Call ratio
- 最关键价格轴（high OI strikes）
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date
import math


# ─────────────────────────────────────────────
#  下载期权链
# ─────────────────────────────────────────────

def get_expirations(ticker: str) -> list:
    """获取所有可用的到期日"""
    try:
        t = yf.Ticker(ticker)
        return list(t.options)
    except Exception:
        return []


def get_option_chain(ticker: str, expiration: str = None) -> dict:
    """
    获取期权链。
    expiration=None 则取最近的到期日。
    返回 {expiration, calls_df, puts_df, spot}
    """
    try:
        t = yf.Ticker(ticker)
        exps = list(t.options)
        if not exps:
            return {"error": "无期权数据"}

        if expiration is None:
            expiration = exps[0]
        if expiration not in exps:
            return {"error": f"到期日 {expiration} 不存在"}

        chain = t.option_chain(expiration)
        calls = chain.calls.copy()
        puts = chain.puts.copy()
        spot = float(t.fast_info.last_price)

        return {
            "ticker": ticker,
            "expiration": expiration,
            "calls": calls,
            "puts": puts,
            "spot": spot,
            "all_expirations": exps,
        }
    except Exception as e:
        return {"error": f"获取失败: {e}"}


# ─────────────────────────────────────────────
#  关键指标
# ─────────────────────────────────────────────

def calc_pcr(calls: pd.DataFrame, puts: pd.DataFrame) -> dict:
    """Put/Call ratio (基于OI和Volume)"""
    call_oi = calls["openInterest"].sum() if "openInterest" in calls.columns else 0
    put_oi = puts["openInterest"].sum() if "openInterest" in puts.columns else 0
    call_vol = calls["volume"].sum() if "volume" in calls.columns else 0
    put_vol = puts["volume"].sum() if "volume" in puts.columns else 0

    pcr_oi = put_oi / call_oi if call_oi > 0 else 0
    pcr_vol = put_vol / call_vol if call_vol > 0 else 0

    return {
        "call_oi": int(call_oi),
        "put_oi": int(put_oi),
        "call_vol": int(call_vol),
        "put_vol": int(put_vol),
        "pcr_oi": round(pcr_oi, 2),
        "pcr_vol": round(pcr_vol, 2),
    }


def pcr_signal(pcr_vol: float) -> str:
    """PCR信号解读"""
    if pcr_vol < 0.5:
        return "🔴 极度看多（PCR<0.5，市场过于乐观，警惕反向）"
    elif pcr_vol < 0.7:
        return "🟠 看多（PCR<0.7，偏乐观）"
    elif pcr_vol < 1.0:
        return "🟡 中性偏多（PCR<1.0）"
    elif pcr_vol < 1.3:
        return "🟡 中性偏空（PCR>1.0）"
    else:
        return "🟢 极度看空（PCR>1.3，恐慌情绪，关注反弹）"


def calc_max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> float:
    """
    Max Pain - 做市商最希望股价到达的位置（最大痛点）。
    在该价格，期权买方总损失最大，做市商总盈利最大。
    """
    if calls.empty or puts.empty:
        return 0.0

    strikes = sorted(set(calls["strike"].tolist() + puts["strike"].tolist()))
    pain_values = {}

    for strike in strikes:
        # Call买方损失：在该价格下，所有更低strike的call都有价值
        call_loss = sum(
            (strike - row["strike"]) * row["openInterest"]
            for _, row in calls.iterrows()
            if row["strike"] < strike
        )
        # Put买方损失
        put_loss = sum(
            (row["strike"] - strike) * row["openInterest"]
            for _, row in puts.iterrows()
            if row["strike"] > strike
        )
        pain_values[strike] = call_loss + put_loss

    if not pain_values:
        return 0.0

    # Max Pain = 使期权买方总价值最低的strike
    max_pain = min(pain_values, key=pain_values.get)
    return float(max_pain)


def calc_gex(calls: pd.DataFrame, puts: pd.DataFrame, spot: float) -> dict:
    """
    Gamma Exposure (GEX) - 做市商净gamma敞口
    正GEX：做市商持有正gamma，会平抑波动
    负GEX：做市商持有负gamma，会放大波动
    """
    if "gamma" not in calls.columns or calls.empty:
        # yfinance有时不返回gamma，自己估算
        return _estimate_gex_simple(calls, puts, spot)

    # 简化模型：做市商通常是call的卖方+put的买方相反
    # 但常用做法是 GEX = sum(call_gamma * OI) - sum(put_gamma * OI)
    call_gex = (calls["gamma"].fillna(0) * calls["openInterest"].fillna(0) * 100).sum()
    put_gex = (puts["gamma"].fillna(0) * puts["openInterest"].fillna(0) * 100).sum()
    net_gex = call_gex - put_gex

    return {
        "call_gex": float(call_gex),
        "put_gex": float(put_gex),
        "net_gex": float(net_gex),
        "interpretation": _interpret_gex(net_gex),
    }


def _estimate_gex_simple(calls: pd.DataFrame, puts: pd.DataFrame, spot: float) -> dict:
    """没有gamma字段时用OI集中度近似估算"""
    if calls.empty or puts.empty:
        return {"error": "无期权OI数据"}

    # 用OI集中在ATM附近作为gamma proxy（gamma在ATM最大）
    atm_range = spot * 0.05  # ATM ±5%
    atm_call_oi = calls[
        (calls["strike"] >= spot - atm_range) &
        (calls["strike"] <= spot + atm_range)
    ]["openInterest"].sum()
    atm_put_oi = puts[
        (puts["strike"] >= spot - atm_range) &
        (puts["strike"] <= spot + atm_range)
    ]["openInterest"].sum()

    # 估算GEX（粗略）
    net_proxy = (atm_call_oi - atm_put_oi) * spot * 0.01

    return {
        "call_gex": float(atm_call_oi),
        "put_gex": float(atm_put_oi),
        "net_gex": float(net_proxy),
        "interpretation": _interpret_gex(net_proxy),
        "note": "估算值（yfinance未返回gamma）",
    }


def _interpret_gex(net_gex: float) -> str:
    if net_gex > 1e7:
        return "🟢 大幅正GEX：做市商被动平抑波动，股价被锁在区间内"
    elif net_gex > 0:
        return "🟡 偏正GEX：温和稳定，方向走出需要催化"
    elif net_gex > -1e7:
        return "🟠 偏负GEX：波动放大，注意短期剧烈波动"
    else:
        return "🔴 大幅负GEX：做市商追涨杀跌，可能出现踩踏或暴拉"


# ─────────────────────────────────────────────
#  关键价格位（high OI strikes）
# ─────────────────────────────────────────────

def find_key_strikes(calls: pd.DataFrame, puts: pd.DataFrame, spot: float, top_n: int = 5) -> dict:
    """找出call/put OI最高的几个strike，这些是关键价格位"""
    top_call = calls.nlargest(top_n, "openInterest")[["strike", "openInterest", "volume", "impliedVolatility"]].copy()
    top_put = puts.nlargest(top_n, "openInterest")[["strike", "openInterest", "volume", "impliedVolatility"]].copy()

    # 距现价百分比
    top_call["距现价%"] = ((top_call["strike"] - spot) / spot * 100).round(1)
    top_put["距现价%"] = ((top_put["strike"] - spot) / spot * 100).round(1)

    # 阻力位 = call OI最高的strike（call wall）
    call_wall = float(top_call.iloc[0]["strike"]) if not top_call.empty else spot
    # 支撑位 = put OI最高的strike（put wall）
    put_wall = float(top_put.iloc[0]["strike"]) if not top_put.empty else spot

    return {
        "top_call_strikes": top_call,
        "top_put_strikes": top_put,
        "call_wall": call_wall,
        "put_wall": put_wall,
    }


# ─────────────────────────────────────────────
#  IV 分析
# ─────────────────────────────────────────────

def calc_iv_summary(calls: pd.DataFrame, puts: pd.DataFrame, spot: float) -> dict:
    """ATM IV 摘要"""
    if "impliedVolatility" not in calls.columns:
        return {}

    # 找最接近现价的strike
    calls_sorted = calls.iloc[(calls["strike"] - spot).abs().argsort()].head(3)
    puts_sorted = puts.iloc[(puts["strike"] - spot).abs().argsort()].head(3)

    atm_call_iv = calls_sorted["impliedVolatility"].mean() * 100
    atm_put_iv = puts_sorted["impliedVolatility"].mean() * 100
    iv_skew = atm_put_iv - atm_call_iv

    if iv_skew > 5:
        skew_signal = "🔴 Put偏度高：市场偏向恐慌，下跌保护需求强"
    elif iv_skew > 0:
        skew_signal = "🟡 轻微Put偏度：正常防御性"
    elif iv_skew > -3:
        skew_signal = "🟢 中性偏度"
    else:
        skew_signal = "🔥 Call偏度高：市场追多情绪强（可能过热）"

    return {
        "atm_call_iv": round(atm_call_iv, 1),
        "atm_put_iv": round(atm_put_iv, 1),
        "iv_skew": round(iv_skew, 1),
        "skew_signal": skew_signal,
    }


# ─────────────────────────────────────────────
#  完整期权报告
# ─────────────────────────────────────────────

def compile_options_report(ticker: str, expiration: str = None) -> dict:
    """完整期权报告"""
    chain = get_option_chain(ticker, expiration)
    if "error" in chain:
        return chain

    calls = chain["calls"]
    puts = chain["puts"]
    spot = chain["spot"]

    pcr = calc_pcr(calls, puts)
    max_pain = calc_max_pain(calls, puts)
    gex = calc_gex(calls, puts, spot)
    key_strikes = find_key_strikes(calls, puts, spot)
    iv = calc_iv_summary(calls, puts, spot)

    # 距Max Pain的百分比
    mp_distance = (max_pain - spot) / spot * 100 if spot > 0 else 0

    if abs(mp_distance) < 2:
        mp_signal = "🟡 已在Max Pain附近，做市商无强引力"
    elif mp_distance > 0:
        mp_signal = f"🟢 Max Pain在上方({mp_distance:+.1f}%)，做市商倾向把价格拉到此处"
    else:
        mp_signal = f"🔴 Max Pain在下方({mp_distance:+.1f}%)，做市商倾向把价格压到此处"

    return {
        "ticker": ticker,
        "expiration": chain["expiration"],
        "all_expirations": chain["all_expirations"],
        "spot": spot,
        "pcr": pcr,
        "pcr_signal": pcr_signal(pcr["pcr_vol"]),
        "max_pain": max_pain,
        "max_pain_distance_pct": round(mp_distance, 2),
        "max_pain_signal": mp_signal,
        "gex": gex,
        "key_strikes": key_strikes,
        "iv": iv,
        "compiled_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ─────────────────────────────────────────────
#  结构化分析：Gamma Flip / Wall强度 / IV制度
# ─────────────────────────────────────────────

def find_gamma_flip(calls: pd.DataFrame, puts: pd.DataFrame, spot: float) -> dict:
    """
    估算 Gamma Flip 点 — net gamma 从正翻负的strike
    spot > flip：正Gamma环境（做市商压波动，区间震荡）
    spot < flip：负Gamma环境（做市商追涨杀跌，波动放大）
    """
    if calls.empty or puts.empty or "openInterest" not in calls.columns:
        return {}

    lo = max(spot * 0.5, 0.01)
    hi = spot * 1.5
    strikes = sorted(set(
        calls[(calls["strike"] >= lo) & (calls["strike"] <= hi)]["strike"].tolist() +
        puts[(puts["strike"] >= lo) & (puts["strike"] <= hi)]["strike"].tolist()
    ))
    if not strikes:
        return {}

    # 在每个strike，做市商的净gamma敞口（call通常做市商卖出=负gamma；put通常做市商卖出=负gamma）
    # 用OI权重做近似：call OI集中区域 = 做市商需要buy delta = supports up moves
    # 简化模型：spot到strike的距离越近，gamma越大
    net_by_strike = {}
    for k in strikes:
        c_oi = float(calls[calls["strike"] == k]["openInterest"].sum() if not calls.empty else 0)
        p_oi = float(puts[puts["strike"] == k]["openInterest"].sum() if not puts.empty else 0)
        # 简化gamma proxy：OI / (1 + |spot-k|/spot * 10)，距越近影响越大
        proximity = 1 / (1 + abs(spot - k) / max(spot * 0.05, 0.5))
        net_by_strike[k] = (c_oi - p_oi) * proximity

    # 累积净gamma从最低strike往上累
    cumulative = 0
    flip_strike = None
    prev_sign = None
    for k in strikes:
        cumulative += net_by_strike[k]
        sign = 1 if cumulative > 0 else (-1 if cumulative < 0 else 0)
        if prev_sign is not None and sign != prev_sign and sign != 0:
            flip_strike = k
            break
        prev_sign = sign if sign != 0 else prev_sign

    if flip_strike is None:
        # 全部同号
        return {
            "flip_strike": None,
            "regime": "正Gamma" if cumulative > 0 else "负Gamma",
            "regime_signal": (
                "🟢 全程正Gamma：股价受到做市商压制，区间震荡为主"
                if cumulative > 0
                else "🔴 全程负Gamma：做市商追涨杀跌，波动剧烈"
            ),
        }

    in_positive = spot > flip_strike
    return {
        "flip_strike": float(flip_strike),
        "flip_distance_pct": round((spot - flip_strike) / spot * 100, 2),
        "regime": "正Gamma" if in_positive else "负Gamma",
        "regime_signal": (
            f"🟢 正Gamma环境（spot ${spot:.2f} > flip ${flip_strike:.2f}）：做市商被动稳定，趋势受抑制"
            if in_positive
            else f"🔴 负Gamma环境（spot ${spot:.2f} < flip ${flip_strike:.2f}）：做市商被迫追涨杀跌，趋势放大"
        ),
    }


def analyze_wall_strength(calls: pd.DataFrame, puts: pd.DataFrame, spot: float) -> dict:
    """
    Wall强度分析：Call Wall / Put Wall 的 OI / 距现价 / 突破后果
    """
    if calls.empty or puts.empty:
        return {}

    # Wall = 现价附近20%范围内OI最高
    lo, hi = spot * 0.8, spot * 1.2
    c_local = calls[(calls["strike"] >= spot) & (calls["strike"] <= hi)].sort_values("openInterest", ascending=False)
    p_local = puts[(puts["strike"] <= spot) & (puts["strike"] >= lo)].sort_values("openInterest", ascending=False)

    if c_local.empty or p_local.empty:
        return {}

    call_wall_strike = float(c_local.iloc[0]["strike"])
    call_wall_oi = int(c_local.iloc[0]["openInterest"])
    put_wall_strike = float(p_local.iloc[0]["strike"])
    put_wall_oi = int(p_local.iloc[0]["openInterest"])

    # OI总量做参考
    avg_call_oi = float(calls["openInterest"].mean())
    avg_put_oi = float(puts["openInterest"].mean())

    # 强度评分（OI / 平均OI）
    call_wall_strength = call_wall_oi / avg_call_oi if avg_call_oi > 0 else 1
    put_wall_strength = put_wall_oi / avg_put_oi if avg_put_oi > 0 else 1

    # 距现价
    call_wall_pct = (call_wall_strike - spot) / spot * 100
    put_wall_pct = (spot - put_wall_strike) / spot * 100

    # 上下空间不对称提示
    if call_wall_pct < put_wall_pct * 0.6:
        asymmetry = "📉 Call Wall更近：上方阻力比下方支撑近，向上空间被压"
    elif put_wall_pct < call_wall_pct * 0.6:
        asymmetry = "📈 Put Wall更近：下方支撑比上方阻力近，向下空间被托"
    else:
        asymmetry = "⚖️ 上下空间对称"

    # Wall强度等级
    def _wall_grade(s):
        if s > 5:
            return "🏰 极强（OI比平均高5倍+）"
        elif s > 3:
            return "🧱 很强"
        elif s > 1.5:
            return "🪨 中等"
        else:
            return "💧 弱"

    return {
        "call_wall_strike": call_wall_strike,
        "call_wall_oi": call_wall_oi,
        "call_wall_pct_above": round(call_wall_pct, 2),
        "call_wall_strength": round(call_wall_strength, 1),
        "call_wall_grade": _wall_grade(call_wall_strength),
        "put_wall_strike": put_wall_strike,
        "put_wall_oi": put_wall_oi,
        "put_wall_pct_below": round(put_wall_pct, 2),
        "put_wall_strength": round(put_wall_strength, 1),
        "put_wall_grade": _wall_grade(put_wall_strength),
        "asymmetry": asymmetry,
    }


def analyze_iv_regime(iv: dict, ticker: str = None) -> dict:
    """
    IV制度分析：当前IV处于什么水平、是否过高/过低
    """
    if not iv:
        return {}

    atm_call = iv.get("atm_call_iv", 0)
    atm_put = iv.get("atm_put_iv", 0)
    avg_iv = (atm_call + atm_put) / 2

    # 估算HV（如果ticker给出，可以从历史算实际波动率）
    hv_20 = None
    if ticker:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2mo")
            if not hist.empty and len(hist) > 20:
                rets = np.log(hist["Close"] / hist["Close"].shift(1)).dropna()
                hv_20 = float(rets.std() * np.sqrt(252) * 100)
        except Exception:
            pass

    # IV/HV ratio
    iv_hv = avg_iv / hv_20 if hv_20 and hv_20 > 0 else None

    # IV高低判断（粗分类）
    if avg_iv > 80:
        iv_level = "🔥 极高IV (>80%)"
        iv_advice = "期权极贵，适合卖方策略（covered call/short put）"
    elif avg_iv > 50:
        iv_level = "🟠 高IV (50-80%)"
        iv_advice = "期权偏贵，买方需谨慎，可考虑垂直价差"
    elif avg_iv > 30:
        iv_level = "🟡 中等IV (30-50%)"
        iv_advice = "正常区间，买卖均可"
    else:
        iv_level = "🟢 低IV (<30%)"
        iv_advice = "期权便宜，适合买方策略（long call/put）"

    # IV/HV
    iv_hv_signal = None
    if iv_hv:
        if iv_hv > 1.5:
            iv_hv_signal = f"⚠️ IV/HV={iv_hv:.2f}：IV远高于实际波动 → 期权过贵，卖方占优（注意财报前夕这通常正常）"
        elif iv_hv < 0.8:
            iv_hv_signal = f"💎 IV/HV={iv_hv:.2f}：IV低于实际波动 → 期权便宜，买方占优"
        else:
            iv_hv_signal = f"⚖️ IV/HV={iv_hv:.2f}：定价合理"

    return {
        "atm_iv_avg": round(avg_iv, 1),
        "hv_20": round(hv_20, 1) if hv_20 else None,
        "iv_hv_ratio": round(iv_hv, 2) if iv_hv else None,
        "iv_level": iv_level,
        "iv_advice": iv_advice,
        "iv_hv_signal": iv_hv_signal,
    }


def analyze_term_structure(ticker: str, n_expirations: int = 4) -> dict:
    """期限结构：近期到期 vs 远期到期 IV对比"""
    try:
        t = yf.Ticker(ticker)
        exps = list(t.options)[:n_expirations]
        if len(exps) < 2:
            return {}

        spot = float(t.fast_info.last_price)
        term = []
        for exp in exps:
            try:
                ch = t.option_chain(exp)
                calls = ch.calls
                puts = ch.puts
                # ATM IV
                c_atm = calls.iloc[(calls["strike"] - spot).abs().argsort()].head(3)
                p_atm = puts.iloc[(puts["strike"] - spot).abs().argsort()].head(3)
                iv_avg = (c_atm["impliedVolatility"].mean() + p_atm["impliedVolatility"].mean()) / 2 * 100
                days = (datetime.strptime(exp, "%Y-%m-%d").date() - date.today()).days
                term.append({"expiration": exp, "dte": days, "atm_iv": round(iv_avg, 1)})
            except Exception:
                continue

        if len(term) < 2:
            return {}

        # 判断曲线形态
        first_iv = term[0]["atm_iv"]
        last_iv = term[-1]["atm_iv"]
        if first_iv > last_iv * 1.15:
            shape = "🔴 倒挂（Backwardation）"
            interpretation = "近期IV >> 远期 → 短期事件驱动（财报/重大消息），事件后IV会快速回落"
        elif last_iv > first_iv * 1.15:
            shape = "🟢 正向（Contango）"
            interpretation = "远期IV > 近期 → 市场长期不确定性更高，短期相对平静"
        else:
            shape = "🟡 平坦"
            interpretation = "期限结构平坦 → 市场对各时间段不确定性预期一致"

        return {
            "term_structure": term,
            "shape": shape,
            "interpretation": interpretation,
        }
    except Exception:
        return {}


def analyze_unusual_activity(calls: pd.DataFrame, puts: pd.DataFrame, top_n: int = 5) -> dict:
    """异常活动：成交量/OI比 异常高的strike（机构可能在大手笔布局）"""
    if calls.empty or puts.empty:
        return {}

    def _flag(df, side):
        if "volume" not in df.columns or "openInterest" not in df.columns:
            return pd.DataFrame()
        d = df[(df["openInterest"] > 100) & (df["volume"] > 100)].copy()
        d["vol_oi"] = d["volume"] / d["openInterest"]
        # vol/oi > 1 表示当日成交量大于持仓量 → 新仓显著
        d["side"] = side
        return d.nlargest(top_n, "vol_oi")[["strike", "volume", "openInterest", "vol_oi", "impliedVolatility", "side"]]

    c_unusual = _flag(calls, "Call")
    p_unusual = _flag(puts, "Put")
    combined = pd.concat([c_unusual, p_unusual], ignore_index=True).sort_values("vol_oi", ascending=False).head(top_n)

    flags = []
    for _, row in combined.iterrows():
        if row["vol_oi"] > 5:
            flags.append(f"🔥 {row['side']} ${row['strike']:.2f}: Vol/OI={row['vol_oi']:.1f}（极度异常，强烈新仓信号）")
        elif row["vol_oi"] > 2:
            flags.append(f"⚡ {row['side']} ${row['strike']:.2f}: Vol/OI={row['vol_oi']:.1f}（活跃新仓）")
        else:
            flags.append(f"📌 {row['side']} ${row['strike']:.2f}: Vol/OI={row['vol_oi']:.1f}")

    return {
        "unusual_strikes": combined,
        "flags": flags,
    }


# ─────────────────────────────────────────────
#  告警引擎 & 操作建议
# ─────────────────────────────────────────────

def generate_alerts(report: dict, flip: dict, walls: dict, iv_regime: dict,
                    term: dict, unusual: dict) -> list:
    """根据结构分析生成 priority alerts"""
    alerts = []
    spot = report.get("spot", 0)
    mp = report.get("max_pain", 0)
    mp_dist = report.get("max_pain_distance_pct", 0)
    pcr = report.get("pcr", {})

    # ── 高优先级 ──
    # 1. 负Gamma环境
    if flip.get("regime") == "负Gamma":
        alerts.append({
            "level": "high",
            "icon": "🔴",
            "title": "处于负Gamma环境",
            "desc": flip.get("regime_signal", ""),
            "action": "降低杠杆，警惕剧烈跳空。短线注意趋势可能加速；不要逆势抄底",
        })

    # 2. Wall极强 + 距现价近
    if walls.get("call_wall_strength", 0) > 5 and walls.get("call_wall_pct_above", 100) < 3:
        alerts.append({
            "level": "high",
            "icon": "🧱",
            "title": f"上方Call Wall极强 (${walls['call_wall_strike']:.2f})",
            "desc": f"OI={walls['call_wall_oi']}，距现价仅{walls['call_wall_pct_above']:.1f}%",
            "action": f"短线大概率在${walls['call_wall_strike']:.2f}遇阻；若突破伴随放量，可能触发空头回补加速上行",
        })
    if walls.get("put_wall_strength", 0) > 5 and walls.get("put_wall_pct_below", 100) < 3:
        alerts.append({
            "level": "high",
            "icon": "🧱",
            "title": f"下方Put Wall极强 (${walls['put_wall_strike']:.2f})",
            "desc": f"OI={walls['put_wall_oi']}，距现价仅{walls['put_wall_pct_below']:.1f}%",
            "action": f"短线大概率在${walls['put_wall_strike']:.2f}得到支撑；若跌破伴随放量，可能引发对冲抛售加速下跌",
        })

    # 3. PCR极端
    pcr_vol = pcr.get("pcr_vol", 1)
    if pcr_vol < 0.4:
        alerts.append({
            "level": "high",
            "icon": "🚨",
            "title": f"PCR极端看多 ({pcr_vol})",
            "desc": "Put/Call成交量比值极低，市场过度乐观",
            "action": "反向指标：考虑减仓或买入保护性Put",
        })
    elif pcr_vol > 1.5:
        alerts.append({
            "level": "high",
            "icon": "🚨",
            "title": f"PCR极端恐慌 ({pcr_vol})",
            "desc": "Put/Call成交量比值极高，市场过度悲观",
            "action": "反向指标：可能临近短期低点，关注反弹机会",
        })

    # ── 中优先级 ──
    # 4. IV倒挂（事件驱动）
    if term.get("shape", "").startswith("🔴"):
        alerts.append({
            "level": "med",
            "icon": "⏳",
            "title": "IV期限结构倒挂",
            "desc": term.get("interpretation", ""),
            "action": "买近期期权=赌事件；若持仓现货，事件后IV crush 将削弱长Call收益",
        })

    # 5. IV极高/极低
    if iv_regime.get("atm_iv_avg", 0) > 80:
        alerts.append({
            "level": "med",
            "icon": "💰",
            "title": "ATM IV 极高",
            "desc": iv_regime.get("iv_level", ""),
            "action": "适合卖方策略（cash-secured put / covered call / 卖跨式）",
        })
    elif iv_regime.get("atm_iv_avg", 0) < 25:
        alerts.append({
            "level": "med",
            "icon": "💎",
            "title": "ATM IV 极低",
            "desc": iv_regime.get("iv_level", ""),
            "action": "期权便宜：买长期看涨/看跌期权代替现货，提供更高杠杆",
        })

    # 6. Max Pain偏离大
    if abs(mp_dist) > 8:
        alerts.append({
            "level": "med",
            "icon": "🎯",
            "title": f"Max Pain 偏离现价 {mp_dist:+.1f}%",
            "desc": report.get("max_pain_signal", ""),
            "action": f"到期日({report['expiration']})临近时，价格大概率向 ${mp:.2f} 收敛",
        })

    # 7. IV Skew异常
    iv_skew = report.get("iv", {}).get("iv_skew", 0)
    if iv_skew > 8:
        alerts.append({
            "level": "med",
            "icon": "📉",
            "title": f"Put Skew极高 ({iv_skew:.1f})",
            "desc": "下跌保护需求异常强 — 通常出现在市场担心崩盘时",
            "action": "若你看多，可卖Put赚高溢价；若你看空，警惕这反而是市场底部信号",
        })
    elif iv_skew < -3:
        alerts.append({
            "level": "med",
            "icon": "📈",
            "title": f"Call Skew异常 ({iv_skew:.1f})",
            "desc": "追涨情绪极强（meme/逼空状态）",
            "action": "市场过热警告，考虑减仓或对冲",
        })

    # 8. 异常活动
    if unusual.get("flags"):
        hot = [f for f in unusual["flags"] if "🔥" in f]
        if hot:
            alerts.append({
                "level": "med",
                "icon": "⚡",
                "title": "检测到异常期权活动",
                "desc": " | ".join(hot[:3]),
                "action": "Vol/OI > 5：可能是机构大单或Smart Money布局，关注这些strike作为目标位",
            })

    # ── 低优先级（信息） ──
    if not alerts:
        alerts.append({
            "level": "info",
            "icon": "✅",
            "title": "期权结构正常",
            "desc": "无显著告警，市场处于平衡状态",
            "action": "按照现货操作策略执行即可",
        })

    return alerts


def generate_playbook(report: dict, flip: dict, walls: dict, iv_regime: dict,
                      alerts: list) -> dict:
    """根据结构生成具体操作playbook"""
    spot = report.get("spot", 0)
    mp = report.get("max_pain", 0)
    pcr_vol = report.get("pcr", {}).get("pcr_vol", 1)

    cw = walls.get("call_wall_strike", spot * 1.1)
    pw = walls.get("put_wall_strike", spot * 0.9)
    iv_avg = iv_regime.get("atm_iv_avg", 30)

    # ─ 现货操作 ─
    stock_advice = []
    if flip.get("regime") == "正Gamma":
        stock_advice.append(f"📍 区间交易：在 ${pw:.2f} (Put Wall) 附近买入，${cw:.2f} (Call Wall) 附近减仓")
        stock_advice.append("📊 持仓中：保持中等仓位，区间内反复操作")
    else:
        stock_advice.append("⚠️ 负Gamma：避免重仓，趋势可能加速")
        stock_advice.append(f"🛑 严格止损：若跌破 ${pw:.2f}，立即减仓50%+")

    if abs(report.get("max_pain_distance_pct", 0)) > 5:
        stock_advice.append(f"🎯 Max Pain 引力：到期日临近 ${mp:.2f} 是大概率落点")

    # ─ 期权策略 ─
    opt_strategies = []
    if iv_avg > 60:
        opt_strategies.append({
            "name": "📉 Covered Call",
            "desc": f"持有100股现货 + 卖出 ${cw:.2f} 的Call (Call Wall位置)",
            "why": "高IV收割时间溢价，Call Wall上方概率小",
        })
        opt_strategies.append({
            "name": "💵 Cash-Secured Put",
            "desc": f"卖出 ${pw:.2f} Put",
            "why": f"愿意在 ${pw:.2f} 接货，同时赚取高额溢价",
        })
        opt_strategies.append({
            "name": "🦋 Iron Condor",
            "desc": f"卖出 ${pw:.2f} Put + 卖出 ${cw:.2f} Call，两边各加保护",
            "why": "正Gamma环境下，预期区间震荡 + 高IV → 赚时间价值",
        })
    elif iv_avg < 30:
        opt_strategies.append({
            "name": "📈 Long Call (LEAPS)",
            "desc": f"买入长期 (>90天) ATM 或 OTM Call",
            "why": "低IV买方占优，期权便宜，杠杆替代现货",
        })
        opt_strategies.append({
            "name": "🦅 Call Debit Spread",
            "desc": f"买入 ATM Call + 卖出 ${cw:.2f} Call",
            "why": "成本低，目标位明确（Call Wall）",
        })
    else:
        opt_strategies.append({
            "name": "⚖️ Vertical Spread",
            "desc": f"看多: 买${spot:.2f} Call + 卖${cw:.2f} Call；看空: 反过来",
            "why": "中等IV，垂直价差降低成本和波动暴露",
        })

    # ─ 对冲建议 ─
    hedge_advice = []
    has_negative_gamma = flip.get("regime") == "负Gamma"
    has_extreme_pcr = pcr_vol < 0.4
    if has_negative_gamma or has_extreme_pcr:
        hedge_advice.append(f"🛡️ 买入 ${pw * 0.95:.2f} OTM Put 作为尾部保护")
    if walls.get("call_wall_pct_above", 100) < 2:
        hedge_advice.append("✂️ 离Call Wall太近，建议先减仓1/3锁利")
    if not hedge_advice:
        hedge_advice.append("✅ 当前结构无需特殊对冲")

    # ─ 关键观察点 ─
    watch_points = [
        f"🔺 上破 ${cw:.2f} (Call Wall)：突破后可能触发Gamma Squeeze，加速上行",
        f"🔻 下破 ${pw:.2f} (Put Wall)：跌破后dealer对冲卖出，可能加速下跌",
        f"🎯 临近到期日，price → Max Pain ${mp:.2f}",
    ]
    if flip.get("flip_strike"):
        watch_points.append(
            f"⚡ Gamma Flip ${flip['flip_strike']:.2f}：穿越此位市场行为切换"
        )

    return {
        "stock_advice": stock_advice,
        "opt_strategies": opt_strategies,
        "hedge_advice": hedge_advice,
        "watch_points": watch_points,
    }


def full_structural_analysis(ticker: str, expiration: str = None) -> dict:
    """完整结构分析 + 告警 + playbook"""
    report = compile_options_report(ticker, expiration)
    if "error" in report:
        return report

    chain = get_option_chain(ticker, expiration or report["expiration"])
    if "error" in chain:
        return chain
    calls = chain["calls"]
    puts = chain["puts"]
    spot = chain["spot"]

    flip = find_gamma_flip(calls, puts, spot)
    walls = analyze_wall_strength(calls, puts, spot)
    iv_regime = analyze_iv_regime(report.get("iv", {}), ticker)
    term = analyze_term_structure(ticker)
    unusual = analyze_unusual_activity(calls, puts)

    alerts = generate_alerts(report, flip, walls, iv_regime, term, unusual)
    playbook = generate_playbook(report, flip, walls, iv_regime, alerts)

    return {
        **report,
        "flip": flip,
        "walls": walls,
        "iv_regime": iv_regime,
        "term": term,
        "unusual": unusual,
        "alerts": alerts,
        "playbook": playbook,
    }
