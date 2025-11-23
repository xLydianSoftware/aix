# Strategy Building Guide for Qubx Framework

Comprehensive guide for building trading strategies in the Qubx framework. This guide is based on real strategy implementations and current best practices.

## Core Architecture

**Key Components:**
- `IStrategy`: Base interface for all strategies
- `IStrategyContext`: Access to market data, trading operations, and account information
- `PositionsTracker`: Position sizing and risk management
- `IUniverse`: Universe selection interface (optional)
- `IUniversePicker`: Helper classes for instrument selection

## Strategy Lifecycle

Every strategy follows a defined lifecycle with specific methods called at different stages:

```
on_init → on_start → on_warmup_finished → [on_fit → on_event] → on_stop
                                              ↑__________|
```

### Lifecycle Methods Overview

```python
from qubx.core.interfaces import IStrategy, IStrategyContext, IStrategyInitializer

class MyStrategy(IStrategy):
    # - configuration parameters (set from YAML)
    timeframe: str = "1h"
    leverage: float = 1.0

    def on_init(self, initializer: IStrategyInitializer) -> None:
        """
        Called once during strategy initialization, BEFORE market data is available.
        Configure subscriptions, schedules, and framework settings.
        """
        # - set base data subscription
        initializer.set_base_subscription(DataType.OHLC[self.timeframe])

        # - set event schedule (when on_event is called)
        initializer.set_event_schedule(self.timeframe)

        # - set universe refit schedule (when on_fit is called)
        initializer.set_fit_schedule("1d")  # or "M @ 23:59" for monthly

        # - set warmup period (data preload before trading starts)
        initializer.set_warmup("2d")

        # - schedule custom events (optional)
        # initializer.schedule("1d", self._daily_check)

    def on_start(self, ctx: IStrategyContext) -> None:
        """
        Called once when market data becomes available.
        Initialize indicators, state variables, and data structures.
        """
        # - initialize state
        self._state = {}

        # - setup indicators for each instrument
        self._indicators = {}
        for instrument in ctx.instruments:
            ohlc = ctx.ohlc(instrument, self.timeframe)
            self._indicators[instrument] = {
                'ema': ema(ohlc.close, 20),
                'atr': atr(ohlc, 14)
            }

        # - initialize universe pickers (if using quantkit)
        # self._picker = TopCapitalizedAssetsPicker(percentile=75)

    def on_warmup_finished(self, ctx: IStrategyContext) -> None:
        """
        Called when warmup period completes.
        Enable trading, finalize initialization.
        """
        logger.info("Warmup finished, strategy ready to trade")

    def on_fit(self, ctx: IStrategyContext) -> None:
        """
        Called on scheduled intervals to refit models or update universe.
        Use for periodic universe updates, model retraining.
        """
        # - update universe
        new_universe = self._select_universe(ctx)
        ctx.set_universe(new_universe, if_has_position_then="close")

    def on_event(self, ctx: IStrategyContext, event: TriggerEvent) -> list[Signal]:
        """
        Main signal generation method, called on scheduled events.
        Generate trading signals based on current market state.
        """
        signals = []

        for instrument in ctx.instruments:
            # - check indicators
            ema_value = self._indicators[instrument]['ema'][0]
            current_price = ctx.quote(instrument).mid_price()

            # - generate signals
            if current_price > ema_value:
                signal = instrument.signal(ctx, side=1, comment="Price above EMA")
                signals.append(signal)
            elif current_price < ema_value:
                signal = instrument.signal(ctx, side=-1, comment="Price below EMA")
                signals.append(signal)

        return signals

    def on_market_data(self, ctx: IStrategyContext, data: MarketEvent) -> None:
        """
        Called on EVERY market data event (bars, quotes, trades, orderbook).
        Keep processing lightweight - called VERY frequently in live trading.
        """
        if data.type == DataType.OHLC:
            # - indicators auto-update via dependency tree
            # - react to bar updates if needed
            pass

    def on_order_update(self, ctx: IStrategyContext, order: Order) -> None:
        """
        Handle order status updates (fills, cancellations, rejections).
        """
        if order.is_filled():
            logger.info(f"Order filled: {order.instrument.symbol} @ {order.fill_price}")

    def on_universe_change(
        self,
        ctx: IStrategyContext,
        add_instruments: list[Instrument],
        rm_instruments: list[Instrument]
    ) -> None:
        """
        Handle universe changes (instruments added/removed).
        Clean up removed instruments, initialize new ones.
        """
        # - clean up removed instruments
        for instrument in rm_instruments:
            if instrument in self._indicators:
                del self._indicators[instrument]

        # - initialize new instruments
        for instrument in add_instruments:
            ohlc = ctx.ohlc(instrument, self.timeframe)
            self._indicators[instrument] = {
                'ema': ema(ohlc.close, 20)
            }

    def tracker(self, ctx: IStrategyContext) -> PositionsTracker:
        """
        Return position tracking and sizing logic.
        Called by framework to determine position sizes.
        """
        return PositionsTracker(FixedLeverageSizer(self.leverage))
```

## Strategy Context and Data Access

The `IStrategyContext` provides all data and trading operations:

### Market Data Access

```python
# - OHLC data (streaming)
ohlc = ctx.ohlc(instrument, timeframe="1h", length=100)  # Returns OHLCV series
ohlc_df = ctx.ohlc_pd(instrument, timeframe="1h", length=100)  # Returns pandas DataFrame

# - quote data
quote = ctx.quote(instrument)
mid_price = quote.mid_price()
bid = quote.bid
ask = quote.ask

# - auxiliary data (funding, fundamentals, etc.)
funding_data = ctx.get_aux_data(
    "funding_payment",
    exchange="BINANCE.UM",
    start=start_time,
    stop=end_time
)
```

### Trading Operations

```python
# - generate signals
signal = instrument.signal(
    ctx,                      # or ctx.time() for timestamp
    side=1,                   # 1=long, -1=short, 0=close
    comment="Long signal",
    take=110.0,              # take profit price (optional)
    stop=95.0                # stop loss price (optional)
)

# - direct position control
ctx.set_target_position(instrument, target_size)
ctx.cancel_orders(instrument)

# - universe management
ctx.set_universe(instruments, if_has_position_then="close")  # or "keep"
```

