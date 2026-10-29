import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="AI Trading Partner V1", page_icon="📈", layout="wide")

st.title("📈 AI Trading Partner — V1")
st.caption("Research and paper-trading prototype. Not financial advice. No live orders are placed.")

st.warning(
    "Prototype only: Yahoo Finance data may be delayed, incomplete, or unsuitable for trading decisions. "
    "Signals are rule-based, not reliable predictions. Do not use this app to place live trades."
)

DEFAULT_TICKERS = "RELIANCE.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS,SBIN.NS,LT.NS,BHARTIARTL.NS,ITC.NS,TATAMOTORS.NS"

with st.sidebar:
    st.header("Settings")
    mode = st.radio("Strategy view", ["Swing (daily)", "Intraday (5-minute research)"])
    tickers_text = st.text_area("NSE symbols (comma-separated)", DEFAULT_TICKERS, height=120)
    max_stocks = st.slider("Maximum stocks to scan", 3, 30, 10)
    st.caption("Use Yahoo Finance symbols, usually with .NS for NSE-listed shares.")
    run_scan = st.button("Scan stocks", type="primary", use_container_width=True)

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def fetch_history(symbol, intraday=False):
    try:
        if intraday:
            df = yf.download(symbol, period="5d", interval="5m", auto_adjust=True, progress=False, threads=False)
        else:
            df = yf.download(symbol, period="1y", interval="1d", auto_adjust=True, progress=False, threads=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        needed = ["Open", "High", "Low", "Close", "Volume"]
        if not set(needed).issubset(df.columns):
            return None
        return df.dropna(subset=["Close"])
    except Exception:
        return None

def calculate_signal(df, intraday=False):
    d = df.copy()
    close = d["Close"]
    d["EMA20"] = close.ewm(span=20, adjust=False).mean()
    d["EMA50"] = close.ewm(span=50, adjust=False).mean()
    d["RSI"] = rsi(close, 14)
    d["VolAvg20"] = d["Volume"].rolling(20).mean()
    d["VolRatio"] = d["Volume"] / d["VolAvg20"].replace(0, np.nan)
    d["PriorHigh20"] = d["High"].shift(1).rolling(20).max()
    if intraday:
        typical = (d["High"] + d["Low"] + d["Close"]) / 3
        # Session VWAP approximation; reset by date when timestamps are available.
        try:
            dates = pd.Index(d.index.date)
            d["PV"] = typical * d["Volume"]
            d["VWAP"] = d.groupby(dates)["PV"].cumsum() / d.groupby(dates)["Volume"].cumsum().replace(0, np.nan)
        except Exception:
            d["VWAP"] = (typical * d["Volume"]).cumsum() / d["Volume"].cumsum().replace(0, np.nan)
    else:
        d["VWAP"] = np.nan

    last = d.iloc[-1]
    price = float(last["Close"])
    rsi_value = float(last["RSI"]) if pd.notna(last["RSI"]) else np.nan
    vol_ratio = float(last["VolRatio"]) if pd.notna(last["VolRatio"]) else np.nan
    ema20 = float(last["EMA20"]) if pd.notna(last["EMA20"]) else np.nan
    ema50 = float(last["EMA50"]) if pd.notna(last["EMA50"]) else np.nan

    if intraday:
        vwap = float(last["VWAP"]) if pd.notna(last["VWAP"]) else np.nan
        trend_ok = pd.notna(ema20) and price > ema20
        vwap_ok = pd.notna(vwap) and price > vwap
        momentum_ok = pd.notna(rsi_value) and 50 <= rsi_value <= 70
        volume_ok = pd.notna(vol_ratio) and vol_ratio >= 1.2
        conditions = sum([trend_ok, vwap_ok, momentum_ok, volume_ok])
        if conditions >= 3:
            signal = "Potential bullish setup"
        elif pd.notna(rsi_value) and price < ema20 and pd.notna(vwap) and price < vwap:
            signal = "Potential bearish setup"
        else:
            signal = "No qualifying setup"
        stop = price * 0.99
        target = price * 1.02
    else:
        prior_high = float(last["PriorHigh20"]) if pd.notna(last["PriorHigh20"]) else np.nan
        trend_ok = pd.notna(ema20) and pd.notna(ema50) and price > ema20 > ema50
        breakout_ok = pd.notna(prior_high) and price > prior_high
        momentum_ok = pd.notna(rsi_value) and 50 <= rsi_value <= 70
        volume_ok = pd.notna(vol_ratio) and vol_ratio >= 1.2
        conditions = sum([trend_ok, breakout_ok, momentum_ok, volume_ok])
        if conditions >= 3:
            signal = "Potential bullish setup"
        elif pd.notna(ema20) and pd.notna(ema50) and price < ema20 < ema50:
            signal = "Potential bearish setup"
        else:
            signal = "No qualifying setup"
        stop = price * 0.97
        target = price * 1.06

    return {
        "Price": price, "Signal": signal, "RSI": rsi_value, "Volume ratio": vol_ratio,
        "EMA20": ema20, "EMA50": ema50, "Stop reference": stop, "Target reference": target,
        "History": d
    }

def fundamentals_and_news(symbol):
    out = {}
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.get_info()
        out["Company"] = info.get("shortName") or info.get("longName") or symbol
        out["Market cap"] = info.get("marketCap")
        out["P/E"] = info.get("trailingPE")
        out["Revenue growth"] = info.get("revenueGrowth")
        out["Profit margin"] = info.get("profitMargins")
        try:
            news = ticker.news or []
            out["News"] = []
            for item in news[:3]:
                content = item.get("content", {}) if isinstance(item, dict) else {}
                title = content.get("title") or item.get("title")
                link = content.get("canonicalUrl", {}).get("url") if isinstance(content.get("canonicalUrl"), dict) else item.get("link")
                if title:
                    out["News"].append((title, link))
        except Exception:
            out["News"] = []
    except Exception:
        out["Company"] = symbol
        out["News"] = []
    return out

if run_scan:
    symbols = [s.strip().upper() for s in tickers_text.split(",") if s.strip()]
    symbols = symbols[:max_stocks]
    intraday = mode.startswith("Intraday")
    results, details = [], {}
    progress = st.progress(0)
    status = st.empty()
    for i, symbol in enumerate(symbols):
        status.write(f"Checking {symbol}…")
        hist = fetch_history(symbol, intraday=intraday)
        if hist is not None and len(hist) >= 30:
            calc = calculate_signal(hist, intraday=intraday)
            results.append({
                "Symbol": symbol, "Price": round(calc["Price"], 2), "Signal": calc["Signal"],
                "RSI": round(calc["RSI"], 1) if pd.notna(calc["RSI"]) else None,
                "Volume ratio": round(calc["Volume ratio"], 2) if pd.notna(calc["Volume ratio"]) else None,
                "EMA20": round(calc["EMA20"], 2) if pd.notna(calc["EMA20"]) else None,
                "EMA50": round(calc["EMA50"], 2) if pd.notna(calc["EMA50"]) else None,
                "Stop reference": round(calc["Stop reference"], 2),
                "Target reference": round(calc["Target reference"], 2)
            })
            details[symbol] = {"calc": calc, "fund": fundamentals_and_news(symbol) if not intraday else {}}
        progress.progress((i + 1) / max(1, len(symbols)))
    status.empty()
    progress.empty()
    if results:
        frame = pd.DataFrame(results)
        frame["_rank"] = frame["Signal"].map({"Potential bullish setup": 0, "Potential bearish setup": 1, "No qualifying setup": 2}).fillna(3)
        frame = frame.sort_values(["_rank", "Volume ratio"], ascending=[True, False]).drop(columns="_rank")
        st.subheader("Stock scan results")
        st.dataframe(frame, use_container_width=True, hide_index=True)
        st.download_button("Download scan as CSV", frame.to_csv(index=False), "ai_trading_scan.csv", "text/csv")
        st.caption("Stop and target are illustrative reference levels, not validated trade recommendations. A signal is not a forecast.")
        st.subheader("Stock details")
        for symbol, item in details.items():
            with st.expander(symbol):
                calc = item["calc"]
                hist = calc["History"]
                st.line_chart(hist[["Close", "EMA20", "EMA50"]].tail(100))
                if item["fund"]:
                    fund = item["fund"]
                    st.write(f"**Company:** {fund.get('Company', symbol)}")
                    f1, f2, f3, f4 = st.columns(4)
                    f1.metric("Market cap", f"{fund['Market cap']:,}" if isinstance(fund.get("Market cap"), (int, float)) else "N/A")
                    f2.metric("Trailing P/E", f"{fund.get('P/E'):.2f}" if isinstance(fund.get("P/E"), (int, float)) else "N/A")
                    f3.metric("Revenue growth", f"{fund.get('Revenue growth'):.1%}" if isinstance(fund.get("Revenue growth"), (int, float)) else "N/A")
                    f4.metric("Profit margin", f"{fund.get('Profit margin'):.1%}" if isinstance(fund.get("Profit margin"), (int, float)) else "N/A")
                    if fund.get("News"):
                        st.write("**Recent headlines (if provided by data source):**")
                        for title, link in fund["News"]:
                            if link:
                                st.markdown(f"- [{title}]({link})")
                            else:
                                st.write(f"- {title}")
    else:
        st.error("No usable data returned. Check the symbols and try again later.")
else:
    st.info("Enter symbols in the sidebar and tap **Scan stocks** to run the first research scan.")
    st.subheader("Default watchlist")
    st.write("RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, LT, BHARTIARTL, ITC and TATAMOTORS.")
    st.subheader("What this version does")
    st.markdown(
        "- Scans daily data for swing setups or recent 5-minute bars for intraday research.\n"
        "- Calculates EMA20, EMA50, RSI and relative volume.\n"
        "- Displays basic company metrics and available headlines for swing scans.\n"
        "- Exports scan results to CSV.\n\n"
        "**Not included yet:** reliable live market data, a validated backtester, paper-order tracking, persistent database, broker authentication, or order placement."
    )

st.divider()
st.caption(f"App build: V1 research prototype • {datetime.now().strftime('%Y-%m-%d')}")
