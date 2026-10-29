import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone

st.set_page_config(page_title="AI Trading Partner V2", page_icon="📈", layout="wide")
st.title("📈 AI Trading Partner — V2")
st.caption("Indian equities research + paper trading. No broker connection and no live orders.")

st.warning(
    "Research prototype only. Yahoo Finance data can be delayed, missing, adjusted, or inaccurate—especially intraday. "
    "Signals are rules-based and are not predictions. Paper trades are simulations, not actual orders."
)

DEFAULT_TICKERS = "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS,SBIN.NS,LT.NS,BHARTIARTL.NS,ITC.NS,TATAMOTORS.NS"

# Indicative cost assumptions for estimates only; verify current broker/exchange/statutory rates.
with st.sidebar:
    st.header("Portfolio settings")
    capital = st.number_input("Paper capital (₹)", min_value=1000, max_value=10000000, value=20000, step=1000)
    risk_pct = st.slider("Planned risk per trade (%)", 0.1, 1.0, 0.5, 0.1)
    daily_loss_pct = st.slider("Daily loss stop (%)", 0.5, 5.0, 2.0, 0.5)
    max_positions = st.slider("Maximum open paper trades", 1, 5, 3)
    st.caption("Default example: ₹20,000 capital, 0.5% planned risk = ₹100 per trade. Stops do not guarantee the actual loss.")
    st.divider()
    st.header("Scanner")
    mode = st.radio("Strategy view", ["Swing (daily)", "Intraday (5-minute research)", "Compare both"])
    tickers_text = st.text_area("NSE symbols (comma-separated)", DEFAULT_TICKERS, height=120)
    max_stocks = st.slider("Maximum stocks to scan", 3, 30, 10)
    run_scan = st.button("Scan stocks", type="primary", use_container_width=True)

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def normalize_history(df):
    if df is None or df.empty:
        return pd.DataFrame()
    # yfinance can return MultiIndex columns even for a single ticker.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    needed = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in df.columns for c in needed):
        return pd.DataFrame()
    for c in needed:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Close"])

@st.cache_data(ttl=180, show_spinner=False)
def fetch_history(symbol, intraday=False):
    try:
        if intraday:
            raw = yf.download(symbol, period="5d", interval="5m", auto_adjust=True, progress=False, threads=False)
        else:
            raw = yf.download(symbol, period="1y", interval="1d", auto_adjust=True, progress=False, threads=False)
        return normalize_history(raw)
    except Exception:
        return pd.DataFrame()

