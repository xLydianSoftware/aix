# XLMCP Usage Guide

## Installation

### Requirements

- Python 3.10+
- Jupyter Server or JupyterHub (for Jupyter tools)
- Claude Code (for MCP integration)

### Install XLMCP

**From PyPI (Recommended):**

```bash
# - Install with pip
pip install xlmcp

# - Or with uv
uv pip install xlmcp
```

**From Source (Development):**

```bash
cd ~/devs/aix

# - Install in editable mode with uv (recommended)
uv pip install -e .

# - Or with pip
pip install -e .
```

This installs:
- `xlmcp` - CLI for server management
- `xlmcp-server` - MCP server executable
- All 24 MCP tools (16 Jupyter + 8 Knowledge RAG)

### Verify Installation

```bash
# - Check CLI is available
xlmcp --help

# - List all tools
xlmcp ls

# - Should show: Total Tools: 24
```

## Configuration

### Environment Variables (.env)

Create or edit `/home/quant0/devs/aix/.env`:

```bash
# - Jupyter Configuration
JUPYTER_SERVER_URL=http://127.0.0.1:51421/user/quant0
JUPYTER_API_TOKEN=your-token-here
JUPYTER_NOTEBOOK_DIR=~/
JUPYTER_ALLOWED_DIRS=~/projects,~/devs,~/research,~/
JUPYTER_WS_TIMEOUT=30
JUPYTER_EXEC_TIMEOUT=300

# - RAG Configuration
RAG_CACHE_DIR=~/.aix/knowledge
RAG_CHUNK_SIZE=4096
RAG_CHUNK_OVERLAP=512
RAG_AUTO_REFRESH=true
RAG_AUTO_REFRESH_INTERVAL=300
RAG_DEFAULT_SEARCH_LIMIT=10
RAG_DEFAULT_SIMILARITY_THRESHOLD=0.5
RAG_MAX_FILE_SIZE_MB=5
RAG_SKIP_NOTEBOOK_OUTPUTS=false

# - MCP Configuration
MCP_TRANSPORT=stdio
MCP_HTTP_PORT=8765
MCP_MAX_OUTPUT_TOKENS=25000
```

### Get Jupyter API Token

**For Jupyter Server:**
```bash
jupyter server list
# - Output shows: http://127.0.0.1:51421/?token=111b2065965b40ffaf21914c52a98735
```

**For JupyterHub:**
1. Go to JupyterHub admin panel
2. Navigate to User → API Tokens
3. Create new token

### Knowledge Bases Registry

Create `~/.aix/knowledges.yaml` to register your knowledge bases.

**Single path:**
```yaml
knowledges:
  quantlib:
    path: ~/projects/xfiles/Library
    description: "Quantitative library - books, papers, research articles"
    tags: [library, research, papers]
```

**Multiple paths (NEW):**
```yaml
knowledges:
  strategies:
    paths: [~/projects/xfiles/Strategies, ~/projects/xincubator]
    description: "Trading strategies across multiple repositories"
    tags: [strategies, trading, research]

  backtests:
    path: ~/projects/xfiles/Research/backtests
    description: "Backtest results with performance metrics"
    tags: [backtests, results, performance]

  research:
    paths:
      - ~/projects/xfiles/Research
      - ~/projects/xincubator/research
    description: "Research notes from multiple projects"
    tags: [research, notes, analysis]
```

**Benefits:**
- Centralized directory management
- Easy discovery of available knowledge bases
- Status checking (exists, indexed)
- Tag-based organization

## Register with Claude Code

### Method 1: Using claude mcp command (Recommended)

```bash
# - Basic registration (uses .env configuration)
claude mcp add --transport stdio xlmcp -- python -m xlmcp.server

# - Or with explicit environment variables
claude mcp add \
  -e JUPYTER_SERVER_URL=http://127.0.0.1:51421/user/quant0 \
  -e JUPYTER_API_TOKEN=your-token-here \
  --transport stdio \
  xlmcp \
  -- python -m xlmcp.server
```

