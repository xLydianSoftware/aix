# Qubx YAML Configuration Guide
#tutorial

## Overview

This guide explains how to write YAML configuration files for Qubx strategies. These configs work for **both simulations (backtests) and live/paper trading** - use the same config file for consistency.

**CRITICAL**: Before writing any config, you must thoroughly read and understand existing configs in your target domain to follow established patterns and conventions.

## Essential Principles

1. **Unified Configuration**: Same YAML file for simulation, paper, and live trading
2. **Required Metadata**: Every config MUST have `name` and `description` fields
3. **File Organization**: Place configs at `configs/strategy_name/config_name.yaml`
4. **Naming Convention**: Use descriptive names like `strategy.modification.parameters.yaml`
   - Example: `nimble.advrisk.48h.yaml` (nimble strategy with advanced risk, 48h lookback)
   - Example: `gemini.v0.kama.yaml` (gemini v0 with kama smoother)
5. **Config Versioning**: Create new config file if changes are significant (don't overwrite)

## Essential Structure

All strategy configs follow the Qubx `StrategyConfig` model. The core required sections:

```yaml
name: "config_identifier"          # REQUIRED
description: "Purpose and changes" # REQUIRED
strategy: your.strategy.class.here # REQUIRED
parameters: {}                     # REQUIRED
simulation: {}                     # REQUIRED for backtests
live: {}                          # REQUIRED for live/paper trading
```

## Core Sections

### 1. Strategy Definition
```yaml
# Single strategy
strategy: xincubator.models.portfolio.funding.strategies.FundingRateMarketAdaptiveLS

# Multiple strategies (composable pattern)
strategy: 
  - xincubator.models.nimble.composit.nimble.NimbleBasicGenerator
  - xincubator.models.nimble.composit.risks.LongShortRiskControl
  - xincubator.models.nimble.composit.risks.PositionSizingSelector
```

### 2. Metadata (REQUIRED)
```yaml
# REQUIRED: Short identifier for this config (no spaces)
name: "lighter.nimble"
name: "kfs.statarb.live.v01"
name: "GeminiV0.solana.ecosystem"

# REQUIRED: Describe purpose of this backtest/config and main changes
# IMPORTANT: Use YAML list format (with -), NOT a single string or | block
description:
    - What this config tests or deploys
    - Key strategy features and modifications
    - Important parameters and their values
    - Expected behavior or performance characteristics

# Example from real config:
description:
    - Basic GeminiModel0 strategy, longs only on fixed set of coins with SOL as index
    - Fast 1h timeframe
    - No shorts allowed

# Another example:
description:
    - Basic Nimble(4h, normal) strategy, Long reenter is True and Short reenter is True
    - Composite ATR(20) tracker with Long(None,4.0) and Short(4.0,4.0). Max stop loss None pct
    - Risk is 4.0% per trade. 'FixedRiskSizer' position sizer.
    - Dynamic universe based on top 20 from 50% of most capitalized instruments
```

**Description Format Rules:**
- ALWAYS use YAML list format with `-` (dash) prefix
- Each bullet point = one distinct aspect of the config
- Keep each item as a clear, complete sentence
- Cover: strategy type, key parameters, risk settings, universe selection

### 3. Parameters Section
```yaml
parameters:
  # Strategy-specific parameters
  # ALWAYS check strategy source code for required parameters
  timeframe: "4h"
  leverage: 1.0
  universe_size: 50
```

### 4. Simulation Section (Required for backtesting)

Based on `SimulationConfig` model, here are the exact available fields:

```yaml
simulation:
  # REQUIRED fields
  capital: 100000.0                     # Starting capital (float)
  instruments: ["BINANCE.UM:BTCUSDT"]   # List of instruments (list[str])
  start: "2024-01-01"                   # Start date YYYY-MM-DD (str)
  stop: "2024-12-31"                    # End date YYYY-MM-DD (str)
  
  # OPTIONAL fields with exact types
  commissions: "vip0_usdt"              # Predefined fee structure (str) - see available options below
  debug: "ERROR"                        # Logging level: ERROR, INFO, DEBUG (str | None)
  n_jobs: 10                            # Parallel jobs for variate runs (int | None)
  run_separate_instruments: false       # Run each instrument separately (bool)
  enable_funding: true                  # Enable funding rate calculations (bool)
  enable_inmemory_emitter: true         # Enable in-memory metrics collection (bool)
  
  # Data configuration (list[TypedReaderConfig])
  data:
    - data_type: [ohlc(1d), funding_payment]
      readers:
        - reader: mqdb
          args:
            host: quantlab
            timeframe: 1d
  
  # Prefetch configuration (PrefetchConfig | None)
  prefetch:
    enabled: true
    aux_data_names:
      - candles
      - funding_payment
      - fundamental_data
  
  # Variate configuration - ONLY for strategy parameters (dict)
  variate:
    funding_lookback_days: [1, 2, 3, 5, 7]         # Direct parameter names
    enforce_funding_sign: [true, false]             # Multiple parameter values
```

### 5. Auxiliary Data (Optional)
```yaml
aux:
  reader: mqdb
  args:
    host: quantlab
```

## Variate Configuration (Parameter Variations)

**IMPORTANT**: You can ONLY variate strategy parameters, not simulation config fields like capital or instruments.

```yaml
simulation:
  variate:
    # Correct - direct parameter names from the parameters section
    funding_lookback_days: [1, 2, 3, 5, 7]
    enforce_funding_sign: [true, false]
    leverage: [1.0, 2.0, 3.0]
    momentum_threshold: [0.0, 0.1, 0.2]
    
    # WRONG - you CANNOT variate simulation config fields
    # capital: [100000, 200000]        # ❌ NOT ALLOWED
    # instruments: [...]               # ❌ NOT ALLOWED
  
  # Set n_jobs to handle all combinations
  n_jobs: 10  # For 5 * 2 = 10 combinations
```

## Commission Configuration

**ONLY predefined fee structures are allowed** (from `~/devs/Qubx/src/qubx/resources/crypto-fees.ini`):

### Binance UM Futures (most common)
```yaml
simulation:
  commissions: "vip0_usdt"  # 0.02% maker, 0.05% taker
  # Other options: vip1_usdt, vip2_usdt, ..., vip9_usdt
```

### Other Available Exchanges
```yaml
# Binance Spot
commissions: "vip0_usdt"    # Spot USDT
commissions: "vip0_bnb"     # Spot BNB

# Binance CM Futures  
commissions: "vip0"         # Coin-margined futures

# BitMEX
commissions: "tierb_xbt"    # Basic tier XBT
commissions: "tierb_usdt"   # Basic tier USDT

# Kraken
commissions: "K0"           # Kraken spot
commissions: "K0"           # Kraken futures (.f)
```

**You CANNOT specify custom commission dictionaries** - only these predefined strings.

## Data Configuration

### Standard OHLC Data
```yaml
data:
  - data_type: [ohlc(4h)]
    readers:
      - reader: mqdb
        args:
          host: quantlab  # or nebula
```

### Multiple Data Types
```yaml
data:
  - data_type: [ohlc(1d), funding_payment]
    readers:
      - reader: mqdb
        args:
          host: quantlab
          timeframe: 1d
```

### Common Data Types
- `ohlc(1h)`, `ohlc(4h)`, `ohlc(1d)` - OHLC bars
- `funding_payment` - Funding rate data
- `trades` - Trade data
- `orderbook` - Order book data

## Prefetch Configuration

```yaml
prefetch:
  enabled: true
  prefetch_period: "1w"           # How much data to prefetch
  cache_size_mb: 1000             # Cache size in MB
  aux_data_names:                 # Additional data to prefetch
    - candles(1h)
    - funding_payment
    - fundamental_data
  args: {}                        # Additional args
```

## Live/Paper Trading Configuration

**CRITICAL**: Use the same config file for simulation and live trading. Add `live` section for production deployment.

### Complete Live Section Structure

```yaml
live:
  # Exchange connectivity
  exchanges:
    BINANCE.UM:
      connector: ccxt            # Connector type: ccxt, xlighter, etc.
      universe:                  # Symbols to trade (no exchange prefix)
        - BTCUSDT
        - ETHUSDT
        - SOLUSDT

    LIGHTER:
      connector: xlighter        # Custom connector
      universe:
        - BTCUSDC

  # Logging configuration
  logging:
    logger: CsvFileLogsWriter    # Log writer type
    position_interval: 5Min      # Position log frequency
    portfolio_interval: 5Min     # Portfolio log frequency
    heartbeat_interval: 10m      # Heartbeat frequency

  # Metrics emission (optional)
  emission:
    stats_interval: 1m           # How often to emit stats
    emitters:
      - emitter: QuestDBMetricEmitter
        parameters:
          host: quantlab
          port: 9000
        tags:
          environment: env:ENVIRONMENT  # Use env variable

  # Notifications (optional)
  notifiers:
    - notifier: SlackNotifier
      parameters:
        bot_token: env:SLACK_BOT_TOKEN       # From environment
        environment: env:ENVIRONMENT          # From environment
        default_channel: "#qubx-bots"
        message_channel: "#qubx-bots-audit"
        error_channel: "#qubx-bots-errors"

  # Data warmup (optional)
  warmup:
    readers:
      - data_type: ohlc(1h)
        readers:
          - reader: mqdb
            args:
              host: quantlab
              timeframe: 1h
          - reader: ccxt           # Fallback to exchange if needed
            args:
              max_history: 2d
              exchanges:
                - BINANCE.UM

      - data_type: funding_payment
        readers:
          - reader: mqdb
            args:
              host: quantlab
              timeframe: 1h

  # Auxiliary data for live (optional)
  aux:
    - reader: xlighter
      args:
        max_history: 40d
    - reader: mqdb
      args:
        host: quantlab
```

### Environment Variables

Use `env:VARIABLE_NAME` syntax to reference environment variables:

```yaml
live:
  notifiers:
    - notifier: SlackNotifier
      parameters:
        bot_token: env:SLACK_BOT_TOKEN       # Reads from $SLACK_BOT_TOKEN
        environment: env:ENVIRONMENT          # Reads from $ENVIRONMENT
```

### Minimal Live Configuration

For simple deployments:

```yaml
live:
  exchanges:
    BINANCE.UM:
      connector: ccxt
      universe:
        - BTCUSDT
        - ETHUSDT

  logging:
    logger: CsvFileLogsWriter
    position_interval: 5Min
    portfolio_interval: 5Min
    heartbeat_interval: 10m
```

## Instrument Configuration

### YAML Anchors for Reusability
```yaml
# Define universe once
STATIC_UNIVERSE1: &static_universe1 
  [ 
    'BINANCE.UM:BTCUSDT', 'BINANCE.UM:ETHUSDT', 'BINANCE.UM:BNBUSDT'
  ]

parameters:
  universe_symbols: *static_universe1

simulation:
  instruments: *static_universe1
```

### Standard Instrument Format
- Always use: `EXCHANGE:SYMBOL`
- Primary exchange: `BINANCE.UM`
- Examples: `BINANCE.UM:BTCUSDT`, `BINANCE.UM:ETHUSDT`

## Complete Config Template (Simulation + Live)

```yaml
# REQUIRED: Config identifier
name: "strategy.modification.params"
# Examples: nimble.advrisk.48h, gemini.v0.kama, statarb.v01

# REQUIRED: Purpose and key changes
description: |
  - Purpose of this config (backtest, live deployment, parameter test)
  - Key strategy features and modifications
  - Important parameter values and their rationale
  - Expected behavior or changes from previous version

# REQUIRED: Strategy class path
strategy: your.strategy.module.StrategyClass
# Can be single class or list of composable strategies:
# strategy:
#   - your.strategy.generators.SignalGenerator
#   - your.strategy.risks.RiskControl
#   - quantkit.universe.basics.TopNUniverse

# REQUIRED: Strategy parameters - ALWAYS check strategy source code
parameters:
  # Time-based parameters
  timeframe: "4h"

  # Universe/selection parameters
  universe_size: 50

  # Risk management parameters
  leverage: 1.0
  max_risk_per_trade: 2.0

  # Strategy-specific parameters
  # CHECK STRATEGY SOURCE FOR REQUIRED PARAMETERS

# Optional: Auxiliary data
aux:
  reader: mqdb
  args:
    host: quantlab

# REQUIRED for backtesting: Simulation configuration
simulation:
  # Required fields
  capital: 100000.0
  instruments:
    - "BINANCE.UM:BTCUSDT"
    - "BINANCE.UM:ETHUSDT"
  start: "2024-01-01"
  stop: "2024-12-31"

  # Optional but commonly used
  commissions: "vip0_usdt"
  debug: "ERROR"
  enable_funding: true              # For funding strategies
  enable_inmemory_emitter: true     # For metrics collection
  portfolio_log_freq: 4h            # Portfolio logging frequency

  # Data configuration
  data:
    - data_type: [ohlc(4h)]
      readers:
        - reader: mqdb
          args:
            host: quantlab
            timeframe: 4h

  # Optional: Prefetch for faster access
  prefetch:
    enabled: true
    aux_data_names:
      - candles(4h)
      - funding_payment

  # Optional: Parameter variations (ONLY strategy parameters)
  # variate:
  #   leverage: [1.0, 2.0]
  #   timeframe: ["1h", "4h"]
  # n_jobs: 4  # For 2 * 2 = 4 combinations

# REQUIRED for live/paper: Live trading configuration
live:
  # Exchange connectivity
  exchanges:
    BINANCE.UM:
      connector: ccxt
      universe:
        - BTCUSDT
        - ETHUSDT

  # Logging
  logging:
    logger: CsvFileLogsWriter
    position_interval: 5Min
    portfolio_interval: 5Min
    heartbeat_interval: 10m

  # Optional: Metrics emission
  emission:
    stats_interval: 1m
    emitters:
      - emitter: QuestDBMetricEmitter
        parameters:
          host: quantlab
          port: 9000
        tags:
          environment: env:ENVIRONMENT

  # Optional: Notifications
  notifiers:
    - notifier: SlackNotifier
      parameters:
        bot_token: env:SLACK_BOT_TOKEN
        environment: env:ENVIRONMENT
        default_channel: "#qubx-bots"
        error_channel: "#qubx-bots-errors"

  # Optional: Warmup data
  warmup:
    readers:
      - data_type: ohlc(4h)
        readers:
          - reader: mqdb
            args:
              host: quantlab
              timeframe: 4h
```

## Best Practices

### 1. Config File Organization
```bash
# Standard location: configs/strategy_name/config_name.yaml
configs/nimble/nimble.advrisk.48h.yaml
configs/gemini/gemini.v0.kama.yaml
configs/statarb/kfs/statarb.v01.yaml

# For live configs, can use subdirectory:
configs/statarb/kfs/live_configs/statarb.v01.yaml
configs/nimble/deploy/lighter/nimble.v2.yaml
```

### 2. Config Naming Convention
**Format**: `strategy.modification.parameters.yaml`

**Examples**:
- `nimble.advrisk.48h.yaml` - Nimble with advanced risk, 48h lookback
- `gemini.v0.kama.yaml` - Gemini v0 using KAMA smoother
- `statarb.equalweight.v01.yaml` - StatArb equal weight version 01
- `funding.adaptive.short.yaml` - Funding strategy adaptive, shorts only

**Rules**:
- Use dots (.) to separate components
- Keep names short but descriptive
- Include version numbers (v0, v01, v2) when iterating
- If file exists with same name, create new file (don't overwrite)

### 3. Required Metadata
**ALWAYS** fill `name` and `description` fields:

```yaml
name: "nimble.advrisk.48h"

description: |
  - Testing advanced risk management modifications
  - Using 48h lookback for volatility calculation
  - Increased stop loss to 4% from 2%
  - Universe limited to top 20 by capitalization
```

### 4. Research Existing Configs First
```bash
# Examine configs in your domain
ls configs/portfolio/funding/
ls configs/nimble/
cat configs/nimble/nimble.v1.yaml  # Study similar configs
```

### 5. Verify Strategy Parameters
**CRITICAL**: Always check the strategy source code for required parameters:
```bash
# Find and read strategy source
find src/ -name "*nimble*"
cat src/xincubator/models/nimble/composit/nimble.py
```

### 6. Use Descriptive Parameter Comments
```yaml
parameters:
  max_funding_bias: 0.25          # Maximum 75/25 vs 50/50 split
  funding_signal_weight: 0.4      # Weight given to funding signal
  min_signal_strength: 0.8        # Minimum signal to override risk parity
  tracker_long_stop_risk: 4.0     # 4% stop loss for longs
```

### 7. Start Small and Iterate
```yaml
simulation:
  capital: 10000.0              # Start with small capital
  start: "2024-01-01"
  stop: "2024-01-31"            # Test short period first
  debug: "INFO"                 # Use INFO for initial tests
```

### 8. Unified Config Principle
- Use **same config** for simulation, paper, and live trading
- Test in simulation first
- Deploy to paper trading with same config
- Promote to live trading when validated
- Only difference: execution mode, not parameters

## Common Parameter Categories

### Time-based Parameters
```yaml
parameters:
  timeframe: "1h"              # "1h", "4h", "1d"
  rebalance_frequency: "1d"    # How often to rebalance
  lookback_days: 30            # Historical window
  period: 14                   # Indicator periods
```

### Risk Management
```yaml
parameters:
  leverage: 1.0                # Position leverage
  max_allocation: 0.1          # Maximum position size
  min_allocation: 0.01         # Minimum position size
  stop_loss: 0.02              # Stop loss percentage
```

### Universe Selection
```yaml
parameters:
  universe_size: 50            # Number of instruments
  instruments_per_leg: 15      # For long/short strategies
  min_volume: 1000000          # Minimum daily volume
```

## Config Validation

**IMPORTANT**: Always validate your config before running backtests or deploying live.

```bash
# Validate config syntax and structure
poetry run python -m qubx.cli.commands <config.yaml>

# Examples:
poetry run python -m qubx.cli.commands configs/nimble/nimble.advrisk.48h.yaml
poetry run python -m qubx.cli.commands configs/gemini/gemini.v0.yaml
```

This command will:
- Parse the YAML file
- Validate all required fields are present
- Check strategy class can be imported
- Verify parameter types and structure
- Report any configuration errors

**Always validate before committing configs or running expensive backtests.**

## Validation Checklist

Before running a config:

1. ✅ **Run validation command** - `poetry run python -m qubx.cli.commands <config.yaml>`
2. ✅ **Name field present** - Config has descriptive name
3. ✅ **Description field present** - Config has detailed description of purpose/changes
4. ✅ **Strategy exists** - Verify import path works
5. ✅ **Required parameters** - Check strategy source for required params
6. ✅ **Instruments valid** - Ensure instruments exist on exchange
7. ✅ **Date range valid** - Check data availability for time range
8. ✅ **Commission valid** - Use only predefined commission strings
9. ✅ **Variate only parameters** - Don't variate simulation config fields
10. ✅ **YAML syntax** - Validate YAML formatting
11. ✅ **File location** - Config in correct directory: configs/strategy_name/
12. ✅ **File naming** - Follows convention: strategy.modification.params.yaml

## Common Mistakes to Avoid

1. **Missing name/description** - These are REQUIRED fields, always fill them
2. **Overwriting configs** - Create new file if name conflict exists
3. **Bad file naming** - Use dots (.), not underscores or dashes in config names
4. **Guessing parameter names** - Always check strategy source
5. **Wrong instrument format** - Use `EXCHANGE:SYMBOL` for simulation, just `SYMBOL` for live universe
6. **Custom commission dicts** - Only predefined strings allowed
7. **Variating wrong fields** - Only strategy parameters can be varied
8. **Missing required simulation fields** - capital, instruments, start, stop required
9. **Missing required live fields** - exchanges, logging required for live
10. **Invalid date format** - Use "YYYY-MM-DD"
11. **Inconsistent configs** - Use same config for simulation and live (unified principle)

## Investigation Workflow

1. **Find similar configs** in the same domain
2. **Read strategy source code** for parameter requirements
3. **Check predefined commission options**
4. **Verify instrument availability** and data ranges
5. **Start with simple config** and add complexity
6. **Test with small capital and short periods first**

Remember: Understanding existing patterns and strategy requirements is more important than memorizing syntax.