### Account Information

```python
# - capital and positions
capital = ctx.get_capital()              # Available capital
total_capital = ctx.get_total_capital()  # Total capital (including positions)
position = ctx.get_position(instrument)  # Current position

# - position details
position.quantity  # Position size (+ for long, - for short)
position.size      # Absolute position size
position.entry_price  # Average entry price
position.unrealized_pnl  # Current P&L
```

## Technical Indicators

### Streaming Indicators (Preferred)

**Always prefer streaming indicators** for better performance (10-100x faster):

```python
from qubx.ta.indicators import sma, ema, rsi, atr, macd

class StreamingStrategy(IStrategy):
    timeframe: str = "1h"

    def on_start(self, ctx: IStrategyContext):
        self._indicators = {}

        for instrument in ctx.instruments:
            # - get streaming OHLCV series from context
            ohlcv = ctx.ohlc(instrument, self.timeframe)

            # - attach streaming indicators (auto-update via dependency tree)
            self._indicators[instrument] = {
                'sma_20': sma(ohlcv.close, 20),
                'ema_50': ema(ohlcv.close, 50),
                'rsi_14': rsi(ohlcv.close, 14),
                'atr_14': atr(ohlcv, 14),           # ATR needs full OHLCV
                'macd': macd(ohlcv.close, 12, 26, 9)
            }

    def on_event(self, ctx: IStrategyContext, event: TriggerEvent) -> list[Signal]:
        signals = []

        for instrument in ctx.instruments:
            ind = self._indicators[instrument]

            # - access current values (automatically updated)
            current_sma = ind['sma_20'][0]  # Most recent value
            prev_sma = ind['sma_20'][1]     # Previous value
            current_rsi = ind['rsi_14'][0]

            # - generate signals based on indicators
            if current_sma > prev_sma and current_rsi < 30:
                signals.append(instrument.signal(ctx, 1, comment="Oversold + uptrend"))

        return signals
```

**Key Benefits:**
- Auto-update via dependency tree
- Sub-microsecond updates
- Fixed memory usage
- Designed for real-time trading

### Pandas Indicators (Use When Needed)

Use pandas indicators only when:
- No streaming implementation exists
- Complex batch processing needed
- One-time analysis or research

```python
from qubx.pandaz.ta import sma, ema, rsi, super_trend, bollinger

def on_event(self, ctx: IStrategyContext, event: TriggerEvent) -> list[Signal]:
    signals = []

    for instrument in ctx.instruments:
        # - get pandas DataFrame
        ohlc_df = ctx.ohlc_pd(instrument, self.timeframe, length=100)

        # - calculate indicators
        st = super_trend(
            ohlc_df,
            length=24,
            mult=3.0,
            src="hl2",
            atr_smoother="sma"
        )

        # - check trend
        current_trend = st["trend"].iloc[-1]
        prev_trend = st["trend"].iloc[-2]

        # - signal on trend change
        if current_trend == 1 and prev_trend == -1:
            signals.append(instrument.signal(ctx, 1, comment="Trend up"))

    return signals
```

## Universe Selection

### Using QuantKit Universe Pickers

```python
from quantkit.pacman.pickers import TopCapitalizedAssetsPicker, CorrelationPicker

class UniverseStrategy(IStrategy):
    top_percentile: float = 75
    min_correlation: float = 0.75
    benchmark: str = "BTCUSDT"

    def on_start(self, ctx: IStrategyContext):
        # - initialize pickers
        self._picker_cap = TopCapitalizedAssetsPicker(
            self.top_percentile,
            required_instruments=[self.benchmark],
            excluded_instruments=["USDCUSDT", "TUSDUSDT"]
        )

        self._picker_corr = CorrelationPicker(
            self.min_correlation,
            lookback=60,
            timeframe="1d",
            method="pearson"
        )

    def on_fit(self, ctx: IStrategyContext):
        # - select universe using pickers
        universe_cap = self._picker_cap.pick(ctx, ctx.exchanges[0])
        universe_corr = self._picker_corr.pick(
            ctx,
            ctx.exchanges[0],
            selector=self.benchmark  # Find instruments correlated to benchmark
        )

        # - combine universes
        final_universe = [i for i in universe_corr if i in universe_cap]

        # - update universe
        ctx.set_universe(final_universe, if_has_position_then="close")
```

### Custom Universe Selection

```python
class CustomUniverseStrategy(IStrategy):
    min_volume: float = 1000000
    max_instruments: int = 20

    def on_fit(self, ctx: IStrategyContext):
        # - get fundamental data
        now = pd.Timestamp(ctx.time())
        f_data = ctx.get_aux_data(
            "fundamental_data",
            exchange=ctx.exchanges[0],
            start=now - pd.Timedelta("7d"),
            stop=now,
            timeframe="1d"
        )

        if f_data is None or f_data.empty:
            return

        # - filter by volume
        volume_avg = f_data.groupby("asset")["total_volume"].mean()
        top_volume = volume_avg[volume_avg > self.min_volume].sort_values(ascending=False)

        # - get top instruments
        selected_assets = top_volume.head(self.max_instruments).index

        # - convert to instruments
        from qubx.core.lookups import lookup
        instruments = []
        for asset in selected_assets:
            found = lookup.find_instruments(ctx.exchanges[0], base=asset, quote="USDT")
            if found:
                instruments.append(found[0])

        # - update universe
        ctx.set_universe(instruments, if_has_position_then="close")
```

## Signal-to-Execution Flow

Understanding how signals become actual positions is crucial for strategy development.

### The Complete Flow

```
Strategy → Signal → Tracker → Sizer → Target → Gatherer → Execution
```

1. **Strategy** generates `Signal` (via `on_event` or `on_market_data`)
2. **Tracker** receives signal and manages risk logic (see `qubx.trackers`)
3. **Sizer** converts signal to `Target` with position sizing (see `qubx.trackers.sizers`)
4. **Target** specifies desired position size (`TargetPosition`)
5. **Gatherer** executes orders to match target (see `qubx.gathering`)

