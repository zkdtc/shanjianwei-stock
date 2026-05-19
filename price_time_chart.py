"""
price_time_chart.py
统一的价格-时间对齐图：
- K线 (主图)
- 横向：江恩九宫位、均线、布林、期权Walls、Max Pain、共振区
- 纵向：江恩时间窗口、财报日、共振时间日
- 副图：成交量、RSI、MACD

核心理念：价格和时间在同一张图上对齐，
寻找"价格-时间共振点"——价格触及关键位 + 当天落在江恩时间窗口
"""

import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date, timedelta


def _rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast).mean()
    ema_slow = series.ewm(span=slow).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal).mean()
    hist = (dif - dea) * 2
    return dif, dea, hist


def build_unified_chart(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
    price_levels: list = None,   # [{"price": 173, "label": "Sq9 540°", "color": "#28a745", "dash": "dash"}]
    time_lines: list = None,     # [{"date": "2026-06-01", "label": "财报", "color": "#dc3545", "dash": "solid"}]
    confluence_zones: list = None,  # [{"low": 169, "high": 174, "strength": "🏰", "label": "强共振"}]
    swings: dict = None,         # {"recent_high":, "recent_high_date":, ...}
    show_volume: bool = True,
    show_rsi: bool = True,
    show_macd: bool = True,
) -> go.Figure:
    """
    主统一图。所有价格/时间维度的关键信号都画在同一张图上。
    """
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval)
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=f"{ticker} 无数据")
        return fig

    # 计算技术指标
    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()
    df["MA200"] = df["Close"].rolling(200).mean() if len(df) >= 100 else df["Close"]
    df["BB_mid"] = df["Close"].rolling(20).mean()
    df["BB_std"] = df["Close"].rolling(20).std()
    df["BB_upper"] = df["BB_mid"] + df["BB_std"] * 2
    df["BB_lower"] = df["BB_mid"] - df["BB_std"] * 2

    # 子图布局
    n_rows = 1 + (1 if show_volume else 0) + (1 if show_rsi else 0) + (1 if show_macd else 0)
    row_heights = [0.55]
    if show_volume:
        row_heights.append(0.13)
    if show_rsi:
        row_heights.append(0.16)
    if show_macd:
        row_heights.append(0.16)

    fig = make_subplots(
        rows=n_rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=[None] * n_rows,
    )

    # ── 主图：K线 + 均线 + 布林带 ──
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        name="K线",
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["EMA20"], name="EMA20",
        line=dict(color="#ffa726", width=1.2),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["EMA50"], name="EMA50",
        line=dict(color="#42a5f5", width=1.2),
    ), row=1, col=1)
    if len(df) >= 100:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MA200"], name="MA200",
            line=dict(color="#9c27b0", width=1.5),
        ), row=1, col=1)

    # 布林带
    fig.add_trace(go.Scatter(
        x=df.index, y=df["BB_upper"], name="BB上轨",
        line=dict(color="rgba(150,150,150,0.5)", width=1, dash="dot"),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["BB_lower"], name="BB下轨",
        line=dict(color="rgba(150,150,150,0.5)", width=1, dash="dot"),
        fill="tonexty", fillcolor="rgba(150,150,150,0.05)",
    ), row=1, col=1)

    # ── 横向价格关键位 (Gann + Walls) ──
    x_start = df.index[0]
    x_end = df.index[-1] + pd.Timedelta(days=14)  # 向右延伸14天
    if price_levels:
        for lvl in price_levels:
            price = lvl["price"]
            color = lvl.get("color", "#888")
            dash = lvl.get("dash", "dash")
            label = lvl.get("label", "")
            width = lvl.get("width", 1.2)
            fig.add_trace(go.Scatter(
                x=[x_start, x_end],
                y=[price, price],
                mode="lines",
                line=dict(color=color, width=width, dash=dash),
                name=f"{label} ${price:.2f}",
                showlegend=False,
                hovertemplate=f"{label}: ${price:.2f}<extra></extra>",
            ), row=1, col=1)
            # 右侧文字标注
            fig.add_annotation(
                x=x_end, y=price,
                text=f"{label} ${price:.2f}",
                showarrow=False,
                xanchor="left", yanchor="middle",
                font=dict(size=10, color=color),
                row=1, col=1,
            )

    # ── 共振价格带 ──
    if confluence_zones:
        for cz in confluence_zones:
            fig.add_hrect(
                y0=cz["low"], y1=cz["high"],
                fillcolor=cz.get("color", "#ffeb3b"),
                opacity=0.15,
                line_width=0,
                row=1, col=1,
            )
            fig.add_annotation(
                x=x_end, y=(cz["low"] + cz["high"]) / 2,
                text=f"{cz.get('strength','')} {cz.get('label','')}",
                showarrow=False, xanchor="left",
                font=dict(size=10, color="#f57c00"),
                row=1, col=1,
            )

    # ── 纵向时间线 (财报 / 江恩时间窗口 / 共振时间日) ──
    if time_lines:
        for tl in time_lines:
            d = tl["date"]
            if isinstance(d, str):
                d = pd.Timestamp(d)
            elif isinstance(d, date) and not isinstance(d, datetime):
                d = pd.Timestamp(d)
            color = tl.get("color", "#888")
            dash = tl.get("dash", "dash")
            label = tl.get("label", "")
            for r in range(1, n_rows + 1):
                fig.add_vline(
                    x=d, line_color=color, line_dash=dash, line_width=1.5,
                    row=r, col=1,
                )
            fig.add_annotation(
                x=d, y=df["High"].max() * 1.02,
                text=label,
                showarrow=True, arrowhead=2,
                ax=0, ay=-30,
                font=dict(size=10, color=color),
                row=1, col=1,
            )

    # ── 标记 swing 高/低点 ──
    if swings:
        if swings.get("recent_high_date"):
            try:
                hd = pd.Timestamp(swings["recent_high_date"])
                hp = swings["recent_high"]
                fig.add_annotation(
                    x=hd, y=hp,
                    text=f"高点<br>${hp:.2f}",
                    showarrow=True, arrowhead=2,
                    ax=0, ay=-25,
                    bgcolor="rgba(220,53,69,0.7)",
                    font=dict(size=9, color="white"),
                    row=1, col=1,
                )
            except Exception:
                pass
        if swings.get("recent_low_date"):
            try:
                ld = pd.Timestamp(swings["recent_low_date"])
                lp = swings["recent_low"]
                fig.add_annotation(
                    x=ld, y=lp,
                    text=f"低点<br>${lp:.2f}",
                    showarrow=True, arrowhead=2,
                    ax=0, ay=25,
                    bgcolor="rgba(40,167,69,0.7)",
                    font=dict(size=9, color="white"),
                    row=1, col=1,
                )
            except Exception:
                pass

    # ── 副图 1: 成交量 ──
    cur_row = 2
    if show_volume:
        colors = ["#26a69a" if c >= o else "#ef5350"
                  for o, c in zip(df["Open"], df["Close"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"], name="成交量",
            marker_color=colors, opacity=0.8, showlegend=False,
        ), row=cur_row, col=1)
        # 量线
        vol_ma = df["Volume"].rolling(20).mean()
        fig.add_trace(go.Scatter(
            x=df.index, y=vol_ma, name="Vol MA20",
            line=dict(color="#fbc02d", width=1), showlegend=False,
        ), row=cur_row, col=1)
        # 时间线
        if time_lines:
            for tl in time_lines:
                d = tl["date"]
                if isinstance(d, str):
                    d = pd.Timestamp(d)
                fig.add_vline(x=d, line_color=tl.get("color","#888"),
                              line_dash=tl.get("dash","dash"), line_width=1,
                              row=cur_row, col=1)
        cur_row += 1

    # ── 副图 2: RSI ──
    if show_rsi:
        rsi_vals = _rsi(df["Close"])
        fig.add_trace(go.Scatter(
            x=df.index, y=rsi_vals, name="RSI(14)",
            line=dict(color="#7e57c2", width=1.5), showlegend=False,
        ), row=cur_row, col=1)
        fig.add_hline(y=70, line_color="#ef5350", line_dash="dot", line_width=1, row=cur_row, col=1)
        fig.add_hline(y=30, line_color="#26a69a", line_dash="dot", line_width=1, row=cur_row, col=1)
        fig.add_hline(y=50, line_color="#888", line_dash="dot", line_width=0.5, row=cur_row, col=1)
        if time_lines:
            for tl in time_lines:
                d = tl["date"]
                if isinstance(d, str):
                    d = pd.Timestamp(d)
                fig.add_vline(x=d, line_color=tl.get("color","#888"),
                              line_dash=tl.get("dash","dash"), line_width=1,
                              row=cur_row, col=1)
        fig.update_yaxes(title_text="RSI", row=cur_row, col=1, range=[0, 100])
        cur_row += 1

    # ── 副图 3: MACD ──
    if show_macd:
        dif, dea, hist = _macd(df["Close"])
        hist_colors = ["#26a69a" if h >= 0 else "#ef5350" for h in hist]
        fig.add_trace(go.Bar(
            x=df.index, y=hist, name="MACD Hist",
            marker_color=hist_colors, opacity=0.7, showlegend=False,
        ), row=cur_row, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=dif, name="DIF",
            line=dict(color="#0288d1", width=1.2), showlegend=False,
        ), row=cur_row, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=dea, name="DEA",
            line=dict(color="#ff9800", width=1.2), showlegend=False,
        ), row=cur_row, col=1)
        fig.add_hline(y=0, line_color="#888", line_dash="solid", line_width=0.5, row=cur_row, col=1)
        if time_lines:
            for tl in time_lines:
                d = tl["date"]
                if isinstance(d, str):
                    d = pd.Timestamp(d)
                fig.add_vline(x=d, line_color=tl.get("color","#888"),
                              line_dash=tl.get("dash","dash"), line_width=1,
                              row=cur_row, col=1)
        fig.update_yaxes(title_text="MACD", row=cur_row, col=1)
        cur_row += 1

    # 布局
    fig.update_layout(
        title=f"{ticker} · 价格-时间统一图",
        height=180 * n_rows + 200,
        xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=140, t=60, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
        plot_bgcolor="white",
    )
    fig.update_yaxes(title_text="价格", row=1, col=1)
    if show_volume:
        fig.update_yaxes(title_text="量", row=2, col=1)
    for r in range(1, n_rows + 1):
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])], row=r, col=1)

    return fig


