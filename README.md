# AI Trading Partner V4 — Paper Trading Only

## What's new
- Performance dashboard: estimated net P/L, win rate, profit factor, average winning/losing trade, estimated costs, and maximum drawdown.
- Strategy classification: label each paper trade as Intraday or Swing and compare results by strategy.
- Risk dashboard: today's closed-trade P/L against the configured daily loss limit.
- Daily paper-trade lockout: prevents creating new paper trades when closed-trade net losses for the current UTC date reach the configured limit.
- V3 ledger compatibility: V4 reuses `paper_trades_v3.json` so existing server-side paper trades are retained where that file is still present.
- CSV and JSON backup/restore remain available.

## Deploy from Android
1. Download and extract the ZIP.
2. Open your existing GitHub repository `ai-trading-partner`.
3. Replace the full contents of `app.py` with this version and commit.
4. Confirm `requirements.txt` includes `streamlit-autorefresh`.
5. Wait for Streamlit Cloud to redeploy, then refresh the app.
6. Download a CSV and JSON ledger backup before major changes.

## Important limitations
- Paper trading only. No Groww connection, no broker credentials, and no real orders.
- Dashboard metrics are based on closed simulated trades and estimated costs; past simulated performance does not predict future results.
- Daily lockout uses UTC close dates and includes closed trades only; it does not include unrealized losses on open paper trades.
- Automatic exits run only while the app is open and refreshing. Yahoo Finance data can be delayed, incomplete, or unavailable; simulated exits are not guaranteed.
- Streamlit-hosted local files may not survive every redeployment/server replacement. Back up the ledger regularly.
- Cost assumptions are illustrative, not official Groww charges. Slippage, gaps, and data limitations may make real outcomes different.