**Note:** The `--` is important - it separates the MCP server name from the command.

### Method 2: Using justfile helper

```bash
just mcp-register
```

### Verify Registration

```bash
# - List registered MCP servers
claude mcp list

# - Should show:
# xlmcp: python -m xlmcp.server

# - Check server status
xlmcp status

# - List tools
xlmcp ls
```

## CLI Commands

### Start Server

```bash
# - Start in background (default)
xlmcp start

# - Start in foreground (see logs)
xlmcp start -f
```

### Check Status

```bash
xlmcp status
```

**Output:**
```
============================================================
XLMCP Server Status
============================================================

Status:  ✓ Running
PID:     12345
Uptime:  01:23:45
Command: python -m xlmcp.server

============================================================
```

### List Tools

```bash
xlmcp ls
```

Shows all 24 tools with descriptions.

### Restart Server

```bash
# - Restart to pick up code changes or new tools
xlmcp restart
```

### Stop Server

```bash
xlmcp stop
```

### Reindex Knowledge Bases

```bash
# - Reindex specific knowledge base
xlmcp reindex quantlib

# - Reindex all registered knowledge bases (runs in parallel)
xlmcp reindex --all

# - Force full reindex (ignores change detection)
xlmcp reindex --all --force

# - Control parallel jobs (default: -1 = all CPUs)
xlmcp reindex --all -j 4            # Use 4 parallel jobs
xlmcp reindex --all -j 1            # Sequential execution

# - Get help
xlmcp reindex --help
```

**Options:**
- `--all` - Reindex all knowledge bases in registry
- `--force` - Force full reindex, ignoring change detection
- `-j, --jobs INTEGER` - Number of parallel jobs (-1 = all CPUs, default)

**Features:**
- **Parallel Execution**: When reindexing multiple knowledge bases (> 1), they are processed in parallel using joblib
- **Progress Display**: Shows results for each knowledge base as they complete
- **Error Handling**: Continues processing even if one knowledge base fails

**Output:**
```
============================================================
Reindexing 3 knowledge base(s)
Mode: Force full reindex
Parallel jobs: all CPUs
============================================================

✓ quantlib: 42 files, 1523 chunks
  Path: /home/user/projects/xfiles/Library

✓ backtests: 15 files, 543 chunks
  Path: /home/user/projects/xfiles/Research/backtests

✓ stochastic: 8 files, 289 chunks
  Path: /home/user/projects/xfiles/Studies/Options

============================================================
Reindex complete: 3 success, 0 failed
============================================================
```

### List Jupyter Kernels

```bash
xlmcp kernels
```

**Output:**
```
============================================================
Active Jupyter Kernels (2)
============================================================

Kernel ID:    abc123-def456-ghi789
Name:         python3
State:        idle
Connections:  1

Kernel ID:    xyz789-uvw012-rst345
Name:         python3
State:        busy
Connections:  2

============================================================
```

Shows all currently running Jupyter kernels with their status and connection information.

## Using Jupyter Tools

### List Notebooks

```python
# - In Claude Code
await jupyter_list_notebooks(directory="~/projects")
```

### Execute Code

```python
# - Connect to notebook
await jupyter_connect_notebook("~/projects/analysis.ipynb")

# - Execute code in kernel
await jupyter_execute_code(kernel_id, "print('Hello')")

# - Execute specific cell
await jupyter_execute_cell("~/projects/analysis.ipynb", cell_index=0)
```

### Manage Notebooks

```python
# - Read notebook content
await jupyter_read_all_cells("~/projects/analysis.ipynb")

# - Add new cell
await jupyter_append_cell(
    "~/projects/analysis.ipynb",
    source="import pandas as pd",
    cell_type="code"
)

# - Update cell
await jupyter_update_cell(
    "~/projects/analysis.ipynb",
    cell_index=2,
    source="# Updated code"
)
```

## Using Knowledge RAG Tools

### List Knowledge Bases

```python
# - See all registered knowledge bases
await knowledge_list_knowledges()
```

