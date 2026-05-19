"""
deep_report.py
深度推演报告合成器：将 Gann Sq9 + 多周期技术 + 期权结构 + 资金流
合成为类似 CRDO 风格的叙事式深度分析报告
"""

from gann_sq9 import full_gann_analysis
from multi_timeframe import multi_timeframe_analysis
from money_flow import analyze_money_flow
from options_gamma import full_structural_analysis, get_expirations
from gann_time import get_next_earnings


def find_confluence(gann: dict, mtf: dict, options: dict) -> list:
    """
    寻找多维度共振：当价格落在多个不同体系的关键位时
    （江恩九宫位 + 布林中轨 + 均线 + 期权Wall + 当前价 = 共振区）
    """
    if not gann or "error" in gann:
        return []

    price = gann.get("current_price", 0)
    if price <= 0:
        return []

    confluences = []
    tol = price * 0.015  # 1.5% 容忍度

    # 收集所有关键位
    levels = []

    # Gann Sq9 关键位
    for r in gann.get("resonances", []):
        levels.append((r["target"], f"江恩{r['type']} ({r.get('degrees','—')}°)"))
    for nr in gann.get("closest_levels", {}).get("next_resistances", [])[:2]:
        levels.append((nr["target"], f"江恩{nr['degrees']}°阻力"))
    for ns in gann.get("closest_levels", {}).get("next_supports_from_top", [])[:2]:
        levels.append((ns["target"], f"江恩-{ns['degrees']}°支撑"))

    # 多周期均线
    if mtf and "error" not in mtf:
        for tf_name, tf in [("周线", mtf.get("weekly", {})),
                            ("日线", mtf.get("daily", {})),
                            ("1H", mtf.get("hourly", {}))]:
            for ma_key in ["ma5", "ma10", "ma20", "ma50"]:
                v = tf.get(ma_key)
                if v:
                    levels.append((v, f"{tf_name}{ma_key.upper()}"))
            for bb_key, label in [("boll_upper", "布林上轨"),
                                  ("boll_mid", "布林中轨"),
                                  ("boll_lower", "布林下轨")]:
                v = tf.get(bb_key)
                if v:
                    levels.append((v, f"{tf_name}{label}"))

        # 筹码POC
        vp = mtf.get("volume_profile")
        if vp:
            levels.append((vp["poc"]["price_mid"], "筹码POC"))
            levels.append((vp["value_area_high"], "Value Area High"))
            levels.append((vp["value_area_low"], "Value Area Low"))

    # 期权 Walls
    if options and "error" not in options:
        walls = options.get("walls", {})
        if walls.get("call_wall_strike"):
            levels.append((walls["call_wall_strike"], "Call Wall"))
        if walls.get("put_wall_strike"):
            levels.append((walls["put_wall_strike"], "Put Wall"))
        if options.get("max_pain"):
            levels.append((options["max_pain"], "Max Pain"))
        flip = options.get("flip", {})
        if flip.get("flip_strike"):
            levels.append((flip["flip_strike"], "Gamma Flip"))

    # 按距当前价分组：所有距离<tol的levels归为一组
    # 然后找出包含2+不同体系的群组
    levels.sort(key=lambda x: x[0])
    groups = []
    for lvl, label in levels:
        added = False
        for g in groups:
            if abs(g["center"] - lvl) < tol:
                g["items"].append((lvl, label))
                # 重新计算中心
                g["center"] = sum(it[0] for it in g["items"]) / len(g["items"])
                added = True
                break
        if not added:
            groups.append({"center": lvl, "items": [(lvl, label)]})

    # 只保留 >= 3个不同体系的共振组
    for g in groups:
        unique_systems = set()
        for v, lbl in g["items"]:
            if "江恩" in lbl:
                unique_systems.add("江恩")
            elif "均线" in lbl or "MA" in lbl or "EMA" in lbl:
                unique_systems.add("均线")
            elif "布林" in lbl:
                unique_systems.add("布林")
            elif "Wall" in lbl or "Max Pain" in lbl or "Gamma" in lbl:
                unique_systems.add("期权")
            elif "筹码" in lbl or "Value" in lbl:
                unique_systems.add("筹码")

        if len(unique_systems) >= 2:
            dist = (g["center"] - price) / price * 100
            confluences.append({
                "center_price": round(g["center"], 2),
                "distance_pct": round(dist, 2),
                "systems_count": len(unique_systems),
                "systems": list(unique_systems),
                "items": [(round(v, 2), lbl) for v, lbl in g["items"]],
                "strength": "🏰 极强共振" if len(unique_systems) >= 4
                            else "🧱 强共振" if len(unique_systems) == 3
                            else "🪨 中等共振",
            })

    # 按距当前价排序
    confluences.sort(key=lambda x: abs(x["distance_pct"]))
    return confluences


