# AIX - AI eXtensions for quantitative development

Collection of MCP servers, agents, and extensions for quantitative development/research with Qubx.

## XLMCP - Jupyter & Markdown RAG MCP Server

XLMCP provides Claude Code with tools to:
- Interact with Jupyter notebooks running on JupyterHub or standalone Jupyter Server
- Search markdown documents using semantic search with tag/metadata filtering

**Total Tools: 24** (16 Jupyter + 8 Markdown RAG)

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

### Markdown RAG Tools (8)

```python
# - Indexing
await markdown_index_directory(directory, recursive=True, force_reindex=False)
await markdown_refresh_index(directory=None, recursive=True)

# - Searching
await markdown_search(
    directory,
    query,
    tags=None,
    metadata_filters=None,
    limit=10,
    threshold=0.5
)

# - Discovery
await markdown_list_knowledges()  # List registered knowledge bases
await markdown_list_indexes()     # List indexed directories
await markdown_get_tags(directory)
await markdown_get_metadata_fields(directory)

# - Management
await markdown_drop_index(directory)
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

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Configure Jupyter Server:
```bash
# - Edit .env
JUPYTER_SERVER_URL=http://localhost:8888
JUPYTER_API_TOKEN=your-token-here
```

3. Configure RAG (optional, defaults provided):
```bash
RAG_CACHE_DIR=~/.aix/knowledge
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=100
RAG_AUTO_REFRESH=true
RAG_AUTO_REFRESH_INTERVAL=300
```

4. Get your Jupyter API token:
   - **JupyterHub**: Admin panel → User → New API Token
   - **Jupyter Server**: `jupyter server list` shows the token

## Register with Claude Code

```bash
# - Add MCP server to Claude Code (uses .env configuration)
claude mcp add --transport stdio xlmcp -- python -m xlmcp.server

# - Or with explicit environment variables
claude mcp add \
  -e JUPYTER_SERVER_URL=http://localhost:8888 \
  -e JUPYTER_API_TOKEN=your-token \
  --transport stdio \
  xlmcp \
  -- python -m xlmcp.server
```

**Note:** The `--` before `python` is required to separate MCP options from the server command.

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

### Markdown Search

```
> Search my research notes for "mean-reversion strategy entries"
> Find all ideas tagged with #strategy related to risk management
> List all backtests with sharpe > 1.5
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
