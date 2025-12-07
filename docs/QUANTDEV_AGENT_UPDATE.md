# QuantDev Agent Update - RAG Integration

## Updated Reference

**File:** `~/.claude/agents/quantdev.md`
**Line:** 19-21

### Old:
```markdown
**XMCP tools**: When working with notebooks, use `jupyter_*` MCP tools to connect, execute cells, and interact with running Jupyter kernels directly.
```

### New:
```markdown
**XMCP tools**:
- **Jupyter**: Use `jupyter_*` MCP tools to connect, execute cells, and interact with running Jupyter kernels directly
- **Markdown Search**: Use `markdown_*` MCP tools for semantic search across research notes, backtests, and documentation with tag/metadata filtering
```

## RAG Tools Available to Rey Agent

### Markdown Search Tools (7 tools)

**1. markdown_index_directory**
- Index research notes, backtest results, and documentation
- Automatic change detection and incremental updates
- Example: Index backtests directory
  ```python
  await markdown_index_directory("/backtests/momentum/nimble/", recursive=True)
  ```

**2. markdown_search**
- Semantic search across indexed documents
- Tag filtering (#backtest, #strategy, #risk-management)
- Metadata filtering (sharpe > 1.5, Type=BACKTEST)
- Example: Find high-Sharpe backtests
  ```python
  await markdown_search(
      directory="/backtests/momentum/nimble/",
      query="high sharpe ratio strategies",
      metadata_filters={"sharpe > 2.0": None},
      limit=10
  )
  ```

**3. markdown_get_tags**
- Extract all tags from indexed documents
- Example: See all tags in backtest directory
  ```python
  await markdown_get_tags("/backtests/momentum/nimble/")
  ```

**4. markdown_list_indexes**
- List all indexed directories with stats
- Example: See what's been indexed
  ```python
  await markdown_list_indexes()
  ```

**5. markdown_refresh_index**
- Manually force refresh of index
- Example: Update after adding new backtests
  ```python
  await markdown_refresh_index("/backtests/momentum/nimble/")
  ```

**6. markdown_get_metadata_fields**
- List available metadata fields for filtering
- Example: See what metadata fields exist
  ```python
  await markdown_get_metadata_fields("/backtests/momentum/nimble/")
  ```

**7. markdown_drop_index**
- Clean up index for directory
- Example: Remove old index
  ```python
  await markdown_drop_index("/backtests/momentum/nimble/")
  ```

## Use Cases for Rey

### 1. Finding Similar Strategies
```python
# Find backtests similar to current strategy
await markdown_search(
    directory="/backtests/",
    query="momentum strategy with inverse volatility sizing",
    tags=["#momentum"],
    limit=5
)
```

### 2. Research Knowledge Base
```python
# Search research notes for specific topics
await markdown_search(
    directory="~/projects/xfiles/",
    query="mean reversion entry signals",
    tags=["#idea", "#strategy"],
    limit=10
)
```

### 3. Backtest Analysis
```python
# Find high-performing backtests
await markdown_search(
    directory="/backtests/",
    query="strategy performance metrics",
    metadata_filters={"sharpe > 1.5": None, "Type": "BACKTEST"},
    limit=20
)
```

### 4. Risk Management Research
```python
# Find all risk management related notes
await markdown_search(
    directory="~/projects/xfiles/",
    query="position sizing and risk management",
    tags=["#risk-management"],
    limit=15
)
```

### 5. Documentation Search
```python
# Find documentation on specific topics
await markdown_search(
    directory="~/devs/Qubx/docs/",
    query="streaming indicators implementation",
    limit=10
)
```

## Integration with Existing Workflow

Rey can now:
1. **Search backtest results** semantically instead of just listing files
2. **Find similar strategies** based on description and metadata
3. **Access research notes** quickly by searching for concepts
4. **Filter by tags** (#backtest, #strategy, #qubx, etc.)
5. **Filter by metrics** (sharpe, cagr, drawdown, etc.)

This complements the existing BacktestsResultsManager by enabling semantic search across all markdown documentation, not just structured backtest results.

## Configuration

RAG tools are configured via environment variables in `.env`:
```bash
RAG_CACHE_DIR=~/.aix/knowledge
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=100
RAG_AUTO_REFRESH=true
RAG_AUTO_REFRESH_INTERVAL=300
```

Indexes are cached in `~/.aix/knowledge/` with automatic refresh every 5 minutes.