**Returns:**
```json
{
  "status": "success",
  "knowledges": {
    "quantlib": {
      "path": "/home/user/projects/xfiles/Library",
      "description": "Quantitative library...",
      "exists": true,
      "indexed": false
    },
    "backtests": {
      "path": "/home/user/projects/xfiles/Research/backtests",
      "exists": true,
      "indexed": true
    }
  }
}
```

### Index a Directory

```python
# - Initial indexing
await knowledge_index_directory(
    directory="~/projects/xfiles/Library",
    recursive=True,
    force_reindex=False
)

# - Force full reindex
await knowledge_index_directory(
    directory="~/projects/xfiles/Library",
    recursive=True,
    force_reindex=True
)
```

### Search Documents

**Basic search:**
```python
await knowledge_search(
    directory="~/projects/xfiles/Library",
    query="mean-reversion strategy entries",
    limit=10
)
```

**With tag filtering:**
```python
await knowledge_search(
    directory="~/projects/xfiles/Research",
    query="strategy entries",
    tags=["#idea", "#strategy"],
    limit=10
)
```

**With metadata filtering:**
```python
await knowledge_search(
    directory="~/projects/xfiles/Research/backtests",
    query="backtests",
    metadata_filters={"sharpe > 1.5": None, "Type": "BACKTEST"},
    limit=10,
    threshold=0.7
)
```

**Combined filters:**
```python
await knowledge_search(
    directory="~/projects/xfiles",
    query="risk management position sizing",
    tags=["#risk-management", "#framework"],
    metadata_filters={"cagr > 20": None},
    limit=15
)
```

### Discover Available Fields

```python
# - Get all tags
await knowledge_get_tags("~/projects/xfiles")

# - Get filterable metadata fields
await knowledge_get_metadata_fields("~/projects/xfiles")
```

### Manage Indexes

```python
# - List all indexed directories
await knowledge_list_indexes()

# - Refresh index manually
await knowledge_refresh_index("~/projects/xfiles")

# - Drop index (cleanup)
await knowledge_drop_index("~/projects/xfiles")
```

## Common Workflows

### Initial Setup

```bash
# - 1. Install xlmcp
cd ~/devs/aix && uv pip install -e .

# - 2. Configure .env
cp env.example .env
vim .env  # Add Jupyter URL and token

# - 3. Create knowledge registry
vim ~/.aix/knowledges.yaml

# - 4. Register with Claude Code
claude mcp add --transport stdio xlmcp -- python -m xlmcp.server

# - 5. Verify
xlmcp status
xlmcp ls
```

### Indexing Knowledge Bases

```python
# - 1. List registered knowledge bases
await knowledge_list_knowledges()

# - 2. Index each one
await knowledge_index_directory("~/projects/xfiles/Library", recursive=True)
await knowledge_index_directory("~/projects/xfiles/Research", recursive=True)
await knowledge_index_directory("~/projects/xfiles/Strategies", recursive=True)

# - 3. Verify indexing
await knowledge_list_indexes()
```

### Daily Usage

```python
# - Search across your knowledge
await knowledge_search(
    directory="~/projects/xfiles",
    query="your research question",
    limit=10
)

# - Execute code in notebook
await jupyter_connect_notebook("~/projects/analysis.ipynb")
await jupyter_execute_cell("~/projects/analysis.ipynb", 0)

# - Indexes auto-refresh every 5 minutes (configurable)
```

## Troubleshooting

### Tools Not Appearing in Claude Code

**Issue:** Markdown tools don't appear in Claude Code

**Solution:** Restart the MCP server

```bash
# - Method 1: Use CLI (recommended)
xlmcp restart

# - Method 2: Restart Claude Code
# Close and reopen Claude Code

# - Method 3: Re-register
claude mcp remove xlmcp
claude mcp add --transport stdio xlmcp -- python -m xlmcp.server
```

### Module Not Found Errors

**Issue:** Server can't import RAG modules

**Solution:** Reinstall dependencies

```bash
cd ~/devs/aix
uv pip install -e .
```

### Server Won't Start

**Issue:** Server crashes on startup