### Key Concepts

**Signals are NOT additive:**
```python
# IMPORTANT: Signals represent desired state, not additive actions

# Time 1: signal = +1 → target = 100 shares → open 100 shares
signal = instrument.signal(ctx, side=1)

# Time 2: signal = +1 → target = 98 shares (price changed) → close 2 shares
signal = instrument.signal(ctx, side=1)  # NOT 100 + 100 = 200!

# The tracker/sizer recalculates the target based on current market conditions
# Gatherer adjusts position to match new target (98), selling 2 shares
```

**Signal values:**
- `side = 1`: Long position (not additive, represents state)
- `side = -1`: Short position
- `side = 0`: Flat/close position
- `signal = 0.5`: 50% weight (for portfolio strategies)

### Accessing Execution Data

The `TradingSessionResult` contains complete execution history:

```python
r = simulate(strategy, ...)
session = r[0]

# All signals generated by strategy
signals_log = session.signals_log  # DataFrame: all signals from on_event/on_market_data

# Targets produced from signals
targets_log = session.targets_log  # DataFrame: targets after tracker/sizer processing

# Actual executions that changed positions
executions_log = session.executions_log  # DataFrame: real orders executed

# Analyze signal-to-execution flow
print(f"Total signals: {len(signals_log)}")
print(f"Total targets: {len(targets_log)}")
print(f"Total executions: {len(executions_log)}")

# Check if signals led to executions
if len(signals_log) > len(executions_log):
    print("Some signals did not result in executions (filtered or same target)")
```

## Position Sizing and Risk Management

### Trackers: Risk Management Layer

**Trackers** implement different risk management approaches. Choose based on your strategy needs:

```python
from qubx.trackers import PositionsTracker, SignalRiskPositionTracker, StopTakePositionTracker
from qubx.trackers.sizers import FixedRiskSizer, InverseVolatilitySizer

# Example: Stop/Take tracker with fixed risk sizing
class MyStrategy(IStrategy):
    max_cap_in_risk: float = 5.0  # Max 5% capital at risk per trade

    def tracker(self, ctx: IStrategyContext):
        # StopTakePositionTracker handles stop loss and take profit
        # FixedRiskSizer calculates position size based on stop level and max risk
        return StopTakePositionTracker(
            FixedRiskSizer(self.max_cap_in_risk)
        )

    def on_event(self, ctx: IStrategyContext, event: TriggerEvent):
        # Signal with stop and take levels
        signal = instrument.signal(
            ctx,
            side=1,
            stop=95.0,   # Stop loss at 95
            take=110.0,  # Take profit at 110
            comment="Long with risk management"
        )
        return [signal]
```

**How it works:**
1. Signal specifies stop=95, take=110
2. Tracker (StopTakePositionTracker) receives signal
3. Sizer (FixedRiskSizer) calculates position size:
   - Risk per share = entry_price - stop_price
   - Max loss = max_cap_in_risk% of capital
   - Position size = max_loss / risk_per_share
4. Target = TargetPosition(size=calculated_size)
5. Gatherer executes orders to match target

### Available Trackers

See `qubx.trackers` and `qubx.trackers.riskctrl` modules for all available trackers:

```python
from qubx.trackers import (
    PositionsTracker,                    # Basic tracker (base class)
    PortfolioRebalancerTracker           # Portfolio rebalancing with tolerance
)
from qubx.trackers.riskctrl import (
    SignalRiskPositionTracker,           # Uses signal's stop/take
    StopTakePositionTracker,             # Fixed % stop/take
    AtrRiskTracker,                      # ATR-based stop/take
    MinAtrExitDistanceTracker,           # Min ATR distance before exit
    TrailingStopPositionTracker,         # Trailing stop (% based)
    SwingsStopLevels,                    # Trailing stop based on swing pivots
)
```

**Tracker Details:**

| Tracker | Description | Risk Control | Best For |
|---------|-------------|--------------|----------|
| `PositionsTracker` | Basic tracker, no stop/take | None | Simple strategies |
| `SignalRiskPositionTracker` | Uses signal's stop/take levels | Client or Broker | When signals include stop/take |
| `StopTakePositionTracker` | Fixed % stop/take from entry | Client or Broker | Fixed risk/reward ratio |
| `AtrRiskTracker` | Stop/take based on ATR multiples | Client or Broker | Volatility-adjusted risk |
| `MinAtrExitDistanceTracker` | Min ATR move before allowing exit | Client | Avoid premature exits |
| `TrailingStopPositionTracker` | Classical trailing stop (%) | Client or Broker | Trend following, lock profits |
| `SwingsStopLevels` | Trailing stop at pivot points | Client or Broker | Technical analysis, swing trading |
| `PortfolioRebalancerTracker` | Rebalances to target weights | N/A | Portfolio strategies |

**Risk Control Sides:**
- **Client-side** (`"client"`): Risk controlled by Qubx using market orders (may have slippage)
- **Broker-side** (`"broker"`): Risk controlled by broker using limit/stop orders (more accurate in backtest)

**Tracker Examples:**

