# Qubx Data Storage API Guide

## Overview

Qubx provides a unified **Storage API** for accessing market data from various sources for **research and data analysis**.

> ⚠️ **IMPORTANT: Usage Context**
>
> | Use Case | What to Use |
> |----------|-------------|
> | **Simulation/Backtesting** | Use old `loader()` from `qubx.data` |
> | **Research & Analysis** | Use new **Storage API** |
>
> The new Storage API is **NOT ready for simulation yet**! Continue using `loader()` for `simulate()` calls.

**Key Concepts:**
- **Storage**: Container that provides information about available data (exchanges, market types, symbols)
- **Reader**: Interface for reading data from a specific exchange/market combination
- **Transformers**: Convert raw data into useful formats (pandas, OHLCV series, typed records)

## Quick Start with StorageRegistry

The easiest way to access storages is via `StorageRegistry`:

```python
from qubx.data.registry import StorageRegistry

# Get QuestDB storage using URI syntax
storage = StorageRegistry.get("qdb::quantlab")

# Get CSV storage
storage = StorageRegistry.get("csv::~/data/market/")

# Get reader and load data
reader = storage["BINANCE.UM", "SWAP"]
df = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "2024-06-01").transform(PandasFrame())
```

**URI formats:**
- `qdb::hostname` or `questdb::hostname` - QuestDB storage
- `csv::/path/to/data/` - CSV storage

## Why Use Storage API (for Research)?

| Feature | Old `loader()` | New Storage API |
|---------|---------------|-----------------|
| Data discovery | Manual | `get_exchanges()`, `get_data_types()`, `get_data_id()` |
| Time range info | Not available | `get_time_range()` |
| Multiple symbols | Sequential | Single read call |
| Chunked reading | Limited | Built-in `chunksize` |
| Data transformation | Manual | Built-in transformers |
| Flexibility | Fixed | Extensible |

## Storage Types

### 1. CSV Storage

Read data from local CSV files organized by exchange/market/symbol.

```python
from qubx.data.storages.csv import CsvStorage

# Create storage pointing to CSV data directory
storage = CsvStorage("~/data/market/")

# Expected directory structure:
# ~/data/market/
#   └── BINANCE.UM/
#       └── SWAP/
#           ├── BTCUSDT.1h.csv
#           ├── BTCUSDT.trades.csv
#           └── ETHUSDT.1h.csv
```

**File naming convention:**
- `SYMBOL.DATATYPE.csv` or `SYMBOL.DATATYPE.csv.gz`
- Examples: `BTCUSDT.1h.csv`, `ETHUSDT.trades.csv.gz`, `BTCUSDT.quotes.csv`

### 2. QuestDB Storage

Read data from QuestDB time-series database.

```python
from qubx.data.storages.questdb import QuestDBStorage

# Connect to QuestDB on quantlab server
storage = QuestDBStorage(
    host="quantlab",
    user="admin",
    password="quest",
    port=8812
)

# Or use default localhost
storage = QuestDBStorage()
```

## Storage Operations

### Discover Available Data

```python
# List available exchanges
storage.get_exchanges()
# ['BINANCE.UM', 'BINANCE.CM', 'KRAKEN']

# List market types for exchange
storage.get_market_types("BINANCE.UM")
# ['SWAP', 'FUTURE']
```

## Reader Operations

### Get a Reader

```python
# Get reader for specific exchange and market
reader = storage.get_reader("BINANCE.UM", "SWAP")

# Shorthand syntax
reader = storage["BINANCE.UM", "SWAP"]
```

### Discover Data in Reader

```python
# List all symbols that have OHLC 1h data
symbols = reader.get_data_id("ohlc(1h)")
# ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', ...]

# List all symbols (any data type)
all_symbols = reader.get_data_id()

# List data types available for a symbol
reader.get_data_types("BTCUSDT")
# ['ohlc(1h)', 'ohlc(4h)', 'trade', 'quote', 'funding_payment']

# Get time range for specific data
start, end = reader.get_time_range("BTCUSDT", "ohlc(1h)")
# (numpy.datetime64('2020-01-01'), numpy.datetime64('2024-12-01'))
```

