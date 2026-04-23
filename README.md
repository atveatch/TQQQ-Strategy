# TQQQ Regime Strategy — Live Dashboard

A systematic TQQQ position-sizing strategy using real market data.
Signals update every hour. Runs locally or deploys free to Streamlit Cloud.

---

## Features

- **Live Signal** — Real-time regime score, TQQQ allocation %, checklist
- **Backtest** — Real daily TQQQ/SPY data since 2010, true peak-to-trough drawdowns
- **Blend Builder** — Dial custom defensive allocation, save & compare blends
- **Rate Regime Toggle** — Historical / Rate-Adjusted / Forward scenario
- **Strategy Guide** — Full rules, HYG logic, limitations

---

## Quick Start (Local)

### 1. Clone / download this folder

```bash
git clone https://github.com/YOUR_USERNAME/tqqq-strategy.git
cd tqqq-strategy
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
streamlit run app.py
```

Opens at http://localhost:8501

---

## Deploy Free to Streamlit Cloud

Streamlit Cloud is the fastest path — free, no server needed.

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "initial"
git remote add origin https://github.com/YOUR_USERNAME/tqqq-strategy.git
git push -u origin main
```

### 2. Deploy

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with GitHub
3. Click **New app**
4. Select your repo → branch: `main` → file: `app.py`
5. Click **Deploy** — live in ~2 minutes

No config needed. Streamlit Cloud installs `requirements.txt` automatically.

### 3. Auto-refresh

By default the app refreshes data every 1 hour (`@st.cache_data(ttl=3600)`).
To force a refresh: click the ☰ menu → **Rerun**.

---

## Optional Enhancements

### Email / SMS alerts when signal changes

Install and configure:
```bash
pip install sendgrid   # or twilio for SMS
```

Add to `utils/data.py`:
```python
def check_signal_change(current_alloc, prev_alloc, threshold=0.25):
    if abs(current_alloc - prev_alloc) >= threshold:
        send_alert(f"TQQQ allocation changed to {current_alloc*100:.0f}%")
```

### Schedule daily data refresh (GitHub Actions)

Create `.github/workflows/refresh.yml`:
```yaml
name: Daily refresh
on:
  schedule:
    - cron: '0 21 * * 1-5'  # 4pm ET weekdays
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - run: curl https://YOUR_APP.streamlit.app/  # wakes app + clears cache
```

### Broker integration (Alpaca — free paper trading)

```bash
pip install alpaca-trade-api
```

```python
import alpaca_trade_api as tradeapi
api = tradeapi.REST(KEY_ID, SECRET_KEY, base_url='https://paper-api.alpaca.markets')

def rebalance(tqqq_pct: float, defensive_blend: dict):
    portfolio_value = float(api.get_account().portfolio_value)
    # Calculate target shares and submit orders
    ...
```

### Add more indicators

Suggested additions in `utils/data.py`:
- **Breadth**: % of S&P 500 stocks above SMA200 (via yfinance bulk download)
- **Yield curve**: 10Y−2Y spread (FRED API, free)
- **Put/Call ratio**: CBOE data
- **Market internals**: Advance/decline line

---

## Data Sources

| Ticker | Source | Notes |
|--------|--------|-------|
| TQQQ, SPY, HYG, TLT, GLD, BTAL, SQQQ, SGOV | yfinance | Free, hourly cache |
| ^VIX | yfinance | CBOE volatility index |

yfinance pulls from Yahoo Finance. For production use consider:
- **Polygon.io** — $29/mo, reliable, WebSocket for real-time
- **Tiingo** — $10/mo, excellent adjusted data
- **Alpha Vantage** — Free tier (25 req/day), paid from $50/mo

---

## File Structure

```
tqqq_strategy/
├── app.py                  # Main entry point + navigation
├── requirements.txt
├── README.md
├── pages/
│   ├── live_signal.py      # Real-time dashboard
│   ├── backtest.py         # Historical backtest
│   ├── blend_builder.py    # Defensive blend optimizer
│   └── guide.py            # Strategy documentation
└── utils/
    ├── data.py             # Data fetching + signal computation
    └── backtest.py         # Backtest engine + stats
```

---

## Known Limitations

1. **yfinance reliability** — Yahoo Finance occasionally rate-limits or returns
   stale data. The 1-hour cache mitigates most issues. For mission-critical use,
   swap to Polygon.io or Tiingo.

2. **BTAL data** — BTAL launched in 2011. Backtest before 2011 uses estimated
   anti-beta returns. Results before 2012 should be treated as approximate.

3. **RVOL** — Computed from daily volume only. True intraday RVOL requires
   intraday data (15min interval from yfinance, free but limited history).

4. **Survivorship bias** — yfinance adjusted prices account for splits/dividends
   but not delisting. Not applicable to these ETFs but worth noting.

5. **Tax drag** — Frequent rebalancing in taxable accounts significantly impacts
   net returns. Consider running this strategy in an IRA or 401(k).

---

*Not financial advice. TQQQ is a 3× leveraged ETF that can lose >20% in a single day.
Only use capital you can afford to lose entirely. This tool is for educational purposes.*
