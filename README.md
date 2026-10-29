# AI Trading Partner V1 — Android-first prototype

This is a research-only stock scanner. It does **not** place orders or provide reliable real-time trading data.

## Easiest route from Android

1. Create an account on a cloud coding/deployment service that supports Python and Streamlit.
2. Upload `app.py` and `requirements.txt` into a new project/repository.
3. Set the run command to `streamlit run app.py`.
4. Open the generated web app URL in Chrome on Android.
5. Test with the default symbols and review the warnings.

A GitHub repository plus Streamlit Community Cloud is one possible deployment route; service availability, limits, and deployment requirements can change.

## Run locally (for reference)

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Included

- Daily-data swing research and recent 5-minute intraday research views
- EMA20/EMA50, RSI, relative volume, simple rule-based signal labels
- Illustrative stop/target reference levels
- Basic fundamentals and headlines where the data source provides them
- CSV export

## Not included

- A validated backtester
- Real-time or exchange-licensed market data
- Persistent paper-trade ledger
- Groww API integration or order placement
- Robust corporate-action/news risk controls

## Safety

- Signals are illustrative rules, not a promise of profitability.
- Yahoo Finance data may be delayed, incomplete, or unsuitable for trading.
- Do not connect real-money trading until backtesting, forward testing, risk controls, broker/API requirements, and applicable Indian regulations have been reviewed.
