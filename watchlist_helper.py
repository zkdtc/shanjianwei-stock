"""
watchlist_helper.py
自动从ticker推断股票元数据 — 用户只需输入ticker即可加入watchlist
"""

import yfinance as yf
import json
import os


WATCHLIST_PATH = "watchlist.json"


def auto_generate_meta(ticker: str, notes: str = "") -> dict:
    """
    根据ticker从yfinance自动获取信息并生成watchlist条目。
    用户只需提供ticker（可选notes），其它字段全部自动推断。
    """
    ticker = ticker.upper().strip()

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        fast = t.fast_info
        price = float(fast.last_price)
    except Exception as e:
        raise ValueError(f"无法获取 {ticker} 的数据: {e}")

    if price <= 0:
        raise ValueError(f"{ticker} 价格无效，可能是无效ticker")

    # ── 自动推断基本信息 ──
    name = info.get("longName") or info.get("shortName") or ticker
    sector_yf = info.get("sector", "")
    industry = info.get("industry", "")
    market_cap = info.get("marketCap", 0)
    beta = info.get("beta", 1.0) or 1.0

    # ── 推断市场身份（按市值）──
    if market_cap > 1_000_000_000_000:  # >1T
        market_identity = "总龙头（时代级）"
        capital_type = "机构核心配置"
    elif market_cap > 200_000_000_000:  # >200B
        market_identity = "平台级龙头"
        capital_type = "机构核心配置"
    elif market_cap > 30_000_000_000:  # >30B
        market_identity = "细分龙头"
        capital_type = "机构成长配置"
    elif market_cap > 5_000_000_000:  # >5B
        market_identity = "次级标的"
        capital_type = "机构+情绪混合"
    else:
        market_identity = "情绪/小市值标的"
        capital_type = "纯情绪/散户"

    # ── 推断主线层次（按sector/industry关键字）──
    text = f"{sector_yf} {industry} {name}".lower()
    if any(k in text for k in ["semiconductor", "chip", "gpu"]):
        mainline_layer = "基础设施层（Infra）"
        sector = "AI Infra"
    elif any(k in text for k in ["software", "saas", "cloud", "platform"]):
        mainline_layer = "平台层（Platform）"
        sector = "AI Platform"
    elif any(k in text for k in ["network", "communic", "fiber", "optic"]):
        mainline_layer = "基础设施层（Infra）"
        sector = "AI Networking"
    elif any(k in text for k in ["security", "cyber"]):
        mainline_layer = "应用层（Application）"
        sector = "AI Cybersecurity"
    elif any(k in text for k in ["health", "medical", "biotech", "pharma"]):
        mainline_layer = "应用层（Application）"
        sector = "AI Healthcare"
    elif any(k in text for k in ["fintech", "bank", "crypto", "bitcoin"]):
        mainline_layer = "应用层（Application）"
        sector = "Fintech / Crypto Adjacent"
    elif any(k in text for k in ["game", "metaverse", "media"]):
        mainline_layer = "应用层（Application）"
        sector = "Gaming / Metaverse"
    elif any(k in text for k in ["energy", "mining", "data center"]):
        mainline_layer = "基础设施层（Infra）"
        sector = "BTC Mining / AI Datacenter"
    elif any(k in text for k in ["auto", "vehicle", "ev"]):
        mainline_layer = "应用层（Application）"
        sector = "EV / AI Robotics"
    else:
        mainline_layer = "应用层（Application）"
        sector = industry or sector_yf or "Other"

    # ── 推断beta类型 ──
    if beta < 0.9:
        beta_type = "低波动平台型"
    elif beta < 1.3:
        beta_type = "中波动成长型"
    elif beta < 1.8:
        beta_type = "高弹性进攻型"
    else:
        beta_type = "极高波动情绪型"

    # ── 自动估算江恩水平和估值 ──
    # 江恩：基于52周高低点的合理分位
    try:
        hist = t.history(period="1y")
        if not hist.empty:
            high_52 = float(hist["High"].max())
            low_52 = float(hist["Low"].min())
        else:
            high_52 = price * 1.3
            low_52 = price * 0.7
    except Exception:
        high_52 = price * 1.3
        low_52 = price * 0.7

    gann_levels = {
        "s2": round(low_52 * 1.05, 2),       # 接近年内低点
        "s1": round((low_52 + price) / 2, 2),  # 当前价与低点中位
        "r1": round((price + high_52) / 2, 2),  # 当前价与高点中位
        "r2": round(high_52 * 1.05, 2),      # 接近年内高点之上
    }

    # 估值：底线≈52周低点*1.0，共识≈当前价附近
    bottom_valuation = round(low_52 * 1.0, 2)
    consensus_valuation = round((price + high_52) / 2 * 0.95, 2)

    # ── 折现窗口（按市场身份）──
    if market_identity in ("总龙头（时代级）", "平台级龙头"):
        discount_horizon = "2026-2028"
    elif market_identity == "细分龙头":
        discount_horizon = "2026-2027"
    elif market_identity == "次级标的":
        discount_horizon = "2025-2026"
    else:
        discount_horizon = "1-2季度"

    return {
        "ticker": ticker,
        "name": name,
        "market_identity": market_identity,
        "mainline_layer": mainline_layer,
        "mainline_position": industry or "—",
        "discount_horizon": discount_horizon,
        "capital_type": capital_type,
        "sector": sector,
        "beta_type": beta_type,
        "gann_levels": gann_levels,
        "bottom_valuation": bottom_valuation,
        "consensus_valuation": consensus_valuation,
        "notes": notes or f"{industry} | 市值 ${market_cap/1e9:.1f}B | Beta {beta:.2f}",
    }