# ─────────────────────────────────────────────
#  价格-时间共振点检测
# ─────────────────────────────────────────────

def detect_price_time_resonance(
    confluences: list,
    time_windows: list,
    current_price: float,
    tol_days: int = 3,
) -> list:
    """
    检测「价格-时间共振点」—— 当未来某一天落在江恩时间窗口
    AND 价格距某个共振区很近（已经在或快进入）时，是极高变盘概率
    """
    if not confluences or not time_windows:
        return []

    resonance_points = []
    for tw in time_windows:
        if tw.get("days_from_today", -999) < 0:
            continue
        if tw.get("days_from_today", 999) > 60:
            continue
        # 对每个时间窗口，找最近的价格共振区
        for cz in confluences:
            dist_pct = abs(cz["distance_pct"])
            # 距共振价 < 5% 视为快到该位置
            if dist_pct < 8:
                resonance_points.append({
                    "date": tw.get("target_date", ""),
                    "days_from_today": tw.get("days_from_today", 0),
                    "price_zone": cz["center_price"],
                    "price_distance_pct": cz["distance_pct"],
                    "time_label": tw.get("cycle_label", "") + f" (锚{tw.get('anchor_type','')})",
                    "price_strength": cz.get("strength", ""),
                    "price_systems": cz.get("systems", []),
                    "score": (5 - dist_pct / 2) + (3 if tw.get("is_critical") else 0) + (cz.get("systems_count", 1)),
                })

    # 按综合分数排序
    resonance_points.sort(key=lambda x: -x["score"])
    # 去重：相同日期+相同价格区只保留一个
    seen = set()
    unique = []
    for r in resonance_points:
        key = (r["date"], round(r["price_zone"], 0))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:10]
