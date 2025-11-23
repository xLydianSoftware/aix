# AIX - AI Extensions for Claude Code

Collection of MCP servers, agents, and extensions for quantitative development/research with Qubx.

## XMCP - Jupyter MCP Server

XMCP provides Claude Code with tools to interact with Jupyter notebooks running on JupyterHub or standalone Jupyter Server.

### Features

**Notebook Operations:**
- `jupyter_list_notebooks` - List notebooks in a directory
- `jupyter_get_notebook_info` - Get notebook metadata and cell summary
- `jupyter_read_cell` / `jupyter_read_all_cells` - Read cell content
- `jupyter_append_cell` / `jupyter_insert_cell` - Add new cells
- `jupyter_update_cell` / `jupyter_delete_cell` - Modify cells

**Kernel Management:**
- `jupyter_list_kernels` - List running kernels
- `jupyter_start_kernel` / `jupyter_stop_kernel` - Start/stop kernels
- `jupyter_restart_kernel` / `jupyter_interrupt_kernel` - Control execution

**Code Execution:**
- `jupyter_execute_code` - Execute code in a kernel
- `jupyter_connect_notebook` - Connect to notebook's kernel
- `jupyter_execute_cell` - Execute a specific cell in a notebook

### Installation

```bash
cd ~/devs/aix

# Install dependencies
pip install -e .

# Or with poetry
poetry install
```

### Configuration

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Configure your Jupyter Server:
```bash
# Edit .env
JUPYTER_SERVER_URL=http://localhost:8888
JUPYTER_API_TOKEN=your-token-here
```

3. Get your Jupyter API token:
   - **JupyterHub**: Admin panel → User → New API Token
   - **Jupyter Server**: `jupyter server list` shows the token

### Register with Claude Code

```bash
# Add MCP server to Claude Code
claude mcp add xmcp -- python -m xmcp.server

# Or with environment variables
claude mcp add xmcp -e JUPYTER_SERVER_URL=http://localhost:8888 -e JUPYTER_API_TOKEN=your-token -- python -m xmcp.server
```

### Usage in Claude Code

Once registered, you can use the tools directly:

```
> Connect to my notebook and execute the first cell
> List all notebooks in research/momentum/
> Execute code: print("Hello from Jupyter!")
```

### Transport Modes

**stdio (default)** - For local Claude Code:
```bash
MCP_TRANSPORT=stdio
```

**http** - For remote access:
```bash
MCP_TRANSPORT=http
MCP_HTTP_PORT=8765

# Then add to Claude Code
claude mcp add xmcp --transport http http://your-server:8765
```

### Security

- Path validation: Only allows access to configured directories
- Token authentication: Uses Jupyter API tokens
- Timeout limits: Prevents runaway executions

## License

MIT
