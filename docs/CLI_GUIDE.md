# XMCP CLI Guide

## Overview

The `xmcp` CLI provides commands to manage the xmcp MCP server.

## Installation

The CLI is automatically installed when you install xmcp:

```bash
uv pip install -e .
```

This creates two command-line tools:
- `xmcp` - CLI for managing the server
- `xmcp-server` - Direct server entry point (used internally)

## Commands

### `xmcp start`

Start the xmcp MCP server in background.

```bash
xmcp start
```

**Options:**
- `-f, --foreground` - Run in foreground (blocks terminal)

**Examples:**
```bash
# Start in background (default)
xmcp start

# Start in foreground (see logs)
xmcp start -f
```

### `xmcp stop`

Stop the running xmcp MCP server.

```bash
xmcp stop
```

Gracefully shuts down the server. If graceful shutdown fails, forces kill.

### `xmcp restart`

Restart the xmcp MCP server.

```bash
xmcp restart
```

Equivalent to: `xmcp stop && xmcp start`

### `xmcp status`

Show xmcp server status.

```bash
xmcp status
```

**Output:**
```
============================================================
XMCP Server Status
============================================================

Status:  ✓ Running
PID:     12345
Uptime:  01:23:45
Command: python -m xmcp.server

============================================================
```

### `xmcp ls` / `xmcp list`

List all available MCP tools.

```bash
xmcp ls
```

**Output:**
```
================================================================================
XMCP Server Tools
================================================================================

Total Tools: 24

 1. jupyter_append_cell
    Append a new cell to the end of a notebook.

 2. jupyter_connect_notebook
    Connect to a notebook's kernel (create session if needed).

...

24. markdown_search
    Search markdown documents with semantic similarity and filters.

================================================================================
```

## Usage Examples

### Starting and Stopping Server

```bash
# Start server
xmcp start

# Check if running
xmcp status

# Stop server
xmcp stop
```

### Development Workflow

```bash
# Start in foreground to see logs
xmcp start -f

# In another terminal, check tools
xmcp ls

# Restart after code changes
xmcp restart
```

### Troubleshooting

```bash
# Check if server is running
xmcp status

# If stuck, force restart
xmcp stop
xmcp start

# View available tools
xmcp ls
```

## Entry Points

The package defines two console scripts in `pyproject.toml`:

```toml
[project.scripts]
xmcp-server = "xmcp.server:main"  # Direct server entry
xmcp = "xmcp.cli:main"            # CLI management tool
```

## CLI Module Structure

```
src/xmcp/
├── cli/
│   └── __init__.py    # CLI commands (click-based)
├── utils.py           # Utility functions (list_server_tools)
└── server.py          # MCP server
```

## Implementation Details

### CLI Framework

- **Framework:** Uses [click](https://click.palletsprojects.com/) for elegant command-line interfaces
- **Commands:** Decorator-based (@cli.command())
- **Options:** Type-safe with automatic help generation
- **Help:** Auto-generated from docstrings and decorators

### Server Process Management

- **PID Detection:** Uses `pgrep -f "xmcp.server"` to find running server
- **Start:** Launches `python -m xmcp.server` as daemon process
- **Stop:** Sends SIGTERM, then SIGKILL if needed
- **Status:** Reads process info via `ps` command

### Tool Listing

- Reads tools from `mcp._tool_manager._tools`
- Fallback: Scans `server.py` for decorated async functions
- Displays name + first line of docstring

## Integration with Claude Code

The CLI complements Claude Code's MCP integration:

```bash
# Check server status before using Claude Code
xmcp status

# Restart if tools don't appear in Claude Code
xmcp restart
```

## Common Workflows

### After Code Changes

```bash
# Restart to pick up new tools
xmcp restart

# Verify tools are registered
xmcp ls
```

### Debugging

```bash
# Run in foreground to see errors
xmcp start -f

# Check logs for issues
```

### Production Deployment

```bash
# Start server
xmcp start

# Verify running
xmcp status

# Check available tools
xmcp ls
```

## Error Handling

The CLI provides clear feedback:

```bash
# If server already running
$ xmcp start
✓ xmcp server is already running
  PID: 12345

# If server not running
$ xmcp stop
✓ xmcp server is not running

# If failed to start
$ xmcp start
Starting xmcp server...
✗ Failed to start xmcp server
```

## Future Enhancements

Potential additions (not yet implemented):
- `xmcp logs` - View server logs
- `xmcp test` - Test server health
- `xmcp config` - View/edit configuration
- `xmcp install` - Install as system service
- `xmcp version` - Show version info