def load_watchlist() -> dict:
    if not os.path.exists(WATCHLIST_PATH):
        return {"stocks": [], "market_context": {}}
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_watchlist(data: dict):
    with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_ticker(ticker: str, notes: str = "") -> str:
    """添加新ticker到watchlist，返回状态消息"""
    ticker = ticker.upper().strip()
    data = load_watchlist()
    existing = [s["ticker"] for s in data["stocks"]]

    if ticker in existing:
        return f"⚠️ {ticker} 已在watchlist中"

    meta = auto_generate_meta(ticker)
    data["stocks"].append(meta)
    save_watchlist(data)
    return f"✅ {ticker} ({meta['name']}) 已添加 — 价格 ${meta['gann_levels']['r1']*2-meta['gann_levels']['r2']*0+meta['bottom_valuation']*0:.2f}"


def remove_ticker(ticker: str) -> str:
    ticker = ticker.upper().strip()
    data = load_watchlist()
    before = len(data["stocks"])
    data["stocks"] = [s for s in data["stocks"] if s["ticker"] != ticker]
    if len(data["stocks"]) == before:
        return f"⚠️ {ticker} 不在watchlist中"
    save_watchlist(data)
    return f"🗑️ {ticker} 已移除"


def refresh_ticker(ticker: str) -> str:
    """重新拉取ticker的元数据（重置江恩/估值）"""
    ticker = ticker.upper().strip()
    data = load_watchlist()
    found = False
    for i, s in enumerate(data["stocks"]):
        if s["ticker"] == ticker:
            old_notes = s.get("notes", "")
            new_meta = auto_generate_meta(ticker, notes=old_notes)
            data["stocks"][i] = new_meta
            found = True
            break
    if not found:
        return f"⚠️ {ticker} 不在watchlist中"
    save_watchlist(data)
    return f"🔄 {ticker} 元数据已刷新"


def update_field(ticker: str, field: str, value) -> str:
    """更新某只股票的某个字段（如notes、bottom_valuation等）"""
    ticker = ticker.upper().strip()
    data = load_watchlist()
    for s in data["stocks"]:
        if s["ticker"] == ticker:
            s[field] = value
            save_watchlist(data)
            return f"✅ {ticker}.{field} 已更新"
    return f"⚠️ {ticker} 不在watchlist中"
