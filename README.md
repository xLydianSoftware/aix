# AIX - AI eXtensions for quantitative development

Collection of MCP servers, agents, and extensions for quantitative development/research with Qubx.

## XLMCP - Jupyter & Knowledge RAG MCP Server

XLMCP provides Claude Code with tools to:
- Interact with Jupyter notebooks running on JupyterHub or standalone Jupyter Server
- Search knowledge files (.md, .py, .ipynb) using semantic search with tag/metadata filtering

**Total Tools: 24** (16 Jupyter + 8 Knowledge RAG)

## Quick Reference

### Jupyter Tools (16)

```python
# - Notebook operations
await jupyter_list_notebooks(directory="")
await jupyter_get_notebook_info(notebook_path)
await jupyter_read_cell(notebook_path, cell_index)
await jupyter_read_all_cells(notebook_path)
await jupyter_append_cell(notebook_path, source, cell_type="code")
await jupyter_insert_cell(notebook_path, cell_index, source, cell_type="code")
await jupyter_update_cell(notebook_path, cell_index, source)
await jupyter_delete_cell(notebook_path, cell_index)

# - Kernel operations
await jupyter_list_kernels()
await jupyter_start_kernel(kernel_name="python3")
await jupyter_stop_kernel(kernel_id)
await jupyter_restart_kernel(kernel_id)
await jupyter_interrupt_kernel(kernel_id)

# - Execution
await jupyter_execute_code(kernel_id, code, timeout=None)
await jupyter_connect_notebook(notebook_path)
await jupyter_execute_cell(notebook_path, cell_index, timeout=None)
```

### Knowledge RAG Tools (8)

```python
# - Indexing
await knowledge_index_directory(directory, recursive=True, force_reindex=False)
await knowledge_refresh_index(directory=None, recursive=True)

# - Searching (directory optional - searches all KBs if not specified)
await knowledge_search(
    query,
    directory=None,        # None = search all registered KBs
    tags=None,
    metadata_filters=None,
    limit=10,
    threshold=0.5
)

# - Discovery (directory optional - aggregates from all KBs if not specified)
await knowledge_list_knowledges()              # List registered knowledge bases
await knowledge_list_indexes()                 # List indexed directories
await knowledge_get_tags(directory=None)       # None = all KBs
await knowledge_get_metadata_fields(directory=None)  # None = all KBs

# - Management
await knowledge_drop_index(directory)
```

## Installation

### From PyPI (Recommended)

```bash
# - Install from PyPI
pip install xlmcp

# - Or using uv
uv pip install xlmcp
```

### From Source

```bash
cd ~/devs/aix

# - Install dependencies
uv pip install -e .
```

## Configuration

### Environment Setup

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Edit `.env` and configure:

**Jupyter Server (Required):**
```bash
JUPYTER_SERVER_URL=http://localhost:8888
JUPYTER_API_TOKEN=your-token-here
JUPYTER_NOTEBOOK_DIR=~/
JUPYTER_ALLOWED_DIRS=~/projects,~/devs,~/research
```

**RAG Configuration (Optional, defaults provided):**
```bash
RAG_CACHE_DIR=~/.aix/knowledge
RAG_CHUNK_SIZE=4096
RAG_CHUNK_OVERLAP=512
RAG_AUTO_REFRESH=true
RAG_AUTO_REFRESH_INTERVAL=300
RAG_MAX_FILE_SIZE_MB=10
RAG_SKIP_NOTEBOOK_OUTPUTS=false
```

**MCP Server (Optional, defaults provided):**
```bash
MCP_TRANSPORT=stdio
MCP_HTTP_PORT=8765
MCP_MAX_OUTPUT_TOKENS=25000
```

### Get Jupyter API Token
   - **JupyterHub**: Admin panel → User → New API Token
   - **Jupyter Server**: `jupyter server list` shows the token

## Global Setup (Multi-Project Environments)

**For users with multiple projects and virtual environments:**

### 1. Install xlmcp Globally

```bash
# Install in system Python (not in project venvs)
pip install xlmcp
# or: /usr/bin/python -m pip install xlmcp
```

### 2. Create Central Configuration

```bash
# Create config directory
mkdir -p ~/.aix/xlmcp

# Copy and configure .env
cp .env.example ~/.aix/xlmcp/.env
nano ~/.aix/xlmcp/.env  # Add your JUPYTER_API_TOKEN
```