def synthesize_tactical_view(gann, mtf, options, money, confluences) -> dict:
    """综合战术判断"""
    price = gann.get("current_price", 0) if gann else 0
    bullish_score = 0
    bearish_score = 0
    factors = []

    # 多周期均线
    if mtf and "error" not in mtf:
        for tf_name, tf in [("周线", mtf["weekly"]), ("日线", mtf["daily"]), ("1H", mtf["hourly"])]:
            ma = tf.get("ma_arrangement", "")
            if "多头" in ma:
                bullish_score += 1
                factors.append(f"✅ {tf_name}{ma}")
            elif "空头" in ma:
                bearish_score += 1
                factors.append(f"❌ {tf_name}{ma}")

        # MACD
        for tf_name, tf in [("周线", mtf["weekly"]), ("日线", mtf["daily"])]:
            msig = tf.get("macd_signal", "")
            if "多头发散" in msig:
                bullish_score += 1
                factors.append(f"✅ {tf_name}MACD {msig}")
            elif "空头发散" in msig:
                bearish_score += 1
                factors.append(f"❌ {tf_name}MACD {msig}")
            elif "钝化" in msig:
                bearish_score += 0.5
                factors.append(f"⚠️ {tf_name}MACD {msig}")

        # RSI 小时极端
        h_rsi = mtf["hourly"].get("rsi_14", 50)
        h_rsi_sig = mtf["hourly"].get("rsi_signal", "")
        if "严重超卖" in h_rsi_sig:
            bullish_score += 1
            factors.append(f"✅ 1H {h_rsi_sig} → 短线反弹机会")
        elif "严重超买" in h_rsi_sig:
            bearish_score += 1
            factors.append(f"❌ 1H {h_rsi_sig} → 短线回调风险")

    # 资金流
    if money and "error" not in money:
        if "底背离" in money.get("obv_divergence", ""):
            bullish_score += 1.5
            factors.append(f"✅ {money['obv_divergence']}")
        elif "顶背离" in money.get("obv_divergence", ""):
            bearish_score += 1.5
            factors.append(f"❌ {money['obv_divergence']}")
        if "累积阶段" in money.get("ad_signal", ""):
            bullish_score += 0.5
            factors.append(f"✅ {money['ad_signal']}")
        elif "派发阶段" in money.get("ad_signal", ""):
            bearish_score += 0.5
            factors.append(f"❌ {money['ad_signal']}")

    # 期权
    if options and "error" not in options:
        flip = options.get("flip", {})
        if flip.get("regime") == "正Gamma":
            factors.append("⚖️ 正Gamma环境：区间震荡为主")
        else:
            factors.append("⚠️ 负Gamma环境：趋势放大，波动加剧")

        pcr = options.get("pcr", {}).get("pcr_vol", 1)
        if pcr > 1.5:
            bullish_score += 0.5
            factors.append(f"✅ PCR极高({pcr}) → 反向看多")
        elif pcr < 0.4:
            bearish_score += 0.5
            factors.append(f"❌ PCR极低({pcr}) → 反向看空")

    # 江恩
    if gann and "error" not in gann:
        if gann.get("resonances"):
            for r in gann["resonances"][:1]:
                factors.append(f"⚡ 当前价精准落在 {r['type']} (${r['target']})")
        # 检查临近时间共振
        for trd in gann.get("time_resonance_days", [])[:1]:
            if 0 <= trd["days_from_today"] <= 14:
                factors.append(
                    f"⏰ {trd['date']} ({trd['days_from_today']}天后) "
                    f"多周期共振日 → 高概率变盘"
                )

    # 净分判断
    net = bullish_score - bearish_score
    if net >= 3:
        direction = "🟢 偏多（多空净+{}）".format(round(net, 1))
        bias = "bullish"
    elif net >= 1:
        direction = "🟡 弱多（多空净+{}）".format(round(net, 1))
        bias = "weak_bullish"
    elif net <= -3:
        direction = "🔴 偏空（多空净{}）".format(round(net, 1))
        bias = "bearish"
    elif net <= -1:
        direction = "🟠 弱空（多空净{}）".format(round(net, 1))
        bias = "weak_bearish"
    else:
        direction = "⚖️ 均衡震荡（多空净{}）".format(round(net, 1))
        bias = "neutral"

    return {
        "bullish_score": bullish_score,
        "bearish_score": bearish_score,
        "net": net,
        "direction": direction,
        "bias": bias,
        "factors": factors,
    }


