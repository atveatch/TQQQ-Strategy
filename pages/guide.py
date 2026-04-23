"""
pages/guide.py — Strategy reference guide
"""

import streamlit as st


def render():
    st.markdown("# 📋 STRATEGY GUIDE")
    st.markdown("---")

    st.markdown("""
    ## Overview

    This strategy uses a multi-factor regime filter to size TQQQ exposure dynamically,
    replacing the destructive buy-and-hold experience (80%+ drawdowns) with a systematic
    risk-managed approach. When the regime turns negative, capital rotates into a custom
    defensive blend rather than sitting in cash.

    ---
    ## Core Indicators

    | Indicator | Weight | What it measures |
    |-----------|--------|-----------------|
    | SPY SMA200 ±3% Band | 40% | Primary trend regime |
    | HYG Credit Health | 25% | Leading indicator — credit leads equity |
    | VIX Level | 20% | Volatility regime filter |
    | RSI (14) | 15% | Momentum confirmation |
    | RVOL | Modifier | Confirms conviction of move |

    ---
    ## Allocation Rules

    | Composite Score | SPY Position | TQQQ Allocation |
    |----------------|--------------|-----------------|
    | 75–100 | Above upper band (+3%) | 100% TQQQ |
    | 58–74  | Above SMA200, below +3% | 75% TQQQ |
    | 42–57  | Within ±3% band | 50% TQQQ |
    | 25–41  | Below SMA200, above −3% | 25% TQQQ |
    | 0–24   | Below lower band (−3%) | 0% — Full defensive |

    **Override rules (hard exits regardless of composite score):**
    - HYG below both SMA50 and SMA200 → reduce to 0–15%
    - VIX > 28 → reduce to 0–15%
    - Both triggered → 0% TQQQ

    ---
    ## HYG Credit Deterioration Signal

    HYG is the most important leading indicator in this strategy.
    Credit markets price in risk before equity markets react.

    | HYG Status | Signal | Action |
    |------------|--------|--------|
    | HYG > SMA50 > SMA200 | Healthy | Hold full allocation |
    | HYG < SMA50, SMA50 flattening | Warning | Reduce 20–30% |
    | HYG < SMA50 < SMA200 | Danger | Exit TQQQ entirely |

    Historical examples where HYG led:
    - **2018 Q4**: HYG broke SMA50 in October, TQQQ fell 40% by December
    - **2020 Feb**: HYG credit spreads widened before SPY peaked
    - **2022**: HYG in bear stack all year, correctly kept strategy defensive

    ---
    ## Defensive Blend Guidance

    | Asset | Role | Best regime |
    |-------|------|-------------|
    | BTAL | Anti-beta long/short | Any bear market |
    | TLT | Rate hedge + duration | Recession, Fed cuts |
    | GLD | Tail risk + inflation | Crisis, dollar weakness |
    | SQQQ | Directional short | Confirmed bear trend only |
    | Cash | Risk-free carry | High-rate sideways chop |

    **Recommended baseline blend:** BTAL 40% / TLT 30% / GLD 15% / Cash 15%

    Key insight: BTAL + TLT covers both types of bear market:
    - Rate-driven bear (2022): BTAL wins, TLT loses → net positive
    - Recession bear (2020, 2008): TLT wins, BTAL flat → net positive

    ---
    ## Rate Regime Considerations

    The 2010–2024 backtest includes a massive Fed tailwind that won't repeat:

    | Factor | 2010–2021 | 2025 Forward |
    |--------|-----------|--------------|
    | Fed Funds Rate | Near 0% | 4–5% |
    | TQQQ carry cost | Minimal | +1.5–2%/yr headwind |
    | TLT hedge strength | Strong (rates falling) | Weaker (range-bound) |
    | Cash yield | ~0% | 4.4%+ real hurdle |
    | Multiple expansion | Significant tailwind | Limited |

    **Forward CAGR expectation:** Reduce historical CAGR by 8–12% for realistic planning.

    ---
    ## Known Limitations

    1. **Leverage decay**: TQQQ loses to 3× SPY in choppy/sideways markets due to daily rebalancing.
       Annual drag: ~2–5% in high-volatility environments.

    2. **Tax efficiency**: Frequent rebalancing triggers short-term capital gains.
       Consider this strategy in tax-advantaged accounts (IRA, 401k) where possible.

    3. **Liquidity**: BTAL has ~$200M AUM. Fine for retail, but spreads widen at scale.

    4. **Signal lag**: SMA200 is a lagging indicator by definition. The strategy will
       never perfectly time tops or bottoms — it trades certainty for avoiding the worst periods.

    5. **Model risk**: All backtests are simulations. Real execution involves slippage,
       dividend timing, and data quality differences.

    ---
    ## Deployment Notes

    This app refreshes data every hour via yfinance. For production use:
    - Schedule a daily data pull (cron job or GitHub Actions)
    - Consider adding email/SMS alerts when allocation signal changes
    - Add broker API integration (Alpaca, IBKR) for semi-automated execution

    ---
    *Not financial advice. Past performance does not predict future results.
    TQQQ is a highly leveraged product — only use capital you can afford to lose entirely.*
    """)
