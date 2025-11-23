# Qubx Research Notebooks Guide

## Overview

This guide covers conventions for creating and organizing Jupyter notebooks in Qubx research projects. Following these patterns ensures consistency, reproducibility, and easy collaboration.

## Notebook Naming Convention

### Pattern: `a.b.c <Topic or short research idea>.ipynb`

The `a.b.c` prefix denotes the **research tree structure**:

| Level | Meaning | Example |
|-------|---------|---------|
| `a` | Major research direction | `1.0.0` = first direction |
| `b` | Sub-branch/feature | `1.1.0` = first branch of direction 1 |
| `c` | Iteration/refinement | `1.1.1` = refinement of branch 1.1 |

### Research Tree Example

```
1.0.0 Initial exploration.ipynb           # - Starting point
├── 1.1.0 Feature 1 deep research.ipynb   # - Branch: investigating feature 1
│   ├── 1.1.1 Feature 1 parameter tuning.ipynb
│   └── 1.1.2 Feature 1 different timeframes.ipynb
├── 1.2.0 Feature 2 investigation.ipynb   # - Branch: investigating feature 2
│   └── 1.2.1 Feature 2 with ML.ipynb
└── 1.3.0 Combining features.ipynb        # - Branch: combining insights

2.0.0 New idea Initial exploration.ipynb  # - Completely new research direction
├── 2.1.0 New idea first branch.ipynb
└── 2.2.0 New idea alternative approach.ipynb
```

### Naming Rules

1. **Always start with version number**: `a.b.c `
2. **Descriptive topic after version**: short but meaningful
3. **Use spaces in name** (not underscores for readability)
4. **Keep names concise**: aim for < 50 characters

**Good examples:**
- `1.0.0 Momentum factor exploration.ipynb`
- `1.1.0 Momentum with volume filter.ipynb`
- `2.0.0 Mean reversion signals.ipynb`

**Bad examples:**
- `exploration.ipynb` (no version, too generic)
- `1.0.0.ipynb` (no description)
- `1.0.0_momentum_factor_exploration_with_different_timeframes_and_filters.ipynb` (too long, underscores)

## Folder Structure

### Pattern: `<project>/research/<general_topic>/<sub_topic>/`

```
~/projects/<project_name>/
└── research/
    ├── momentum/                      # - General research topic
    │   ├── quicktrade/                # - Sub-topic
    │   │   ├── exploration/           # - Optional: pure exploration notebooks
    │   │   │   ├── 1.0.0 Initial signals.ipynb
    │   │   │   └── 1.1.0 Signal filtering.ipynb
    │   │   ├── trading/               # - Optional: strategy-focused notebooks
    │   │   │   ├── 1.0.0 Strategy backtest.ipynb
    │   │   │   └── 1.1.0 Parameter optimization.ipynb
    │   │   └── results/               # - Exported results, plots, etc.
    │   └── trend_following/
    │       └── ...
    ├── altdata/                       # - Another general topic
    │   ├── funding_rates/
    │   └── open_interest/
    └── misc/                          # - Miscellaneous experiments
        └── ...
```

### Subdirectory Guidelines

| Directory | Purpose |
|-----------|---------|
| `exploration/` | Pure data exploration, feature discovery, EDA |
| `trading/` | Strategy development, backtesting, optimization |
| `results/` | Exported plots, CSVs, saved models |

**Note:** `exploration/` and `trading/` subdirs are optional - use them when research naturally splits into exploration vs strategy development phases.

## First Cell Template

Every research notebook should start with a standardized first cell containing imports:

```python
# - static section (rarely change, no autoreload needed)
import qubx
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# - qubx utilities
from qubx.pandaz.utils import srows, scols, ohlc_resample, continuous_session_splits

# - Storage API for data access (NOT loader!)
from qubx.data.registry import StorageRegistry
from qubx.data.transformers import PandasFrame, OHLCVSeries, TypedRecords, TickSeries
from qubx.core.basics import DataType

# - visualization (choose one approach - see Visualization section below)
from qubx.utils.charting.lookinglass import LookingGlass
# OR for matplotlib with seaborn:
# from qubx.utils.charting.mpl_helpers import fig, sbp, ohlc_plot

# - if simulation needed
from qubx.backtester.simulator import simulate

import seaborn as sns
%qubxd

# - dynamic section (project imports that may be modified during research)
%load_ext autoreload
%autoreload 2

# - project-specific imports go here (after autoreload)
from xincubator.research.momentum import quicktrade_utils
from xincubator.indicators.momentum import rsi_divergence
```