def generate_tactical_playbook(price, gann, mtf, options, money,
                               confluences, tactical) -> dict:
    """生成具体操作playbook"""
    bias = tactical["bias"]

    # 找最近上下共振区作为目标位
    up_target = None
    down_support = None
    for c in confluences:
        if c["distance_pct"] > 0 and up_target is None:
            up_target = c
        if c["distance_pct"] < 0 and down_support is None:
            down_support = c

    # 短线（1-3天）
    if bias in ("bullish", "weak_bullish"):
        short = f"📈 偏多操作：现价 ${price:.2f} 可轻仓试多"
        if down_support:
            short += f"，止损放在 ${down_support['center_price']:.2f}（{down_support['strength']}）下方"
        if up_target:
            short += f"，第一目标 ${up_target['center_price']:.2f}"
    elif bias in ("bearish", "weak_bearish"):
        short = f"📉 偏空操作：现价 ${price:.2f} 不宜追多"
        if up_target:
            short += f"，反弹至 ${up_target['center_price']:.2f} 是减仓机会"
        if down_support:
            short += f"，等待 ${down_support['center_price']:.2f} 共振区企稳"
    else:
        short = f"⚖️ 区间震荡：${down_support['center_price']:.2f}-${up_target['center_price']:.2f} 高抛低吸" \
            if down_support and up_target else "🟡 方向不明，建议观望"

    # 中线（1-2周）
    mid = []
    if mtf and "error" not in mtf:
        wk = mtf.get("weekly", {})
        if "多头" in wk.get("ma_arrangement", ""):
            mid.append("✅ 周线多头排列未破：中线趋势仍在上行通道")
        if "钝化" in wk.get("macd_signal", ""):
            mid.append("⚠️ 周线MACD钝化：中线进入震荡期，操作降低频率")

    if gann:
        # 时间共振预警
        for trd in gann.get("time_resonance_days", [])[:2]:
            if 0 < trd["days_from_today"] <= 14:
                mid.append(
                    f"⏰ {trd['date']} 共振时间窗（{trd['days_from_today']}天后）"
                    f"→ 这一天前后注意大波动，提前调整仓位"
                )

    # 长线（1-3月）
    long_view = []
    if gann:
        swings = gann.get("swings", {})
        if swings.get("recent_low") and swings.get("recent_high"):
            range_low = swings["recent_low"]
            range_high = swings["recent_high"]
            mid_50 = (range_low + range_high) / 2
            long_view.append(
                f"📐 大区间：${range_low:.2f} - ${range_high:.2f}，"
                f"50%黄金回调 ${mid_50:.2f} 是中长线核心介入位"
            )

    # 期权策略
    opt_strategies = []
    if options and "error" not in options:
        for s in options.get("playbook", {}).get("opt_strategies", [])[:2]:
            opt_strategies.append(s)

    return {
        "short_term": short,
        "mid_term": mid if mid else ["按现有策略持续跟踪"],
        "long_term": long_view if long_view else ["关注大周期方向"],
        "options_strategies": opt_strategies,
        "up_target": up_target,
        "down_support": down_support,
    }


def compile_deep_report(ticker: str) -> dict:
    """编译完整深度推演报告"""
    # 1. Gann 分析
    gann = full_gann_analysis(ticker)
    if "error" in gann:
        return {"error": f"Gann分析失败: {gann['error']}"}

    # 2. 多周期技术
    mtf = multi_timeframe_analysis(ticker)

    # 3. 资金流
    money = analyze_money_flow(ticker)

    # 4. 期权结构
    options = None
    try:
        exps = get_expirations(ticker)
        if exps:
            options = full_structural_analysis(ticker, exps[0])
    except Exception as e:
        options = {"error": str(e)}

    # 5. 共振分析
    confluences = find_confluence(gann, mtf, options)

    # 6. 战术综合
    tactical = synthesize_tactical_view(gann, mtf, options, money, confluences)

    # 7. Playbook
    price = gann.get("current_price", 0)
    playbook = generate_tactical_playbook(price, gann, mtf, options, money,
                                          confluences, tactical)

    # 8. 价格关键位（用于统一图）
    price_levels = build_price_levels(gann, mtf, options)

    # 9. 时间关键日（用于统一图）
    earnings = get_next_earnings(ticker)
    time_lines = build_time_lines(gann, earnings)

    # 10. 价格-时间共振检测
    from price_time_chart import detect_price_time_resonance
    all_time_windows = gann.get("time_windows", []) if gann else []
    pt_resonance = detect_price_time_resonance(
        confluences, all_time_windows, price
    )

    return {
        "ticker": ticker,
        "price": price,
        "gann": gann,
        "mtf": mtf,
        "money": money,
        "options": options,
        "confluences": confluences,
        "tactical": tactical,
        "playbook": playbook,
        "price_levels": price_levels,
        "time_lines": time_lines,
        "earnings": earnings,
        "pt_resonance": pt_resonance,
    }


