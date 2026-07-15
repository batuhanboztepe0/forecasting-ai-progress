---
name: prediction-market-microstructure
description: Domain knowledge on how prediction markets work mechanically and how to turn a probabilistic edge into a realistic, cost-aware backtest. Use for RQ4, for reading a market price as a probability, and for anything about liquidity, slippage, fees, AMM/CPMM mechanics, order books, or information aggregation. Consult before building any trading-value simulation so frictions are modeled honestly.
---

# Prediction-Market Microstructure

The bridge from "calibrated probability" to "tradeable value". This is where a forecasting edge
usually dies — model the frictions honestly.

## Reading a price as a probability

- A binary market's price ≈ the crowd's probability, but it is shaped by the mechanism.
  **AMM/CPMM (Manifold):** price moves along a bonding curve; a trade of finite size moves the
  price, so the *effective* fill probability differs from the quoted one.
  **Order book (real-money venues):** you fill against posted liquidity at multiple levels.
- Always take the **pre-outcome snapshot** price/state (see `DATA.md`), never the settled price.

## Frictions to model (RQ4)

- **Slippage / price impact:** simulate the actual fill given trade size against the AMM curve
  or book depth — not the mid quote. Size positions realistically relative to liquidity.
- **Fees:** platform/trading fees per trade.
- **Liquidity limits:** cap position size by available depth; thin markets cap deployable capital.
- **Play-money caveat (Manifold):** mana is not USD; "P&L" is mechanical/illustrative, not real
  economic value. State this explicitly. A real-money venue is required for a strong economic claim.

## Backtest design

- Trade only when the forecaster's probability diverges from the market price beyond a
  pre-specified edge threshold (net of expected costs).
- Post-cutoff questions only (no contamination).
- Position sizing: fixed-fraction or edge-proportional (document the rule); optionally compare to
  a calibration-corrected sizing.
- Report **risk-adjusted** outcomes with bootstrap CIs, not a single P&L number. "Survives" only
  if the net-of-cost P&L CI excludes ≤ 0.

## Information aggregation (links to RQ3)

Markets aggregate dispersed, incentivized information; that is why a market price can carry
signal a model lacks — and why the encompassing test (which source adds information over the
other) is the economically interesting question, not a raw accuracy horse-race.

## Pitfalls

Trading at the mid (ignoring impact), ignoring fees, over-sizing beyond liquidity, using the
settled price, reporting one P&L without a CI, and presenting play-money returns as real value.