### Section Explanation

| Section | Purpose | Autoreload? |
|---------|---------|-------------|
| Static | Standard libraries (qubx, pandas, numpy) | No |
| qubx utilities | Data manipulation helpers | No |
| Storage API | Data access (StorageRegistry, transformers) | No |
| visualization | Charting tools (LookingGlass, seaborn) | No |
| Dynamic | Project code under active development | Yes |

### Key Points

1. **Use Storage API for data, NOT `loader()`**
   - `loader()` is only for `simulate()` calls
   - StorageRegistry is for research data access

2. **`%qubxd`** - Qubx display magic for enhanced output

3. **Autoreload placement** - Import `%load_ext autoreload` AFTER static imports

4. **Project imports last** - All `from <project>...` imports go after `%autoreload 2`

## Data Access in Notebooks

> **CRITICAL**: Use Storage API for research, `loader()` only for simulation!

### Quick Data Access Pattern

```python
# - get storage (do this ONCE, then reuse)
storage = StorageRegistry.get("qdb::quantlab")
reader = storage["BINANCE.UM", "SWAP"]

# - discover data
symbols = reader.get_data_id("ohlc(1h)")
start, end = reader.get_time_range("BTCUSDT", "ohlc(1h)")

# - load data as DataFrame
df = reader.read(
    ["BTCUSDT", "ETHUSDT"],
    "ohlc(1h)",
    start="2024-01-01",
    stop="2024-06-01"
).transform(PandasFrame())
```

### Best Practice: Create Storage/Reader Once

**DO NOT** recreate storage and reader every time you load data. Create them once in a separate cell, then reuse:

```python
# - Cell 1: Create storage and reader (run once)
storage = StorageRegistry.get("qdb::quantlab")
ohlc_reader = storage["BINANCE.UM", "SWAP"]
fund_reader = storage["COINGECKO", "FUNDAMENTAL"]

# - Cell 2+: Reuse reader for multiple queries
df1 = ohlc_reader.read(["BTCUSDT"], "ohlc(1h)", "2024-01-01", "2024-06-01").transform(PandasFrame())
df2 = ohlc_reader.read(["ETHUSDT"], "ohlc(1h)", "2024-01-01", "2024-06-01").transform(PandasFrame())
fund = fund_reader.read(assets, "fundamental", start, stop).transform(PandasFrame(True))
```

### When You Need Simulation

```python
# - for quick smoke tests, use loader() with simulate()
from qubx.data import loader

ldr = loader("BINANCE.UM", "1h", source="mqdb::quantlab")

r = simulate(
    MyStrategy(),
    data={"ohlc(1h)": ldr},
    instruments=["BINANCE.UM:BTCUSDT"],
    capital=10000,
    start="2024-01-01",
    stop="2024-06-01"
)
```

See `~/.claude/shared/qubx-data.md` for complete Storage API documentation.

## Visualization

Qubx provides two main visualization approaches. **When creating notebooks, always ask which approach is preferred.**

### Option 1: LookingGlass (Interactive - Plotly/Matplotlib)

Best for: Interactive exploration, OHLC charts with overlays, multi-panel layouts.

```python
from qubx.utils.charting.lookinglass import LookingGlass

# - Basic OHLC with studies (default: plotly backend)
LookingGlass(
    ohlc_df,                          # - Master: OHLC data
    {"RSI": [rsi_series]},            # - Studies: dict of panels
).look().hover(h=500)

# - With overlays and arrows
LookingGlass(
    [ohlc_df,
     "arrow-down", 'r', bear_signals,  # - Red down arrows
     "arrow-up", 'g', bull_signals],   # - Green up arrows
    {"Volume": ["bar", 'g', volume]},
).look("2025-01-01", "30d").hover(h=600)

# - Matplotlib backend (for combining with seaborn)
from qubx.utils.charting.mpl_helpers import fig
fig(21, 12)  # - Create figure first
LookingGlass(
    [ohlc_df, "arrow-down", 'w', signals],
    {"Indicator": ['w', indicator]},
    backend='mpl'
).look(title="My Chart").hover(h=500).show()
```