```python
# 1. PositionsTracker - basic (no stop/take)
from qubx.trackers.sizers import FixedLeverageSizer
tracker = PositionsTracker(FixedLeverageSizer(1.0))

# 2. SignalRiskPositionTracker - uses signal's stop/take
from qubx.trackers.riskctrl import SignalRiskPositionTracker
tracker = SignalRiskPositionTracker(
    sizer=InverseVolatilitySizer(0.25),
    risk_controlling_side="broker"  # or "client"
)

# 3. StopTakePositionTracker - fixed % stop/take
from qubx.trackers.riskctrl import StopTakePositionTracker
tracker = StopTakePositionTracker(
    take_target=3.0,                 # Take profit at +3%
    stop_risk=1.0,                   # Stop loss at -1%
    sizer=FixedRiskSizer(2.0),       # 2% capital at risk
    risk_controlling_side="broker"
)

# 4. AtrRiskTracker - ATR-based stop/take
from qubx.trackers.riskctrl import AtrRiskTracker
tracker = AtrRiskTracker(
    take_target=2.0,                 # Take at entry + 2*ATR
    stop_risk=1.0,                   # Stop at entry - 1*ATR
    atr_timeframe="4h",
    atr_period=14,
    atr_smoother="sma",
    sizer=FixedRiskSizer(2.0),
    risk_controlling_side="broker"
)

# 5. TrailingStopPositionTracker - trailing stop
from qubx.trackers.riskctrl import TrailingStopPositionTracker
tracker = TrailingStopPositionTracker(
    trailing_stop_percentage=2.0,    # Trail 2% below high
    min_price_change_ticks=10,       # Min 10 ticks move to activate
    sizer=InverseVolatilitySizer(0.25),
    risk_controlling_side="client"   # Client-side for trailing
)

# 6. SwingsStopLevels - swing-based trailing stop
from qubx.trackers.riskctrl import SwingsStopLevels
tracker = SwingsStopLevels(
    timeframe="4h",                  # Timeframe for swing detection
    iaf=0.02,                        # Initial acceleration factor
    maxaf=0.2,                       # Max acceleration factor
    sizer=FixedLeverageSizer(1.0),
    risk_controlling_side="broker",
    activation_atr_threshold=1.0,    # Activate after 1 ATR move
    atr_timeframe="4h",
    atr_period=14
)

# 7. PortfolioRebalancerTracker - portfolio rebalancing
from qubx.trackers import PortfolioRebalancerTracker
tracker = PortfolioRebalancerTracker(
    capital_invested=100000,
    tolerance=10  # Rebalance if drift > 10%
)
```

**Choosing the Right Tracker:**

```python
# Simple strategy, no stop/take
→ PositionsTracker

# Signals include stop/take levels
→ SignalRiskPositionTracker

# Fixed risk/reward (e.g., 1% stop, 3% take)
→ StopTakePositionTracker

# Volatility-adjusted stop/take
→ AtrRiskTracker

# Trend following with trailing stop
→ TrailingStopPositionTracker or SwingsStopLevels

# Portfolio strategy with weights
→ PortfolioRebalancerTracker

# Avoid premature exits in volatile markets
→ MinAtrExitDistanceTracker
```

### Available Sizers

See `qubx.trackers.sizers` module for position sizing implementations:

```python
from qubx.trackers.sizers import (
    FixedSizer,                           # Fixed size (simplest)
    FixedLeverageSizer,                   # Fixed leverage
    FixedRiskSizer,                       # Fixed risk % per trade
    FixedRiskSizerWithConstantCapital,    # Fixed risk with constant capital
    InverseVolatilitySizer,               # Volatility-adjusted sizing
    LongShortRatioPortfolioSizer,         # Weighted portfolio with L/S ratio
)
```

**Sizer Details:**

| Sizer | Description | Best For | Parameters |
|-------|-------------|----------|------------|
| `FixedSizer` | Simplest fixed size for all signals | Quick backtesting, equal positions | `fixed_size`, `amount_in_quote` |
| `FixedLeverageSizer` | Fixed leverage per signal unit | Simple strategies, leverage control | `leverage`, `split_by_symbols` |
| `FixedRiskSizer` | Fixed % of capital at risk per trade | Risk management, requires stop | `max_cap_in_risk`, `reinvest_profit` |
| `FixedRiskSizerWithConstantCapital` | Fixed risk with constant capital (no reinvest) | Conservative sizing | `capital`, `max_cap_in_risk` |
| `InverseVolatilitySizer` | Risk-adjusted sizing based on ATR | Volatility scaling, adaptive sizing | `target_risk`, `atr_timeframe`, `atr_period` |
| `LongShortRatioPortfolioSizer` | Weighted portfolio with L/S ratio | Portfolio strategies, market-neutral | `capital_using`, `longs_to_shorts_ratio` |

**Sizer Examples:**

```python
# 1. FixedSizer - simplest
sizer = FixedSizer(
    fixed_size=10000,          # $10,000 per position
    amount_in_quote=True       # Amount in quote currency (USDT)
)

# 2. FixedLeverageSizer - simple leverage control
sizer = FixedLeverageSizer(
    leverage=1.0,              # 1x leverage
    split_by_symbols=True      # Divide by universe size
)

# 3. FixedRiskSizer - risk % per trade
sizer = FixedRiskSizer(
    max_cap_in_risk=2.0,       # Max 2% capital at risk
    reinvest_profit=True,      # Reinvest profits
    divide_by_symbols=True,    # Divide by universe size
    scale_by_signal=False      # Don't scale by signal value
)

# 4. InverseVolatilitySizer - volatility-adjusted
sizer = InverseVolatilitySizer(
    target_risk=0.25,          # Target 25% annual volatility
    atr_timeframe="4h",        # ATR timeframe
    atr_period=40,             # ATR period
    atr_smoother="sma"         # ATR smoother
)

# 5. LongShortRatioPortfolioSizer - portfolio weighting
sizer = LongShortRatioPortfolioSizer(
    capital_using=0.95,        # Use 95% of capital
    longs_to_shorts_ratio=1.0  # Equal long/short (market-neutral)
)

class RiskManagedStrategy(IStrategy):
    leverage: float = 1.0
    target_risk: float = 0.25
    max_cap_in_risk: float = 2.0

    def tracker(self, ctx: IStrategyContext):
        # Option 1: Fixed leverage (simple)
        return PositionsTracker(FixedLeverageSizer(self.leverage))

        # Option 2: Fixed risk per trade
        # return PositionsTracker(FixedRiskSizer(self.max_cap_in_risk))

        # Option 3: Inverse volatility (risk-adjusted)
        # return PositionsTracker(
        #     InverseVolatilitySizer(
        #         self.target_risk,
        #         atr_timeframe="1h",
        #         atr_period=24
        #     )
        # )

        # Option 4: Signal-based risk tracking (for strategies with take/stop)
        # return SignalRiskPositionTracker(
        #     InverseVolatilitySizer(self.target_risk, "1h", 24)
        # )

        # Option 5: Stop/take with fixed risk
        # return StopTakePositionTracker(
        #     FixedRiskSizer(self.max_cap_in_risk)
        # )

        # Option 6: Portfolio rebalancer (for weight-based strategies)
        # return PortfolioRebalancerTracker(
        #     capital_invested=100000,
        #     tolerance=10  # rebalance if position drift > 10%
        # )
```