def build_price_levels(gann, mtf, options):
    """收集所有要画在主图上的水平价格线"""
    levels = []
    if not gann or "error" in gann:
        return levels

    # 当前价
    cp = gann.get("current_price", 0)

    # Gann Sq9 关键位（只取距现价 ±30% 内）
    if cp > 0:
        for nr in gann.get("closest_levels", {}).get("next_resistances", [])[:3]:
            if abs(nr["target"] - cp) / cp < 0.3:
                levels.append({
                    "price": nr["target"],
                    "label": f"江恩 {nr['degrees']}° 阻力",
                    "color": "#ef5350",
                    "dash": "dash",
                    "width": 1.2,
                })
        for ns in gann.get("closest_levels", {}).get("next_supports_from_top", [])[:3]:
            if abs(ns["target"] - cp) / cp < 0.3:
                levels.append({
                    "price": ns["target"],
                    "label": f"江恩 -{ns['degrees']}° 支撑",
                    "color": "#26a69a",
                    "dash": "dash",
                    "width": 1.2,
                })

    # 多周期均线（取日线和周线 MA20/50）
    if mtf and "error" not in mtf:
        for name, key, color in [
            ("日MA20", ("daily", "ma20"), "#ffa726"),
            ("日MA50", ("daily", "ma50"), "#42a5f5"),
            ("周MA20", ("weekly", "ma20"), "#9c27b0"),
        ]:
            tf, k = key
            v = mtf.get(tf, {}).get(k)
            if v and cp > 0 and abs(v - cp) / cp < 0.3:
                levels.append({
                    "price": v,
                    "label": name,
                    "color": color,
                    "dash": "dot",
                    "width": 1,
                })

        # 筹码 POC
        vp = mtf.get("volume_profile")
        if vp:
            poc = vp.get("poc", {}).get("price_mid")
            if poc:
                levels.append({
                    "price": poc,
                    "label": "筹码 POC",
                    "color": "#ff5722",
                    "dash": "longdash",
                    "width": 1.5,
                })

    # 期权 Walls / Max Pain / Gamma Flip
    if options and "error" not in options:
        walls = options.get("walls", {})
        if walls.get("call_wall_strike"):
            levels.append({
                "price": walls["call_wall_strike"],
                "label": f"Call Wall {walls.get('call_wall_grade','').split(' ')[0]}",
                "color": "#388e3c",
                "dash": "solid",
                "width": 2,
            })
        if walls.get("put_wall_strike"):
            levels.append({
                "price": walls["put_wall_strike"],
                "label": f"Put Wall {walls.get('put_wall_grade','').split(' ')[0]}",
                "color": "#c62828",
                "dash": "solid",
                "width": 2,
            })
        if options.get("max_pain"):
            levels.append({
                "price": options["max_pain"],
                "label": "Max Pain",
                "color": "#ff9800",
                "dash": "dashdot",
                "width": 1.5,
            })
        flip = options.get("flip", {})
        if flip.get("flip_strike"):
            levels.append({
                "price": flip["flip_strike"],
                "label": f"⚡ Gamma Flip",
                "color": "#9c27b0",
                "dash": "dashdot",
                "width": 1.5,
            })

    return levels


def build_time_lines(gann, earnings):
    """收集所有要画在图上的纵向时间线"""
    lines = []

    # 财报
    if earnings and "error" not in earnings:
        d = earnings.get("date")
        if d:
            lines.append({
                "date": d,
                "label": f"📅 财报 {d}",
                "color": "#dc3545",
                "dash": "solid",
            })

    # 江恩时间窗口
    if gann and "error" not in gann:
        # 时间共振日（最重要）
        for trd in gann.get("time_resonance_days", [])[:5]:
            if 0 <= trd.get("days_from_today", -1) <= 60:
                star = "🔥🔥" if trd.get("is_critical") else "⏰"
                lines.append({
                    "date": trd["date"],
                    "label": f"{star} 共振日",
                    "color": "#ff9800",
                    "dash": "dot",
                })
        # 普通江恩时间窗口（标重要的）
        seen_dates = set(l["date"] for l in lines)
        for w in gann.get("upcoming_windows", [])[:6]:
            if w["target_date"] in seen_dates:
                continue
            if not w.get("is_critical"):
                continue
            if 0 <= w["days_from_today"] <= 60:
                lines.append({
                    "date": w["target_date"],
                    "label": f"⭐ {w['cycle_days']}天",
                    "color": "#7e57c2",
                    "dash": "dot",
                })
                seen_dates.add(w["target_date"])

    return lines