**xlmcp automatically finds config in this order:**
1. `.env` in current directory (project-specific override)
2. `~/.aix/xlmcp/.env` (global default) ← **Recommended**
3. Environment variables

### 3. Register with Claude Code

**Per-Project Registration:**

```bash
# In each project directory where you want xlmcp:
cd /path/to/project
source .venv/bin/activate  # If using venv
claude mcp add --transport stdio xlmcp -- /usr/bin/python -m xlmcp.server
```

**Note:** Replace `/usr/bin/python` with your system Python path. Find it with: `which python` (outside any venv)

**Verify:**
```bash
claude mcp list
# Should show: xlmcp: /usr/bin/python -m xlmcp.server - ✓ Connected
```

**Benefits:**
- ✅ One xlmcp installation for all projects
- ✅ Central configuration in `~/.aix/xlmcp/.env`
- ✅ Connects to Jupyter kernels in any project venv
- ✅ No package conflicts between projects
- ✅ Simple registration - direct Python invocation

## Simple Setup (Single Project / Quick Start)

**For single project or testing:**

```bash
# Install xlmcp
pip install xlmcp

# Create .env with your configuration
cp .env.example .env
nano .env  # Add JUPYTER_API_TOKEN

# Register with Claude Code (from project directory)
claude mcp add --transport stdio xlmcp -- python -m xlmcp.server
```

**Or with environment variables (no .env file needed):**

```bash
claude mcp add \
  -e JUPYTER_SERVER_URL=http://localhost:8888 \
  -e JUPYTER_API_TOKEN=your-token \
  --transport stdio \
  xlmcp \
  -- python -m xlmcp.server
```

**Note:** The `--` before `python` separates MCP options from the server command.

## XLMCP CLI

The `xlmcp` command provides easy server management:

```bash
# - Start server
xlmcp start

# - Check status
xlmcp status

# - List all tools
xlmcp ls

# - Reindex knowledge bases
xlmcp reindex quantlib              # Reindex specific knowledge base
xlmcp reindex --all                 # Reindex all (parallel if > 1)
xlmcp reindex --all --force         # Force full reindex
xlmcp reindex --all -j 4            # Use 4 parallel jobs

# - Restart server (e.g., after adding new tools)
xlmcp restart

# - Stop server
xlmcp stop
```

## Usage Examples

### Jupyter Notebooks

```
> Connect to my notebook and execute the first cell
> List all notebooks in research/momentum/
> Execute code: print("Hello from Jupyter!")
```

### Knowledge Search

Claude AI can search across ALL your knowledge bases without you specifying which one:

```
> Search my notes for "mean-reversion strategy entries"
  (searches all registered knowledge bases)

> Find ideas tagged with #strategy about risk management
  (aggregates results from library, backtests, strategies, etc.)

> Show me all backtests with sharpe > 1.5
  (searches across all indexed directories)

> Search only in backtests for "momentum factor"
  (you can still specify a specific KB if needed)
```

## After Adding New Tools

**IMPORTANT:** When new tools are added to xlmcp, you must restart the MCP server for them to be visible to MCP clients.

### Restart Methods:

**Option 1: Use xlmcp CLI** (Recommended)
```bash
xlmcp restart
```

**Option 2: Restart Claude Code**
```bash
# - Just close and reopen Claude Code
```

**Option 3: Remove and Re-add MCP Server**
```bash
claude mcp remove xlmcp -s local
claude mcp add --transport stdio xlmcp python -m xlmcp.server
```

## Verification

```bash
# - Check server status
xlmcp status

# - List all tools
xlmcp ls

# - Should show: Total Tools: 24
```

## Transport Modes

**stdio (default)** - For local Claude Code:
```bash
MCP_TRANSPORT=stdio
```

**http** - For remote access:
```bash
MCP_TRANSPORT=http
MCP_HTTP_PORT=8765

# - Then add to Claude Code
claude mcp add xlmcp --transport http http://your-server:8765
```

## Security

- Path validation: Only allows access to configured directories
- Token authentication: Uses Jupyter API tokens
- Timeout limits: Prevents runaway executions

## Documentation

- **[Usage Guide](docs/USAGE.md)** - Installation, configuration, CLI, and usage examples
- **[Implementation](docs/IMPLEMENTATION.md)** - Technical architecture and design details

## License

MIT