### Gatherers: Order Execution

**Gatherers** execute actual orders to match target positions (see `qubx.gathering`):

```python
from qubx.gathering import IPositionGathering
```

**Gatherer behavior:**
- Receives `TargetPosition` from tracker/sizer
- Compares target vs current position
- **If same target**: Does nothing (no orders)
- **If different target**: Executes orders to match target
- Can use market orders, limit orders, etc. (implementation-specific)

**Example flow:**
```python
# Current position: 0
# Signal: side=1 → Target: 100 shares → Gatherer: Buy 100

# Current position: 100
# Signal: side=1 → Target: 100 shares → Gatherer: Do nothing (already at target)

# Current position: 100
# Signal: side=1 → Target: 98 shares (price changed) → Gatherer: Sell 2

# Current position: 98
# Signal: side=-1 → Target: -100 shares → Gatherer: Sell 198 (close 98 + open -100)

# Current position: -100
# Signal: side=0 → Target: 0 shares → Gatherer: Buy 100 (close short)
```

### Signal Types

```python
# - simple directional signal
signal = instrument.signal(ctx, side=1)  # long
signal = instrument.signal(ctx, side=-1)  # short
signal = instrument.signal(ctx, side=0)  # close/flat

# - signal with take profit and stop loss
signal = instrument.signal(
    ctx,
    side=1,
    take=110.0,   # take profit at 110
    stop=95.0,    # stop loss at 95
    comment="Long with risk management"
)

# - weighted signal (for portfolio strategies)
signal = instrument.signal(ctx, signal=0.25)  # 25% weight
```

## Configuration-Driven Design

All strategy parameters should be class attributes (configurable via YAML):

```python
class MyStrategy(IStrategy):
    # - time parameters
    timeframe: str = "4h"
    rebalance_frequency: str = "1d"

    # - risk parameters
    leverage: float = 1.0
    max_position_size: float = 10000

    # - strategy parameters
    sma_period: int = 20
    rsi_period: int = 14
    threshold: float = 0.5

    # - universe parameters
    universe_size: int = 50
    min_volume: float = 1000000
```

Corresponding YAML configuration:

```yaml
strategy: xincubator.models.mymodel.MyStrategy

parameters:
  timeframe: "1h"
  leverage: 2.0
  sma_period: 50
  universe_size: 30
```

## State Management

### Internal State

```python
class StatefulStrategy(IStrategy):
    def on_start(self, ctx: IStrategyContext):
        # - store state in instance variables
        self._positions_state = {}
        self._indicators = {}
        self._last_rebalance = None

        # - per-instrument state
        self._state = {
            instrument: {
                'trend': 0,
                'last_signal_time': None,
                'signal_count': 0
            }
            for instrument in ctx.instruments
        }
```

### Live Trading State Sync

```python
from qubx.core.interfaces import StateResolver

def on_init(self, initializer: IStrategyInitializer):
    # - enable state synchronization for live trading
    if not initializer.is_simulation:
        initializer.set_state_resolver(StateResolver.SYNC_STATE)
        initializer.set_warmup("2d")  # warm up with historical data
```

## Real-World Strategy Examples

### Example 1: Trend Following with SuperTrend

```python
from qubx.pandaz.ta import super_trend
from qubx.trackers.riskctrl import SignalRiskPositionTracker
from qubx.trackers.sizers import InverseVolatilitySizer

class TrendFollowingStrategy(IStrategy):
    timeframe: str = "15Min"
    atr_period: int = 24
    atr_multiplier: float = 3.0
    stop_loss_pct: float = 1.0
    take_profit_pct: float = 2.0
    target_risk: float = 0.2

    def on_init(self, initializer: IStrategyInitializer):
        initializer.set_base_subscription(DataType.OHLC[self.timeframe])

    def on_start(self, ctx: IStrategyContext):
        # - track trend state per instrument
        self._trends = {i: 0 for i in ctx.instruments}

    def on_event(self, ctx: IStrategyContext, event: TriggerEvent) -> list[Signal]:
        signals = []

        for instrument in ctx.instruments:
            # - get OHLC data
            ohlc = ctx.ohlc_pd(instrument, length=5 * self.atr_period)
            if len(ohlc) < self.atr_period:
                continue

            # - calculate SuperTrend
            st = super_trend(
                ohlc,
                length=self.atr_period,
                mult=self.atr_multiplier,
                src="hl2",
                atr_smoother="sma"
            )

            # - check trend change
            current_trend = st["trend"].iloc[-1]
            prev_trend = self._trends[instrument]

            if current_trend == prev_trend:
                continue

            # - get current price
            price = ctx.quote(instrument).mid_price()

            # - long signal
            if current_trend == 1:
                signal = instrument.signal(
                    ctx,
                    side=1,
                    take=price * (1 + self.take_profit_pct / 100),
                    stop=price * (1 - self.stop_loss_pct / 100),
                    comment="Trend up"
                )
                signals.append(signal)

            # - short signal
            elif current_trend == -1:
                signal = instrument.signal(
                    ctx,
                    side=-1,
                    take=price * (1 - self.take_profit_pct / 100),
                    stop=price * (1 + self.stop_loss_pct / 100),
                    comment="Trend down"
                )
                signals.append(signal)

            self._trends[instrument] = current_trend

        return signals

    def tracker(self, ctx: IStrategyContext):
        return SignalRiskPositionTracker(
            InverseVolatilitySizer(self.target_risk, self.timeframe, self.atr_period)
        )
```

### Example 2: Pairs Trading Strategy

