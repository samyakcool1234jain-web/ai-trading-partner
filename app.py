import json
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="AI Trading Partner V5", page_icon="📈", layout="wide")
st.title("📈 AI Trading Partner — V5.1")
st.caption("NSE equity research + automatic paper exits + trade journal. No broker connection and no live orders.")

st.warning(
    "Research prototype only. Yahoo Finance data may be delayed, incomplete, or unavailable. "
    "Automatic exits are simulated only while this app is open and refreshing; they are NOT broker orders "
    "and may miss fast price moves or gaps."
)

DEFAULT_TICKERS = "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS,SBIN.NS,LT.NS,BHARTIARTL.NS,ITC.NS,TATAMOTORS.NS"
DATA_DIR = Path(__file__).parent
LEDGER_FILE = DATA_DIR / "paper_trades_v3.json"  # Reuse V3 ledger to preserve existing paper trades

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def load_ledger():
    try:
        if LEDGER_FILE.exists():
            data = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        st.warning("Saved ledger could not be read. Import a previous JSON/CSV backup if you have one.")
    return []

def save_ledger(trades):
    # Atomic replacement avoids partially written files during a save.
    try:
        fd, tmp_name = tempfile.mkstemp(prefix="ledger_", suffix=".json", dir=str(DATA_DIR))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(trades, f, indent=2, ensure_ascii=False)
        os.replace(tmp_name, LEDGER_FILE)
        return True
    except Exception:
        return False

with st.sidebar:
    st.header("Portfolio settings")
    capital = st.number_input("Paper capital (₹)", min_value=1000, max_value=10000000, value=20000, step=1000)
    risk_pct = st.slider("Planned risk per trade (%)", 0.1, 1.0, 0.5, 0.1)
    daily_loss_pct = st.slider("Daily loss stop (%)", 0.5, 5.0, 2.0, 0.5)
    max_positions = st.slider("Maximum open paper trades", 1, 5, 3)
    st.caption("Default: ₹20,000 capital, 0.5% planned risk = ₹100 per trade.")
    st.divider()
    st.header("Auto paper monitoring")
    auto_monitor = st.checkbox("Refresh and monitor open trades", value=True)
    refresh_seconds = st.select_slider("Refresh interval", options=[15, 30, 60], value=30)
    st.caption("Monitoring works only while this app is open. Yahoo Finance 1-minute data may be delayed or unavailable.")
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

@st.cache_data(ttl=20, show_spinner=False)
def fetch_monitor_bars(symbol):
    try:
        raw = yf.download(symbol, period="1d", interval="1m", auto_adjust=True, progress=False, threads=False)
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
    e20, e50 = float(ema20.iloc[-1]), float(ema50.iloc[-1])
    r = float(rs.iloc[-1]) if pd.notna(rs.iloc[-1]) else np.nan
    vratio = float(vol.iloc[-1] / vol_avg.iloc[-1]) if pd.notna(vol_avg.iloc[-1]) and vol_avg.iloc[-1] > 0 else np.nan
    if price > e20 > e50 and 50 <= r <= 70:
        signal, score = "Potential bullish setup", 3
    elif price < e20 < e50 and 30 <= r <= 50:
        signal, score = "Potential bearish setup", -3
    elif price > e20 and r < 75:
        signal, score = "Watch: positive momentum", 1
    elif price < e20 and r > 25:
        signal, score = "Watch: negative momentum", -1
    else:
        signal, score = "No qualifying setup", 0
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - close.shift()).abs(),
                    (df["Low"] - close.shift()).abs()], axis=1).max(axis=1)
    tr_mean = tr.rolling(14).mean()
    atr = float(tr_mean.iloc[-1]) if len(tr) >= 14 and pd.notna(tr_mean.iloc[-1]) else price * 0.02
    return {"Symbol": symbol, "View": label, "Price (₹)": round(price, 2), "Signal": signal,
            "RSI": round(r, 1) if pd.notna(r) else None, "EMA20": round(e20, 2), "EMA50": round(e50, 2),
            "Vol / 20-bar avg": round(vratio, 2) if pd.notna(vratio) else None,
            "ATR estimate (₹)": round(atr, 2), "_score": score}