def analyse(symbol, df, label):
    if df.empty or len(df) < 55:
        return None
    close = df["Close"].dropna()
    vol = df["Volume"].fillna(0)
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    rs = rsi(close)
    vol_avg = vol.rolling(20).mean()
    price = float(close.iloc[-1])
    e20 = float(ema20.iloc[-1])
    e50 = float(ema50.iloc[-1])
    r = float(rs.iloc[-1]) if pd.notna(rs.iloc[-1]) else np.nan
    vratio = float(vol.iloc[-1] / vol_avg.iloc[-1]) if pd.notna(vol_avg.iloc[-1]) and vol_avg.iloc[-1] > 0 else np.nan
    if price > e20 > e50 and 50 <= r <= 70:
        signal = "Potential bullish setup"
        score = 3
    elif price < e20 < e50 and 30 <= r <= 50:
        signal = "Potential bearish setup"
        score = -3
    elif price > e20 and r < 75:
        signal = "Watch: positive momentum"
        score = 1
    elif price < e20 and r > 25:
        signal = "Watch: negative momentum"
        score = -1
    else:
        signal = "No qualifying setup"
        score = 0
    # ATR-like stop distance based on rolling high-low range; only a planning estimate.
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - close.shift()).abs(),
        (df["Low"] - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 and pd.notna(tr.rolling(14).mean().iloc[-1]) else price * 0.02
    return {
        "Symbol": symbol, "View": label, "Price (₹)": round(price, 2), "Signal": signal,
        "RSI": round(r, 1) if pd.notna(r) else None,
        "EMA20": round(e20, 2), "EMA50": round(e50, 2),
        "Vol / 20-bar avg": round(vratio, 2) if pd.notna(vratio) else None,
        "ATR estimate (₹)": round(atr, 2), "_score": score
    }

def estimated_costs(entry, exit_price, qty, product):
    turnover = max(0.0, entry * qty) + max(0.0, exit_price * qty)
    # Rough illustrative estimates, not a live tariff engine.
    brokerage = 0.0 if product == "Delivery" else min(40.0, 0.0003 * turnover)
    stt = (0.001 if product == "Delivery" else 0.00025) * (entry * qty if product == "Delivery" else turnover)
    exchange = 0.0000297 * turnover
    sebi = 0.000001 * turnover
    stamp = 0.00003 * entry * qty
    gst = 0.18 * (brokerage + exchange + sebi)
    return round(brokerage + stt + exchange + sebi + stamp + gst, 2)

def safe_float(v, default=0.0):
    try:
        return float(v) if pd.notna(v) else default
    except Exception:
        return default

# Paper trading state is session-only on free Streamlit hosting; refresh/browser session changes may reset it.
if "paper_trades" not in st.session_state:
    st.session_state.paper_trades = []
if "scan_results" not in st.session_state:
    st.session_state.scan_results = pd.DataFrame()

if run_scan:
    symbols = list(dict.fromkeys([x.strip().upper() for x in tickers_text.split(",") if x.strip()]))[:max_stocks]
    results = []
    with st.spinner("Downloading market data and calculating indicators…"):
        for symbol in symbols:
            views = []
            if mode in ("Swing (daily)", "Compare both"):
                daily = fetch_history(symbol, intraday=False)
                item = analyse(symbol, daily, "Swing")
                if item:
                    results.append(item)
            if mode in ("Intraday (5-minute research)", "Compare both"):
                intra = fetch_history(symbol, intraday=True)
                item = analyse(symbol, intra, "Intraday")
                if item:
                    results.append(item)
    if results:
        result_df = pd.DataFrame(results)
        result_df["_rank"] = result_df["_score"].abs()
        result_df = result_df.sort_values(["View", "_rank"], ascending=[True, False]).drop(columns=["_rank"])
        st.session_state.scan_results = result_df
    else:
        st.session_state.scan_results = pd.DataFrame()

st.subheader("1. Stock scanner")
st.write("Run a scan to refresh prices and indicators. Swing uses daily candles; intraday uses recent 5-minute candles where available.")
if not st.session_state.scan_results.empty:
    display_df = st.session_state.scan_results.drop(columns=["_score"], errors="ignore")
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download scan results (CSV)", csv, "ai_trading_scan.csv", "text/csv")
else:
    st.info("No scan results yet. Choose a strategy in the sidebar and tap **Scan stocks**.")

st.divider()
st.subheader("2. Trade planner")
st.write("Use a setup you have independently reviewed. The planner estimates quantity from your planned rupee risk and stop distance.")
c1, c2 = st.columns(2)
with c1:
    symbol_list = [s.strip().upper() for s in tickers_text.split(",") if s.strip()]
    selected_symbol = st.selectbox("Symbol", symbol_list or ["RELIANCE.NS"])
    entry = st.number_input("Planned entry price (₹)", min_value=0.01, value=100.0, step=0.5)
    stop = st.number_input("Stop-loss price (₹)", min_value=0.01, value=98.0, step=0.5)
    target = st.number_input("Target price (₹)", min_value=0.01, value=104.0, step=0.5)
with c2:
    product = st.selectbox("Paper product type", ["Delivery", "Intraday"])
    risk_rupees = capital * risk_pct / 100
    if stop < entry:
        stop_distance = entry - stop
        risk_qty = int(risk_rupees // stop_distance) if stop_distance > 0 else 0
        affordable_qty = int(capital // entry)
        qty = max(0, min(risk_qty, affordable_qty))
        risk_reward = (target - entry) / stop_distance if target > entry else 0
        est_cost = estimated_costs(entry, target, qty, product) if qty > 0 else 0
        gross_risk = stop_distance * qty
        st.metric("Planned risk budget", f"₹{risk_rupees:,.0f}")
        st.metric("Suggested quantity (long trade)", f"{qty} shares")
        st.metric("Reward / risk", f"{risk_reward:.2f} : 1" if risk_reward > 0 else "Invalid target")
        st.caption(f"Approx. round-trip costs at target: ₹{est_cost:,.2f}. Estimated gross stop risk: ₹{gross_risk:,.2f}, excluding costs and slippage.")
    else:
        qty, risk_reward, est_cost = 0, 0, 0
        st.error("For this long-only planner, stop-loss must be below entry.")
    daily_limit = capital * daily_loss_pct / 100
    st.caption(f"Illustrative daily loss limit: ₹{daily_limit:,.0f}. This app does not enforce exchange-level risk controls.")
    if qty > 0 and (target <= entry or target <= stop):
        st.warning("Target should be above entry for this long-only planner.")

if st.button("Create paper trade", type="primary", disabled=(qty <= 0 or target <= entry or stop >= entry)):
    open_count = sum(1 for t in st.session_state.paper_trades if t["Status"] == "OPEN")
    if open_count >= max_positions:
        st.error(f"Maximum open paper trades reached ({max_positions}). Close a paper trade before adding another.")
    else:
        st.session_state.paper_trades.append({
            "ID": len(st.session_state.paper_trades) + 1,
            "Symbol": selected_symbol, "Product": product, "Entry": float(entry), "Stop": float(stop),
            "Target": float(target), "Qty": int(qty), "Status": "OPEN",
            "Created (UTC)": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "Exit": None, "Gross P/L": None, "Est. costs": None, "Net P/L est.": None
        })
        st.success("Paper trade created. No real order was sent.")

st.divider()
st.subheader("3. Paper trade ledger")
st.caption("Paper ledger is stored only in this browser session. It may reset after a server sleep, app restart, or session change. Do not treat it as a permanent trading journal.")
open_trades = [t for t in st.session_state.paper_trades if t["Status"] == "OPEN"]
if open_trades:
    st.dataframe(pd.DataFrame(open_trades), use_container_width=True, hide_index=True)
    trade_options = {f'#{t["ID"]} {t["Symbol"]} ({t["Qty"]} shares)': t["ID"] for t in open_trades}
    chosen_label = st.selectbox("Choose an open paper trade to close", list(trade_options.keys()))
    exit_price = st.number_input("Simulated exit price (₹)", min_value=0.01, value=float(open_trades[0]["Entry"]), step=0.5)
    if st.button("Close selected paper trade"):
        trade_id = trade_options[chosen_label]
        for t in st.session_state.paper_trades:
            if t["ID"] == trade_id and t["Status"] == "OPEN":
                gross = (exit_price - t["Entry"]) * t["Qty"]
                costs = estimated_costs(t["Entry"], exit_price, t["Qty"], t["Product"])
                t["Status"] = "CLOSED"
                t["Exit"] = round(exit_price, 2)
                t["Gross P/L"] = round(gross, 2)
                t["Est. costs"] = costs
                t["Net P/L est."] = round(gross - costs, 2)
                t["Closed (UTC)"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        st.rerun()
else:
    st.info("No open paper trades. Use the planner above to create one.")

if st.session_state.paper_trades:
    st.markdown("**All paper trades**")
    ledger = pd.DataFrame(st.session_state.paper_trades)
    st.dataframe(ledger, use_container_width=True, hide_index=True)
    closed = ledger[ledger["Status"] == "CLOSED"]
    if not closed.empty:
        total_net = pd.to_numeric(closed["Net P/L est."], errors="coerce").fillna(0).sum()
        st.metric("Closed paper trades — estimated net P/L", f"₹{total_net:,.2f}")
        st.download_button("Download paper ledger (CSV)", ledger.to_csv(index=False).encode("utf-8"), "paper_trade_ledger.csv", "text/csv")

st.divider()
st.subheader("4. Risk rules to follow")
st.markdown("""
- **Risk per trade:** default 0.5% of ₹20,000 = ₹100 planned gross stop risk.
- **Daily loss stop:** default 2% = ₹400; stop initiating new trades if reached. The prototype does not automatically enforce this rule.
- **Maximum open paper trades:** default 3. Avoid stacking highly correlated positions.
- **No leverage or options in this prototype.** The planner is for long-only NSE equity examples.
- **Costs and slippage matter:** displayed charges are rough illustrative estimates, not an official Groww tariff calculator. Actual STT, exchange charges, GST, stamp duty, brokerage, and slippage can change results.
- **Stop orders can slip or gap:** actual losses can exceed planned risk, particularly in fast markets and overnight gaps.
- **Test first:** record enough paper trades across different market conditions and include costs before considering any real-money use.
""")
st.caption("Version 2 • Research and paper trading only • Not investment advice • No live trading API")