**LookingGlass Features:**
- Auto-detects OHLC DataFrames → candlestick chart
- Study panels: dict keys become panel titles
- Plot styles: `"line"`, `"bar"`, `"area"`, `"step"`, `"dots"`, `"arrow-up"`, `"arrow-down"`
- Colors: matplotlib color names or hex (`'r'`, `'g'`, `'w'`, `'#ff00d0'`)
- Zoom: `.look("2025-01-01", "30d")` or `.look("1d", "2025-03-15", "1d")` (before, at, after)
- Hover: `.hover(h=500, w=1500, legend=True)`

### Option 2: Matplotlib Helpers (Static - with Seaborn)

Best for: Statistical plots, distribution analysis, combining with seaborn, publication-quality figures.

```python
from qubx.utils.charting.mpl_helpers import fig, sbp, ohlc_plot
import seaborn as sns

# - Create figure with custom size
fig(16, 8)  # - width=16, height=8

# - Subplot grid (similar to MATLAB)
sbp(21, 1)  # - 2 rows, 1 col, position 1
ohlc_plot(ohlc_df)  # - Plot OHLC candlesticks
plt.title("Price")

sbp(21, 2)  # - 2 rows, 1 col, position 2
plt.plot(indicator)
plt.title("Indicator")

# - More complex grid
fig(16, 10)
sbp(22, 1)  # - 2x2 grid, position 1 (top-left)
sbp(22, 2)  # - 2x2 grid, position 2 (top-right)
sbp(22, 3)  # - 2x2 grid, position 3 (bottom-left)
sbp(22, 4)  # - 2x2 grid, position 4 (bottom-right)

# - Combining with seaborn
fig(12, 5)
sbp(12, 1)
sns.kdeplot(returns, label='Returns')
sbp(12, 2)
sns.heatmap(correlation_matrix)
```

**Matplotlib Helper Functions:**
- `fig(w, h, dpi=96)` - Create figure (use instead of `plt.figure()`)
- `sbp(shape, loc, r=1, c=1)` - Subplot (shape=21 means 2 rows, 1 col; loc=1,2,...)
- `ohlc_plot(df)` - Plot OHLC candlesticks
- `vline(ax, x, c)` - Vertical line
- `hline(*zs)` - Horizontal line(s)

### When to Use Which

| Use Case | Recommended |
|----------|-------------|
| OHLC with overlays (signals, entries/exits) | LookingGlass |
| Interactive zoom/pan exploration | LookingGlass (plotly) |
| Statistical distributions (KDE, histograms) | Matplotlib + seaborn |
| Correlation heatmaps | Matplotlib + seaborn |
| Publication-quality static figures | Matplotlib |
| Combining OHLC with statistical analysis | LookingGlass (mpl backend) + seaborn |

### Visualization Import Patterns

```python
# - LookingGlass only (most common for OHLC analysis)
from qubx.utils.charting.lookinglass import LookingGlass

# - Matplotlib helpers + seaborn (for statistical analysis)
from qubx.utils.charting.mpl_helpers import fig, sbp, ohlc_plot
import seaborn as sns

# - Both (for mixed analysis)
from qubx.utils.charting.lookinglass import LookingGlass
from qubx.utils.charting.mpl_helpers import fig, sbp, ohlc_plot
import seaborn as sns
```

## Notebook Structure

Organize notebooks with clear markdown sections to make research easy to follow.

### Section Hierarchy

| Level | Usage | Example |
|-------|-------|---------|
| `#` | Notebook title (optional, usually in filename) | `# Pairs Momentum Research` |
| `##` | Main sections/topics | `## Data Loading`, `## Signal Analysis` |
| `###` | Subsections | `### BTC \| ETH`, `### Parameter Tuning` |
| `####` | Sub-subsections (rare) | `#### Sensitivity Analysis` |

### Main Section Format

Use a horizontal line after main section headers for visual separation:

```markdown
## Trading Signals
<hr style="border-bottom: 2px dashed #6295fbff; color:green;"/>
```

### Highlighting Important Sections

Use colored font for key results or conclusions:

```markdown
## <font color="orange">Final Results</font>
<hr style="border-bottom: 2px dashed #fb9262ff; color:green;"/>
```

### Typical Notebook Structure

