# AI Trading Partner V2 (Android-friendly deployment)

A Streamlit research dashboard for Indian NSE equities with daily swing and 5-minute intraday research views, rule-based indicators, a risk-based quantity planner, and a session-only paper-trade ledger.

## Important limitations
- No broker connection and no live orders.
- Yahoo Finance data may be delayed, incomplete, unavailable, or unsuitable for execution decisions.
- Signals are simple rule-based indicators, not predictions.
- Paper ledger is stored in Streamlit session state and may reset after server sleep/restart or browser session changes. Download CSVs if you need a record.
- Charge calculations are rough illustrative estimates only. They are not an official Groww tariff calculator; verify current brokerage, statutory charges, taxes, and slippage before relying on any estimate.
- The app is long-only for the trade planner and does not support options, leverage, or automatic stop/target execution.

## Deploy from an Android phone
1. Download and extract the ZIP on your phone.
2. Open your GitHub repository `ai-trading-partner`.
3. Open `app.py`, tap the pencil/edit option, replace its full contents with this `app.py`, then commit. Alternatively use **Add file → Upload files** and upload `app.py` and `requirements.txt`, accepting the replacement prompt.
4. Upload/replace `requirements.txt` too. You may also replace `README.md`.
5. Open https://share.streamlit.io/ and select your existing app. It should redeploy automatically after the GitHub commit. If not, use the app menu to reboot/redeploy.
6. Wait for the app to finish restarting, then refresh the app URL.

## Local run
`pip install -r requirements.txt`
`streamlit run app.py`

Never place broker credentials, API tokens, or personal account information in a public repository.