**Solution:** Check for errors

```bash
# - Run in foreground to see errors
xlmcp start -f

# - Or check manually
python -m xlmcp.server
```

### Permission Errors

**Issue:** Can't access directories

**Solution:** Check `JUPYTER_ALLOWED_DIRS` in `.env`

```bash
# - Add directories to allowed list
JUPYTER_ALLOWED_DIRS=~/projects,~/devs,~/research,~/
```

### Search Returns No Results

**Issue:** Search doesn't find anything

**Possible causes:**
1. Directory not indexed yet
2. Similarity threshold too high
3. Wrong directory path

**Solutions:**
```python
# - Check if indexed
await knowledge_list_indexes()

# - Index directory
await knowledge_index_directory("~/projects/xfiles", recursive=True)

# - Lower threshold
await knowledge_search(
    directory="~/projects/xfiles",
    query="your query",
    threshold=0.3  # Lower threshold
)
```

### Stale Index

**Issue:** Search doesn't find new documents

**Solution:** Force refresh

```python
# - Manual refresh
await knowledge_refresh_index("~/projects/xfiles", recursive=True)

# - Or force reindex
await knowledge_index_directory(
    directory="~/projects/xfiles",
    recursive=True,
    force_reindex=True
)
```

## Advanced Configuration

### Custom Chunking

```bash
# - In .env
RAG_CHUNK_SIZE=1024  # Larger chunks
RAG_CHUNK_OVERLAP=200  # More overlap
```

### Disable Auto-Refresh

```bash
# - In .env
RAG_AUTO_REFRESH=false
```

### Change Cache Location

```bash
# - In .env
RAG_CACHE_DIR=~/custom/cache/location
```

### HTTP Transport (Remote Access)

```bash
# - In .env
MCP_TRANSPORT=http
MCP_HTTP_PORT=8765

# - Register with Claude Code
claude mcp add xlmcp --transport http http://your-server:8765
```

## Best Practices

1. **Register Knowledge Bases**: Add all directories to `~/.aix/knowledges.yaml` for easy discovery
2. **Use Tags**: Add meaningful tags to frontmatter for better filtering
3. **Regular Indexing**: Let auto-refresh handle updates or manually refresh weekly
4. **Descriptive Queries**: Use specific, detailed search queries for better results
5. **Adjust Threshold**: Lower threshold (0.3-0.5) for broad search, higher (0.6-0.8) for precise
6. **Security**: Only add trusted directories to `JUPYTER_ALLOWED_DIRS`

## Example Use Cases

### Research Assistant

```python
# - Find all research on a topic
await knowledge_search(
    directory="~/projects/xfiles",
    query="portfolio optimization risk-adjusted returns",
    tags=["#research"],
    limit=20
)
```

### Code Analysis

```python
# - Connect to notebook
await jupyter_connect_notebook("~/projects/analysis.ipynb")

# - Read cells
await jupyter_read_all_cells("~/projects/analysis.ipynb")

# - Execute specific cell
await jupyter_execute_cell("~/projects/analysis.ipynb", cell_index=5)
```

### Strategy Discovery

```python
# - Find high-performing strategies
await knowledge_search(
    directory="~/projects/xfiles/Strategies",
    query="mean reversion with volatility targeting",
    metadata_filters={"sharpe > 2.0": None, "Type": "BACKTEST"},
    tags=["#mean-reversion"],
    limit=10
)
```

### Knowledge Base Audit

```python
# - List all knowledge bases
result = await knowledge_list_knowledges()

# - Check which ones are indexed
# - Index any that aren't
for name, info in result["knowledges"].items():
    if not info["indexed"] and info["exists"]:
        await knowledge_index_directory(info["path"], recursive=True)
```

## Getting Help

- **CLI Help**: `xlmcp --help`
- **Tool Listing**: `xlmcp ls`
- **Server Status**: `xlmcp status`
- **Documentation**: See `docs/IMPLEMENTATION.md` for technical details
- **GitHub Issues**: https://github.com/xlydian/aix/issues