```python
from qubx.ta.indicators import sma
from qubx.trackers.sizers import InverseVolatilitySizer

class PairsTradingStrategy(IStrategy):
    timeframe: str = "1h"
    index_symbol: str = "BTCUSDT"
    period: int = 24
    threshold: float = 0.25
    target_risk: float = 0.25

    def on_init(self, initializer: IStrategyInitializer):
        initializer.set_base_subscription(DataType.OHLC[self.timeframe])
        initializer.set_fit_schedule("M @ 23:59")  # monthly refit

    def on_start(self, ctx: IStrategyContext):
        # - get index instrument
        self._index = ctx.query_instrument(self.index_symbol, ctx.exchanges[0])

        # - create pair state for each instrument
        self._pairs = {}
        for instrument in ctx.instruments:
            if instrument != self._index:
                self._pairs[instrument] = {'side': 0}

    def on_event(self, ctx: IStrategyContext, event: TriggerEvent) -> list[Signal]:
        signals = []

        # - get index momentum
        index_ohlc = ctx.ohlc(self._index, self.timeframe, self.period * 7)
        if len(index_ohlc) < self.period * 7:
            return signals

        index_momentum = self._calculate_momentum(ctx, self._index)

        for instrument in ctx.instruments:
            if instrument == self._index:
                continue

            # - calculate relative momentum
            instr_momentum = self._calculate_momentum(ctx, instrument)
            if instr_momentum is None:
                continue

            rel_momentum = instr_momentum - index_momentum
            pair_state = self._pairs[instrument]

            # - exit conditions
            if (pair_state['side'] == 1 and rel_momentum <= 0) or \
               (pair_state['side'] == -1 and rel_momentum >= 0):
                signals.append(instrument.signal(ctx, 0, comment="Exit"))
                pair_state['side'] = 0
                continue

            # - entry conditions
            if rel_momentum > self.threshold:
                signals.append(instrument.signal(ctx, 1, comment="Long"))
                pair_state['side'] = 1

            elif rel_momentum < -self.threshold:
                signals.append(instrument.signal(ctx, -1, comment="Short"))
                pair_state['side'] = -1

        return signals

    def _calculate_momentum(self, ctx: IStrategyContext, instrument: Instrument) -> float | None:
        ohlc = ctx.ohlc(instrument, self.timeframe, self.period * 7)
        if len(ohlc) < self.period * 7:
            return None
        # - implement custom momentum calculation
        # (simplified for example)
        return ohlc.close[0] / ohlc.close[self.period] - 1.0

    def tracker(self, ctx: IStrategyContext):
        return PositionsTracker(
            InverseVolatilitySizer(self.target_risk, self.timeframe, self.period)
        )
```

### Example 3: Portfolio Rebalancing Strategy

```python
from quantkit.pacman.pickers import TopCapitalizedAssetsPicker
from qubx.trackers import PortfolioRebalancerTracker

class PortfolioStrategy(IStrategy):
    timeframe: str = "1d"
    refit_period: str = "M @ 23:59"  # monthly
    trigger_at: str = "1d @ 23:59"   # daily
    top_percentile: float = 75
    lookback: int = 90
    portfolio_percentile: float = 0.1
    capital_invested: float = 100000
    tolerance: float = 10  # 10% drift tolerance

    def on_init(self, initializer: IStrategyInitializer):
        initializer.set_base_subscription(DataType.OHLC[self.timeframe])
        initializer.set_fit_schedule(self.refit_period)
        initializer.set_event_schedule(self.trigger_at)

    def on_start(self, ctx: IStrategyContext):
        # - initialize universe picker
        self._picker = TopCapitalizedAssetsPicker(
            self.top_percentile,
            excluded_instruments=["USDCUSDT", "TUSDUSDT"]
        )

        # - state
        self._weights = {}

    def on_fit(self, ctx: IStrategyContext):
        # - update universe
        instruments = self._picker.pick(ctx, ctx.exchanges[0])
        ctx.set_universe(instruments, if_has_position_then="close")

    def on_event(self, ctx: IStrategyContext, event: TriggerEvent) -> list[Signal]:
        signals = []

        # - calculate portfolio weights (simplified)
        total_inv_vol = 0
        weights = {}

        for instrument in ctx.instruments:
            ohlc = ctx.ohlc_pd(instrument, self.timeframe, self.lookback)
            if len(ohlc) < self.lookback:
                continue

            # - inverse volatility weighting
            returns = ohlc['close'].pct_change()
            vol = returns.std() * np.sqrt(252)

            if vol > 0:
                weights[instrument] = 1.0 / vol
                total_inv_vol += weights[instrument]

        # - normalize weights
        for instrument in weights:
            weights[instrument] /= total_inv_vol

        # - generate signals with weights
        for instrument, weight in weights.items():
            if weight > 0.01:  # minimum threshold
                signal = instrument.signal(
                    ctx,
                    signal=weight,
                    comment=f"Weight: {weight:.3f}"
                )
                signals.append(signal)

        return signals

    def tracker(self, ctx: IStrategyContext):
        return PortfolioRebalancerTracker(
            self.capital_invested,
            self.tolerance
        )
```

## Best Practices

### 1. Parameter Configuration
- All parameters as class attributes
- Use descriptive names
- Set sensible defaults
- Document parameter purpose and range

### 2. Performance
- Prefer streaming indicators over pandas
- Cache expensive calculations
- Minimize data fetches in hot paths
- Use appropriate data types

### 3. State Management
- Initialize state in `on_start`
- Clean up in `on_universe_change`
- Use dictionaries for per-instrument state
- Enable state sync for live trading

### 4. Universe Management
- Refit universe periodically via `on_fit`
- Use `if_has_position_then` to handle existing positions
- Clean up removed instruments in `on_universe_change`
- Log universe changes for debugging

### 5. Signal Generation
- Return empty list if no signals
- Add descriptive comments to signals
- Use take/stop parameters for risk management
- Consider position state before signaling

### 6. Error Handling
- Check data availability before processing
- Handle insufficient data gracefully
- Log warnings for abnormal conditions
- Fail gracefully, don't crash

### 7. Logging
```python
from qubx import logger

# - use appropriate log levels
logger.debug("Detailed calculation step")
logger.info("Important state change")
logger.warning("Unusual condition detected")
logger.error("Critical error occurred")

# - use colored tags for visibility
logger.info(f"Universe: <g>{len(instruments)}</g> instruments")
logger.warning(f"Low volume: <r>{symbol}</r>")
```

## Common Patterns

