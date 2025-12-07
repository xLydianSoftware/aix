# Test Data Structure

## Nested Directory Layout

The test data in `tests/data/knowledge1/` now has a realistic 2-3 level nested structure:

```
tests/data/knowledge1/
├── research/
│   ├── options/
│   │   ├── SC01_Continuous_Processes_Brownian_Motion.md
│   │   ├── SC02_Ito_Formula_Product_Rule.md
│   │   └── SC03_Change_of_Measure_CMG.md
│   └── risk-management/
│       └── test_risk_management.md
└── strategies/
    ├── backtests/
    │   └── test_backtest.md
    └── ideas/
        └── test_ideas.md
```

## Directory Levels

**Level 1**: `research/`, `strategies/`
**Level 2**: `options/`, `risk-management/`, `backtests/`, `ideas/`
**Level 3**: Markdown files

## File Contents

### research/options/ (3 files)
Advanced stochastic calculus and options pricing documents from xfiles:
- SC01: Continuous Processes & Brownian Motion
- SC02: Itô Formula & Product Rule
- SC03: Change of Measure & CMG

### research/risk-management/ (1 file)
Custom test file with:
- Tags: `#risk-management`, `#framework`
- Type: RESEARCH
- Content: Risk management framework with position sizing, stop losses, diversification

### strategies/backtests/ (1 file)
Custom test file with complete metadata:
- Tags: `#backtest`, `#qubx`, `#strategy`, `#mean-reversion`
- Type: BACKTEST
- Metrics: sharpe=2.35, cagr=18.5, drawdown=-12.3
- Strategy: MeanReversionMA

### strategies/ideas/ (1 file)
Custom test file with multiple ideas:
- Tags: `#idea`, `#research`, `#orderbook-imbalance`, `#volatility`, `#market-making`
- Type: IDEA
- Content: Trading ideas collection with 3 distinct ideas

## Benefits

1. **Realistic Structure**: Mimics actual knowledge base organization
2. **Tests Recursion**: Verifies recursive directory traversal works correctly
3. **Category Organization**: Files grouped by topic (research, strategies)
4. **Sub-categorization**: Further organized by type (options, backtests, ideas)
5. **Path Testing**: Ensures indexing and search work with nested paths

## Test Coverage

All 22 tests work correctly with this structure:
- ✅ Recursive indexing
- ✅ File path resolution
- ✅ Metadata extraction from nested files
- ✅ Search across nested directories
- ✅ Change detection in nested structure

## Usage in Tests

Tests reference files using nested paths:
```python
test_file = TEST_DATA_DIR / "strategies" / "backtests" / "test_backtest.md"
```

The `recursive=True` parameter ensures all nested files are indexed.