```
[Code Cell] - Imports (static + dynamic)
[Code Cell] - Data loading

## Data Exploration
<hr style="border-bottom: 2px dashed #6295fbff; color:green;"/>
[Markdown] - Brief description of what we're exploring
[Code Cell] - Load/prepare data
[Code Cell] - Visualizations
[Markdown] - Observations/findings

## Feature Engineering
<hr style="border-bottom: 2px dashed #6295fbff; color:green;"/>
[Markdown] - Approach description
[Code Cell] - Feature calculations
[Code Cell] - Feature analysis

### Feature 1: Momentum
[Code Cell] - Momentum calculations
[Markdown] - Notes on results

### Feature 2: Volatility
[Code Cell] - Volatility calculations

## Signal Generation
<hr style="border-bottom: 2px dashed #6295fbff; color:green;"/>
[Code Cell] - Signal logic
[Code Cell] - Visualize signals

## Backtesting
<hr style="border-bottom: 2px dashed #6295fbff; color:green;"/>

### Experiment 1
[Code Cell] - Run backtest
[Code Cell] - Results

### Experiment 2
[Code Cell] - Run backtest
[Code Cell] - Results

## <font color="orange">Conclusions</font>
<hr style="border-bottom: 2px dashed #6295fbff; color:green;"/>
[Markdown] - Summary of findings
[Markdown] - Next steps
```

### Markdown Cell Guidelines

1. **Before code blocks**: Briefly explain what the code does
2. **After results**: Note observations, insights, or concerns
3. **Keep it concise**: 1-3 sentences per markdown cell
4. **Use bullet points** for multiple observations

**Good examples:**
```markdown
Let's compare BTC / ETH momentums
```

```markdown
- Note: KAMA as ATR smoother leads to better Sharpe !
```

```markdown
Relative momentum difference has enough fat tails
```

**Avoid:**
- Long paragraphs
- Repeating what the code obviously does
- Empty markdown cells

## Research Log

Each research folder should have a `research-log.md` (or `description.md`) file to track progress, findings, and next steps.

**Location**: `research/<topic>/<subtopic>/research-log.md`

**When to update**: Ask if the log should be updated after significant results are obtained.

### Research Log Structure

```markdown
# Research Topic Title
#tag1 #tag2 #tag3

Brief description of the research idea (2-5 sentences).

## Main Concept
- Core hypothesis or approach
- Key assumptions
- Expected outcomes

## Links
- Indicator implementation: [indicator name](<../../../src/project/indicators/file.py>)
- Strategy implementation: [strategy name](<../../../src/project/models/type/strategy.py>)
- Initial exploration: [notebook description](<exploration/1.0 Initial exploration.ipynb>)
- Trading tests: [test description](<trading/1.0 Strategy test.ipynb>)

## Research Progress

### 2025-01-15: Initial exploration
- Tested momentum indicator on BTC/ETH pair
- Correlation: 0.84 (hourly log returns 2020-2023)
- [See notebook](<exploration/1.0 Initial exploration.ipynb>)

### 2025-01-20: Signal generation
- Threshold reversion signal shows promise
- Sharpe ~1.8 on ETH/SOL portfolio
- [See results](<trading/1.0 Strategy test.ipynb#cell-id>)
> Finding: KAMA smoother leads to better Sharpe than simple MA

### 2025-01-25: Parameter optimization
- Tested lookback periods: 12h, 24h, 48h
- Best results with 24h lookback
- [See analysis](<exploration/1.2 Parameter tuning.ipynb>)

## Tasks / Next Steps
- [ ] Test on larger universe (top 20 symbols)
- [ ] Add volume confirmation filter
- [x] Compare MA vs KAMA smoothing | [results](<trading/1.0 Strategy test.ipynb>)
  > KAMA shows 15% better Sharpe
- [x] Test short positions | [results](<trading/1.1 Short test.ipynb>)
  > Short enabled led to degradation (Sharpe 1, max dd -> 26%)
```

### Required Tags

Add relevant tags after the title:

| Tag | When to use |
|-----|-------------|
| `#indicator` | Research involves indicator development |
| `#oscillator` | Oscillator-type indicators (RSI, stochastic, etc.) |
| `#momentum` | Momentum-based research |
| `#mean-reversion` | Mean reversion strategies |
| `#portfolio` | Portfolio construction/selection |
| `#backtest` | Results include backtest data |
| `#strategy` | Research related to trading strategy |
| `#feature` | Feature engineering research |
| `#ml` | Machine learning approaches |

