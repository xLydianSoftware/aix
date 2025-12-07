# MCP Tools Troubleshooting

## Tools Are Registered ✅

All **24 MCP tools** are properly registered in the xmcp server:

**Jupyter Tools (16):**
- jupyter_list_notebooks
- jupyter_get_notebook_info
- jupyter_read_cell
- jupyter_read_all_cells
- jupyter_append_cell
- jupyter_insert_cell
- jupyter_update_cell
- jupyter_delete_cell
- jupyter_list_kernels
- jupyter_start_kernel
- jupyter_stop_kernel
- jupyter_restart_kernel
- jupyter_interrupt_kernel
- jupyter_execute_code
- jupyter_connect_notebook
- jupyter_execute_cell

**Markdown RAG Tools (8):**
- markdown_index_directory
- markdown_search
- markdown_list_indexes
- markdown_refresh_index
- markdown_get_tags
- markdown_get_metadata_fields
- markdown_drop_index
- markdown_list_knowledges

## Issue: Tools Not Appearing in MCP Client

If the markdown tools don't appear in your Claude Code or MCP client, this is because the **MCP server needs to be restarted** for new tools to be recognized.

## Solution: Restart MCP Server

### Method 1: Use xmcp CLI (Recommended)

```bash
# Restart the server
xmcp restart

# Verify it's running
xmcp status

# Check tools are available
xmcp ls
```

### Method 2: Restart xmcp Server via Claude MCP Commands

```bash
# Stop the current xmcp server
claude mcp remove xmcp -s local

# Re-add it (this will start fresh)
claude mcp add --transport stdio xmcp python -m xmcp.server
```

### Method 3: Restart Claude Code

The easiest way is to restart Claude Code entirely:
1. Close all Claude Code windows
2. Reopen Claude Code
3. The xmcp server will restart automatically

### Method 4: Manual Server Restart

If you're running the server manually:

```bash
# Stop server
xmcp stop

# Start server
xmcp start
```

## Verification: Check Tools Are Available

### From Command Line

```bash
# List all tools
python list_tools.py
```

Expected output: Should show all 24 tools.

### From Claude Code

Once restarted, try:

```python
# This should work
await markdown_list_knowledges()
```

If this fails with "tool not found", the server didn't restart.

## Common Issues

### Issue 1: "Module not found" errors

**Cause:** Server can't import the RAG modules

**Solution:** Ensure dependencies are installed:
```bash
uv pip install -e .
```

### Issue 2: Tools registered but not callable

**Cause:** Import errors in the modules

**Solution:** Check imports:
```bash
python -c "from xmcp.tools.rag import indexer, searcher, storage, registry; print('OK')"
```

### Issue 3: Server crashes on startup

**Cause:** Missing dependencies or configuration errors

**Solution:** Check server can start:
```bash
python -m xmcp.server
```

Should show FastMCP banner without errors.

## How MCP Tool Discovery Works

1. **Server Startup:**
   - `python -m xmcp.server` loads server.py
   - All `@mcp.tool()` decorated functions are registered
   - FastMCP creates tool schemas

2. **Client Connection:**
   - MCP client (Claude Code) connects to server
   - Client requests list of available tools
   - Server returns all registered tools

3. **Tool Updates:**
   - Adding new tools to server.py
   - Client MUST reconnect to see new tools
   - **Restart is required!**

## Debugging Commands

### Check if server is running
```bash
ps aux | grep xmcp
```

### Check which tools are registered
```bash
python list_tools.py
```

### Test a tool directly
```bash
python -c "
import asyncio
from xmcp.tools.rag import registry

result = asyncio.run(registry.list_knowledges())
print(result)
"
```

### Verify imports work
```bash
python -c "
from xmcp.tools.rag import indexer, searcher, storage, registry, metadata, models
print('All RAG modules import successfully')
"
```

## Expected Tool Count

After restart, you should see:
- **24 total tools** (16 Jupyter + 8 Markdown)
- All tools should be callable
- No import errors in server logs

## Still Not Working?

1. **Check server logs** for import errors
2. **Verify .env file** has correct configuration
3. **Check Python environment** is correct (should be in venv)
4. **Reinstall dependencies**:
   ```bash
   uv pip install -e .
   ```

## Quick Fix Checklist

- [ ] Restart Claude Code
- [ ] Verify server starts without errors
- [ ] Check `python list_tools.py` shows 24 tools
- [ ] Test `await markdown_list_knowledges()` works
- [ ] If still failing, reinstall dependencies

## Contact

If tools still don't appear after restart:
1. Check server.py for syntax errors
2. Verify all imports are correct
3. Check Python version (requires 3.10+)
4. Review MCP server logs for errors