### Read Data

```python
from qubx.core.basics import DataType

# Read single symbol
raw_data = reader.read("BTCUSDT", DataType.OHLC["1h"], start="2024-01-01", stop="2024-06-01")

# Read with string data type
raw_data = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "2024-06-01")

# Read multiple symbols at once
raw_data = reader.read(
    ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    DataType.OHLC["4h"],
    start="2024-01-01",
    stop="2024-06-01"
)

# Read by chunks (for large datasets)
for chunk in reader.read("BTCUSDT", "ohlc(1h)", "2020-01-01", "2024-01-01", chunksize=10000):
    # Process each chunk
    df = chunk.transform(PandasFrame())
    process(df)
```

### Supported Data Types

```python
from qubx.core.basics import DataType

# OHLC bars with timeframe
DataType.OHLC["1h"]      # 1 hour bars
DataType.OHLC["4h"]      # 4 hour bars
DataType.OHLC["1d"]      # Daily bars
DataType.OHLC["1Min"]    # 1 minute bars

# Other data types
DataType.TRADE           # Individual trades
DataType.QUOTE           # Bid/ask quotes
DataType.ORDERBOOK       # Order book snapshots
DataType.FUNDING_RATE    # Funding rate
DataType.FUNDING_PAYMENT # Funding payments
DataType.LIQUIDATION     # Liquidation events
DataType.OPEN_INTEREST   # Open interest
```

## Transformers

Raw data from readers needs to be transformed into usable formats.

### PandasFrame - Convert to DataFrame

```python
from qubx.data.transformers import PandasFrame

# Read raw data
raw = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "2024-02-01")

# Transform to pandas DataFrame
df = raw.transform(PandasFrame())
#                         open     high      low    close     volume
# timestamp
# 2024-01-01 00:00:00  42000.1  42500.0  41800.0  42300.5   1234.567

# With symbol in index (for multi-symbol data)
df = raw.transform(PandasFrame(id_in_index=True))
#                             open     high      low    close
# timestamp           symbol
# 2024-01-01 00:00:00 BTCUSDT  42000.1  42500.0  41800.0  42300.5
```

### OHLCVSeries - Convert to Qubx OHLCV Series

```python
from qubx.data.transformers import OHLCVSeries

raw = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "2024-02-01")

# Transform to OHLCV series (used in strategies)
ohlcv = raw.transform(OHLCVSeries())

# With max length limit
ohlcv = raw.transform(OHLCVSeries(max_length=1000))
```

### TypedRecords - Convert to Qubx Objects

```python
from qubx.data.transformers import TypedRecords

# Read quotes and convert to Quote objects
raw = reader.read("BTCUSDT", DataType.QUOTE, "2024-01-01", "2024-01-02")
quotes = raw.transform(TypedRecords())
# [Quote(time=..., bid=42000.0, ask=42000.5, bid_size=10.0, ask_size=5.0), ...]

# Read trades and convert to Trade objects
raw = reader.read("BTCUSDT", DataType.TRADE, "2024-01-01", "2024-01-02")
trades = raw.transform(TypedRecords())
# [Trade(time=..., price=42000.0, size=0.5, side=1), ...]

# Read OHLC and convert to Bar objects
raw = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "2024-01-02")
bars = raw.transform(TypedRecords())
# [Bar(time=..., open=42000.0, high=42500.0, low=41800.0, close=42300.0), ...]
```

### TickSeries - Simulate Ticks from OHLC

Convert OHLC bars into simulated quotes/trades (useful for backtesting).

```python
from qubx.data.transformers import TickSeries

raw = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "2024-01-02")

# Generate simulated quotes from OHLC
quotes = raw.transform(TickSeries())
# Creates 4 quotes per bar: open, high, low, close

# Generate simulated trades
trades = raw.transform(TickSeries(trades=True, quotes=False))

# Generate both quotes and trades
both = raw.transform(TickSeries(trades=True, quotes=True))

# Custom spread and timing
ticks = raw.transform(TickSeries(
    spread=0.01,                    # Bid/ask spread
    open_close_time_shift_secs=1.0  # Time offset for open/close quotes
))
```