def estimated_costs(entry, exit_price, qty, product):
    turnover = max(0.0, entry * qty) + max(0.0, exit_price * qty)
    brokerage = 0.0 if product == "Delivery" else min(40.0, 0.0003 * turnover)
    stt = (0.001 if product == "Delivery" else 0.00025) * (entry * qty if product == "Delivery" else turnover)
    exchange = 0.0000297 * turnover
    sebi = 0.000001 * turnover
    stamp = 0.00003 * entry * qty
    gst = 0.18 * (brokerage + exchange + sebi)
    return round(brokerage + stt + exchange + sebi + stamp + gst, 2)

def close_trade(trade, exit_price, reason):
    entry_price, qty = float(trade["Entry"]), int(trade["Qty"])
    gross = (float(exit_price) - entry_price) * qty
    costs = estimated_costs(entry_price, float(exit_price), qty, trade["Product"])
    trade.update({
        "Status": "CLOSED", "Exit": round(float(exit_price), 2),
        "Gross P/L": round(gross, 2), "Est. costs": costs,
        "Net P/L est.": round(gross - costs, 2), "Exit reason": reason,
        "Closed (UTC)": now_utc()
    })

if "paper_trades" not in st.session_state:
    st.session_state.paper_trades = load_ledger()
if "scan_results" not in st.session_state:
    st.session_state.scan_results = pd.DataFrame()

# Periodic rerun lets the app check for new market bars while the page stays open.
if auto_monitor:
    st_autorefresh(interval=int(refresh_seconds * 1000), key="v3_auto_refresh")

# Monitor open trades on each rerun. Use one-minute candle high/low. If both levels are touched
# in the same candle, assume the stop-loss first (conservative handling).
monitor_messages = []
if auto_monitor:
    changed = False
    open_trades_now = [t for t in st.session_state.paper_trades if t.get("Status") == "OPEN"]
    for trade in open_trades_now:
        bars = fetch_monitor_bars(str(trade.get("Symbol", "")))
        if bars.empty:
            continue
        # Skip the newest candle because it may still be forming. Only evaluate
        # completed candles whose start time is strictly after trade creation.
        completed_bars = bars.iloc[:-1].tail(10)
        for idx, bar in completed_bars.iterrows():
            try:
                bar_time = pd.Timestamp(idx)
                if bar_time.tzinfo is None:
                    bar_time = bar_time.tz_localize("UTC")
                else:
                    bar_time = bar_time.tz_convert("UTC")

                created_value = trade.get("Created (UTC)")
                if not created_value:
                    continue
                created_time = pd.Timestamp(str(created_value).replace(" UTC", ""))
                if created_time.tzinfo is None:
                    created_time = created_time.tz_localize("UTC")
                else:
                    created_time = created_time.tz_convert("UTC")
                # Prevent old candles from closing a newly created paper trade.
                if bar_time <= created_time:
                    continue

                bar_key = bar_time.strftime("%Y-%m-%d %H:%M:%S UTC")
                last_checked = trade.get("Last checked bar")
                if last_checked:
                    try:
                        last_ts = pd.Timestamp(last_checked.replace(" UTC", "")).tz_localize("UTC")
                        if bar_time <= last_ts:
                            continue
                    except Exception:
                        pass
                low, high = float(bar["Low"]), float(bar["High"])
                open_px = float(bar["Open"])
                stop_px, target_px = float(trade["Stop"]), float(trade["Target"])
                if low <= stop_px and high >= target_px:
                    exit_px, reason = min(open_px, stop_px), "Stop-loss (both levels in same 1m candle; conservative)"
                    close_trade(trade, exit_px, reason)
                    monitor_messages.append(f'{trade["Symbol"]}: paper stop-loss triggered at approx ₹{exit_px:.2f}.')
                    changed = True
                    break
                elif low <= stop_px:
                    exit_px = min(open_px, stop_px) if open_px < stop_px else stop_px
                    close_trade(trade, exit_px, "Stop-loss triggered by 1m candle")
                    monitor_messages.append(f'{trade["Symbol"]}: paper stop-loss triggered at approx ₹{exit_px:.2f}.')
                    changed = True
                    break
                elif high >= target_px:
                    close_trade(trade, target_px, "Target touched by 1m candle")
                    monitor_messages.append(f'{trade["Symbol"]}: paper target triggered at ₹{target_px:.2f}.')
                    changed = True
                    break
                trade["Last checked bar"] = bar_key
                changed = True
            except Exception:
                continue
    if changed and not save_ledger(st.session_state.paper_trades):
        st.warning("Could not save ledger to this app instance's local file. Download a backup.")

