# Strategy Debugging Guide for X-Incubator
#tutorial

A comprehensive guide for debugging trading strategies in the X-Incubator quantitative trading system built on the Qubx platform. This guide provides templates and techniques learned from the debug scripts in `research/bugs/`.

## Table of Contents

1. [Quick Debug Checklist](#quick-debug-checklist)
2. [Debug Simulation Setup](#debug-simulation-setup)
3. [Common Debugging Techniques](#common-debugging-techniques)
4. [Method Patching for Deep Debugging](#method-patching-for-deep-debugging)
5. [Data Debugging](#data-debugging)
6. [Position Analysis](#position-analysis)
7. [Debug Script Templates](#debug-script-templates)
8. [Notebook Debugging](#notebook-debugging)

---

## Quick Debug Checklist

When a strategy isn't working as expected, follow this systematic approach:

### 1. Initial Checks

- [ ] **Run with DEBUG logging**: Set `debug="DEBUG"` in simulate()
- [ ] **Use short time periods**: Start with 1-2 days for faster iteration
- [ ] **Use single job**: Set `n_jobs=1` to avoid threading issues
- [ ] **Check MRO**: Print Method Resolution Order to understand inheritance
- [ ] **Verify data availability**: Ensure all required aux_data is prefetched

### 2. Common Issues

- [ ] **No positions created**: Check universe selection and group assignment
- [ ] **Imbalanced long/short**: Debug group balancing and portfolio allocation
- [ ] **Unexpected signals**: Trace signal generation with method patching
- [ ] **Performance issues**: Check indicator calculations and data access patterns

---

## Debug Simulation Setup

### Basic Debug Template

**ALWAYS run debug scripts with `poetry run python script.py`**

```python
"""Basic debug simulation template."""

from qubx.backtester.simulator import simulate
from qubx.core.metrics import tearsheet, portfolio_symbols
from qubx.data.helpers import CachedPrefetchReader, ReaderRegistry
import pandas as pd

# Import your strategy
from xincubator.models.your_strategy import YourStrategy

# Short debug period - ALWAYS start small
START = "2025-01-15"
STOP = "2025-01-17"  # 2-3 days max for initial debugging

# Setup cached reader for performance
reader = ReaderRegistry.get("mqdb::quantlab")
cached_reader = CachedPrefetchReader(reader, prefetch_period="1w")

# Prefetch ALL required auxiliary data
print("Prefetching auxiliary data...")
cached_reader.prefetch_aux_data(
    aux_data_names=["candles", "funding_payment", "fundamental_data"],
    exchange="BINANCE.UM",
    start=START,
    stop=STOP,
)

print("Running debug simulation...")
r = simulate(
    YourStrategy(
        # Use minimal parameters for debugging
        topn_max_symbols=20,      # Smaller universe
        fit_schedule="1h",        # Frequent fitting for debugging
        event_schedule="1h",      # Frequent events
        min_instruments_per_leg=2, # Lower minimums
        instruments_per_leg=5,
    ),
    data={"ohlc(1h)": cached_reader, "funding_payment": cached_reader},
    aux_data=cached_reader,
    capital=100_000,
    commissions="vip0_usdt",
    instruments=["BINANCE.UM:BTCUSDT"],
    exchange="BINANCE.UM",
    start=START,
    stop=STOP,
    enable_funding=True,
    debug="DEBUG",  # Enable full debugging
    n_jobs=1,       # ALWAYS use single job for debugging
)

print("\n=== DEBUG ANALYSIS ===")
session = r[0] if isinstance(r, list) else r

# Basic session info
print(f"Strategy: {session.strategy_class}")
print(f"Capital: ${session.get_total_capital():,.2f}")
print(f"Period: {session.start} to {session.stop}")

# Portfolio analysis
portfolio_log = session.portfolio_log
symbols = portfolio_symbols(portfolio_log)
print(f"Traded symbols: {len(symbols)}")

# Final positions analysis
if not portfolio_log.empty:
    end_date = portfolio_log.index[-1]
    print(f"\n=== FINAL POSITIONS at {end_date} ===")
    
    # Extract position values
    position_values = {}
    for col in portfolio_log.columns:
        if col.endswith('_Value'):
            symbol = col.replace('_Value', '')
            value = portfolio_log.loc[end_date, col]
            if abs(value) > 0.01:  # Filter tiny positions
                position_values[symbol] = value
    
    # Separate long/short
    long_positions = {k: v for k, v in position_values.items() if v > 0}
    short_positions = {k: v for k, v in position_values.items() if v < 0}
    
    print(f"Long positions: {len(long_positions)}")
    print(f"Short positions: {len(short_positions)}")
    
    # Calculate exposures
    total_long = sum(long_positions.values())
    total_short = sum(short_positions.values())
    total_gross = total_long + abs(total_short)
    total_net = total_long + total_short
    
    print(f"Total long value: ${total_long:,.2f}")
    print(f"Total short value: ${total_short:,.2f}")
    print(f"Total gross exposure: ${total_gross:,.2f}")
    print(f"Total net exposure: ${total_net:,.2f}")
    
    # Show top positions
    if long_positions:
        print("\n=== TOP LONG POSITIONS ===")
        sorted_long = sorted(long_positions.items(), key=lambda x: x[1], reverse=True)
        for symbol, value in sorted_long[:10]:
            print(f"  {symbol}: ${value:,.2f}")
    
    if short_positions:
        print("\n=== TOP SHORT POSITIONS ===")
        sorted_short = sorted(short_positions.items(), key=lambda x: x[1])
        for symbol, value in sorted_short[:10]:
            print(f"  {symbol}: ${value:,.2f}")
    else:
        print("\n=== NO SHORT POSITIONS FOUND ===")
        print("This may indicate a problem with group assignment or balancing.")

# Generate tearsheet for visual analysis
print("\nGenerating tearsheet...")
tearsheet(r, plot_leverage=True)
```

---

## Common Debugging Techniques

### 1. Enable Comprehensive Logging

```python
# Set debug level to see all internal operations
r = simulate(
    strategy,
    debug="DEBUG",  # Shows all internal strategy operations
    n_jobs=1,       # Prevents log interleaving
    # ... other parameters
)
```

### 2. Check Method Resolution Order (MRO)

```python
# Always check MRO when dealing with multiple inheritance
print("\n=== Method Resolution Order ===")
for i, cls in enumerate(YourStrategy.__mro__):
    print(f"{i:2d}. {cls.__module__}.{cls.__name__}")

# Find which class provides specific methods
print("\nLooking for 'rebalance_group' method in MRO:")
for cls in YourStrategy.__mro__:
    if hasattr(cls, 'rebalance_group') and 'rebalance_group' in cls.__dict__:
        print(f"Found in: {cls.__module__}.{cls.__name__}")
```

### 3. Verify Data Prefetching

```python
# Check what data was actually prefetched
prefetch_result = cached_reader.prefetch_aux_data(
    aux_data_names=["candles", "funding_payment", "fundamental_data"],
    exchange="BINANCE.UM",
    start=START,
    stop=STOP,
)
print(f"Prefetch result: {prefetch_result}")
```

---

## Method Patching for Deep Debugging

### Pattern: Patch and Trace Strategy Methods

Use this pattern to debug specific methods in your strategy:

```python
"""Template for patching strategy methods to trace execution."""

# Import the strategy and related classes
from xincubator.models.your_strategy import YourStrategy
from quantkit.pacman.core import PortfolioModel

# Store original methods
original_rebalance = YourStrategy.rebalance
original_pm_rebalance = PortfolioModel.rebalance

def debug_rebalance(self, mtx):
    """Debug wrapper for main rebalance method."""
    print("\n" + "="*50)
    print(f"REBALANCE DEBUG at {mtx.time()}")
    print("="*50)
    
    # Call original method
    signals = original_rebalance(self, mtx)
    
    # Debug output
    print(f"Generated {len(signals)} signals")
    if signals:
        print("First 5 signals:")
        for i, sig in enumerate(signals[:5]):
            print(f"  {i+1}. {sig.instrument.symbol}: side={sig.side}, signal={sig.signal}")
    
    return signals

def debug_pm_rebalance(self, mtx):
    """Debug wrapper for portfolio model rebalance."""
    print(f"\n=== PortfolioModel.rebalance START ===")
    print(f"Strategy class: {self.__class__.__name__}")
    
    # Check groups and ranks
    if hasattr(self, 'groups') and len(self) > 0:
        groups = self.groups()
        ranks = self.rank_groups(mtx, groups)
        print(f"Groups: {[g.name for g in groups]}")
        print(f"Ranks: {ranks}")
        
        # Show group details
        for group, rank in zip(groups, ranks):
            print(f"  Group '{group.name}': {len(group.instruments)} instruments, rank={rank}")
    
    result = original_pm_rebalance(self, mtx)
    print(f"Portfolio model generated {len(result)} signals")
    return result

# Apply patches
YourStrategy.rebalance = debug_rebalance
PortfolioModel.rebalance = debug_pm_rebalance

# ... run simulation with patched methods
```

### Pattern: Patch Group Balancers

```python
"""Template for debugging group balancing logic."""

from your_strategy_balancers import YourGroupBalancer, YourPortfolioBalancer

# Store originals
original_group_rebalance = YourGroupBalancer.rebalance_group
original_portfolio_rebalance = YourPortfolioBalancer.rebalance_portfolio

def debug_group_rebalance(self, mtx, group, rank):
    """Debug group rebalancing."""
    print(f"\n=== {self.__class__.__name__}.rebalance_group ===")
    print(f"Group: {group.name}")
    print(f"Side: {group.meta.get('side', 'unknown')}")
    print(f"Rank (target weight): {rank}")
    print(f"Instruments: {len(group.instruments)}")
    
    # Show first few instruments
    for i, instr in enumerate(group.instruments[:3]):
        print(f"  {i+1}. {instr.symbol}")
    
    result = original_group_rebalance(self, mtx, group, rank)
    
    # Analyze result
    weight_sum = sum(result.values())
    print(f"Generated {len(result)} weights, sum={weight_sum:.4f} (target: {rank:.1f})")
    
    # Show top weights
    sorted_weights = sorted(result.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
    for instr, weight in sorted_weights:
        print(f"  {instr.symbol}: {weight:.4f}")
    
    return result

def debug_portfolio_rebalance(self, mtx, g_balances):
    """Debug portfolio rebalancing."""
    print(f"\n=== {self.__class__.__name__}.rebalance_portfolio ===")
    print(f"Number of groups: {len(g_balances)}")
    
    for group_name, balances in g_balances.items():
        weight_sum = sum(balances.values())
        print(f"Group '{group_name}': {len(balances)} instruments, weight_sum={weight_sum:.4f}")
    
    result = original_portfolio_rebalance(self, mtx, g_balances)
    
    # Analyze final allocation
    long_weights = {k: v for k, v in result.items() if v > 0}
    short_weights = {k: v for k, v in result.items() if v < 0}
    
    print(f"\n=== Final Portfolio Allocation ===")
    print(f"Long instruments: {len(long_weights)}, total weight: {sum(long_weights.values()):.4f}")
    print(f"Short instruments: {len(short_weights)}, total weight: {sum(short_weights.values()):.4f}")
    
    return result

# Apply patches
YourGroupBalancer.rebalance_group = debug_group_rebalance
YourPortfolioBalancer.rebalance_portfolio = debug_portfolio_rebalance
```

---

## Data Debugging

### Check Auxiliary Data Availability

```python
"""Template for debugging data issues."""

def debug_data_availability(mtx, strategy_instance):
    """Check if all required data is available."""
    print(f"\n=== DATA AVAILABILITY CHECK at {mtx.time()} ===")
    
    # Check funding data
    try:
        start_time = mtx.time() - pd.Timedelta(days=7)  # Look back 7 days
        funding_data = mtx.get_aux_data(
            "funding_payment", 
            exchange="BINANCE.UM", 
            start=start_time, 
            stop=mtx.time()
        )
        
        if funding_data is not None and not funding_data.empty:
            print(f"Funding data: {len(funding_data)} records")
            symbols = funding_data.index.get_level_values("symbol").unique()
            print(f"Funding symbols: {len(symbols)} ({list(symbols[:5])}...)")
        else:
            print("❌ No funding data available!")
            
    except Exception as e:
        print(f"❌ Error accessing funding data: {e}")
    
    # Check fundamental data
    try:
        fundamental_data = mtx.get_aux_data(
            "fundamental_data",
            exchange="BINANCE.UM",
            start=start_time,
            stop=mtx.time()
        )
        
        if fundamental_data is not None and not fundamental_data.empty:
            print(f"Fundamental data: {len(fundamental_data)} records")
            symbols = fundamental_data.index.get_level_values("symbol").unique()
            print(f"Fundamental symbols: {len(symbols)}")
        else:
            print("❌ No fundamental data available!")
            
    except Exception as e:
        print(f"❌ Error accessing fundamental data: {e}")
    
    # Check current universe
    if hasattr(strategy_instance, 'current_universe'):
        universe = strategy_instance.current_universe
        print(f"Current universe: {len(universe)} instruments")
        for i, instr in enumerate(universe[:5]):
            print(f"  {i+1}. {instr.symbol}")

# Use in patched methods
def debug_fit(self, mtx):
    """Debug universe fitting."""
    print(f"\n=== FITTING DEBUG at {mtx.time()} ===")
    
    # Check data first
    debug_data_availability(mtx, self)
    
    # Call original fit
    result = original_fit(self, mtx)
    
    return result
```

---

## Position Analysis

### Analyze Portfolio Log

```python
"""Template for analyzing portfolio positions and exposures."""

def analyze_portfolio_positions(portfolio_log, analysis_date=None):
    """Comprehensive position analysis."""
    if portfolio_log.empty:
        print("❌ Empty portfolio log!")
        return
    
    if analysis_date is None:
        analysis_date = portfolio_log.index[-1]
    
    print(f"\n=== POSITION ANALYSIS at {analysis_date} ===")
    
    # Extract all position values
    position_cols = [col for col in portfolio_log.columns if col.endswith('_Value')]
    position_data = portfolio_log.loc[analysis_date, position_cols]
    
    # Convert to clean format
    positions = {}
    for col in position_cols:
        symbol = col.replace('_Value', '')
        value = position_data[col]
        if abs(value) > 0.01:  # Filter tiny positions
            positions[symbol] = value
    
    if not positions:
        print("❌ No significant positions found!")
        return
    
    # Separate long/short
    long_positions = {k: v for k, v in positions.items() if v > 0}
    short_positions = {k: v for k, v in positions.items() if v < 0}
    
    # Calculate metrics
    total_long = sum(long_positions.values())
    total_short = sum(short_positions.values())
    total_gross = total_long + abs(total_short)
    total_net = total_long + total_short
    
    print(f"Total positions: {len(positions)}")
    print(f"Long positions: {len(long_positions)} (${total_long:,.2f})")
    print(f"Short positions: {len(short_positions)} (${total_short:,.2f})")
    print(f"Gross exposure: ${total_gross:,.2f}")
    print(f"Net exposure: ${total_net:,.2f}")
    print(f"Long/Short ratio: {len(long_positions)/max(len(short_positions), 1):.2f}")
    
    # Top positions by absolute value
    sorted_positions = sorted(positions.items(), key=lambda x: abs(x[1]), reverse=True)
    
    print(f"\n=== TOP 10 POSITIONS BY SIZE ===")
    for i, (symbol, value) in enumerate(sorted_positions[:10], 1):
        side = "LONG" if value > 0 else "SHORT"
        print(f"{i:2d}. {symbol}: {side} ${abs(value):,.2f}")
    
    # Check balance
    if len(short_positions) == 0:
        print(f"\n❌ WARNING: No short positions! Strategy may not be market-neutral.")
    elif abs(total_net) > 0.1 * total_gross:
        print(f"\n⚠️  WARNING: High net exposure ({total_net/total_gross:.1%}). Strategy may not be neutral.")
    
    return {
        'long_positions': long_positions,
        'short_positions': short_positions,
        'total_long': total_long,
        'total_short': total_short,
        'total_gross': total_gross,
        'total_net': total_net,
    }

# Use after simulation
analysis = analyze_portfolio_positions(session.portfolio_log)
```

---

## Debug Script Templates

Add debug scripts usually to research/bugs/

### Template 1: Basic Strategy Debug

```python
#!/usr/bin/env python3
"""
Basic strategy debugging script.
Run with: poetry run python debug_basic.py
"""

from qubx.backtester.simulator import simulate
from qubx.core.metrics import tearsheet, portfolio_symbols
from qubx.data.helpers import CachedPrefetchReader, ReaderRegistry
import pandas as pd

# Import your strategy
from xincubator.models.your_strategy import YourStrategy

def main():
    # Configuration
    START = "2025-01-15"
    STOP = "2025-01-17"  # Short period for debugging
    
    # Setup data reader
    reader = ReaderRegistry.get("mqdb::quantlab")
    cached_reader = CachedPrefetchReader(reader, prefetch_period="1w")
    
    print("Prefetching data...")
    cached_reader.prefetch_aux_data(
        aux_data_names=["candles", "funding_payment", "fundamental_data"],
        exchange="BINANCE.UM",
        start=START,
        stop=STOP,
    )
    
    # Create strategy with debug parameters
    strategy = YourStrategy(
        topn_max_symbols=20,
        fit_schedule="1h",
        event_schedule="1h",
        min_instruments_per_leg=2,
        instruments_per_leg=5,
        debug_mode=True,  # If your strategy has this parameter
    )
    
    print("Running simulation...")
    result = simulate(
        strategy,
        data={"ohlc(1h)": cached_reader, "funding_payment": cached_reader},
        aux_data=cached_reader,
        capital=100_000,
        commissions="vip0_usdt",
        instruments=["BINANCE.UM:BTCUSDT"],
        exchange="BINANCE.UM",
        start=START,
        stop=STOP,
        enable_funding=True,
        debug="DEBUG",
        n_jobs=1,
    )
    
    # Analyze results
    session = result[0] if isinstance(result, list) else result
    
    print("\n" + "="*60)
    print("SIMULATION RESULTS")
    print("="*60)
    
    print(f"Strategy: {session.strategy_class}")
    print(f"Period: {session.start} to {session.stop}")
    print(f"Capital: ${session.get_total_capital():,.2f}")
    
    # Position analysis
    portfolio_log = session.portfolio_log
    if not portfolio_log.empty:
        symbols = portfolio_symbols(portfolio_log)
        print(f"Traded symbols: {len(symbols)}")
        
        # Final position analysis
        final_date = portfolio_log.index[-1]
        position_values = {}
        
        for col in portfolio_log.columns:
            if col.endswith('_Value'):
                symbol = col.replace('_Value', '')
                value = portfolio_log.loc[final_date, col]
                if abs(value) > 0.01:
                    position_values[symbol] = value
        
        long_pos = {k: v for k, v in position_values.items() if v > 0}
        short_pos = {k: v for k, v in position_values.items() if v < 0}
        
        print(f"\nFinal positions:")
        print(f"  Long: {len(long_pos)} positions")
        print(f"  Short: {len(short_pos)} positions")
        print(f"  Total exposure: ${sum(abs(v) for v in position_values.values()):,.2f}")
        
        if len(short_pos) == 0:
            print("  ❌ WARNING: No short positions!")
    
    # Generate tearsheet
    print("\nGenerating tearsheet...")
    tearsheet(result, plot_leverage=True)

if __name__ == "__main__":
    main()
```

### Template 2: Deep Debug with Patching

```python
#!/usr/bin/env python3
"""
Deep debugging with method patching.
Run with: poetry run python debug_deep.py
"""

from qubx.backtester.simulator import simulate
from qubx.data.helpers import CachedPrefetchReader, ReaderRegistry
import pandas as pd

# Import strategy components
from xincubator.models.your_strategy import YourStrategy
from quantkit.pacman.core import PortfolioModel

# Global debug state
debug_info = {'call_count': 0, 'signals_generated': []}

def setup_debug_patches():
    """Setup method patches for debugging."""
    
    # Store originals
    global original_rebalance, original_pm_rebalance
    original_rebalance = YourStrategy.rebalance
    original_pm_rebalance = PortfolioModel.rebalance
    
    def debug_rebalance(self, mtx):
        """Debug main rebalance method."""
        debug_info['call_count'] += 1
        call_num = debug_info['call_count']
        
        print(f"\n{'='*60}")
        print(f"REBALANCE CALL #{call_num} at {mtx.time()}")
        print('='*60)
        
        # Check universe
        if hasattr(self, '_current_universe'):
            print(f"Current universe: {len(self._current_universe)} instruments")
        
        # Call original
        signals = original_rebalance(self, mtx)
        
        # Analyze signals
        if signals:
            print(f"✓ Generated {len(signals)} signals")
            
            # Count by side
            long_signals = [s for s in signals if s.side > 0]
            short_signals = [s for s in signals if s.side < 0]
            close_signals = [s for s in signals if s.side == 0]
            
            print(f"  Long: {len(long_signals)}")
            print(f"  Short: {len(short_signals)}")  
            print(f"  Close: {len(close_signals)}")
            
            # Store for analysis
            debug_info['signals_generated'].append({
                'time': mtx.time(),
                'total': len(signals),
                'long': len(long_signals),
                'short': len(short_signals),
                'close': len(close_signals),
            })
            
            # Show sample signals
            print("Sample signals:")
            for i, sig in enumerate(signals[:5]):
                side_str = "LONG" if sig.side > 0 else ("SHORT" if sig.side < 0 else "CLOSE")
                print(f"  {i+1}. {sig.instrument.symbol}: {side_str} (signal={sig.signal:.4f})")
        else:
            print("❌ No signals generated!")
        
        return signals
    
    def debug_pm_rebalance(self, mtx):
        """Debug portfolio model rebalance."""
        print(f"\n--- PortfolioModel.rebalance ---")
        print(f"Class: {self.__class__.__name__}")
        
        # Show MRO for rebalance_group method
        print("MRO for rebalance_group:")
        for cls in self.__class__.__mro__:
            if hasattr(cls, 'rebalance_group') and 'rebalance_group' in cls.__dict__:
                print(f"  → {cls.__module__}.{cls.__name__}")
        
        # Check groups
        if hasattr(self, 'groups') and len(self) > 0:
            groups = self.groups()
            ranks = self.rank_groups(mtx, groups)
            
            print(f"Groups: {len(groups)}")
            for group, rank in zip(groups, ranks):
                side = group.meta.get('side', 'unknown')
                print(f"  '{group.name}' ({side}): {len(group.instruments)} instruments, rank={rank:.2f}")
        
        result = original_pm_rebalance(self, mtx)
        print(f"Portfolio model result: {len(result)} signals")
        
        return result
    
    # Apply patches
    YourStrategy.rebalance = debug_rebalance
    PortfolioModel.rebalance = debug_pm_rebalance
    
    print("✓ Debug patches applied")

def analyze_debug_results():
    """Analyze collected debug information."""
    print(f"\n{'='*60}")
    print("DEBUG ANALYSIS")
    print('='*60)
    
    print(f"Total rebalance calls: {debug_info['call_count']}")
    
    if debug_info['signals_generated']:
        signals_df = pd.DataFrame(debug_info['signals_generated'])
        signals_df.set_index('time', inplace=True)
        
        print(f"\nSignal generation summary:")
        print(f"  Average signals per call: {signals_df['total'].mean():.1f}")
        print(f"  Average long signals: {signals_df['long'].mean():.1f}")
        print(f"  Average short signals: {signals_df['short'].mean():.1f}")
        
        # Check for imbalances
        total_long = signals_df['long'].sum()
        total_short = signals_df['short'].sum()
        if total_short == 0:
            print(f"  ❌ WARNING: No short signals generated!")
        else:
            ratio = total_long / total_short
            print(f"  Long/Short ratio: {ratio:.2f}")
        
        print(f"\nSignal timeline:")
        for idx, row in signals_df.iterrows():
            print(f"  {idx}: L={row['long']} S={row['short']} C={row['close']}")

def main():
    # Setup
    START = "2025-01-15"
    STOP = "2025-01-15 04:00:00"  # Very short for deep debugging
    
    print("Setting up debug environment...")
    setup_debug_patches()
    
    # Data setup
    reader = ReaderRegistry.get("mqdb::quantlab")
    cached_reader = CachedPrefetchReader(reader, prefetch_period="1w")
    
    print("Prefetching data...")
    cached_reader.prefetch_aux_data(
        aux_data_names=["candles", "funding_payment", "fundamental_data"],
        exchange="BINANCE.UM",
        start=START,
        stop=STOP,
    )
    
    # Create strategy
    strategy = YourStrategy(
        topn_max_symbols=30,
        fit_schedule="1h",      # Frequent for debugging
        event_schedule="1h",
        min_instruments_per_leg=3,
        instruments_per_leg=8,
    )
    
    print("Running deep debug simulation...")
    try:
        result = simulate(
            strategy,
            data={"ohlc(1h)": cached_reader, "funding_payment": cached_reader},
            aux_data=cached_reader,
            capital=100_000,
            commissions="vip0_usdt",
            instruments=["BINANCE.UM:BTCUSDT"],
            exchange="BINANCE.UM",
            start=START,
            stop=STOP,
            enable_funding=True,
            debug="WARNING",  # Reduce noise, keep our debug output
            n_jobs=1,
        )
        
        print("✓ Simulation completed")
        analyze_debug_results()
        
    except Exception as e:
        print(f"❌ Simulation failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Still analyze what we collected
        analyze_debug_results()

if __name__ == "__main__":
    main()
```

---

## Notebook Debugging

### Debug Notebook Template

For Jupyter notebook debugging, use this structure:

```python
# Cell 1: Setup with debug focus
import qubx
%qubxd
%load_ext autoreload
%autoreload 2

# Minimal imports for debugging
import pandas as pd
import numpy as np
from qubx.backtester.simulator import simulate
from qubx.core.metrics import tearsheet, portfolio_symbols
from qubx.data.helpers import CachedPrefetchReader, ReaderRegistry
from qubx.utils.charting.mpl_helpers import fig, sbp

# Import your strategy
from xincubator.models.your_strategy import YourStrategy

# Cell 2: Debug Configuration
# Use VERY short periods for notebook debugging
START = "2025-01-15"
STOP = "2025-01-15 06:00:00"  # 6 hours only!

# Minimal parameters
DEBUG_PARAMS = {
    'topn_max_symbols': 10,      # Small universe
    'fit_schedule': '1h',        # Frequent fitting
    'event_schedule': '1h',      # Frequent events  
    'min_instruments_per_leg': 2, # Low minimums
    'instruments_per_leg': 3,
}

print(f"Debug period: {START} to {STOP}")
print(f"Debug parameters: {DEBUG_PARAMS}")

# Cell 3: Data Setup with Validation
reader = ReaderRegistry.get("mqdb::quantlab")
cached_reader = CachedPrefetchReader(reader, prefetch_period="1w")

# Check prefetch result
prefetch_result = cached_reader.prefetch_aux_data(
    aux_data_names=["candles", "funding_payment", "fundamental_data"],
    exchange="BINANCE.UM",
    start=START,
    stop=STOP,
)

print(f"Prefetch results: {prefetch_result}")

# Cell 4: Run Debug Simulation
print("Running debug simulation...")
result = simulate(
    YourStrategy(**DEBUG_PARAMS),
    data={"ohlc(1h)": cached_reader, "funding_payment": cached_reader},
    aux_data=cached_reader,
    capital=100_000,
    commissions="vip0_usdt",
    instruments=["BINANCE.UM:BTCUSDT"],
    exchange="BINANCE.UM",
    start=START,
    stop=STOP,
    enable_funding=True,
    debug="DEBUG",  # Full debug output
    n_jobs=1,
)

session = result[0] if isinstance(result, list) else result
print(f"✓ Simulation completed: {session.start} to {session.stop}")

# Cell 5: Position Analysis
portfolio_log = session.portfolio_log

if portfolio_log.empty:
    print("❌ Empty portfolio log - no trades executed!")
else:
    print(f"Portfolio log shape: {portfolio_log.shape}")
    
    # Check final positions
    final_date = portfolio_log.index[-1]
    position_cols = [col for col in portfolio_log.columns if col.endswith('_Value')]
    
    positions = {}
    for col in position_cols:
        symbol = col.replace('_Value', '')
        value = portfolio_log.loc[final_date, col]
        if abs(value) > 0.01:
            positions[symbol] = value
    
    long_pos = {k: v for k, v in positions.items() if v > 0}
    short_pos = {k: v for k, v in positions.items() if v < 0}
    
    print(f"\n=== POSITION SUMMARY ===")
    print(f"Total positions: {len(positions)}")
    print(f"Long positions: {len(long_pos)}")
    print(f"Short positions: {len(short_pos)}")
    
    if positions:
        total_long = sum(v for v in positions.values() if v > 0)
        total_short = sum(v for v in positions.values() if v < 0)
        print(f"Long exposure: ${total_long:,.2f}")
        print(f"Short exposure: ${total_short:,.2f}")
        print(f"Net exposure: ${total_long + total_short:,.2f}")
        
        # Show positions
        if long_pos:
            print(f"\nLong positions:")
            for symbol, value in sorted(long_pos.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {symbol}: ${value:,.2f}")
        
        if short_pos:
            print(f"\nShort positions:")
            for symbol, value in sorted(short_pos.items(), key=lambda x: x[1])[:10]:
                print(f"  {symbol}: ${value:,.2f}")
        else:
            print("\n❌ NO SHORT POSITIONS FOUND!")

# Cell 6: Visual Analysis
if not portfolio_log.empty:
    # Plot position evolution
    fig(15, 8)
    sbp(21, 1)
    
    # Plot total exposures over time
    long_exposure = portfolio_log[[col for col in portfolio_log.columns if col.endswith('_Value')]].apply(
        lambda row: sum(v for v in row if v > 0), axis=1
    )
    short_exposure = portfolio_log[[col for col in portfolio_log.columns if col.endswith('_Value')]].apply(
        lambda row: sum(v for v in row if v < 0), axis=1
    )
    
    plt.plot(long_exposure.index, long_exposure.values, label='Long Exposure', color='green')
    plt.plot(short_exposure.index, abs(short_exposure.values), label='Short Exposure', color='red')
    plt.title('Portfolio Exposures Over Time')
    plt.legend()
    plt.ylabel('Exposure ($)')
    
    sbp(21, 2)
    # Plot net exposure
    net_exposure = long_exposure + short_exposure
    plt.plot(net_exposure.index, net_exposure.values, label='Net Exposure', color='blue')
    plt.axhline(y=0, color='black', linestyle='--', alpha=0.5)
    plt.title('Net Exposure Over Time')
    plt.ylabel('Net Exposure ($)')
    plt.xlabel('Time')
    plt.legend()
    
    plt.tight_layout()
    plt.show()

# Cell 7: Generate Tearsheet
print("Generating tearsheet for visual analysis...")
tearsheet(result, plot_leverage=True)
```

---

## Key Debugging Principles

### 1. Always Use Poetry

```bash
# Run all debug scripts with poetry
poetry run python debug_script.py
```

### 2. Start Small

- Use 1-6 hour time periods initially
- Small universe (10-20 symbols)
- Single job execution (`n_jobs=1`)
- Frequent fit/event schedules for more data points

### 3. Progressive Debugging

1. **Basic run** - Check if strategy runs without errors
2. **Position analysis** - Verify positions are created correctly
3. **Method patching** - Deep dive into specific issues
4. **Data debugging** - Check data availability and quality

### 4. Common Debug Questions

- Are short positions being created? (Check group assignment)
- Is the universe being updated? (Check fit method and data)
- Are signals being generated? (Check rebalance method)
- Is data available? (Check aux_data prefetching)

### 5. Debug Output Interpretation

- Look for "Fitting groups", "Long side", "Short side" messages
- Check for "Insufficient instruments" warnings  
- Monitor signal generation patterns
- Verify weight sums match expected ranks

Remember: **Debugging is iterative!** Start with basic checks, then progressively add more detailed tracing until you isolate the issue.