## Complete Examples

### Example 1: Load OHLC Data for Analysis

```python
from qubx.data.storages.questdb import QuestDBStorage
from qubx.data.transformers import PandasFrame

# Connect to QuestDB
storage = QuestDBStorage(host="quantlab")
reader = storage["BINANCE.UM", "SWAP"]

# Check available data
print(f"Symbols: {reader.get_data_id('ohlc(1h)')[:10]}")
print(f"Time range: {reader.get_time_range('BTCUSDT', 'ohlc(1h)')}")

# Load data as DataFrame
df = reader.read(
    ["BTCUSDT", "ETHUSDT"],
    "ohlc(1h)",
    start="2024-01-01",
    stop="2024-06-01"
).transform(PandasFrame())

# Calculate returns
returns = df.xs("close", axis=1, level=1).pct_change()
```

### Example 2: Load Data from CSV for Backtest

```python
from qubx.data.storages.csv import CsvStorage
from qubx.data.transformers import OHLCVSeries

# Load from local CSV
storage = CsvStorage("~/data/crypto/")
reader = storage["BINANCE.UM", "SWAP"]

# Get OHLCV series for strategy
btc_ohlcv = reader.read(
    "BTCUSDT",
    "ohlc(4h)",
    start="2023-01-01",
    stop="2024-01-01"
).transform(OHLCVSeries())

# Use in strategy context
# ctx.ohlcv["BTCUSDT"] = btc_ohlcv
```

### Example 3: Process Large Dataset in Chunks

```python
from qubx.data.storages.questdb import QuestDBStorage
from qubx.data.transformers import PandasFrame

storage = QuestDBStorage(host="quantlab")
reader = storage["BINANCE.UM", "SWAP"]

# Process 5 years of data in chunks
results = []
for chunk in reader.read("BTCUSDT", "ohlc(1h)", "2019-01-01", "2024-01-01", chunksize=10000):
    df = chunk.transform(PandasFrame())
    # Calculate some metric per chunk
    results.append(df["close"].mean())

overall_mean = sum(results) / len(results)
```

### Example 4: Get Funding Payment Data

```python
from qubx.data.storages.questdb import QuestDBStorage
from qubx.data.transformers import PandasFrame
from qubx.core.basics import DataType

storage = QuestDBStorage(host="quantlab")
reader = storage["BINANCE.UM", "SWAP"]

# Load funding payments
funding = reader.read(
    "BTCUSDT",
    DataType.FUNDING_PAYMENT,
    start="2024-01-01",
    stop="2024-06-01"
).transform(PandasFrame())

# Analyze funding rates
print(f"Mean funding rate: {funding['funding_rate'].mean():.6f}")
print(f"Total funding events: {len(funding)}")
```

### Example 5: Get Fundamental Data (Market Cap, Volume, etc.)

CoinGecko fundamental data is collected daily and stored in QuestDB.

```python
from qubx.data.registry import StorageRegistry
from qubx.data.transformers import PandasFrame

# Get storage
storage = StorageRegistry.get("qdb::quantlab")

# Check available market types for CoinGecko
storage.get_market_types("COINGECKO")
# ['FUNDAMENTAL']

# Get fundamental data reader
freader = storage.get_reader("COINGECKO", "FUNDAMENTAL")

# List all available coins (NOT trading pairs - just BTC, ETH, SOL, etc.)
available_coins = freader.get_data_id()
# ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', ...]

# Read fundamental data for all coins
fd = freader.read(available_coins, "fundamental", "2020-01-01", "now")
df = fd.transform(PandasFrame(True))  # True = include symbol in index

# df contains columns like:
# - market_cap
# - total_volume
# - circulating_supply
# - etc.
```

**Available fundamental metrics:**
- `market_cap` - Market capitalization in USD
- `total_volume` - 24h trading volume
- `circulating_supply` - Circulating supply
- Other CoinGecko metrics (varies by coin)

**Note:** Fundamental data uses coin symbols (BTC, ETH) not trading pairs (BTCUSDT).

