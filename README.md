# AI Trading Partner V5.2 — Android-friendly Streamlit app

## What's changed from V5.1
- Automatic paper monitoring ignores candles that started before or at the trade's creation time.
- The newest one-minute candle is skipped because it may still be forming.
- Paper-trade creation is blocked if the latest available market price is already at/beyond the planned stop-loss or target. This prevents a trade with unrealistic levels (for example, a ₹100 target on a stock currently trading far above ₹100) from closing immediately.
- If market data is unavailable at creation, the app warns and uses future available completed candles only.

## Important limitations
- Paper trading only: no Groww connection and no real orders.
- Yahoo Finance data can be delayed, missing, or inconsistent. The monitor runs only while the app is open and refreshing, and can miss price moves.
- This version retains the existing `paper_trades_v3.json` ledger filename to preserve prior ledger data in the same app instance. Hosted Streamlit local files may not persist across redeploys; download regular CSV/JSON backups.

## Run
Install packages from `requirements.txt`, then run:
`streamlit run app.py`
