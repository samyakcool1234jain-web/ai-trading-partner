# AI Trading Partner V5.1 (Paper Trading Only)

## Fix in V5.1
- Simulation buttons close the isolated test trade immediately.
- A clear status banner shows the most recent simulated exit, exit reason, exit price, gross P/L, and estimated net P/L after the app reruns.
- Closed test trades appear in **Isolated simulation test results**, not the main paper ledger. This separation is intentional.

## Install from Android / GitHub
1. Download and extract this ZIP.
2. In your GitHub repository, replace the existing root `app.py` with this `app.py` and commit it.
3. Replace `requirements.txt` only if needed; V5.1 uses the same dependencies as V5.
4. Wait for Streamlit to redeploy, then refresh the app.
5. Confirm the title says **AI Trading Partner — V5.1**.

## Test stop-loss
1. Under **Controlled simulation test mode**, create a test trade with entry 101, stop 100, target 115.5, quantity 100.
2. Tap **Simulate stop-loss hit**.
3. The test trade should close immediately. The status banner should show exit reason `SIM TEST: Stop-loss hit`, exit ₹100, gross P/L -₹100 (before estimated costs).
4. Check **Isolated simulation test results** for the closed record.

## Test target
Create another isolated test trade and tap **Simulate target hit**. Expected exit ₹115.50 and gross P/L +₹1,450 before estimated costs.

## Notes
- Controlled tests use simulated prices and do not alter the main paper ledger or its performance metrics.
- Market-data paper exits require the app to be open and refreshing and depend on data availability. No Groww connection or live orders are included.
- Download backups regularly; local files on hosted Streamlit instances are not guaranteed to survive all redeployments.