```python
# Example: Get market cap for top coins
top_coins = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
fd = freader.read(top_coins, "fundamental", "2024-01-01", "now")
df = fd.transform(PandasFrame(True))

# Pivot to get market cap time series per coin
market_caps = df.reset_index().pivot(index='timestamp', columns='symbol', values='market_cap')
```

## When to Use What

> ⚠️ **CRITICAL**: Storage API is NOT for simulation yet!

### For Simulation/Backtesting → Use `loader()`

The old `loader()` approach is **still required** for `simulate()` calls:

```python
from qubx.data import loader

# Create loader for simulation
ldr = loader("BINANCE.UM", "1h", source="mqdb::quantlab")

# Use in simulate() - THIS IS THE CORRECT WAY FOR BACKTESTING
r = simulate(
    Strategy(),
    data={"ohlc(1h)": ldr},
    instruments=["BINANCE.UM:BTCUSDT"],
    capital=10000,
    start="2024-01-01",
    stop="2024-06-01"
)
```

### For Research & Analysis → Use Storage API

The new Storage API is for **research notebooks and data analysis**:

```python
from qubx.data.registry import StorageRegistry
from qubx.data.transformers import PandasFrame

# Get storage via registry (convenient)
storage = StorageRegistry.get("qdb::quantlab")
reader = storage["BINANCE.UM", "SWAP"]

# Direct data access with full control - FOR RESEARCH ONLY
df = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "2024-06-01").transform(PandasFrame())

# Analyze data
returns = df["close"].pct_change()
volatility = returns.rolling(24).std()
```

### Summary Table

| Task | Use This | Example |
|------|----------|---------|
| Running `simulate()` | `loader()` | `data={"ohlc(1h)": loader(...)}` |
| Research notebooks | Storage API | `StorageRegistry.get("qdb::quantlab")` |
| Data exploration | Storage API | `reader.get_data_id()`, `reader.get_time_range()` |
| Feature engineering | Storage API | `reader.read(...).transform(PandasFrame())` |
| YAML config backtests | `loader()` via config | Defined in YAML data section |

## Quick Reference

```python
# === FOR RESEARCH & ANALYSIS ===
from qubx.data.registry import StorageRegistry
from qubx.data.transformers import PandasFrame, OHLCVSeries, TypedRecords, TickSeries
from qubx.core.basics import DataType

# Create storage via registry (RECOMMENDED)
storage = StorageRegistry.get("qdb::quantlab")     # QuestDB
storage = StorageRegistry.get("csv::~/data/")      # CSV

# Or create directly
from qubx.data.storages.questdb import QuestDBStorage
storage = QuestDBStorage(host="quantlab")

# Get reader
reader = storage["BINANCE.UM", "SWAP"]

# Discover data
reader.get_data_id("ohlc(1h)")           # List symbols
reader.get_data_types("BTCUSDT")         # List data types
reader.get_time_range("BTCUSDT", "ohlc(1h)") # Get time range

# Read and transform
df = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "2024-06-01").transform(PandasFrame())
ohlcv = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "2024-06-01").transform(OHLCVSeries())
records = reader.read("BTCUSDT", DataType.TRADE, "2024-01-01", "2024-01-02").transform(TypedRecords())
ticks = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "2024-01-02").transform(TickSeries())

# === FOR SIMULATION/BACKTESTING ===
from qubx.data import loader

ldr = loader("BINANCE.UM", "1h", source="mqdb::quantlab")
# Use ldr in simulate() data parameter
```

## Source Code References

- **Storage registry**: `~/devs/Qubx/src/qubx/data/registry.py`
- Storage interface: `~/devs/Qubx/src/qubx/data/storage.py`
- CSV storage: `~/devs/Qubx/src/qubx/data/storages/csv.py`
- QuestDB storage: `~/devs/Qubx/src/qubx/data/storages/questdb.py`
- Transformers: `~/devs/Qubx/src/qubx/data/transformers.py`
- Old loader (for simulation): `~/devs/Qubx/src/qubx/data/helpers.py`