**Example tags:**
```markdown
# Pairs Momentum Strategy
#momentum #portfolio #strategy #backtest
```

```markdown
# RSI Divergence Indicator
#indicator #oscillator
```

### Link Formats

**Link to notebook:**
```markdown
[Brief description](<relative/path/to/notebook.ipynb>)
```

**Link to specific cell (for GitHub):**
```markdown
[Result description](<path/to/notebook.ipynb#cell-id>)
```

**Link to code:**
```markdown
[Indicator implementation](<../../../src/project/indicators/file.py>)
[Strategy line 151](<../../../src/project/models/strategy.py#151>)
```

**Link to related research:**
```markdown
[See related research](../../other_topic/research-log.md)
```

### Progress Entry Format

Each progress entry should include:
1. **Date** as header: `### 2025-01-15: Brief title`
2. **Key findings** as bullet points
3. **Link to notebook** with results
4. **Quoted conclusions** using `>` for important findings

```markdown
### 2025-01-15: Correlation analysis
- BTC/ETH correlation: 0.84 (2020-2023)
- SOL/ETH correlation: 0.67
- [See notebook](<exploration/1.0 Correlation analysis.ipynb>)
> Finding: High correlation pairs show better mean-reversion properties
```

### Highlight Colors for Sections

Use colored headers for important topics:
```markdown
## <font color="red">Important Finding</font>
## <font color="green">Positive Results</font>
## <font color="orange">Needs Further Research</font>
```

## Code Organization

### Rule: Keep Notebooks Clean

Notebooks should focus on:
- **Exploration** - visualizations, quick experiments
- **Analysis** - results interpretation, comparisons
- **Documentation** - explaining findings, conclusions

### Avoid Long Functions in Notebooks

**Bad practice:**
```python
# In notebook cell - DON'T DO THIS
def complex_feature_engineering(df, param1, param2, param3):
    """200 lines of code..."""
    # ... lots of processing
    return result
```

**Good practice:**
```python
# In src/<project>/research/<topic>/<subtopic>_utils.py
def complex_feature_engineering(df, param1, param2, param3):
    """200 lines of code..."""
    # ... lots of processing
    return result

# In notebook cell - just import and use
from xincubator.research.momentum import quicktrade_utils as qtu

result = qtu.complex_feature_engineering(df, p1, p2, p3)
```

### Research Utils Location

```
src/<project_module>/
└── research/
    ├── __init__.py
    ├── common.py                     # - Shared research utilities
    └── momentum/
        ├── __init__.py
        ├── quicktrade_utils.py       # - Utils for momentum/quicktrade/ notebooks
        └── trend_following_utils.py  # - Utils for momentum/trend_following/ notebooks
```

### When to Extract Code

Move code to `src/` when:
- Function is > 20-30 lines
- Code is reused across multiple cells
- Code is reused across multiple notebooks
- Logic needs testing
- You want autoreload to work

## Common Patterns

### Pattern 1: Data Exploration

```python
# Cell 1: Standard imports (see First Cell Template)

# Cell 2: Load data
storage = StorageRegistry.get("qdb::quantlab")
reader = storage["BINANCE.UM", "SWAP"]

df = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "now").transform(PandasFrame())

# Cell 3: Basic analysis
df["returns"] = df["close"].pct_change()
df["volatility"] = df["returns"].rolling(24).std()

# Cell 4: Visualization
fig, axes = plt.subplots(2, 1, figsize=(12, 8))
df["close"].plot(ax=axes[0], title="Price")
df["volatility"].plot(ax=axes[1], title="Volatility")
plt.tight_layout()
```

### Pattern 2: Feature Engineering

```python
# Cell 1: Standard imports

# Cell 2: Load data (same as above)

# Cell 3: Engineer features
from xincubator.research.momentum import feature_utils as fu

features = fu.compute_momentum_features(df)
features = fu.add_volume_metrics(features, df)

# Cell 4: Analyze features
features.describe()
```

### Pattern 3: Quick Strategy Test

