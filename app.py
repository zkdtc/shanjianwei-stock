"""
app.py — 私人市场雷达 · AI时代股票操作系统
每天帮你快速判断持仓状态，结合江恩时间价格 + 流动性主线 + 段永平底线估值
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import time
from datetime import datetime

from radar_rules import analyze_all, analyze_stock, fetch_price_data
from gann_time import compile_time_axis, compile_all_time_axis, earnings_window_advice, GANN_CYCLES
from options_gamma import compile_options_report, get_expirations, full_structural_analysis, get_option_chain
from deep_report import compile_deep_report
from price_time_chart import build_unified_chart
from runtime_engine import compile_market_runtime
from ticker_runtime import compile_ticker_runtime
from narrative_translator import translate_runtime

# ─────────────────────────────────────────────
#  页面配置
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="私人市场雷达 · AI时代",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  CSS 样式
# ─────────────────────────────────────────────
st.markdown("""
<style>
    .main-title {
        font-size: 2rem; font-weight: 800; color: #1a1a2e;
        border-bottom: 3px solid #e94560; padding-bottom: 8px;
    }
    .card {
        background: #f8f9fa; border-radius: 12px;
        padding: 16px; margin-bottom: 12px;
        border-left: 5px solid #e94560;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    .card-green { border-left-color: #28a745; }
    .card-yellow { border-left-color: #ffc107; }
    .card-orange { border-left-color: #fd7e14; }
    .card-red { border-left-color: #dc3545; }
    .ticker-big { font-size: 1.6rem; font-weight: 800; color: #1a1a2e; }
    .price-big { font-size: 1.3rem; font-weight: 700; color: #e94560; }
    .label-tag {
        display: inline-block;
        background: #e8f4fd; color: #0d6efd;
        border-radius: 6px; padding: 2px 8px;
        font-size: 0.78rem; font-weight: 600; margin: 2px;
    }
    .score-circle {
        display: inline-block;
        width: 52px; height: 52px;
        border-radius: 50%;
        text-align: center; line-height: 52px;
        font-size: 1.1rem; font-weight: 800;
        color: white;
    }
    .action-box {
        border-radius: 8px; padding: 10px 14px; margin: 4px 0;
        font-size: 0.9rem;
    }
    .market-banner {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        color: white; border-radius: 12px; padding: 18px 24px;
        margin-bottom: 20px;
    }
    .stMetric { background: #f0f2f6; border-radius: 8px; padding: 8px; }
    hr { border: 1px solid #eee; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  工具函数
# ─────────────────────────────────────────────

def score_color(score):
    if score >= 70:
        return "#28a745"
    elif score >= 55:
        return "#ffc107"
    elif score >= 40:
        return "#fd7e14"
    else:
        return "#dc3545"


def card_class(score):
    if score >= 70:
        return "card card-green"
    elif score >= 55:
        return "card card-yellow"
    elif score >= 40:
        return "card card-orange"
    else:
        return "card card-red"


def load_watchlist():
    with open("watchlist.json", "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(ttl=900, show_spinner=False)  # cache 15 minutes
def get_all_analysis():
    results, market_ctx = analyze_all("watchlist.json")
    return results, market_ctx


def get_single_analysis(ticker_meta):
    from radar_rules import get_benchmark_return
    spy_ret = get_benchmark_return("SPY", 20)
    qqq_ret = get_benchmark_return("QQQ", 20)
    return analyze_stock(ticker_meta, spy_ret, qqq_ret)


# ─────────────────────────────────────────────
#  侧边栏
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 📡 私人市场雷达")
    st.caption("AI时代流动性驱动操作系统")
    st.divider()

    page = st.radio(
        "导航",
        ["🏙️ AMOS 指挥中心", "🎯 Ticker Runtime",
         "🏠 总览仪表盘", "🔬 深度推演", "🔍 个股详情",
         "📅 时间轴 & 财报", "🎰 期权 & Gamma", "📊 市场结构", "⚙️ 设置"],
        label_visibility="collapsed"
    )

    st.divider()
    st.markdown("**数据刷新**")
    if st.button("🔄 刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.caption(f"最后更新: {datetime.now().strftime('%H:%M:%S')}")
    st.divider()

    # 快速筛选
    st.markdown("**快速筛选**")
    filter_sector = st.multiselect(
        "板块",
        ["AI Infra", "AI Platform", "AI Networking", "AI Photonics",
         "AI Software / Edge", "AI Cybersecurity", "AI Healthcare",
         "AI Robotics", "Fintech / Crypto Adjacent", "Gaming / Metaverse",
         "BTC Mining / AI Datacenter", "EV / AI Robotics",
         "Wireless / Industrial AI"],
        default=[],
        placeholder="全部"
    )

    min_score = st.slider("最低综合评分", 0, 100, 0)


# ─────────────────────────────────────────────
#  数据加载
# ─────────────────────────────────────────────

with st.spinner("正在获取行情数据，请稍候…"):
    try:
        all_results, market_ctx = get_all_analysis()
        data_ok = True
    except Exception as e:
        st.error(f"数据加载失败：{e}")
        data_ok = False
        all_results, market_ctx = [], {}

wl_data = load_watchlist()
ticker_meta_map = {s["ticker"]: s for s in wl_data["stocks"]}


# ─────────────────────────────────────────────
#  筛选
# ─────────────────────────────────────────────

def filter_results(results):
    out = []
    for r in results:
        if "error" in r:
            continue
        meta = ticker_meta_map.get(r["ticker"], {})
        sector = meta.get("sector", "")
        if filter_sector and sector not in filter_sector:
            continue
        score = r.get("plan", {}).get("composite_score", 0)
        if score < min_score:
            continue
        out.append(r)
    return out

filtered = filter_results(all_results) if data_ok else []


# ─────────────────────────────────────────────
#  页面：总览仪表盘
# ─────────────────────────────────────────────

# ═════════════════════════════════════════════
#  AMOS v1 — GLOBAL MARKET COMMAND CENTER
# ═════════════════════════════════════════════
if page == "🏙️ AMOS 指挥中心":
    st.markdown("# 🏙️ AMOS — Global Market Command Center")
    st.caption("Market Regime · Narrative Heatmap · Leadership · Opportunity / Danger Radar · Attention · Memory")

    with st.spinner("正在编译市场 Runtime（宏观+8个 Narrative+龙头+机会+危险）…"):
        @st.cache_data(ttl=900, show_spinner=False)
        def _amos_runtime():
            return compile_market_runtime("watchlist.json")
        mr = _amos_runtime()

    # ── 1. TOP GLOBAL RUNTIME BAR ────────────────────
    regime = mr["regime"]
    with st.container(border=True):
        st.markdown("### 🌐 GLOBAL MARKET RUNTIME")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Market Regime", regime["regime"])
        c2.metric("Liquidity", regime["liquidity"])
        c3.metric("Risk Appetite", regime["risk_appetite"])
        c4.metric("Leadership", regime["leadership"])
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("VIX", regime["vix_level"])
        c6.metric("10Y Rate", regime["rates_level"])
        c7.metric("BTC", regime["btc_trend"])
        c8.metric("Current Risk", regime["current_risk"])
        st.info(f"💬 **中文解释**：{mr['regime_narrative']}")

    st.divider()

    # ── 2. NARRATIVE HEATMAP ────────────────────────
    st.markdown("### 🔥 NARRATIVE HEATMAP (8 大主线热力)")
    narratives = mr["narratives"]
    if narratives:
        cols = st.columns(4)
        for i, n in enumerate(narratives):
            with cols[i % 4]:
                st.markdown(
                    f"""
<div style="background: {n['color']}22; border-left: 4px solid {n['color']}; padding: 10px; margin-bottom: 8px; border-radius: 4px;">
<div style="font-weight:bold; font-size: 0.95em;">{n['name']}</div>
<div style="font-size: 1.05em; margin: 4px 0;">{n['state']}</div>
<div style="font-size: 0.82em; color: #555;">
20d: <b>{n['avg_20d']:+.1f}%</b> · 5d: {n['avg_5d']:+.1f}%<br>
量比 {n['vol_ratio']:.2f}x · {n['above_sma_pct']:.0f}% 在SMA上方<br>
{n['layer']}
</div>
</div>
""",
                    unsafe_allow_html=True,
                )

    st.divider()

    # ── 3. LEADERSHIP BOARD ─────────────────────────
    st.markdown("### 👑 LEADERSHIP BOARD")
    ld = mr["leadership"]
    lc1, lc2 = st.columns(2)
    with lc1:
        st.markdown("#### 🏛️ CORE LEADERS")
        for L in ld["core"]:
            st.markdown(
                f"**{L['state']} {L['ticker']}** — {L['role']}  \n"
                f"<span style='color:#666; font-size:0.85em;'>${L['price']:.2f} · "
                f"5d {L['chg_5d']:+.1f}% · 20d {L['chg_20d']:+.1f}%</span>",
                unsafe_allow_html=True,
            )
    with lc2:
        st.markdown("#### ⚡ HIGH-BETA LEADERS")
        for L in ld["high_beta"]:
            st.markdown(
                f"**{L['state']} {L['ticker']}** — {L['role']}  \n"
                f"<span style='color:#666; font-size:0.85em;'>${L['price']:.2f} · "
                f"5d {L['chg_5d']:+.1f}% · 20d {L['chg_20d']:+.1f}%</span>",
                unsafe_allow_html=True,
            )

    st.divider()

    # ── 4. OPPORTUNITY RADAR ──────────────────────────
    st.markdown("### 🎯 OPPORTUNITY RADAR")
    st.caption("≥2 共振信号自动入榜 · 仅显示符合用户Edge的机会")
    opps = mr["opportunities"]
    if opps:
        for o in opps[:5]:
            with st.container(border=True):
                c1, c2 = st.columns([1, 3])
                with c1:
                    st.markdown(f"### {o['grade']}")
                    st.markdown(f"### {o['ticker']}")
                    st.caption(f"${o['price']:.2f}")
                    st.caption(f"Execution: **{o['execution_state']}**")
                with c2:
                    st.markdown(f"**Type**: {o['type']}")
                    st.markdown(f"**Narrative**: {o['narrative']}")
                    st.markdown("**Confluences**: " + " · ".join(o["confluences"]))
                    st.caption(
                        f"5d {o['chg_5d']:+.1f}% · 20d {o['chg_20d']:+.1f}% · "
                        f"RSI {o['rsi']:.0f} · Risk: {o['risk']}"
                    )
    else:
        st.info("📭 当前无 A/B 级共振机会 — 市场处于等待阶段")

    st.divider()

    # ── 5. DANGER RADAR ───────────────────────────────
    st.markdown("### ⚠️ DANGER RADAR")
    dangers = mr["dangers"]
    if dangers:
        for d in dangers[:5]:
            with st.container(border=True):
                dc1, dc2 = st.columns([1, 3])
                with dc1:
                    st.markdown(f"### {d['severity']}")
                    st.markdown(f"### {d['ticker']}")
                    st.caption(f"${d['price']:.2f}")
                with dc2:
                    for f in d["flags"]:
                        st.markdown(f"- {f}")
                    st.caption(f"5d {d['chg_5d']:+.1f}% · 20d {d['chg_20d']:+.1f}%")
    else:
        st.success("✅ 无显著危险信号")

    st.divider()

    # ── 6. ATTENTION MAP ──────────────────────────────
    st.markdown("### 👀 TODAY'S ATTENTION MAP")
    att = mr["attention"]
    a1, a2, a3, a4 = st.columns(4)
    a1.markdown(f"#### 🔴 HIGH ({len(att['high'])})")
    a1.markdown(" · ".join(att["high"]) if att["high"] else "_(none)_")
    a2.markdown(f"#### 🟡 WATCH ({len(att['watch'])})")
    a2.markdown(" · ".join(att["watch"]) if att["watch"] else "_(none)_")
    a3.markdown(f"#### 🟢 LOW ({len(att['low'])})")
    a3.markdown(" · ".join(att["low"]) if att["low"] else "_(none)_")
    a4.markdown(f"#### 🔇 MUTED ({len(att['muted'])})")
    a4.markdown(" · ".join(att["muted"]) if att["muted"] else "_(none)_")

    st.divider()

    # ── 7. MARKET MEMORY ──────────────────────────────
    st.markdown("### 🧠 MARKET MEMORY")
    mem = mr["memory"]
    mc1, mc2 = st.columns(2)
    with mc1:
        st.markdown(f"**Most Similar To**: {mem['most_similar']}")
        st.markdown(f"**Not Yet**: {mem['not_yet']}")
    with mc2:
        st.markdown(f"**Key Difference**: {mem['key_diff']}")

    # ── 8. COGNITIVE PANEL ────────────────────────────
    st.markdown("### 🧭 PERSONAL COGNITIVE PANEL")
    cog = mr["cognitive"]
    cc1, cc2, cc3 = st.columns(3)
    cc1.markdown("**正在改进 ✅**")
    for x in cog["improving"]:
        cc1.caption(f"- {x}")
    cc2.markdown("**当前弱点 ⚠️**")
    for x in cog["weakness"]:
        cc2.caption(f"- {x}")
    cc3.markdown("**Focus 焦点**")
    cc3.info(cog["focus"])

    st.caption(f"⏱️ Runtime 编译于 {mr['compiled_at']}")


# ═════════════════════════════════════════════
#  AMOS v1 — TICKER RUNTIME PAGE
# ═════════════════════════════════════════════
elif page == "🎯 Ticker Runtime":
    st.markdown("# 🎯 Ticker Runtime")
    st.caption("Hero State · Narrative Tree · Valuation Stack · Gann+Time · Tech Regime · Options · Flow · Execution")

    tickers_avail = [s["ticker"] for s in wl_data["stocks"]]
    sel_t = st.selectbox("选择标的", tickers_avail, key="amos_tr_sel")

    with st.spinner(f"正在编译 {sel_t} 全维度 Runtime…"):
        @st.cache_data(ttl=900, show_spinner=False)
        def _amos_tr(t):
            from runtime_engine import fetch_macro_signals, classify_regime
            macro = classify_regime(fetch_macro_signals())
            return compile_ticker_runtime(t, macro_regime=macro)
        tr = _amos_tr(sel_t)

    if "error" in tr:
        st.error(tr["error"])
        st.stop()

    narratives = translate_runtime(tr)
    hero = tr["hero"]
    nar_state = tr["narrative_state"]
    val_stack = tr["valuation_stack"]

    # ── HERO RUNTIME ───────────────────────────────
    with st.container(border=True):
        st.markdown(f"## {tr['ticker']} — {tr['name']}")
        st.caption(hero["identity"])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current Regime", hero["current_regime"])
        c2.metric("Narrative", hero["narrative_strength"])
        c3.metric("Leadership Dep.", hero["leadership_dependency"])
        c4.metric("Execution", f"{hero['execution_color']} {hero['execution_state']}")
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Price", f"${hero['price']:.2f}")
        c6.metric("Liquidity State", hero["liquidity_state"])
        c7.metric("Current Risk", hero["current_risk"])
        c8.metric("Execution Mode", hero["execution_desc"][:18])
        st.info(f"💬 **Runtime 中文解读**：{narratives['hero_narrative']}")

    # ── NARRATIVE POSITIONING TREE ─────────────────
    st.markdown("### 🌳 NARRATIVE POSITIONING")
    tree_str = "  →  ".join(tr["narrative_tree"])
    st.markdown(f"<div style='background:#f0f4f8; padding:12px; border-radius:6px; font-family:monospace; font-size:1.05em;'>{tree_str}</div>", unsafe_allow_html=True)
    nrt1, nrt2, nrt3, nrt4 = st.columns(4)
    nrt1.metric("Phase", nar_state["phase"])
    nrt2.metric("Crowding", nar_state["crowding"])
    nrt3.metric("Narrative Risk", nar_state["narrative_risk"])
    nrt4.metric("Outlook", nar_state["long_term_outlook"])

    st.divider()

    # ── VALUATION STACK ────────────────────────────
    st.markdown("### 💰 VALUATION STACK (4-layer)")
    if val_stack:
        v1, v2, v3, v4 = st.columns(4)
        v1.metric("🛡️ Conservative", f"${val_stack['conservative']}")
        v2.metric("⚖️ Base", f"${val_stack['base']}")
        v3.metric("📈 Bull", f"${val_stack['bull']}")
        v4.metric("🔥 Euphoria", f"${val_stack['euphoria']}")
        st.markdown(f"**Current Zone**: {val_stack['zone']}")
        st.caption(f"距 Conservative {val_stack['distance_to_conservative_pct']:+.1f}% · "
                   f"距 Base {val_stack['distance_to_base_pct']:+.1f}%")
        st.caption(f"📅 {val_stack['discount_narrative']}")
        st.info(f"💬 **估值 Runtime 解读**：{narratives['valuation_narrative']}")
    else:
        st.warning("估值数据不可用")

    st.divider()

    # ── GANN + TIME-PRICE ──────────────────────────
    st.markdown("### ⏱️ GANN + TIME-PRICE RUNTIME")
    g = tr["gann"]
    if g and "error" not in g:
        tg1, tg2, tg3 = st.columns(3)
        sw = g.get("swings", {})
        tg1.metric("Current", f"${tr['indicators']['price']:.2f}")
        tg2.metric("Recent High", f"${sw.get('recent_high','—')}",
                   str(sw.get("recent_high_date", "")))
        tg3.metric("Recent Low", f"${sw.get('recent_low','—')}",
                   str(sw.get("recent_low_date", "")))
        closest = g.get("closest_levels", {})
        sr1, sr2 = st.columns(2)
        with sr1:
            st.markdown("**🔺 Resistance (Sq9)**")
            for r in closest.get("next_resistances", [])[:3]:
                st.caption(f"+{r['degrees']}° → ${r['target']:.2f}")
        with sr2:
            st.markdown("**🔻 Support (Sq9)**")
            for s in closest.get("next_supports_from_top", [])[:3]:
                st.caption(f"-{s['degrees']}° → ${s['target']:.2f}")
        if g.get("time_resonance_days"):
            st.markdown("**🔥 Time Resonance Days**")
            for d in g["time_resonance_days"][:3]:
                st.caption(f"⏰ {d['date']} (+{d['days_from_today']}d) · {len(d['windows'])} cycles overlap")
    st.info(f"💬 **时间-价格 Runtime 解读**：{narratives['time_price_narrative']}")

    st.divider()

    # ── TECHNICAL REGIME ───────────────────────────
    st.markdown("### 📊 TECHNICAL REGIME (周/日/小时)")
    mtf = tr["mtf"]
    if mtf and "error" not in mtf:
        wm, dm, hm = mtf.get("weekly", {}), mtf.get("daily", {}), mtf.get("hourly", {})
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            st.markdown("**📅 Weekly**")
            st.caption(f"{wm.get('ma_arrangement','—')}")
            st.caption(f"MACD: {wm.get('macd_signal','—')}")
            st.caption(f"RSI: {wm.get('rsi_14','—')}")
        with tc2:
            st.markdown("**📆 Daily**")
            st.caption(f"{dm.get('ma_arrangement','—')}")
            st.caption(f"Boll: {dm.get('boll_signal','—')}")
            st.caption(f"RSI: {dm.get('rsi_14','—')}")
        with tc3:
            st.markdown("**⚡ 1H**")
            st.caption(f"{hm.get('ma_arrangement','—')}")
            st.caption(f"RSI: {hm.get('rsi_14','—')}")
            st.caption(f"Vol Ratio: {hm.get('vol_ratio','—')}")
    st.info(f"💬 **多周期 Runtime 解读**：{narratives['technical_narrative']}")

    st.divider()

    # ── OPTIONS RUNTIME ───────────────────────────
    st.markdown("### 🎰 OPTIONS & GAMMA RUNTIME")
    opt = tr["options"]
    if opt and "error" not in opt:
        oc1, oc2, oc3, oc4 = st.columns(4)
        flip = opt.get("flip", {})
        walls = opt.get("walls", {})
        iv = opt.get("iv_regime", {})
        if iv.get("atm_iv_avg"):
            oc1.metric("IV", f"{iv['atm_iv_avg']:.0f}%", iv.get("iv_level", ""))
        oc2.metric("Gamma", flip.get("regime", "—"),
                   f"flip ${flip.get('flip_strike','—')}")
        if walls.get("call_wall_strike"):
            oc3.metric("Call Wall", f"${walls['call_wall_strike']:.2f}")
        if walls.get("put_wall_strike"):
            oc4.metric("Put Wall", f"${walls['put_wall_strike']:.2f}")
    st.info(f"💬 **期权 Runtime 解读**：{narratives['options_narrative']}")

    st.divider()

    # ── FLOW RUNTIME ──────────────────────────────
    st.markdown("### 💰 FLOW RUNTIME")
    money = tr["money"]
    if money and "error" not in money:
        fc1, fc2, fc3 = st.columns(3)
        if money.get("avg_turnover_pct"):
            fc1.metric("Avg Turnover", f"{money['avg_turnover_pct']:.2f}%")
        fc2.metric("OBV 20d", f"{money['obv_change_20d']:,.0f}")
        fc3.metric("Price 20d", f"{money['price_change_20d_pct']:+.1f}%")
    st.info(f"💬 **资金 Runtime 解读**：{narratives['flow_narrative']}")

    st.divider()

    # ── EXECUTION RUNTIME (synthesized) ───────────
    st.markdown("### 🎯 EXECUTION RUNTIME")
    with st.container(border=True):
        st.markdown(f"#### {hero['execution_color']} **{hero['execution_state']}**")
        st.markdown(f"_{hero['execution_desc']}_")
        st.markdown(f"**当前 Risk**: {hero['current_risk']}")
        if val_stack:
            cz = val_stack["zone"]
            if "Conservative" in cz or "💎" in cz:
                st.success("✅ 估值落在 Conservative 区 — 战略性建仓窗口")
            elif "Euphoria" in cz or "🔴" in cz:
                st.error("⚠️ 估值落在 Euphoria 区 — 优先锁利/对冲，不追高")
            elif "Bull" in cz:
                st.warning("🟠 Bull 区 — 谨慎加仓，重点关注 Narrative 兑现速度")

    st.caption(f"⏱️ Runtime 编译于 {tr['compiled_at']}")


elif page == "🏠 总览仪表盘":

    # 市场背景横幅
    st.markdown(f"""
    <div class="market-banner">
        <div style="font-size:1.2rem;font-weight:800;margin-bottom:8px;">
            📡 今日市场背景
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:24px;">
            <div><b>主线：</b>{market_ctx.get('current_mainline','—')}</div>
            <div><b>流动性：</b>{market_ctx.get('liquidity_env','—')}</div>
            <div><b>风险偏好：</b>{market_ctx.get('risk_appetite','—')}</div>
            <div><b>周期阶段：</b>{market_ctx.get('cycle_phase','—')}</div>
        </div>
        <div style="margin-top:8px;font-size:0.85rem;opacity:0.8;">
            关键催化剂：{market_ctx.get('key_catalyst','—')} &nbsp;|&nbsp;
            {market_ctx.get('macro_note','—')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not data_ok or not filtered:
        st.warning("暂无数据，请点击左侧「刷新数据」")
        st.stop()

    # 汇总指标
    scores = [r["plan"]["composite_score"] for r in filtered if "plan" in r]
    strong = sum(1 for s in scores if s >= 70)
    watch = sum(1 for s in scores if 40 <= s < 70)
    avoid = sum(1 for s in scores if s < 40)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 关注标的", len(filtered))
    c2.metric("🟢 进攻/强势", strong)
    c3.metric("🟡 持有/观察", watch)
    c4.metric("🔴 回避/弱势", avoid)

    st.divider()

    # 按评分排序
    sorted_results = sorted(filtered, key=lambda r: r["plan"]["composite_score"], reverse=True)

    st.markdown("### 🃏 股票状态卡")
    st.caption("综合评分 = 技术(40%) + 相对强弱(30%) + 估值位置(30%)，越高越好")

    # 每行3列显示
    cols_per_row = 3
    for i in range(0, len(sorted_results), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j >= len(sorted_results):
                break
            r = sorted_results[i + j]
            score = r["plan"]["composite_score"]
            ind = r["indicators"]
            gann = r["gann"]
            rs = r["rs"]
            tech = r["tech"]
            val = r["val"]
            plan = r["plan"]

            color = score_color(score)
            price = ind.get("price", 0)
            rsi = ind.get("rsi_14", 0)
            mom20 = ind.get("momentum_20d", 0)
            mom_str = f"+{mom20:.1f}%" if mom20 >= 0 else f"{mom20:.1f}%"

            with col:
                with st.container(border=True):
                    # 头部
                    h1, h2 = st.columns([3, 1])
                    with h1:
                        st.markdown(f"**{r['ticker']}** · {r['name']}")
                        st.caption(r.get("market_identity", ""))
                    with h2:
                        st.markdown(
                            f'<div class="score-circle" style="background:{color}">'
                            f'{score:.0f}</div>',
                            unsafe_allow_html=True
                        )

                    # 价格行
                    st.markdown(
                        f'<span class="price-big">${price:.2f}</span>'
                        f'&nbsp;&nbsp;<span style="color:{"#28a745" if mom20>=0 else "#dc3545"}">'
                        f'{mom_str} (20日)</span>',
                        unsafe_allow_html=True
                    )

                    # 标签
                    tags = [
                        r.get("mainline_layer", ""),
                        r.get("beta_type", ""),
                        gann.get("zone", ""),
                    ]
                    tags_html = "".join(
                        f'<span class="label-tag">{t}</span>'
                        for t in tags if t
                    )
                    st.markdown(tags_html, unsafe_allow_html=True)

                    st.divider()

                    # 指标行
                    m1, m2, m3 = st.columns(3)
                    m1.metric("RSI", f"{rsi:.0f}")
                    m2.metric("技术", tech.get("label", "—"))
                    m3.metric("RS", rs.get("rs_label", "—").split(" ")[0])

                    # 估值
                    st.caption(f"📐 估值：{val.get('val_zone','—')}")
                    st.caption(f"江恩区间：{gann.get('zone_signal','—')}")

                    st.divider()

                    # 三层操作
                    short = plan.get("short", {})
                    mid = plan.get("mid", {})
                    long_ = plan.get("long", {})

                    st.markdown(f"**1-3天** {short.get('action','')}")
                    st.caption(short.get("desc", ""))

                    st.markdown(f"**1-2周** {mid.get('action','')}")
                    st.caption(mid.get("desc", ""))

                    st.markdown(f"**1-2月** {long_.get('action','')}")
                    st.caption(long_.get("desc", ""))


# ─────────────────────────────────────────────
#  页面：🔬 深度推演
# ─────────────────────────────────────────────

elif page == "🔬 深度推演":
    st.markdown("## 🔬 价格-时间统一推演")
    st.caption("**核心原则**：价格与时间必须对齐。在同一张图上叠加江恩位、均线、期权墙、时间窗口 → 寻找周期共振点")

    tickers_avail = [s["ticker"] for s in wl_data["stocks"]]
    cc1, cc2 = st.columns([2, 1])
    sel_t = cc1.selectbox("选择股票", tickers_avail, key="deep_sel")
    chart_period = cc2.selectbox("图表周期", ["3mo", "6mo", "1y", "2y"], index=1, key="deep_period")

    with st.spinner(f"正在生成 {sel_t} 全维度推演（江恩+多周期+期权+资金流+时间共振）…"):
        @st.cache_data(ttl=900, show_spinner=False)
        def _cached_deep(t):
            return compile_deep_report(t)
        rpt = _cached_deep(sel_t)

    if "error" in rpt:
        st.error(rpt["error"])
        st.stop()

    g = rpt["gann"]
    mtf = rpt["mtf"]
    money = rpt["money"]
    options = rpt["options"]
    confluences = rpt["confluences"]
    tactical = rpt["tactical"]
    playbook = rpt["playbook"]
    price = rpt["price"]
    price_levels = rpt.get("price_levels", [])
    time_lines = rpt.get("time_lines", [])
    earnings = rpt.get("earnings", {})
    pt_resonance = rpt.get("pt_resonance", [])

    swings = g.get("swings", {})
    sel_meta = next((s for s in wl_data["stocks"] if s["ticker"] == sel_t), {})

    # ═══════════════════════════════════════
    # 头部摘要：价格 + 时间 + 方向
    # ═══════════════════════════════════════
    st.markdown(f"### 📋 {sel_t} · {sel_meta.get('name', sel_t)}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("当前价", f"${price:.2f}")
    c2.metric("近期高", f"${swings.get('recent_high','—')}",
              str(swings.get("recent_high_date", "")))
    c3.metric("近期低", f"${swings.get('recent_low','—')}",
              str(swings.get("recent_low_date", "")))
    if earnings and "error" not in earnings:
        c4.metric("下次财报", earnings.get("date", "—"),
                  f"{earnings.get('days_until','')}天后")
    else:
        c4.metric("下次财报", "—")
    c5.metric("综合方向", tactical.get("direction", "—"))

    # ═══════════════════════════════════════
    # 🌟 SECTION 1: 统一价格-时间图（最重要，最上面）
    # ═══════════════════════════════════════
    st.markdown("### 🌟 价格-时间统一图（核心视图）")
    st.caption("""
横线 = 江恩九宫位 / 均线 / 期权墙 / Max Pain / Gamma Flip / 筹码POC  
竖线 = 财报日 / 江恩时间窗口 / 时间共振日  
**价格-时间共振点** = 横竖线交叉处 = 高概率变盘点
    """)

    # 构造共振区
    conflu_zones = []
    for c in confluences[:5]:
        # 共振区上下浮动 1%
        conflu_zones.append({
            "low": c["center_price"] * 0.985,
            "high": c["center_price"] * 1.015,
            "strength": c["strength"],
            "label": "共振",
            "color": "#fff59d",
        })

    fig = build_unified_chart(
        ticker=sel_t,
        period=chart_period,
        interval="1d",
        price_levels=price_levels,
        time_lines=time_lines,
        confluence_zones=conflu_zones,
        swings={
            "recent_high": swings.get("recent_high"),
            "recent_high_date": swings.get("recent_high_date"),
            "recent_low": swings.get("recent_low"),
            "recent_low_date": swings.get("recent_low_date"),
        },
        show_volume=True, show_rsi=True, show_macd=True,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ═══════════════════════════════════════
    # 🎯 SECTION 2: 价格-时间共振点（核心结论）
    # ═══════════════════════════════════════
    st.markdown("### 🎯 价格-时间共振点（高变盘概率日 + 关键位）")
    st.caption("当某一天既落在江恩时间窗口，又价格快到达某个多维共振区 → 极高战略价值")

    if pt_resonance:
        for r in pt_resonance[:5]:
            with st.container(border=True):
                cR1, cR2, cR3 = st.columns([1, 1, 2])
                cR1.markdown(f"### ⏰ {r['date']}")
                cR1.caption(f"距今 {r['days_from_today']}天")
                cR2.markdown(f"### ${r['price_zone']:.2f}")
                cR2.caption(f"距现价 {r['price_distance_pct']:+.1f}%")
                with cR3:
                    st.markdown(f"**时间维度**: {r['time_label']}")
                    st.markdown(f"**价格维度**: {r['price_strength']} 涉及 {', '.join(r['price_systems'])}")
                    st.markdown(f"**综合分数**: {r['score']:.1f}")
    else:
        st.info("未检测到显著价格-时间共振点（市场尚未进入临近关键时间-价格交叉点）")

    st.divider()

    # ═══════════════════════════════════════
    # 📐 SECTION 3: 价格维度详情（江恩+多周期+期权墙）
    # ═══════════════════════════════════════
    st.markdown("### 📐 价格维度详情")

    # 横排展示：左边江恩 Sq9，中间多维共振，右边期权墙
    pcol1, pcol2, pcol3 = st.columns(3)

    with pcol1:
        st.markdown("#### ⚔️ 江恩九宫图")
        st.caption("从近期低/高点的旋转角度计算的精确位")
        if g.get("interpretation"):
            for line in g["interpretation"][:3]:
                st.caption(line)

        # Sq9 关键位表
        closest = g.get("closest_levels", {})
        rows = []
        for nr in closest.get("next_resistances", [])[:3]:
            rows.append({"位": f"江恩+{nr['degrees']}°", "价格": nr["target"],
                         "类型": "🔺 阻力", "距%": f"{(nr['target']-price)/price*100:+.1f}"})
        for ns in closest.get("next_supports_from_top", [])[:3]:
            rows.append({"位": f"江恩-{ns['degrees']}°", "价格": ns["target"],
                         "类型": "🔻 支撑", "距%": f"{(ns['target']-price)/price*100:+.1f}"})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    with pcol2:
        st.markdown("#### 💎 多维度共振区")
        st.caption("≥2个独立体系同时识别为关键位")
        if confluences:
            for c in confluences[:5]:
                color_emoji = "🏰" if c["systems_count"] >= 4 else "🧱" if c["systems_count"] == 3 else "🪨"
                st.markdown(f"**{color_emoji} ${c['center_price']:.2f}** ({c['distance_pct']:+.1f}%)")
                st.caption(f"涵盖 {', '.join(c['systems'])} · {c['systems_count']}个体系")
        else:
            st.info("无显著共振")

    with pcol3:
        st.markdown("#### 🧱 期权关键位")
        if options and "error" not in options:
            walls = options.get("walls", {})
            flip = options.get("flip", {})
            opt_rows = []
            if walls.get("call_wall_strike"):
                opt_rows.append({"位": "Call Wall", "价格": walls["call_wall_strike"],
                                 "距%": f"{walls.get('call_wall_pct_above',0):+.1f}",
                                 "强度": walls.get('call_wall_grade','').split(" ")[0]})
            if walls.get("put_wall_strike"):
                opt_rows.append({"位": "Put Wall", "价格": walls["put_wall_strike"],
                                 "距%": f"-{walls.get('put_wall_pct_below',0):.1f}",
                                 "强度": walls.get('put_wall_grade','').split(" ")[0]})
            if options.get("max_pain"):
                opt_rows.append({"位": "Max Pain", "价格": options["max_pain"],
                                 "距%": f"{options['max_pain_distance_pct']:+.1f}", "强度": "—"})
            if flip.get("flip_strike"):
                opt_rows.append({"位": "⚡Gamma Flip", "价格": flip["flip_strike"],
                                 "距%": f"{flip.get('flip_distance_pct',0):+.1f}",
                                 "强度": flip.get('regime','')})
            if opt_rows:
                st.dataframe(pd.DataFrame(opt_rows), hide_index=True, use_container_width=True)

            # 期权制度
            iv_r = options.get("iv_regime", {})
            if iv_r:
                st.caption(f"📊 {iv_r.get('iv_level','')} · IV/HV={iv_r.get('iv_hv_ratio','—')}")
            if flip.get("regime_signal"):
                st.caption(flip['regime_signal'][:90])
        else:
            st.info("期权数据不可用")

    st.divider()

    # ═══════════════════════════════════════
    # ⏰ SECTION 4: 时间维度详情
    # ═══════════════════════════════════════
    st.markdown("### ⏰ 时间维度详情")

    tcol1, tcol2 = st.columns([1, 1])

    with tcol1:
        st.markdown("#### 📅 财报 & 关键时间窗口")
        if earnings and "error" not in earnings:
            from gann_time import earnings_window_advice
            adv = earnings_window_advice(earnings.get("days_until"))
            st.markdown(f"**财报日**: {earnings.get('date')} ({earnings.get('weekday')})")
            st.markdown(f"**距今**: {earnings.get('days_until')} 天 · {adv.get('phase')}")
            st.info(f"{adv.get('color','')} {adv.get('advice','')}")

        # 时间共振日
        if g.get("time_resonance_days"):
            st.markdown("**🔥 时间共振日（多周期重合 → 高概率变盘）**")
            for trd in g["time_resonance_days"][:4]:
                star = "🔥🔥" if trd.get("is_critical") else "⏰"
                st.markdown(f"- {star} **{trd['date']}** (距今 {trd['days_from_today']}天)")
                for w in trd["windows"][:2]:
                    st.caption(f"  · {w['anchor_type']} + {w['cycle_label']}")

    with tcol2:
        st.markdown("#### ⭐ 江恩重要时间循环（未来60天）")
        upcoming = g.get("upcoming_windows", [])
        important = [w for w in upcoming if w.get("is_critical")][:6]
        if important:
            for w in important:
                badge = "🔥" if w.get("is_imminent") else "⭐"
                st.markdown(
                    f"{badge} **{w['target_date']}** (+{w['days_from_today']}d) · "
                    f"{w['cycle_label']}"
                )
                st.caption(f"  锚点: {w.get('anchor_type','')} (${w.get('anchor_price','—')})")

    st.divider()

    # ═══════════════════════════════════════
    # 📊 SECTION 5: 多周期盘面快照（折叠）
    # ═══════════════════════════════════════
    with st.expander("📊 多周期盘面解读（周/日/小时）— 详细技术指标", expanded=False):
        if mtf and "error" not in mtf:
            if mtf.get("cross_signals"):
                for s in mtf["cross_signals"]:
                    if "🟢" in s or "🔥" in s:
                        st.success(s)
                    elif "🔴" in s:
                        st.error(s)
                    else:
                        st.warning(s)

            tab_w, tab_d, tab_h = st.tabs(["周线", "日线", "1小时"])

            def render_tf(tf):
                if "error" in tf:
                    st.warning(tf["error"]); return
                cc = st.columns(4)
                cc[0].metric("收盘", f"${tf['price']:.2f}", f"{tf['chg_pct']:+.2f}%")
                cc[1].metric("MA20", f"${tf['ma20']:.2f}")
                cc[2].metric("RSI", f"{tf['rsi_14']:.1f}")
                cc[3].metric("量比", f"{tf['vol_ratio']:.2f}x")
                st.markdown(f"**均线**: {tf['ma_arrangement']}")
                st.markdown(f"**MACD**: {tf['macd_signal']}")
                st.markdown(f"**RSI**: {tf['rsi_signal']}")
                st.markdown(f"**布林**: {tf['boll_signal']}")
                st.markdown(f"**成交量**: {tf['vol_signal']}")

            with tab_w: render_tf(mtf["weekly"])
            with tab_d: render_tf(mtf["daily"])
            with tab_h: render_tf(mtf["hourly"])

            # Volume Profile
            vp = mtf.get("volume_profile")
            if vp:
                vc1, vc2, vc3 = st.columns(3)
                vc1.metric("筹码POC", f"${vp['poc']['price_mid']:.2f}")
                vc2.metric("Value Area Hi", f"${vp['value_area_high']:.2f}")
                vc3.metric("Value Area Lo", f"${vp['value_area_low']:.2f}")

    # ═══════════════════════════════════════
    # 💰 SECTION 6: 资金流向（折叠）
    # ═══════════════════════════════════════
    with st.expander("💰 资金流向 & 主力意图", expanded=False):
        if money and "error" not in money:
            mc1, mc2, mc3 = st.columns(3)
            if money.get("avg_turnover_pct"):
                mc1.metric("日均换手率", f"{money['avg_turnover_pct']:.2f}%")
            mc2.metric("OBV 20日", f"{money['obv_change_20d']:,.0f}")
            mc3.metric("A/D 20日", f"{money['ad_change_20d']:,.0f}")
            st.markdown(f"**OBV**: {money['obv_divergence']}")
            st.markdown(f"**A/D**: {money['ad_signal']}")
            st.markdown(f"**量能**: {money['recent_vol_trend']}")
            for s in money["main_intent"]:
                st.markdown(f"- {s}")

    # ═══════════════════════════════════════
    # 🎯 SECTION 7: 综合战术 Playbook
    # ═══════════════════════════════════════
    st.divider()
    st.markdown("### 🎯 综合战术 Playbook")
    st.markdown(f"#### 综合方向：{tactical['direction']}")

    with st.expander("📋 多空因子明细", expanded=False):
        for f in tactical["factors"]:
            st.markdown(f"- {f}")
        st.caption(f"多头分: {tactical['bullish_score']} | 空头分: {tactical['bearish_score']} | 净值: {tactical['net']:+.1f}")

    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        st.markdown("#### 📍 短线 (1-3天)")
        st.info(playbook["short_term"])
        if playbook.get("up_target"):
            st.caption(f"🔺 上方目标：${playbook['up_target']['center_price']:.2f}")
        if playbook.get("down_support"):
            st.caption(f"🔻 下方支撑：${playbook['down_support']['center_price']:.2f}")
    with pc2:
        st.markdown("#### 📅 中线 (1-2周)")
        for m in playbook["mid_term"]:
            st.markdown(f"- {m}")
    with pc3:
        st.markdown("#### 🏔️ 长线 (1-3月)")
        for l in playbook["long_term"]:
            st.markdown(f"- {l}")

    if playbook.get("options_strategies"):
        st.markdown("#### ⚙️ 推荐期权策略")
        for s in playbook["options_strategies"]:
            with st.container(border=True):
                st.markdown(f"**{s['name']}** — {s['desc']}")
                st.caption(f"💡 _{s['why']}_")

    # ─── 江恩 Sq9 完整目标表（折叠） ───
    with st.expander("📐 江恩九宫图完整数学推演（Sq9详细目标位表）", expanded=False):
        if swings.get("recent_low") and swings.get("recent_high"):
            bottom = swings["recent_low"]
            top = swings["recent_high"]
            import math as _math
            sqrt_b = _math.sqrt(bottom)
            sqrt_t = _math.sqrt(top)

            st.markdown(f"**从近期低点 ${bottom:.2f} 向上**")
            st.caption(f"√{bottom:.2f} = {sqrt_b:.3f}，每+0.125 = 旋转45°，每+1.0 = 一整圈360°")
            df_up = pd.DataFrame(g["sq9_from_bottom"])
            df_up.columns = ["旋转角度°", "圈数", "Δ√", "目标价$", "涨幅%"]
            def _hl(row):
                if abs(row["目标价$"] - price) / price * 100 < 2:
                    return ["background-color: #fff3cd"] * len(row)
                return [""] * len(row)
            st.dataframe(df_up.style.apply(_hl, axis=1), hide_index=True, use_container_width=True)

            st.markdown(f"**从近期高点 ${top:.2f} 向下**")
            st.caption(f"√{top:.2f} = {sqrt_t:.3f}")
            df_dn = pd.DataFrame(g["sq9_from_top"])
            df_dn.columns = ["回撤角度°", "圈数", "Δ√", "目标价$", "跌幅%"]
            st.dataframe(df_dn.style.apply(_hl, axis=1), hide_index=True, use_container_width=True)

    st.divider()
    st.caption("⚠️ 以上分析仅作技术推演与学术探讨，不构成具体投资建议。")

# ─────────────────────────────────────────────
#  页面：个股详情
# ─────────────────────────────────────────────

elif page == "🔍 个股详情":
    st.markdown("## 🔍 个股深度报告")

    ticker_list = [s["ticker"] for s in wl_data["stocks"]]
    selected = st.selectbox("选择标的", ticker_list)

    meta = ticker_meta_map.get(selected, {})

    with st.spinner(f"正在分析 {selected}…"):
        # Try from cache first
        cached = next((r for r in all_results if r.get("ticker") == selected), None)
        if cached and "error" not in cached:
            r = cached
        else:
            r = get_single_analysis(meta)

    if "error" in r:
        st.error(f"❌ 数据获取失败：{r['error']}")
        st.stop()

    ind = r["indicators"]
    gann = r["gann"]
    rs = r["rs"]
    tech = r["tech"]
    val = r["val"]
    plan = r["plan"]
    score = plan["composite_score"]

    # ─ 头部 ─
    col_l, col_r = st.columns([3, 1])
    with col_l:
        st.markdown(f"### {selected} · {r['name']}")
        st.markdown(f"**{r.get('market_identity','')}** | {r.get('mainline_position','')}")
        st.markdown(
            f'<span class="label-tag">{r.get("mainline_layer","")}</span>'
            f'<span class="label-tag">{r.get("beta_type","")}</span>'
            f'<span class="label-tag">折现窗口: {r.get("discount_horizon","")}</span>',
            unsafe_allow_html=True
        )
    with col_r:
        st.markdown(
            f'<div style="text-align:center">'
            f'<div class="score-circle" style="background:{score_color(score)};width:80px;height:80px;line-height:80px;font-size:1.5rem">'
            f'{score:.0f}</div>'
            f'<div style="font-size:0.8rem;margin-top:4px">综合评分</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.info(f"📝 {meta.get('notes','')}")
    st.divider()

    # ─ 价格图 ─
    st.markdown("#### 📈 价格走势（含均线）")
    df_chart = fetch_price_data(selected, "6mo")
    if not df_chart.empty:
        close = df_chart["Close"]
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df_chart.index,
            open=df_chart["Open"], high=df_chart["High"],
            low=df_chart["Low"], close=df_chart["Close"],
            name="K线", increasing_line_color="#28a745",
            decreasing_line_color="#dc3545"
        ))
        fig.add_trace(go.Scatter(x=df_chart.index, y=ema20, name="EMA20",
                                  line=dict(color="#ffc107", width=1.5)))
        fig.add_trace(go.Scatter(x=df_chart.index, y=ema50, name="EMA50",
                                  line=dict(color="#0d6efd", width=1.5)))

        # 江恩水平线
        for lvl, label, color in [
            (gann.get("s2"), "江恩S2", "#28a745"),
            (gann.get("s1"), "江恩S1", "#17a2b8"),
            (gann.get("r1"), "江恩R1", "#fd7e14"),
            (gann.get("r2"), "江恩R2", "#dc3545"),
        ]:
            if lvl and lvl > 0:
                fig.add_hline(y=lvl, line_dash="dash", line_color=color,
                              annotation_text=f"{label}: {lvl}", annotation_position="right")

        fig.update_layout(
            height=420, xaxis_rangeslider_visible=False,
            margin=dict(l=0, r=80, t=20, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ─ 核心指标 ─
    st.markdown("#### 🔢 核心技术指标")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("当前价格", f"${ind.get('price',0):.2f}")
    c2.metric("RSI(14)", f"{ind.get('rsi_14',0):.1f}")
    c3.metric("EMA20", f"${ind.get('ema_20',0):.2f}")
    c4.metric("EMA50", f"${ind.get('ema_50',0):.2f}")
    c5.metric("10日动量", f"{ind.get('momentum_10d',0):+.1f}%")
    c6.metric("成交量比", f"{ind.get('vol_ratio',1):.2f}x")

    # 均线状态
    ema_status = []
    if ind.get("above_ema20"):
        ema_status.append("✅ 价格>EMA20")
    else:
        ema_status.append("❌ 价格<EMA20")
    if ind.get("above_ema50"):
        ema_status.append("✅ 价格>EMA50")
    else:
        ema_status.append("❌ 价格<EMA50")
    if ind.get("ema20_above_ema50"):
        ema_status.append("✅ 多头排列(EMA20>EMA50)")
    else:
        ema_status.append("❌ 空头排列(EMA20<EMA50)")
    st.caption(" · ".join(ema_status))

    st.divider()

    # ─ 三大维度 ─
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown("#### ⚔️ 江恩价格轴")
        st.markdown(f"{gann.get('zone_color','')} **{gann.get('zone','')}**")
        st.markdown(f"信号：{gann.get('zone_signal','')}")
        gann_data = {
            "水平": ["江恩S2", "江恩S1", "当前价", "江恩R1", "江恩R2"],
            "价格": [
                gann.get("s2", 0), gann.get("s1", 0),
                ind.get("price", 0),
                gann.get("r1", 0), gann.get("r2", 0)
            ]
        }
        gann_df = pd.DataFrame(gann_data)
        st.dataframe(gann_df, hide_index=True, use_container_width=True)
        st.caption(f"距S1: {gann.get('dist_to_s1_pct',0):+.1f}% | 距R1: {gann.get('dist_to_r1_pct',0):.1f}%")

    with col_b:
        st.markdown("#### 📊 相对强弱 (20日)")
        st.markdown(f"**{rs.get('rs_label','')}**")
        st.metric("vs SPY", f"{rs.get('rs_vs_spy',0):+.1f}%")
        st.metric("vs QQQ", f"{rs.get('rs_vs_qqq',0):+.1f}%")
        # RS雷达图（简化为进度条）
        st.markdown("RS评分")
        st.progress(rs.get("rs_score", 3) / 5)

    with col_c:
        st.markdown("#### 💰 估值状态（段永平式）")
        st.markdown(f"**{val.get('val_zone','')}**")
        st.caption(val.get("val_signal", ""))
        val_data = {
            "估值层": ["底线估值", "市场共识", "当前价格"],
            "价格": [
                val.get("bottom_valuation", 0),
                val.get("consensus_valuation", 0),
                ind.get("price", 0)
            ]
        }
        val_df = pd.DataFrame(val_data)
        st.dataframe(val_df, hide_index=True, use_container_width=True)
        upside = val.get("upside_to_consensus_pct", 0)
        st.metric("至共识估值空间", f"{upside:+.1f}%")

    st.divider()

    # ─ 技术信号 ─
    st.markdown("#### 🔍 技术信号详情")
    tech_label = tech.get("label", "")
    tech_score_val = tech.get("score", 0)
    st.markdown(f"技术状态：**{tech_label}**（评分：{tech_score_val}/100）")
    for sig in tech.get("signals", []):
        st.caption(f"• {sig}")

    st.divider()

    # ─ 操作建议 ─
    st.markdown("#### 🎯 三层操作建议")

    short = plan.get("short", {})
    mid = plan.get("mid", {})
    long_ = plan.get("long", {})

    tab1, tab2, tab3 = st.tabs(["⚡ 短线 (1-3天)", "📅 中线 (1-2周)", "🏔️ 长线 (1-2月)"])

    with tab1:
        st.markdown(f"### {short.get('action','')}")
        st.markdown(f"**策略**：{short.get('desc','')}")
        st.success(f"✅ 触发条件：{short.get('trigger','')}")
        st.error(f"🛑 止损：{short.get('stop','')}")

    with tab2:
        st.markdown(f"### {mid.get('action','')}")
        st.markdown(f"**策略**：{mid.get('desc','')}")
        st.success(f"✅ 续持条件：{mid.get('trigger','')}")
        st.warning(f"⚠️ 退出条件：{mid.get('exit','')}")

    with tab3:
        st.markdown(f"### {long_.get('action','')}")
        st.markdown(f"**策略**：{long_.get('desc','')}")
        st.info(f"📌 {long_.get('note','')}")

    st.divider()
    st.divider()

    # ─ 财报 + 期权快照 ─
    with st.expander("📅 财报日历 & 江恩时间窗口", expanded=False):
        with st.spinner("加载时间轴…"):
            ta = compile_time_axis(selected)
        ed = ta.get("earnings", {})
        adv = ta.get("earnings_advice", {})
        ec1, ec2, ec3 = st.columns(3)
        if "error" not in ed:
            ec1.metric("下次财报", ed.get("date", "—"))
            ec2.metric("距今", f"{ed.get('days_until','—')} 天")
            ec3.metric("阶段", adv.get("phase", "—"))
            st.markdown(f"{adv.get('color','')} **{adv.get('advice','')}**")
        else:
            st.info("无财报数据")
        upcoming = ta.get("upcoming_windows", [])
        if upcoming:
            st.markdown("**接下来江恩时间窗口：**")
            for w in upcoming[:3]:
                badge = "🔥" if w.get("is_imminent") else "📅"
                st.caption(f"{badge} {w['target_date']} (+{w['days_from_today']}d) · {w['cycle']} · 锚点: {w.get('anchor_type','—')}")

    with st.expander("🎰 期权 & Gamma 快照（最近到期）", expanded=False):
        try:
            with st.spinner("加载期权链…"):
                exps_l = get_expirations(selected)
                if exps_l:
                    rpt_l = compile_options_report(selected, exps_l[0])
                else:
                    rpt_l = {"error": "无期权数据"}
            if "error" in rpt_l:
                st.info(rpt_l["error"])
            else:
                oc1, oc2, oc3, oc4 = st.columns(4)
                oc1.metric("到期日", rpt_l["expiration"])
                oc2.metric("Max Pain", f"${rpt_l['max_pain']:.2f}",
                           f"{rpt_l['max_pain_distance_pct']:+.1f}%")
                oc3.metric("Call Wall", f"${rpt_l['key_strikes']['call_wall']:.2f}")
                oc4.metric("Put Wall", f"${rpt_l['key_strikes']['put_wall']:.2f}")
                st.info(f"📊 {rpt_l['pcr_signal']}")
                st.info(f"🎯 {rpt_l['max_pain_signal']}")
                if rpt_l.get("gex", {}).get("interpretation"):
                    st.info(f"💫 {rpt_l['gex']['interpretation']}")
                st.caption("→ 完整期权链请见左侧「🎰 期权 & Gamma」页")
        except Exception as e:
            st.warning(f"期权数据获取失败: {e}")

    st.caption(f"数据更新时间：{r.get('updated_at','—')}")


# ─────────────────────────────────────────────
#  页面：时间轴 & 财报
# ─────────────────────────────────────────────

elif page == "📅 时间轴 & 财报":
    st.markdown("## 📅 江恩时间轴 & 财报日历")
    st.caption("不同时间窗口对应不同操作策略 — 财报敏感期/江恩转折日提前预警")

    # ─── 财报日历总览 ───
    st.markdown("### 🗓️ 近30天财报日历")
    with st.spinner("正在汇总财报数据…"):
        @st.cache_data(ttl=3600, show_spinner=False)
        def _cached_all_time_axis():
            return compile_all_time_axis("watchlist.json")
        all_ta = _cached_all_time_axis()

    # 整理财报表
    earnings_rows = []
    for ta in all_ta:
        if "error" in ta:
            continue
        ed = ta.get("earnings", {})
        if "error" in ed:
            continue
        du = ed.get("days_until")
        if du is None or du < -5 or du > 60:
            continue
        adv = ta.get("earnings_advice", {})
        earnings_rows.append({
            "Ticker": ta["ticker"],
            "名称": ta.get("name", ""),
            "财报日": ed.get("date", ""),
            "星期": ed.get("weekday", ""),
            "距今天数": du,
            "阶段": adv.get("phase", ""),
            "颜色": adv.get("color", ""),
            "操作建议": adv.get("advice", ""),
        })

    earnings_rows.sort(key=lambda x: x["距今天数"])

    if earnings_rows:
        df_e = pd.DataFrame(earnings_rows)
        # 按距财报天数着色
        def color_days(d):
            try:
                d = int(d)
            except Exception:
                return ""
            if d <= 0:
                return "background-color: #f8d7da"
            elif d <= 3:
                return "background-color: #f5c6cb"
            elif d <= 7:
                return "background-color: #ffe5d0"
            elif d <= 14:
                return "background-color: #fff3cd"
            else:
                return "background-color: #d4edda"
        styled = df_e.style.applymap(color_days, subset=["距今天数"])
        st.dataframe(styled, hide_index=True, use_container_width=True)
    else:
        st.info("近期无可用财报数据")

    st.divider()

    # ─── 单只股票时间轴详情 ───
    st.markdown("### 🎯 单只股票江恩时间窗口")
    tickers_avail = [s["ticker"] for s in wl_data["stocks"]]
    sel_t = st.selectbox("选择股票", tickers_avail, key="time_axis_sel")

    with st.spinner(f"加载 {sel_t} 时间轴…"):
        ta = compile_time_axis(sel_t)

    # 财报信息
    ed = ta.get("earnings", {})
    adv = ta.get("earnings_advice", {})
    c1, c2, c3 = st.columns(3)
    if "error" in ed:
        c1.metric("下次财报", "—")
    else:
        c1.metric("下次财报", ed.get("date", "—"), f"{ed.get('weekday','')}")
        c2.metric("距今天数", f"{ed.get('days_until','—')} 天")
        c3.metric("阶段", adv.get("phase", "—"))

    if adv.get("advice"):
        st.markdown(f"{adv.get('color','')} **{adv.get('advice','')}**")

    st.divider()

    # 锚点信息
    anchors = ta.get("anchors", {})
    if anchors:
        st.markdown("#### 📍 关键锚点日期")
        ac1, ac2, ac3 = st.columns(3)
        if anchors.get("52w_high_date"):
            ac1.metric("52周高点日",
                       str(anchors["52w_high_date"]),
                       f"${anchors['52w_high_price']:.2f}")
        if anchors.get("52w_low_date"):
            ac2.metric("52周低点日",
                       str(anchors["52w_low_date"]),
                       f"${anchors['52w_low_price']:.2f}")
        if anchors.get("recent_spike_date"):
            ac3.metric("近期放量日", str(anchors["recent_spike_date"]))

    # 接下来江恩时间窗口
    st.markdown("#### ⏰ 接下来的江恩时间窗口（按距今天数排序）")
    upcoming = ta.get("upcoming_windows", [])
    if upcoming:
        for w in upcoming:
            badge = "🔥" if w.get("is_imminent") else "📅"
            st.markdown(f"""
{badge} **{w['target_date']}** （距今 +{w['days_from_today']}天） · {w['cycle']}  
&nbsp;&nbsp;&nbsp;&nbsp;锚点：{w.get('anchor_type', '—')} ({w.get('anchor_date','')})
""")
    else:
        st.info("近30天无江恩重要时间窗口")

    with st.expander("📚 江恩时间循环说明"):
        st.markdown("""
| 循环 | 意义 |
|------|------|
| 30天 | 短小循环 |
| 45天 | 江恩转折日（重要） |
| 60天 | 中循环 |
| **90天** | **季度循环（重要）** — 通常对应一次明确转折 |
| 120天 | 江恩中周期 |
| 144天 | 江恩主循环（江恩最重要的数字之一） |
| **180天** | **半年循环（重要）** |
| 270天 | 三季度循环 |
| **360天** | **年度循环（重要）** — 通常出现大级别转折 |

**使用方法**：
- 从52周高/低点开始计算
- 若价格接近某个江恩窗口（±2天内），警惕转折
- 多个时间窗口在同一天叠加 = **极高概率转折日**
""")


# ─────────────────────────────────────────────
#  页面：期权 & Gamma
# ─────────────────────────────────────────────

elif page == "🎰 期权 & Gamma":
    st.markdown("## 🎰 期权结构分析 · 告警 & 操作建议")
    st.caption("Gamma Flip · Wall强度 · IV制度 · 期限结构 · 异常活动 → 具体操作playbook")

    tickers_avail = [s["ticker"] for s in wl_data["stocks"]]
    csel, cexp = st.columns([1, 1])
    sel_t = csel.selectbox("选择股票", tickers_avail, key="opt_sel")

    with st.spinner("加载到期日…"):
        exps = get_expirations(sel_t)
    if not exps:
        st.error(f"{sel_t} 无可用期权数据")
        st.stop()
    sel_exp = cexp.selectbox("到期日", exps, index=0)

    with st.spinner(f"分析 {sel_t} 期权结构 ({sel_exp})…"):
        rpt = full_structural_analysis(sel_t, sel_exp)
    if "error" in rpt:
        st.error(rpt["error"])
        st.stop()

    spot = rpt["spot"]
    flip = rpt.get("flip", {})
    walls = rpt.get("walls", {})
    iv_regime = rpt.get("iv_regime", {})
    term = rpt.get("term", {})
    alerts = rpt.get("alerts", [])
    playbook = rpt.get("playbook", {})

    # ═══════════════════════════════════════
    # 🚨 SECTION 1: 优先级告警
    # ═══════════════════════════════════════
    st.markdown("### 🚨 结构告警（按优先级排序）")
    high_alerts = [a for a in alerts if a.get("level") == "high"]
    med_alerts = [a for a in alerts if a.get("level") == "med"]
    info_alerts = [a for a in alerts if a.get("level") == "info"]

    if high_alerts:
        for a in high_alerts:
            st.error(f"{a['icon']} **{a['title']}**\n\n{a['desc']}\n\n👉 **操作**：{a['action']}")
    if med_alerts:
        for a in med_alerts:
            st.warning(f"{a['icon']} **{a['title']}**\n\n{a['desc']}\n\n👉 **操作**：{a['action']}")
    if info_alerts and not high_alerts and not med_alerts:
        for a in info_alerts:
            st.success(f"{a['icon']} **{a['title']}** — {a['desc']}\n\n👉 {a['action']}")

    st.divider()

    # ═══════════════════════════════════════
    # 🎯 SECTION 2: 操作 Playbook
    # ═══════════════════════════════════════
    st.markdown("### 🎯 操作 Playbook（基于当前结构）")

    pb1, pb2 = st.columns(2)
    with pb1:
        st.markdown("#### 📊 现货操作")
        for a in playbook.get("stock_advice", []):
            st.markdown(f"- {a}")

        st.markdown("#### 🛡️ 对冲建议")
        for a in playbook.get("hedge_advice", []):
            st.markdown(f"- {a}")

    with pb2:
        st.markdown("#### ⚙️ 推荐期权策略")
        for s in playbook.get("opt_strategies", []):
            with st.container(border=True):
                st.markdown(f"**{s['name']}**")
                st.caption(s["desc"])
                st.caption(f"💡 _理由_：{s['why']}")

    st.markdown("#### 👀 关键观察点")
    for w in playbook.get("watch_points", []):
        st.markdown(f"- {w}")

    st.divider()

    # ═══════════════════════════════════════
    # 🧱 SECTION 3: 结构详情
    # ═══════════════════════════════════════
    st.markdown("### 🧱 结构详情")

    # 顶部4个关键指标
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("现价", f"${spot:.2f}")
    if flip.get("flip_strike"):
        regime_color = "🟢" if flip["regime"] == "正Gamma" else "🔴"
        s2.metric(f"Gamma Flip {regime_color}",
                  f"${flip['flip_strike']:.2f}",
                  f"{flip['flip_distance_pct']:+.1f}% from spot")
    else:
        s2.metric("Gamma状态", flip.get("regime", "—"))
    s3.metric("Max Pain", f"${rpt['max_pain']:.2f}",
              f"{rpt['max_pain_distance_pct']:+.1f}%")
    if iv_regime.get("atm_iv_avg"):
        delta_label = None
        if iv_regime.get("iv_hv_ratio"):
            delta_label = f"IV/HV={iv_regime['iv_hv_ratio']}"
        s4.metric("ATM IV", f"{iv_regime['atm_iv_avg']:.1f}%", delta_label)

    # Gamma 制度
    with st.expander("⚡ Gamma 制度详情", expanded=True):
        if flip.get("regime_signal"):
            st.markdown(f"**{flip['regime_signal']}**")
        st.caption("""
**正Gamma环境**：做市商持有正gamma → 上涨时卖出对冲，下跌时买入对冲 → 抑制波动，区间震荡  
**负Gamma环境**：做市商持有负gamma → 上涨时买入加剧上涨，下跌时卖出加剧下跌 → 趋势放大，剧烈波动
        """)

    # Wall 详情
    with st.expander("🧱 Wall 强度分析", expanded=True):
        if walls:
            wc1, wc2 = st.columns(2)
            with wc1:
                st.markdown(f"#### 🔺 Call Wall (上方阻力)")
                st.metric(f"${walls['call_wall_strike']:.2f}",
                          f"{walls['call_wall_pct_above']:+.1f}% 距现价",
                          f"OI {walls['call_wall_oi']}")
                st.caption(f"强度: {walls['call_wall_grade']} (OI是平均{walls['call_wall_strength']:.1f}x)")
            with wc2:
                st.markdown(f"#### 🔻 Put Wall (下方支撑)")
                st.metric(f"${walls['put_wall_strike']:.2f}",
                          f"-{walls['put_wall_pct_below']:.1f}% 距现价",
                          f"OI {walls['put_wall_oi']}")
                st.caption(f"强度: {walls['put_wall_grade']} (OI是平均{walls['put_wall_strength']:.1f}x)")

            st.info(f"📐 **结构对称性**：{walls['asymmetry']}")

    # IV 制度
    with st.expander("📊 IV 制度 & 期限结构", expanded=True):
        if iv_regime:
            ic1, ic2 = st.columns(2)
            with ic1:
                st.markdown(f"**{iv_regime['iv_level']}**")
                st.caption(iv_regime["iv_advice"])
                if iv_regime.get("iv_hv_signal"):
                    st.info(iv_regime["iv_hv_signal"])
            with ic2:
                iv_data = {
                    "指标": ["ATM IV平均", "20日HV", "IV/HV比", "Put Skew"],
                    "值": [
                        f"{iv_regime['atm_iv_avg']:.1f}%",
                        f"{iv_regime.get('hv_20', '—')}%" if iv_regime.get('hv_20') else "—",
                        iv_regime.get('iv_hv_ratio', '—'),
                        f"{rpt.get('iv',{}).get('iv_skew',0):.1f}",
                    ],
                }
                st.dataframe(pd.DataFrame(iv_data), hide_index=True, use_container_width=True)

        if term.get("term_structure"):
            st.markdown(f"**期限结构: {term['shape']}**")
            st.caption(term["interpretation"])
            term_df = pd.DataFrame(term["term_structure"])
            term_df.columns = ["到期日", "DTE", "ATM IV%"]
            st.dataframe(term_df, hide_index=True, use_container_width=True)

    # 异常活动
    unusual = rpt.get("unusual", {})
    if unusual.get("flags"):
        with st.expander("⚡ 异常期权活动（Smart Money追踪）", expanded=True):
            for f in unusual["flags"]:
                st.markdown(f"- {f}")
            if not unusual.get("unusual_strikes", pd.DataFrame()).empty:
                df_u = unusual["unusual_strikes"].copy()
                df_u["impliedVolatility"] = (df_u["impliedVolatility"] * 100).round(1)
                df_u.columns = ["Strike", "Volume", "OI", "Vol/OI", "IV%", "Side"]
                st.dataframe(df_u, hide_index=True, use_container_width=True)

    st.divider()

    # ═══════════════════════════════════════
    # 📊 SECTION 4: OI 分布可视化
    # ═══════════════════════════════════════
    st.markdown("### 📊 Open Interest 分布")
    import plotly.graph_objects as _go
    full = get_option_chain(sel_t, sel_exp)
    if "error" not in full:
        calls_df = full["calls"]
        puts_df = full["puts"]
        lo, hi = spot * 0.7, spot * 1.3
        c_filt = calls_df[(calls_df["strike"] >= lo) & (calls_df["strike"] <= hi)]
        p_filt = puts_df[(puts_df["strike"] >= lo) & (puts_df["strike"] <= hi)]

        fig = _go.Figure()
        fig.add_trace(_go.Bar(
            x=c_filt["strike"], y=c_filt["openInterest"],
            name="Call OI", marker_color="#28a745", opacity=0.7,
        ))
        fig.add_trace(_go.Bar(
            x=p_filt["strike"], y=-p_filt["openInterest"],
            name="Put OI", marker_color="#dc3545", opacity=0.7,
        ))
        # 关键参考线
        fig.add_vline(x=spot, line_dash="solid", line_color="#0d6efd",
                      annotation_text=f"现价 ${spot:.2f}", annotation_position="top")
        fig.add_vline(x=rpt["max_pain"], line_dash="dash", line_color="#ff9800",
                      annotation_text=f"Max Pain ${rpt['max_pain']:.2f}", annotation_position="top")
        if walls.get("call_wall_strike"):
            fig.add_vline(x=walls["call_wall_strike"], line_dash="dot", line_color="#28a745",
                          annotation_text=f"Call Wall", annotation_position="bottom")
        if walls.get("put_wall_strike"):
            fig.add_vline(x=walls["put_wall_strike"], line_dash="dot", line_color="#dc3545",
                          annotation_text=f"Put Wall", annotation_position="bottom")
        if flip.get("flip_strike"):
            fig.add_vline(x=flip["flip_strike"], line_dash="dashdot", line_color="#9c27b0",
                          annotation_text=f"⚡ Gamma Flip", annotation_position="bottom")
        fig.update_layout(
            barmode="overlay", height=420,
            xaxis_title="Strike", yaxis_title="OI (Put为负值)",
            margin=dict(l=40, r=20, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.caption(f"数据更新：{rpt.get('compiled_at','—')}")


# ─────────────────────────────────────────────
#  页面：市场结构
# ─────────────────────────────────────────────

elif page == "📊 市场结构":
    st.markdown("## 📊 市场结构全景")

    if not data_ok or not all_results:
        st.warning("暂无数据，请点击左侧「刷新数据」")
        st.stop()

    valid = [r for r in all_results if "error" not in r and "plan" in r]

    # ─ 评分排名 ─
    st.markdown("### 🏆 综合评分排名")
    score_data = []
    for r in valid:
        score_data.append({
            "Ticker": r["ticker"],
            "名称": r["name"],
            "板块": ticker_meta_map.get(r["ticker"], {}).get("sector", ""),
            "综合评分": r["plan"]["composite_score"],
            "技术状态": r["tech"]["label"],
            "相对强弱": r["rs"]["rs_label"],
            "估值区间": r["val"].get("val_zone", ""),
            "江恩区间": r["gann"].get("zone", ""),
            "价格": r["indicators"]["price"],
            "RSI": r["indicators"]["rsi_14"],
            "20日动量%": r["indicators"]["momentum_20d"],
            "短线操作": r["plan"]["short"]["action"],
        })
    df_scores = pd.DataFrame(score_data).sort_values("综合评分", ascending=False)

    # 颜色映射
    def color_score(val):
        if val >= 70:
            return "background-color: #d4edda"
        elif val >= 55:
            return "background-color: #fff3cd"
        elif val >= 40:
            return "background-color: #ffe5d0"
        else:
            return "background-color: #f8d7da"

    styled = df_scores.style.applymap(color_score, subset=["综合评分"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.divider()

    # ─ 主线层次分布 ─
    st.markdown("### 🗂️ 主线层次分布")
    layer_counts = {}
    for r in valid:
        layer = r.get("mainline_layer", "其他")
        score = r["plan"]["composite_score"]
        if layer not in layer_counts:
            layer_counts[layer] = {"count": 0, "avg_score": 0, "scores": []}
        layer_counts[layer]["count"] += 1
        layer_counts[layer]["scores"].append(score)

    for layer, info in layer_counts.items():
        info["avg_score"] = sum(info["scores"]) / len(info["scores"])

    layer_df = pd.DataFrame([
        {"层次": k, "股票数": v["count"], "平均评分": round(v["avg_score"], 1)}
        for k, v in layer_counts.items()
    ]).sort_values("平均评分", ascending=False)

    col1, col2 = st.columns(2)
    with col1:
        st.dataframe(layer_df, hide_index=True, use_container_width=True)
    with col2:
        fig_pie = go.Figure(go.Pie(
            labels=layer_df["层次"],
            values=layer_df["股票数"],
            hole=0.4,
        ))
        fig_pie.update_layout(height=280, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # ─ RS vs 评分气泡图 ─
    st.markdown("### 🔵 相对强弱 vs 综合评分")
    bubble_data = []
    for r in valid:
        bubble_data.append({
            "Ticker": r["ticker"],
            "RS vs QQQ": r["rs"]["rs_vs_qqq"],
            "综合评分": r["plan"]["composite_score"],
            "RSI": r["indicators"]["rsi_14"],
            "Sector": ticker_meta_map.get(r["ticker"], {}).get("sector", ""),
        })
    df_bubble = pd.DataFrame(bubble_data)

    fig_bubble = go.Figure()
    for _, row in df_bubble.iterrows():
        fig_bubble.add_trace(go.Scatter(
            x=[row["RS vs QQQ"]],
            y=[row["综合评分"]],
            mode="markers+text",
            text=[row["Ticker"]],
            textposition="top center",
            marker=dict(
                size=row["RSI"] / 4,
                color=score_color(row["综合评分"]),
                opacity=0.8,
            ),
            name=row["Ticker"],
            showlegend=False,
        ))

    fig_bubble.add_hline(y=55, line_dash="dot", line_color="gray",
                          annotation_text="评分分界线")
    fig_bubble.add_vline(x=0, line_dash="dot", line_color="gray",
                          annotation_text="相对强弱分界")
    fig_bubble.update_layout(
        xaxis_title="20日RS vs QQQ (%)",
        yaxis_title="综合评分",
        height=480,
        margin=dict(l=40, r=40, t=20, b=40),
    )
    st.plotly_chart(fig_bubble, use_container_width=True)
    st.caption("气泡大小 = RSI大小 | 右上角 = 强势进攻区 | 左下角 = 弱势回避区")


# ─────────────────────────────────────────────
#  页面：设置
# ─────────────────────────────────────────────

elif page == "⚙️ 设置":
    st.markdown("## ⚙️ Watchlist 管理")

    from watchlist_helper import (
        add_ticker, remove_ticker, refresh_ticker,
        update_field, auto_generate_meta
    )

    # ─── 添加新ticker ───
    st.markdown("### ➕ 添加新股票")
    st.caption("只需输入 ticker，其它字段（市场身份、江恩水平、估值等）将自动从yfinance推断")

    with st.form("add_ticker_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 4, 1])
        with c1:
            new_ticker = st.text_input("Ticker", placeholder="例如 NVDA, AAPL")
        with c2:
            new_notes = st.text_input("备注（可选）", placeholder="留空将自动填充行业/市值/Beta")
        with c3:
            st.markdown("&nbsp;")
            submit = st.form_submit_button("➕ 添加", use_container_width=True, type="primary")

        if submit and new_ticker:
            try:
                with st.spinner(f"正在从 yfinance 获取 {new_ticker.upper()} 数据…"):
                    msg = add_ticker(new_ticker, new_notes)
                if "✅" in msg:
                    st.success(msg)
                    st.cache_data.clear()
                else:
                    st.warning(msg)
            except Exception as e:
                st.error(f"❌ 添加失败：{e}")

    # 一键批量添加
    with st.expander("📋 批量添加（每行一个ticker）"):
        bulk = st.text_area("Tickers", placeholder="NVDA\nMSFT\nGOOG\nAAPL", height=120)
        if st.button("批量添加"):
            tickers = [t.strip().upper() for t in bulk.splitlines() if t.strip()]
            ok, fail = [], []
            progress = st.progress(0)
            for i, t in enumerate(tickers):
                try:
                    msg = add_ticker(t)
                    if "✅" in msg:
                        ok.append(t)
                    else:
                        fail.append(f"{t}: {msg}")
                except Exception as e:
                    fail.append(f"{t}: {e}")
                progress.progress((i + 1) / len(tickers))
            if ok:
                st.success(f"✅ 成功添加: {', '.join(ok)}")
                st.cache_data.clear()
            if fail:
                st.warning("⚠️ 失败:\n" + "\n".join(fail))

    st.divider()

    # ─── 当前Watchlist ───
    st.markdown("### 📋 当前 Watchlist")
    wl_now = load_watchlist()
    st.caption(f"共 {len(wl_now['stocks'])} 只股票")

    if not wl_now["stocks"]:
        st.info("Watchlist 为空，请先在上方添加股票")
    else:
        # 编辑模式选择
        edit_mode = st.radio(
            "查看模式",
            ["📊 表格视图（快速删除/刷新）", "✏️ 详细编辑（修改单只股票）"],
            horizontal=True,
            label_visibility="collapsed"
        )

        if edit_mode == "📊 表格视图（快速删除/刷新）":
            for s in wl_now["stocks"]:
                with st.container(border=True):
                    cols = st.columns([1, 3, 2, 2, 1, 1])
                    cols[0].markdown(f"**{s['ticker']}**")
                    cols[1].caption(s.get("name", ""))
                    cols[2].caption(s.get("sector", ""))
                    cols[3].caption(s.get("market_identity", ""))
                    if cols[4].button("🔄", key=f"refresh_{s['ticker']}", help="重新获取最新元数据"):
                        try:
                            with st.spinner(f"刷新 {s['ticker']}…"):
                                msg = refresh_ticker(s["ticker"])
                            st.toast(msg)
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"刷新失败: {e}")
                    if cols[5].button("🗑️", key=f"del_{s['ticker']}", help="移除"):
                        msg = remove_ticker(s["ticker"])
                        st.toast(msg)
                        st.cache_data.clear()
                        st.rerun()

        else:  # 详细编辑
            tickers = [s["ticker"] for s in wl_now["stocks"]]
            sel = st.selectbox("选择股票", tickers)
            stock = next(s for s in wl_now["stocks"] if s["ticker"] == sel)

            with st.form(f"edit_{sel}"):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("名称", stock.get("name", ""))
                    market_identity = st.selectbox(
                        "市场身份",
                        ["总龙头（时代级）", "平台级龙头", "细分龙头",
                         "次级标的", "情绪/小市值标的", "身份切换阶段（矿企→AI算力）",
                         "新兴小票/情绪龙头", "AI infra细分龙头",
                         "AI网络安全龙头", "AI软件/边缘网络龙头",
                         "AI医疗应用龙头", "AI+能源+自动驾驶综合体",
                         "AI时代元宇宙/创作平台", "AI时代新金融平台",
                         "AI软件/政府+企业AI平台"],
                        index=0 if stock.get("market_identity", "") not in [
                            "总龙头（时代级）", "平台级龙头", "细分龙头",
                            "次级标的", "情绪/小市值标的"
                        ] else ["总龙头（时代级）", "平台级龙头", "细分龙头",
                                "次级标的", "情绪/小市值标的"].index(stock.get("market_identity", "细分龙头"))
                    )
                    mainline_layer = st.selectbox(
                        "主线层次",
                        ["基础设施层（Infra）", "平台层（Platform）", "应用层（Application）"],
                        index=["基础设施层（Infra）", "平台层（Platform）", "应用层（Application）"].index(
                            stock.get("mainline_layer", "应用层（Application）")
                        )
                    )
                    sector = st.text_input("板块", stock.get("sector", ""))
                    discount_horizon = st.text_input("折现窗口", stock.get("discount_horizon", ""))

                with col2:
                    bottom_val = st.number_input(
                        "底线估值（段永平式）",
                        value=float(stock.get("bottom_valuation", 0)),
                        step=1.0, format="%.2f"
                    )
                    consensus_val = st.number_input(
                        "共识估值",
                        value=float(stock.get("consensus_valuation", 0)),
                        step=1.0, format="%.2f"
                    )
                    g = stock.get("gann_levels", {})
                    g_s2 = st.number_input("江恩 S2（强支撑）", value=float(g.get("s2", 0)), format="%.2f")
                    g_s1 = st.number_input("江恩 S1（次支撑）", value=float(g.get("s1", 0)), format="%.2f")
                    g_r1 = st.number_input("江恩 R1（次压力）", value=float(g.get("r1", 0)), format="%.2f")
                    g_r2 = st.number_input("江恩 R2（强压力）", value=float(g.get("r2", 0)), format="%.2f")

                notes = st.text_area("备注/分析笔记", stock.get("notes", ""), height=80)

                btn1, btn2 = st.columns(2)
                save = btn1.form_submit_button("💾 保存修改", use_container_width=True, type="primary")
                regen = btn2.form_submit_button("🔄 重新自动生成（覆盖手动修改）", use_container_width=True)

                if save:
                    stock.update({
                        "name": name,
                        "market_identity": market_identity,
                        "mainline_layer": mainline_layer,
                        "sector": sector,
                        "discount_horizon": discount_horizon,
                        "bottom_valuation": bottom_val,
                        "consensus_valuation": consensus_val,
                        "gann_levels": {"s2": g_s2, "s1": g_s1, "r1": g_r1, "r2": g_r2},
                        "notes": notes,
                    })
                    from watchlist_helper import save_watchlist
                    save_watchlist(wl_now)
                    st.cache_data.clear()
                    st.success(f"✅ {sel} 已保存")
                    st.rerun()

                if regen:
                    try:
                        with st.spinner(f"重新生成 {sel}…"):
                            msg = refresh_ticker(sel)
                        st.success(msg)
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"失败: {e}")

    st.divider()

    # ─── 市场环境编辑 ───
    with st.expander("🌍 市场环境配置（影响顶部横幅）"):
        ctx = wl_now.get("market_context", {})
        with st.form("ctx_form"):
            c1, c2 = st.columns(2)
            with c1:
                cm = st.text_input("当前主线", ctx.get("current_mainline", ""))
                le = st.text_input("流动性环境", ctx.get("liquidity_env", ""))
                ra = st.text_input("风险偏好", ctx.get("risk_appetite", ""))
            with c2:
                kc = st.text_input("关键催化剂", ctx.get("key_catalyst", ""))
                cp = st.text_input("周期阶段", ctx.get("cycle_phase", ""))
                mn = st.text_input("宏观备注", ctx.get("macro_note", ""))
            if st.form_submit_button("💾 保存市场环境", type="primary"):
                wl_now["market_context"] = {
                    "current_mainline": cm, "liquidity_env": le,
                    "risk_appetite": ra, "key_catalyst": kc,
                    "cycle_phase": cp, "macro_note": mn,
                }
                from watchlist_helper import save_watchlist
                save_watchlist(wl_now)
                st.cache_data.clear()
                st.success("✅ 市场环境已保存")
                st.rerun()

    # ─── 高级：直接编辑JSON ───
    with st.expander("🛠️ 高级：直接编辑 JSON"):
        with open("watchlist.json", "r", encoding="utf-8") as f:
            wl_raw = f.read()
        edited = st.text_area("watchlist.json", wl_raw, height=400)
        if st.button("💾 保存 JSON"):
            try:
                json.loads(edited)
                with open("watchlist.json", "w", encoding="utf-8") as f:
                    f.write(edited)
                st.cache_data.clear()
                st.success("✅ JSON 已保存")
            except json.JSONDecodeError as e:
                st.error(f"❌ JSON 格式错误：{e}")

    st.divider()
    st.markdown("### 📖 使用说明")
    st.markdown("""
**综合评分（0-100）**
- 🟢 70+ → 进攻/强势，可积极操作
- 🟡 55-70 → 持有/偏强，保持持仓
- 🟠 40-55 → 观察/中性，谨慎操作
- 🔴 <40 → 回避/弱势，控制风险

**江恩价格轴**
- S2/S1 = 支撑位（买入参考）
- R1/R2 = 压力位（减仓参考）
- 当前区间决定操作倾向

**段永平式估值**
- 底线估值 = 即使最悲观也值这个价（安全垫）
- 共识估值 = 当前市场主流机构定价
- 上涨空间 = (共识估值 - 现价) / 现价

**操作三层**
- 1-3天：短线节奏，跟技术状态和RSI
- 1-2周：中线趋势，跟相对强弱和均线
- 1-2月：长线配置，跟估值和折现窗口

**刷新频率**：数据每15分钟自动缓存，点「刷新数据」可强制更新
    """)

    st.divider()
    st.markdown("### 🔑 核心理念")
    st.info("""
    **流动性决定一切** → 先判断宏观流动性方向  
    **主线识别** → 资金在哪一层流动  
    **江恩时间价格** → 在正确的价格区间、正确的时间窗口操作  
    **段永平底线** → 永远知道最坏情况下能守住的价格  
    **空仓是操作** → 不在不适合的环境里强行做单
    """)