for msg in monitor_messages:
    st.success(msg)

if run_scan:
    symbols = list(dict.fromkeys([x.strip().upper() for x in tickers_text.split(",") if x.strip()]))[:max_stocks]
    results = []
    with st.spinner("Downloading market data and calculating indicators…"):
        for symbol in symbols:
            if mode in ("Swing (daily)", "Compare both"):
                item = analyse(symbol, fetch_history(symbol, False), "Swing")
                if item:
                    results.append(item)
            if mode in ("Intraday (5-minute research)", "Compare both"):
                item = analyse(symbol, fetch_history(symbol, True), "Intraday")
                if item:
                    results.append(item)
    if results:
        result_df = pd.DataFrame(results)
        result_df["_rank"] = result_df["_score"].abs()
        st.session_state.scan_results = result_df.sort_values(["View", "_rank"], ascending=[True, False]).drop(columns=["_rank"])
    else:
        st.session_state.scan_results = pd.DataFrame()

st.subheader("1. Stock scanner")
st.write("Swing uses daily candles; intraday uses recent 5-minute candles where available.")
if not st.session_state.scan_results.empty:
    display_df = st.session_state.scan_results.drop(columns=["_score"], errors="ignore")
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.download_button("Download scan results (CSV)", display_df.to_csv(index=False).encode("utf-8"), "ai_trading_scan.csv", "text/csv")
else:
    st.info("No scan results yet. Choose a strategy in the sidebar and tap Scan stocks.")

st.divider()
st.subheader("2. Trade planner")
st.write("Long-only NSE equity planner. Quantity is estimated from planned risk and available capital.")
c1, c2 = st.columns(2)
with c1:
    symbol_list = list(dict.fromkeys([s.strip().upper() for s in tickers_text.split(",") if s.strip()]))
    selected_symbol = st.selectbox("Symbol", symbol_list or ["RELIANCE.NS"])
    entry = st.number_input("Planned entry price (₹)", min_value=0.01, value=100.0, step=0.5)
    stop = st.number_input("Stop-loss price (₹)", min_value=0.01, value=98.0, step=0.5)
    target = st.number_input("Target price (₹)", min_value=0.01, value=104.0, step=0.5)