```python
# Cell 1: Standard imports + simulator

# Cell 2: Load strategy
from xincubator.models.momentum.quicktrade import model0

# Cell 3: Quick backtest
from qubx.data import loader

ldr = loader("BINANCE.UM", "1h", source="mqdb::quantlab")

r = simulate(
    model0.QuickTradeStrategy(param1=10, param2=20),
    data={"ohlc(1h)": ldr},
    instruments=["BINANCE.UM:BTCUSDT"],
    capital=10000,
    start="2024-01-01",
    stop="2024-06-01"
)

# Cell 4: Analyze results
r.performance()
```

## Best Practices

### Do's

1. **Version your notebooks** with `a.b.c` prefix
2. **Use Storage API** for data access in research
3. **Keep imports organized** with static/dynamic sections
4. **Extract complex code** to `src/research/` utils
5. **Document findings** in markdown cells
6. **Save intermediate results** to `results/` folder
7. **Clear outputs** before committing (optional but recommended)

### Don'ts

1. **Don't use `loader()`** except in `simulate()` calls
2. **Don't write long functions** directly in notebook cells
3. **Don't skip version numbers** in naming
4. **Don't put `.py` files** in `research/` folders
5. **Don't hardcode paths** - use relative paths or config
6. **Don't mix exploration and production code** - keep them separate

## Quick Reference

### File Locations

| What | Where |
|------|-------|
| Notebooks | `research/<topic>/<subtopic>/` |
| Research utils | `src/<project>/research/<topic>_utils.py` |
| Indicators | `src/<project>/indicators/` |
| Strategies | `src/<project>/models/<type>/` |
| Results | `research/<topic>/<subtopic>/results/` |

### Imports Cheatsheet

```python
# === STATIC (no autoreload) ===
import qubx
import pandas as pd
import numpy as np
from qubx.pandaz.utils import srows, scols
from qubx.data.registry import StorageRegistry
from qubx.data.transformers import PandasFrame

# - Visualization (choose based on needs)
from qubx.utils.charting.lookinglass import LookingGlass  # - Interactive OHLC
from qubx.utils.charting.mpl_helpers import fig, sbp, ohlc_plot  # - Matplotlib
import seaborn as sns
%qubxd

# === DYNAMIC (with autoreload) ===
%load_ext autoreload
%autoreload 2
from <project>.research.<topic> import <utils>
from <project>.indicators import <indicator>
```

### Data Access Cheatsheet

```python
# Research data access
storage = StorageRegistry.get("qdb::quantlab")
reader = storage["BINANCE.UM", "SWAP"]
df = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "now").transform(PandasFrame())

# Simulation data access (ONLY for simulate())
from qubx.data import loader
ldr = loader("BINANCE.UM", "1h", source="mqdb::quantlab")
```

## Working with Notebooks via XMCP

XMCP is an MCP server that allows Claude Code to interact directly with Jupyter notebooks running on JupyterHub.

### Available Tools

| Tool | Description |
|------|-------------|
| `jupyter_list_notebooks` | List notebooks in a directory |
| `jupyter_get_notebook_info` | Get notebook metadata and cell summary |
| `jupyter_read_cell` | Read content of a specific cell |
| `jupyter_read_all_cells` | Read all cells from a notebook |
| `jupyter_append_cell` | Add a new cell at the end |
| `jupyter_insert_cell` | Insert cell at specific position |
| `jupyter_update_cell` | Update existing cell content |
| `jupyter_delete_cell` | Delete a cell |
| `jupyter_connect_notebook` | Connect to notebook's kernel |
| `jupyter_execute_cell` | Execute a specific cell |
| `jupyter_execute_code` | Execute arbitrary code in kernel |
| `jupyter_list_kernels` | List running kernels |

### Common Workflows

**1. Explore a notebook:**
```
> Show me the structure of research/momentum/1.0 Exploration.ipynb
> Read cell 5 from that notebook
```

**2. Execute cells:**
```
> Connect to research/momentum/1.0 Exploration.ipynb and execute cell 0 (imports)
> Execute cells 1-3 in sequence
```

**3. Add new analysis:**
```
> Append a code cell with: df.describe()
> Insert a markdown cell at position 5 with section header "## Results"
```

**4. Run code interactively:**
```
> Execute this code in the notebook's kernel:
  storage = StorageRegistry.get("qdb::quantlab")
  reader = storage["BINANCE.UM", "SWAP"]
  df = reader.read("BTCUSDT", "ohlc(1h)", "2024-01-01", "now").transform(PandasFrame())
  print(df.shape)
```

