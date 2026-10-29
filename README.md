# AI Trading Partner V5 (Paper Trading Only)

## What's new
- Adds a controlled, isolated simulation test bench to test target hits, stop-loss hits, custom exit prices, and candle high/low behavior.
- Simulation test trades are kept separate from the main paper ledger and performance dashboard.
- Existing V4 features remain: scanner, planner, automatic paper exits, risk dashboard, ledger export/restore.

## Android / Streamlit deployment
1. Download and extract the ZIP.
2. In your GitHub repository, replace `app.py` and `requirements.txt` with these files.
3. Commit the changes and wait for Streamlit to redeploy.
4. Refresh the app and find **Controlled simulation test mode** above the main paper-trade ledger.

## Test the stop-loss
1. Create an isolated test trade with entry 101, stop 100, target 115.5, quantity 100.
2. Tap **Simulate stop-loss hit**.
3. Expected result: exit 100, gross P/L -100 before estimated costs, exit reason `SIM TEST: Stop-loss hit`.

## Test the target
Create a new test trade and tap **Simulate target hit**. Expected result: exit 115.5 and gross P/L +1450 before estimated costs.

## Test a candle touching both levels
Create a test trade, set simulated candle low at/below the stop and high at/above the target, then tap **Evaluate simulated candle**. The test bench uses the conservative assumption that stop-loss is hit first. A single candle does not reveal the true intrabar sequence.

## Important limitations
- This is a research prototype, not investment advice. No Groww connection, broker credentials, or live orders.
- Controlled simulation tests are not live market tests and do not modify the main ledger. Their session-only history may reset if the app restarts; download the test CSV if needed.
- Market-driven auto exits still require the app to be open and refreshing and depend on Yahoo Finance data availability.
- Server-side main ledger files are not guaranteed to survive all hosting redeployments. Download CSV/JSON backups regularly.
- Costs are illustrative and may differ from actual brokerage, taxes, fees, and slippage.