with c2:
    product = st.selectbox("Paper product type", ["Delivery", "Intraday"])
    strategy = st.selectbox("Strategy classification", ["Swing", "Intraday"], help="Used to compare performance by intended holding style.")
    risk_rupees = capital * risk_pct / 100
    if stop < entry:
        stop_distance = entry - stop
        risk_qty = int(risk_rupees // stop_distance) if stop_distance > 0 else 0
        affordable_qty = int(capital // entry)
        qty = max(0, min(risk_qty, affordable_qty))
        reward_risk = (target - entry) / stop_distance if target > entry else 0
        est_cost = estimated_costs(entry, target, qty, product) if qty > 0 else 0
        st.metric("Planned risk budget", f"₹{risk_rupees:,.0f}")
        st.metric("Suggested quantity (long trade)", f"{qty} shares")
        st.metric("Reward / risk", f"{reward_risk:.2f} : 1" if reward_risk > 0 else "Invalid target")
        st.caption(f"Approx. costs at target: ₹{est_cost:,.2f}; gross stop risk: ₹{(stop_distance*qty):,.2f}, excluding slippage.")
    else:
        qty, reward_risk, est_cost = 0, 0, 0
        st.error("Stop-loss must be below entry.")
    st.caption(f"Illustrative daily loss limit: ₹{capital*daily_loss_pct/100:,.0f}. This is not an exchange-enforced control.")
    if qty > 0 and (target <= entry or target <= stop):
        st.warning("Target should be above entry.")

if st.button("Create paper trade", type="primary", disabled=(qty <= 0 or target <= entry or stop >= entry)):
    # A paper trade represents an assumed fill now. Do not create it if the
    # latest available price is already outside its planned stop/target range.
    latest_bars = fetch_monitor_bars(selected_symbol)
    latest_price = float(latest_bars["Close"].dropna().iloc[-1]) if not latest_bars.empty and not latest_bars["Close"].dropna().empty else None
    if latest_price is not None and not (stop < latest_price < target):
        st.error(
            f"Paper trade not created: latest available {selected_symbol} price is ₹{latest_price:.2f}, "
            f"outside your stop/target range (₹{stop:.2f}–₹{target:.2f}). Update entry, stop-loss, and target "
            "to match the current market, then try again."
        )
    else:
        if latest_price is None:
            st.warning("Latest market price is unavailable. Trade will be simulated using future available candles only.")
        open_count = sum(1 for t in st.session_state.paper_trades if t.get("Status") == "OPEN")
        closed_today = [
            t for t in st.session_state.paper_trades
            if t.get("Status") == "CLOSED"
            and str(t.get("Closed (UTC)", "")).startswith(datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        ]
        daily_realized_net = sum(float(t.get("Net P/L est.") or 0) for t in closed_today)
        daily_limit_amount = capital * daily_loss_pct / 100
        if daily_realized_net <= -daily_limit_amount:
            st.error(f"Daily paper-trading loss limit reached (₹{daily_limit_amount:,.2f}). New paper trades are blocked for today.")
        elif open_count >= max_positions:
            st.error(f"Maximum open paper trades reached ({max_positions}). Close a paper trade first.")
        else:
            next_id = max([int(t.get("ID", 0)) for t in st.session_state.paper_trades] + [0]) + 1
            st.session_state.paper_trades.append({
                "ID": next_id, "Symbol": selected_symbol, "Product": product, "Strategy": strategy, "Entry": float(entry),
                "Stop": float(stop), "Target": float(target), "Qty": int(qty), "Status": "OPEN",
                "Created (UTC)": now_utc(), "Exit": None, "Gross P/L": None, "Est. costs": None,
                "Net P/L est.": None, "Exit reason": None, "Last checked bar": None
            })
            if save_ledger(st.session_state.paper_trades):
                st.success("Paper trade created and saved to the app instance. No real order was sent.")
            else:
                st.warning("Paper trade created for this session, but local persistence failed. Download a backup.")
            st.rerun()


st.divider()
st.subheader("3. Controlled simulation test mode")
st.warning(
    "This section is an isolated test bench. It uses manually simulated prices/candles, "
    "does not use live market data to trigger these tests, and does not add test trades to your real paper ledger or performance dashboard."
)
if "simulation_test_open" not in st.session_state:
    st.session_state.simulation_test_open = None
if "simulation_test_history" not in st.session_state:
    st.session_state.simulation_test_history = []
if "simulation_test_last_result" not in st.session_state:
    st.session_state.simulation_test_last_result = None

if st.session_state.simulation_test_last_result is not None:
    last_result = st.session_state.simulation_test_last_result
    st.success(
        f"Last simulation closed automatically: {last_result.get('Exit reason')} | "
        f"Exit ₹{float(last_result.get('Exit') or 0):.2f} | "
        f"Gross P/L ₹{float(last_result.get('Gross P/L') or 0):.2f} | "
        f"Net P/L est. ₹{float(last_result.get('Net P/L est.') or 0):.2f}"
    )
    st.caption("The test trade is closed. It appears in the isolated simulation results below, not in your main paper ledger.")

with st.expander("Create or run a controlled exit test", expanded=True):
    tc1, tc2 = st.columns(2)
    with tc1:
        test_symbol = st.text_input("Test symbol", value="TEST.NS", key="v5_test_symbol").strip().upper() or "TEST.NS"
        test_entry = st.number_input("Test entry price (₹)", min_value=0.01, value=101.0, step=0.5, key="v5_test_entry")
        test_stop = st.number_input("Test stop-loss (₹)", min_value=0.01, value=100.0, step=0.5, key="v5_test_stop")
    with tc2:
        test_target = st.number_input("Test target (₹)", min_value=0.01, value=115.5, step=0.5, key="v5_test_target")
        test_qty = st.number_input("Test quantity", min_value=1, max_value=100000, value=100, step=1, key="v5_test_qty")
        test_product = st.selectbox("Test product", ["Delivery", "Intraday"], key="v5_test_product")

    if st.button("Create isolated test trade", key="v5_create_test"):
        if not (test_stop < test_entry < test_target):
            st.error("For this long-trade test, stop-loss must be below entry and target must be above entry.")
        elif st.session_state.simulation_test_open is not None:
            st.error("Close or reset the current test trade before creating another.")
        else:
            st.session_state.simulation_test_open = {
                "ID": len(st.session_state.simulation_test_history) + 1,
                "Symbol": test_symbol, "Product": test_product, "Strategy": "Test only",
                "Entry": float(test_entry), "Stop": float(test_stop), "Target": float(test_target),
                "Qty": int(test_qty), "Status": "OPEN", "Created (UTC)": now_utc(),
                "Exit": None, "Gross P/L": None, "Est. costs": None, "Net P/L est.": None,
                "Exit reason": None, "Last checked bar": None
            }
            st.success("Isolated test trade created. It is separate from the main ledger.")
            st.rerun()

    test_trade = st.session_state.simulation_test_open
    if test_trade is not None and test_trade.get("Status") == "OPEN":
        st.markdown("**Current isolated test trade**")
        st.dataframe(pd.DataFrame([test_trade]), use_container_width=True, hide_index=True)
        st.caption("Choose a deterministic test outcome. These buttons do not wait for or depend on actual market prices.")
        b1, b2, b3 = st.columns(3)
        if b1.button("Simulate target hit", type="primary", key="v5_test_target_btn"):
            close_trade(test_trade, float(test_trade["Target"]), "SIM TEST: Target hit")
            st.session_state.simulation_test_history.append(test_trade.copy())
            st.session_state.simulation_test_last_result = test_trade.copy()
            st.session_state.simulation_test_open = None
            st.rerun()
        if b2.button("Simulate stop-loss hit", key="v5_test_stop_btn"):
            close_trade(test_trade, float(test_trade["Stop"]), "SIM TEST: Stop-loss hit")
            st.session_state.simulation_test_history.append(test_trade.copy())
            st.session_state.simulation_test_last_result = test_trade.copy()
            st.session_state.simulation_test_open = None
            st.rerun()
        if b3.button("Reset test trade", key="v5_test_reset_btn"):
            st.session_state.simulation_test_open = None
            st.rerun()

        st.markdown("**Custom simulated exit price**")
        custom_exit = st.number_input("Custom exit price (₹)", min_value=0.01, value=float(test_trade["Entry"]), step=0.5, key="v5_custom_exit")
        if st.button("Close test at custom price", key="v5_custom_close"):
            reason = "SIM TEST: Custom price"
            close_trade(test_trade, float(custom_exit), reason)
            st.session_state.simulation_test_history.append(test_trade.copy())
            st.session_state.simulation_test_last_result = test_trade.copy()
            st.session_state.simulation_test_open = None
            st.rerun()

        st.markdown("**Simulate one candle's high and low**")
        cc1, cc2 = st.columns(2)
        with cc1:
            candle_low = st.number_input("Simulated candle LOW (₹)", min_value=0.01, value=float(test_trade["Stop"]), step=0.5, key="v5_candle_low")
        with cc2:
            candle_high = st.number_input("Simulated candle HIGH (₹)", min_value=0.01, value=float(test_trade["Target"]), step=0.5, key="v5_candle_high")
        if st.button("Evaluate simulated candle", key="v5_eval_candle"):
            if candle_low > candle_high:
                st.error("Candle low must be less than or equal to candle high.")
            elif candle_low <= float(test_trade["Stop"]) and candle_high >= float(test_trade["Target"]):
                close_trade(test_trade, float(test_trade["Stop"]), "SIM TEST: Both levels touched; stop first")
                st.session_state.simulation_test_history.append(test_trade.copy())
                st.session_state.simulation_test_last_result = test_trade.copy()
                st.session_state.simulation_test_open = None
                st.rerun()
            elif candle_low <= float(test_trade["Stop"]):
                close_trade(test_trade, float(test_trade["Stop"]), "SIM TEST: Stop-loss touched")
                st.session_state.simulation_test_history.append(test_trade.copy())
                st.session_state.simulation_test_last_result = test_trade.copy()
                st.session_state.simulation_test_open = None
                st.rerun()
            elif candle_high >= float(test_trade["Target"]):
                close_trade(test_trade, float(test_trade["Target"]), "SIM TEST: Target touched")
                st.session_state.simulation_test_history.append(test_trade.copy())
                st.session_state.simulation_test_last_result = test_trade.copy()
                st.session_state.simulation_test_open = None
                st.rerun()
            else:
                st.info("Neither stop-loss nor target was touched. Test trade remains open.")

    if st.session_state.simulation_test_history:
        st.markdown("**Isolated simulation test results**")
        test_results = pd.DataFrame(st.session_state.simulation_test_history)
        st.dataframe(test_results, use_container_width=True, hide_index=True)
        st.download_button(
            "Download isolated test results (CSV)",
            test_results.to_csv(index=False).encode("utf-8"),
            "ai_trading_v5_simulation_tests.csv", "text/csv", key="v5_download_tests"
        )
        if st.button("Clear isolated test history", key="v5_clear_test_history"):
            st.session_state.simulation_test_history = []
            st.session_state.simulation_test_open = None
            st.session_state.simulation_test_last_result = None
            st.rerun()


st.divider()
st.subheader("4. Paper trade ledger")
st.caption("The app saves a JSON ledger on its server and supports backup/restore. Streamlit-hosted local files are not guaranteed to survive redeployments or server replacement. Download backups regularly. V3 trades without a Strategy field are classified automatically for reporting.")
open_trades = [t for t in st.session_state.paper_trades if t.get("Status") == "OPEN"]
if open_trades:
    st.dataframe(pd.DataFrame(open_trades), use_container_width=True, hide_index=True)
    st.caption("Automatic target/stop checks run on refresh while this page is open. A manual close is also available.")
    trade_options = {f'#{t["ID"]} {t["Symbol"]} ({t["Qty"]} shares)': t["ID"] for t in open_trades}
    chosen_label = st.selectbox("Choose an open paper trade to close manually", list(trade_options.keys()))
    chosen_trade = next(t for t in open_trades if t["ID"] == trade_options[chosen_label])
    exit_price = st.number_input("Simulated closing price (₹)", min_value=0.01, value=float(chosen_trade["Entry"]), step=0.5)
    if st.button("Close selected paper trade manually"):
        for trade in st.session_state.paper_trades:
            if trade.get("ID") == trade_options[chosen_label] and trade.get("Status") == "OPEN":
                close_trade(trade, exit_price, "Manual simulated close")
        save_ledger(st.session_state.paper_trades)
        st.rerun()
else:
    st.info("No open paper trades. Create one in the planner above.")

if st.session_state.paper_trades:
    ledger = pd.DataFrame(st.session_state.paper_trades)
    st.markdown("**All paper trades**")
    st.dataframe(ledger, use_container_width=True, hide_index=True)
    closed = ledger[ledger["Status"] == "CLOSED"]
    if not closed.empty:
        total_net = pd.to_numeric(closed["Net P/L est."], errors="coerce").fillna(0).sum()
        wins = (pd.to_numeric(closed["Net P/L est."], errors="coerce") > 0).sum()
        st.metric("Closed trades — estimated net P/L", f"₹{total_net:,.2f}")
        st.metric("Closed-trade win rate", f"{wins / len(closed) * 100:.1f}%")
    st.download_button("Download paper ledger (CSV)", ledger.to_csv(index=False).encode("utf-8"), "paper_trade_ledger_v4.csv", "text/csv")
    st.download_button("Download paper ledger (JSON backup)", json.dumps(st.session_state.paper_trades, indent=2).encode("utf-8"), "paper_trade_ledger_v4.json", "application/json")

st.subheader("Restore a saved ledger")
uploaded_ledger = st.file_uploader("Upload a previous V3 or V4 JSON/CSV backup", type=["json", "csv"])
if uploaded_ledger is not None and st.button("Restore uploaded ledger"):
    try:
        if uploaded_ledger.name.lower().endswith(".json"):
            restored = json.loads(uploaded_ledger.getvalue().decode("utf-8"))
        else:
            restored = pd.read_csv(uploaded_ledger).replace({np.nan: None}).to_dict(orient="records")
        if not isinstance(restored, list):
            raise ValueError("Backup must contain a list of trades.")
        required = {"ID", "Symbol", "Entry", "Stop", "Target", "Qty", "Status", "Product"}
        if restored and not required.issubset(set(restored[0].keys())):
            raise ValueError("This file does not appear to be a supported paper ledger.")
        st.session_state.paper_trades = restored
        if save_ledger(restored):
            st.success(f"Restored {len(restored)} trades.")
        else:
            st.warning("Restored in this session, but server save failed.")
        st.rerun()
    except Exception as exc:
        st.error(f"Could not restore file: {exc}")

st.divider()
st.subheader("5. Performance & risk dashboard")
st.caption("Metrics use closed paper trades and estimated costs. They are descriptive, not evidence of future profitability.")
all_trades = pd.DataFrame(st.session_state.paper_trades)
if all_trades.empty:
    st.info("Create and close paper trades to populate performance metrics.")
else:
    if "Strategy" not in all_trades.columns:
        all_trades["Strategy"] = np.where(all_trades.get("Product", pd.Series(index=all_trades.index, dtype=str)).eq("Intraday"), "Intraday", "Swing")
    else:
        product_fallback = np.where(all_trades.get("Product", pd.Series(index=all_trades.index, dtype=str)).eq("Intraday"), "Intraday", "Swing")
        all_trades["Strategy"] = all_trades["Strategy"].fillna(pd.Series(product_fallback, index=all_trades.index))
    closed_all = all_trades[all_trades["Status"].eq("CLOSED")].copy()
    if not closed_all.empty:
        closed_all["Net P/L est."] = pd.to_numeric(closed_all["Net P/L est."], errors="coerce").fillna(0.0)
        closed_all["Gross P/L"] = pd.to_numeric(closed_all["Gross P/L"], errors="coerce").fillna(0.0)
        closed_all["Est. costs"] = pd.to_numeric(closed_all["Est. costs"], errors="coerce").fillna(0.0)
        net_values = closed_all["Net P/L est."]
        wins = net_values[net_values > 0]
        losses = net_values[net_values < 0]
        win_rate = (net_values > 0).mean() * 100
        avg_win = wins.mean() if len(wins) else 0.0
        avg_loss = losses.mean() if len(losses) else 0.0
        profit_factor = wins.sum() / abs(losses.sum()) if len(losses) and abs(losses.sum()) > 0 else (float("inf") if len(wins) else 0.0)
        closed_all["Close date"] = closed_all["Closed (UTC)"].astype(str).str.slice(0, 10)
        closed_all = closed_all.sort_values("Closed (UTC)")
        closed_all["Cumulative net P/L"] = closed_all["Net P/L est."].cumsum()
        closed_all["Equity (illustrative)"] = float(capital) + closed_all["Cumulative net P/L"]
        closed_all["Running peak"] = closed_all["Equity (illustrative)"].cummax()
        closed_all["Drawdown (₹)"] = closed_all["Equity (illustrative)"] - closed_all["Running peak"]
        max_drawdown = abs(float(closed_all["Drawdown (₹)"].min())) if len(closed_all) else 0.0
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_closed = closed_all[closed_all["Close date"] == today_utc]
        daily_net = float(daily_closed["Net P/L est."].sum())
        daily_limit_amount = float(capital) * daily_loss_pct / 100
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total net P/L (est.)", f"₹{net_values.sum():,.2f}")
        k2.metric("Win rate", f"{win_rate:.1f}%")
        k3.metric("Profit factor", "∞" if profit_factor == float("inf") else f"{profit_factor:.2f}")
        k4.metric("Max drawdown", f"₹{max_drawdown:,.2f}")
        k5, k6, k7, k8 = st.columns(4)
        k5.metric("Closed trades", f"{len(closed_all)}")
        k6.metric("Average winning trade", f"₹{avg_win:,.2f}")
        k7.metric("Average losing trade", f"₹{avg_loss:,.2f}")
        k8.metric("Estimated costs total", f"₹{closed_all['Est. costs'].sum():,.2f}")
        st.markdown("**Intraday vs swing results**")
        by_strategy = closed_all.groupby("Strategy", dropna=False).agg(
            Trades=("ID", "count"),
            Net_PL=("Net P/L est.", "sum"),
            Win_rate=("Net P/L est.", lambda x: (x > 0).mean() * 100),
            Avg_net_PL=("Net P/L est.", "mean")
        ).reset_index()
        by_strategy = by_strategy.rename(columns={"Strategy":"Strategy", "Net_PL":"Net P/L (₹)", "Win_rate":"Win rate (%)", "Avg_net_PL":"Average net P/L (₹)"})
        st.dataframe(by_strategy.round(2), use_container_width=True, hide_index=True)
        st.markdown("**Cumulative net P/L after estimated costs**")
        chart_df = closed_all[["Closed (UTC)", "Cumulative net P/L"]].copy().set_index("Closed (UTC)")
        st.line_chart(chart_df)
        st.markdown("**Daily loss-limit monitor (UTC date)**")
        daily_col1, daily_col2 = st.columns(2)
        daily_col1.metric("Today's closed-trade net P/L", f"₹{daily_net:,.2f}")
        daily_col2.metric("Daily loss threshold", f"−₹{daily_limit_amount:,.2f}")
        if daily_net <= -daily_limit_amount:
            st.error("Daily realized loss limit reached. New paper trades will be blocked.")
        elif daily_net < 0:
            st.warning(f"Daily realized loss is ₹{abs(daily_net):,.2f}; remaining room to limit: ₹{daily_limit_amount + daily_net:,.2f}.")
        else:
            st.success(f"Daily realized loss limit not reached. Current realized P/L: ₹{daily_net:,.2f}.")
        st.caption("Daily loss calculations use UTC close dates, not India-local calendar dates. Open/unrealized losses are not included in this daily lockout.")
    else:
        st.info("No closed trades yet. Close a paper trade to see win rate, P/L, profit factor, and drawdown.")

st.divider()
st.subheader("6. Risk rules and limitations")
st.markdown("""
- Default risk budget: 0.5% of ₹20,000 = ₹100 planned gross stop risk.
- Default daily loss limit: 2% = ₹400. V4 blocks creating new paper trades after closed-trade net losses reach this limit; open/unrealized P/L is not included, and the date basis is UTC.
- Maximum open paper trades defaults to 3.
- No Groww connection, broker credentials, real orders, leverage, or options.
- Auto exits use Yahoo Finance one-minute candle highs/lows, not a guaranteed real-time feed. Data can be delayed, missing, or arrive after a move.
- If stop and target are both touched within the same one-minute candle, the app assumes stop-loss first as a conservative rule.
- The app only monitors while it is open and refreshing; it does not run in the background after you close it.
- Cost estimates are illustrative, not an official Groww tariff calculator. Actual charges and slippage may differ.
- Server-side JSON persistence is convenient but not durable across every Streamlit Cloud redeployment/replacement. Download CSV/JSON backups.
""")
st.caption("Version 5 • Research and paper trading only • No live trading API • Not investment advice")