### Setup Requirements

1. **Jupyter Server running**: JupyterHub or standalone Jupyter
2. **XMCP configured**: `~/devs/aix/.env` with correct URL and token
3. **MCP registered**: `claude mcp add xmcp -- python -m xmcp.server`
4. **MCP permissions**: Add `mcp__xmcp` to allowlist in `~/.claude/settings.json`:
   ```json
   {
     "permissions": {
       "allow": ["mcp__xmcp"]
     }
   }
   ```

### Kernel Selection

XMCP respects the notebook's kernel metadata when creating sessions:

1. **Set kernel in notebook metadata** - Ensure notebook has correct `kernelspec.name`:
   ```python
   # - Check/update notebook kernel metadata
   import json
   with open('notebook.ipynb') as f:
       nb = json.load(f)
   nb['metadata']['kernelspec'] = {
       'display_name': 'Python (xmetals)',
       'language': 'python',
       'name': 'xmetals'  # - This is the key field
   }
   with open('notebook.ipynb', 'w') as f:
       json.dump(nb, f, indent=1)
   ```

2. **Create project kernel** (if not exists):
   ```bash
   cd ~/projects/<project>
   poetry run python -m ipykernel install --user --name <project> --display-name "Python (<project>)"
   ```

3. **List available kernels**:
   ```bash
   jupyter kernelspec list
   ```

### Sharing Kernel Between XMCP and VS Code

To work collaboratively (both Claude and user on same kernel):

1. **Claude connects first**: Use `jupyter_connect_notebook` - creates session with correct kernel
2. **User connects in VS Code**: Open notebook → Select Kernel → Choose "Existing Jupyter Server" → Select the running kernel
3. **Verify shared state**: Set a variable in VS Code, read it via xmcp (or vice versa)

**Example verification:**
```
# - In VS Code
a = 42

# - Via xmcp
> Execute: print(a)
# - Should print: 42
```

### Checking Jupyter Connection

```bash
# - Show running Jupyter servers
jupyter server list

# - Check MCP status
claude mcp list

# - List running kernels (via xmcp)
> Use jupyter_list_kernels tool
```

### Important Notes

- **Kernel state**: Executing cells maintains state in the kernel (variables persist)
- **Cell indices**: All cell indices are 0-based
- **Jupyter token**: Token changes on server restart - update `.env` if connection fails
- **Timeout**: Long-running cells have 300s timeout (configurable)
- **Notebook paths**: Use paths relative to Jupyter root (e.g., `projects/xmetals/research/...`)

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Wrong kernel (python3 instead of project kernel) | Check notebook metadata has correct `kernelspec.name`, delete old session, reconnect |
| "Module not found" errors | Verify kernel points to correct venv: `jupyter kernelspec list` then check `kernel.json` |
| Can't see kernel in VS Code | Kernel must be attached to a session - use `jupyter_connect_notebook` first |
| Old session persists | Stop kernel with `jupyter_stop_kernel`, then reconnect |
| xmcp tools not available | Add `mcp__xmcp` to permissions in `~/.claude/settings.json`, restart Claude Code |

### Example Session

```
User: Connect to research/altdata/1.0 OI Analysis.ipynb

Claude: [Uses jupyter_connect_notebook]
Connected to notebook with kernel_id: abc123

User: Execute the first 3 cells (imports and data loading)

Claude: [Uses jupyter_execute_cell for cells 0, 1, 2]
Cell 0: Imports loaded successfully
Cell 1: Data loaded - 50000 rows
Cell 2: Preprocessing complete

User: Now add a cell that calculates correlation matrix and execute it

Claude: [Uses jupyter_append_cell then jupyter_execute_cell]
Added cell at index 15, executed successfully:
          BTCUSDT  ETHUSDT
BTCUSDT   1.0000   0.8518
ETHUSDT   0.8518   1.0000
```

## Related Documentation

- **Data Access**: `~/.claude/shared/qubx-data.md`
- **Strategy Building**: `~/.claude/shared/qubx-strategy.md`
- **Config Files**: `~/.claude/shared/qubx-config.md`
- **XMCP Source**: `~/devs/aix/src/xmcp/`