### Pattern 1: Indicator-Based Strategy
```python
class IndicatorStrategy(IStrategy):
    def on_start(self, ctx):
        self._indicators = {i: self._init_indicators(ctx, i) for i in ctx.instruments}

    def on_event(self, ctx, event):
        return [self._check_instrument(ctx, i) for i in ctx.instruments]
```

### Pattern 2: State Machine Strategy
```python
class StateMachineStrategy(IStrategy):
    def on_start(self, ctx):
        self._state = {i: 'idle' for i in ctx.instruments}

    def on_event(self, ctx, event):
        signals = []
        for i in ctx.instruments:
            new_state, signal = self._process_state(ctx, i, self._state[i])
            self._state[i] = new_state
            if signal:
                signals.append(signal)
        return signals
```

### Pattern 3: Periodic Rebalancing
```python
class RebalancingStrategy(IStrategy):
    def on_init(self, initializer):
        initializer.set_fit_schedule("M @ 23:59")
        initializer.set_event_schedule("1d @ 23:59")

    def on_fit(self, ctx):
        self._update_universe(ctx)

    def on_event(self, ctx, event):
        return self._rebalance_portfolio(ctx)
```

## Running Simulations

### Quick Testing with simulate()

**The `simulate()` function is primarily for fast smoke tests and debugging**, not for production backtesting. Use YAML configs with `qubx.cli.commands` for production backtests.

**Basic usage:**
```python
from qubx.backtester.simulator import simulate

r = simulate(
    strategy_instance,
    data={"ohlc(1h)": reader},
    capital=100000,
    instruments=["BINANCE.UM:BTCUSDT"],
    start="2024-01-01",
    stop="2024-12-31",
    commissions="vip0_usdt",
    debug="INFO"
)

# Get result
session = r[0] if isinstance(r, list) else r
```

### Running Multiple Strategies in Parallel

**You can test multiple strategy instances simultaneously** by passing a dictionary:

```python
from xincubator.models.gemini.g0 import GeminiModel0

# Run multiple strategy configurations in parallel
r = simulate(
    {
        "G0_BTC_kama": GeminiModel0(timeframe="1h", index="BTCUSDT", v_smoother="kama"),
        "G0_BTC_sma": GeminiModel0(timeframe="1h", index="BTCUSDT", v_smoother="sma"),
        "G0_ETH_kama": GeminiModel0(timeframe="1h", index="ETHUSDT", v_smoother="kama"),
    },
    data={"ohlc(1h)": reader},
    capital=10000,
    instruments=[f"BINANCE.UM:{s}" for s in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]],
    start="2024-01-01",
    stop="2024-12-31",
    commissions="vip0_usdt",
    n_jobs=-1,  # Use all CPU cores for parallel execution
    debug="INFO",
    enable_inmemory_emitter=True
)

# Results is a list indexed by strategy names (alphabetically sorted)
# r[0] = result for "G0_BTC_kama"
# r[1] = result for "G0_BTC_sma"
# r[2] = result for "G0_ETH_kama"

# Access individual results
for i, session in enumerate(r):
    print(f"Strategy: {session.strategy_class}")
    print(f"Period: {session.start} to {session.stop}")
```

### Accessing Performance Metrics

Each simulation result is a `TradingSessionResult` instance with a `.performance()` method:

```python
# Get main performance metrics
session = r[0]
metrics = session.performance()

# Example output:
# {
#     'sharpe': -0.1277335219040116,
#     'cagr': -1.2380933309437903,        # -123.8% annual return (as decimal)
#     'daily_turnover': 1.9638378466063464,
#     'qr': 0.0332537855176549,            # Quality ratio
#     'mdd_pct': 6.4958005284820315,       # Max drawdown %
#     'mdd_start': '2022-06-15T21:35:00',  # Drawdown start
#     'mdd_peak': '2022-11-09T23:35:00',   # Drawdown peak
#     'mdd_recover': '2022-12-01T00:55:00',# Drawdown recovery
#     'sortino': -0.1896064436768856,
#     'calmar': -22.699351879372927,
#     'avg_return': -0.0026310362079233264,
#     'gain': -124.14642244500283,         # Absolute capital gain/loss
#     'mdd_usd': 672.8902172800026,        # Max drawdown in USD
#     'fees': 71.044572445,                # Total fees paid
#     'execs': 137                         # Number of executions
# }

# Print key metrics
print(f"Sharpe Ratio: {metrics['sharpe']:.2f}")
print(f"CAGR: {metrics['cagr']*100:.2f}%")  # Convert to percentage
print(f"Gain: ${metrics['gain']:.2f}")      # Absolute P&L
print(f"Max Drawdown: {metrics['mdd_pct']:.2f}%")
print(f"Max Drawdown USD: ${metrics['mdd_usd']:.2f}")
print(f"Sortino: {metrics['sortino']:.2f}")
print(f"Calmar: {metrics['calmar']:.2f}")
print(f"Total Fees: ${metrics['fees']:.2f}")
print(f"Executions: {metrics['execs']}")
```

**Available metrics from .performance():**
- `sharpe`: Sharpe ratio
- `sortino`: Sortino ratio
- `calmar`: Calmar ratio
- `cagr`: Compound Annual Growth Rate (as decimal, -1.2 = -120%)
- `gain`: Absolute capital gain/loss in USD
- `avg_return`: Average return per period
- `mdd_pct`: Maximum drawdown percentage
- `mdd_usd`: Maximum drawdown in USD
- `mdd_start`: Drawdown start timestamp
- `mdd_peak`: Drawdown peak timestamp
- `mdd_recover`: Drawdown recovery timestamp
- `daily_turnover`: Daily turnover ratio
- `qr`: Quality ratio
- `fees`: Total fees paid
- `execs`: Number of executions/trades

**Compare multiple strategies:**
```python
import pandas as pd

# Compare performance across strategies
comparison = []
for session in r:
    metrics = session.performance()
    comparison.append({
        'strategy': session.strategy_class,
        'sharpe': metrics['sharpe'],
        'cagr_%': metrics['cagr'] * 100,      # Convert to %
        'gain': metrics['gain'],
        'mdd_%': metrics['mdd_pct'],
        'fees': metrics['fees'],
        'execs': metrics['execs']
    })

comparison_df = pd.DataFrame(comparison)
print(comparison_df.sort_values('sharpe', ascending=False))
```

### Production Backtesting

**For production backtests, always use YAML configs:**

```bash
# Run backtest with standardized output path
poetry run python -m qubx.cli.commands simulate \
    'configs/mymodel/config.yaml' \
    -o /backtests/configs/mymodel/config/
```

This ensures:
- Reproducible results
- Proper output organization
- Compatibility with analysis tools
- Configuration versioning

## Debugging Tips

### 1. Enable DEBUG Logging
```python
# In simulation - always use n_jobs=1 for debugging
r = simulate(strategy, debug="DEBUG", n_jobs=1)
```

### 2. Use Emitter for Internal State Tracking

**The emitter is a powerful debugging tool** that allows you to track internal strategy states, indicator values, and custom metrics during simulation.

**Enable in-memory emitter:**
```python
r = simulate(
    strategy,
    enable_inmemory_emitter=True,  # Enable emitter data collection
    debug="DEBUG",
    n_jobs=1,
    # ... other parameters
)

# Access emitted data after simulation
session = r[0] if isinstance(r, list) else r
emitter_data = session.emitter_data  # Returns pandas DataFrame
```

**Emit data in your strategy:**
```python
class MyStrategy(IStrategy):
    def on_event(self, ctx: IStrategyContext, event: TriggerEvent):
        for instrument in ctx.instruments:
            # - emit indicator values
            ctx.emitter.emit("sma_value", sma_value, instrument=instrument)
            ctx.emitter.emit("rsi_value", rsi_value, instrument=instrument)

            # - emit internal state
            ctx.emitter.emit("trend_state", self._trends[instrument], instrument=instrument)
            ctx.emitter.emit("signal_strength", signal_strength, instrument=instrument)

            # - emit custom metrics with tags for filtering
            ctx.emitter.emit(
                "probability",
                model_probability,
                instrument=instrument,
                tags={"type": "prediction", "model": "ml_classifier"}
            )

            ctx.emitter.emit(
                "feature_value",
                feature_value,
                instrument=instrument,
                tags={"type": "feature", "feature_name": "momentum"}
            )

            # - emit position score with category tag
            ctx.emitter.emit(
                "position_score",
                score,
                instrument=instrument,
                tags={"category": "scoring"}
            )
```

**Analyze emitted data:**
```python
# Get emitter data
emitter_data = session.emitter_data

# Inspect structure
print(emitter_data.columns)  # Shows: metric, value, instrument, timestamp, and tag columns
print(emitter_data.head())

# Filter by metric name
sma_data = emitter_data[emitter_data['metric'] == 'sma_value']

# Filter by tags - very powerful for categorizing data
predictions = emitter_data[emitter_data['type'] == 'prediction']
ml_predictions = emitter_data[
    (emitter_data['type'] == 'prediction') &
    (emitter_data['model'] == 'ml_classifier')
]

# Filter features by name
momentum_features = emitter_data[
    (emitter_data['type'] == 'feature') &
    (emitter_data['feature_name'] == 'momentum')
]

# Combine filters: get predictions for specific instrument
btc_predictions = emitter_data[
    (emitter_data['type'] == 'prediction') &
    (emitter_data['instrument'] == 'BTCUSDT')
]

# Plot indicator over time
import matplotlib.pyplot as plt
for symbol in sma_data['instrument'].unique():
    symbol_data = sma_data[sma_data['instrument'] == symbol]
    plt.plot(symbol_data.index, symbol_data['value'], label=symbol)
plt.legend()
plt.title('SMA Values by Instrument')
plt.show()

# Compare predictions vs actual returns
btc_pred = predictions[predictions['instrument'] == 'BTCUSDT']
btc_returns = session.portfolio_log['BTCUSDT_Close'].pct_change()

# Analyze prediction accuracy
import pandas as pd
analysis = pd.DataFrame({
    'prediction': btc_pred['value'].values,
    'actual_return': btc_returns.iloc[1:len(btc_pred)+1].values
})
correlation = analysis['prediction'].corr(analysis['actual_return'])
print(f"Prediction correlation: {correlation:.3f}")
```

**Common use cases:**
- Track indicator values over time
- Monitor internal state transitions
- Debug signal generation logic
- Verify calculations
- Analyze strategy behavior
- Compare multiple metrics
- **Use tags to organize data**: Categorize emissions by type (predictions, features, signals, scores)
- **Filter by tags**: Easily extract specific data categories for analysis
- **ML model debugging**: Track predictions, features, and model outputs separately
- **Multi-model strategies**: Tag emissions by model name for comparison

### 3. Log State Changes
```python
logger.info(f"State change: {old_state} -> {new_state}")
logger.info(f"<g>Long signal</g> at {price:.2f} for {instrument.symbol}")
logger.warning(f"<r>Insufficient data</r>: {len(ohlc)} < {required_length}")
```

### 4. Check Data Availability
```python
ohlc = ctx.ohlc_pd(instrument, length=100)
if len(ohlc) < required_length:
    logger.warning(f"Insufficient data: {len(ohlc)} < {required_length}")
    return

# Verify data quality
if ohlc['close'].isna().any():
    logger.error(f"NaN values in OHLC data for {instrument.symbol}")
```

### 5. Validate Signals
```python
signals = [s for s in signals if s is not None]
logger.info(f"Generated {len(signals)} signals")

# Count by side
long_signals = sum(1 for s in signals if s.side > 0)
short_signals = sum(1 for s in signals if s.side < 0)
logger.info(f"Signals - Long: {long_signals}, Short: {short_signals}")
```

## Additional Resources

- Qubx Framework Documentation: `~/devs/Qubx/`
- QuantKit Extensions: `~/devs/quantkit/`
- Indicator Implementation Guide: `~/devs/Qubx/.claude/skills/implementing_streaming_indicators.md`
- Strategy Debugging Guide: See `strategy-debugging-guide.md`
- YAML Configuration Guide: See `yaml-config-guide.md`
