"""
XMCP Server - MCP Server for JupyterHub Integration

Provides Claude Code with tools to interact with Jupyter notebooks.
"""

import asyncio
import sys
import warnings

# - Suppress Pydantic warning from llama-index library
warnings.filterwarnings("ignore", category=Warning, message=".*validate_default.*")

from fastmcp import FastMCP  # noqa: E402

from xmcp.config import get_config  # noqa: E402
from xmcp.tools.jupyter import kernel, notebook  # noqa: E402
from xmcp.tools.rag import indexer, registry, searcher, storage  # noqa: E402

# - Create MCP server
config = get_config()
mcp = FastMCP(config.mcp.name)


# =============================================================================
# Notebook Tools
# =============================================================================


@mcp.tool()
async def jupyter_list_notebooks(directory: str = "") -> str:
    """
    List all Jupyter notebooks in a directory.

    Args:
        directory: Directory path relative to Jupyter root (empty for root)

    Returns:
        JSON with list of notebooks including name, path, and last_modified
    """
    return await notebook.list_notebooks(directory)


@mcp.tool()
async def jupyter_get_notebook_info(notebook_path: str) -> str:
    """
    Get information about a notebook including cell counts and kernel info.

    Args:
        notebook_path: Path to the notebook (relative to Jupyter root)

    Returns:
        JSON with notebook metadata, kernel info, and cell type summary
    """
    return await notebook.get_notebook_info(notebook_path)


@mcp.tool()
async def jupyter_read_cell(notebook_path: str, cell_index: int) -> str:
    """
    Read content of a specific cell in a notebook.

    Args:
        notebook_path: Path to the notebook
        cell_index: Index of the cell (0-based)

    Returns:
        JSON with cell type, source, outputs (if code cell), and metadata
    """
    return await notebook.read_cell(notebook_path, cell_index)


@mcp.tool()
async def jupyter_read_all_cells(notebook_path: str) -> str:
    """
    Read all cells from a notebook.

    Args:
        notebook_path: Path to the notebook

    Returns:
        JSON with list of all cells (index, type, source, execution_count)
    """
    return await notebook.read_all_cells(notebook_path)


@mcp.tool()
async def jupyter_append_cell(
    notebook_path: str,
    source: str,
    cell_type: str = "code",
) -> str:
    """
    Append a new cell to the end of a notebook.

    Args:
        notebook_path: Path to the notebook
        source: Cell content (code or markdown)
        cell_type: Type of cell - 'code' or 'markdown' (default: code)

    Returns:
        JSON with success status and new cell index
    """
    return await notebook.append_cell(notebook_path, source, cell_type)


@mcp.tool()
async def jupyter_insert_cell(
    notebook_path: str,
    cell_index: int,
    source: str,
    cell_type: str = "code",
) -> str:
    """
    Insert a new cell at a specific position in the notebook.

    Args:
        notebook_path: Path to the notebook
        cell_index: Position to insert (0-based, cells after this shift down)
        source: Cell content (code or markdown)
        cell_type: Type of cell - 'code' or 'markdown' (default: code)

    Returns:
        JSON with success status
    """
    return await notebook.insert_cell(notebook_path, cell_index, source, cell_type)


@mcp.tool()
async def jupyter_update_cell(
    notebook_path: str,
    cell_index: int,
    source: str,
) -> str:
    """
    Update content of an existing cell.

    Args:
        notebook_path: Path to the notebook
        cell_index: Index of the cell to update (0-based)
        source: New cell content

    Returns:
        JSON with success status
    """
    return await notebook.update_cell(notebook_path, cell_index, source)


@mcp.tool()
async def jupyter_delete_cell(notebook_path: str, cell_index: int) -> str:
    """
    Delete a cell from the notebook.

    Args:
        notebook_path: Path to the notebook
        cell_index: Index of the cell to delete (0-based)

    Returns:
        JSON with success status and deleted cell type
    """
    return await notebook.delete_cell(notebook_path, cell_index)


# =============================================================================
# Kernel Tools
# =============================================================================


@mcp.tool()
async def jupyter_list_kernels() -> str:
    """
    List all running Jupyter kernels.

    Returns:
        JSON with list of kernels (id, name, state, connections)
    """
    return await kernel.list_kernels()


@mcp.tool()
async def jupyter_start_kernel(kernel_name: str = "python3") -> str:
    """
    Start a new Jupyter kernel.

    Args:
        kernel_name: Name of the kernel spec (default: python3)

    Returns:
        JSON with new kernel id, name, and state
    """
    return await kernel.start_kernel(kernel_name)


@mcp.tool()
async def jupyter_stop_kernel(kernel_id: str) -> str:
    """
    Stop a running kernel.

    Args:
        kernel_id: ID of the kernel to stop

    Returns:
        JSON with success status
    """
    return await kernel.stop_kernel(kernel_id)


@mcp.tool()
async def jupyter_restart_kernel(kernel_id: str) -> str:
    """
    Restart a kernel (clears all state).

    Args:
        kernel_id: ID of the kernel to restart

    Returns:
        JSON with new kernel state
    """
    return await kernel.restart_kernel(kernel_id)


@mcp.tool()
async def jupyter_interrupt_kernel(kernel_id: str) -> str:
    """
    Interrupt a running kernel (stop current execution).

    Args:
        kernel_id: ID of the kernel to interrupt

    Returns:
        JSON with success status
    """
    return await kernel.interrupt_kernel(kernel_id)


# =============================================================================
# Execution Tools
# =============================================================================


@mcp.tool()
async def jupyter_execute_code(
    kernel_id: str,
    code: str,
    timeout: float | None = None,
) -> str:
    """
    Execute Python code in a running kernel.

    Args:
        kernel_id: ID of the kernel to execute in
        code: Python code to execute
        timeout: Execution timeout in seconds (default: 300)

    Returns:
        JSON with status ('ok' or 'error'), outputs, and error details if any
    """
    return await kernel.execute_code(kernel_id, code, timeout)


@mcp.tool()
async def jupyter_connect_notebook(notebook_path: str) -> str:
    """
    Connect to a notebook's kernel (create session if needed).

    This gets an existing kernel session for the notebook or creates a new one.
    Use the returned kernel_id for subsequent execute_code calls.

    Args:
        notebook_path: Path to the notebook

    Returns:
        JSON with session_id, kernel_id, and kernel state
    """
    return await kernel.get_or_create_kernel_for_notebook(notebook_path)


@mcp.tool()
async def jupyter_execute_cell(
    notebook_path: str,
    cell_index: int,
    timeout: float | None = None,
) -> str:
    """
    Execute a specific cell in a notebook.

    This will:
    1. Connect to the notebook's kernel (or create one)
    2. Execute the cell's code
    3. Save outputs to notebook file (visible in VS Code)
    4. Return the execution outputs

    Args:
        notebook_path: Path to the notebook
        cell_index: Index of the cell to execute (0-based)
        timeout: Execution timeout in seconds (default: 300)

    Returns:
        JSON with cell_index, status, outputs, and error if any
    """
    return await kernel.execute_notebook_cell(notebook_path, cell_index, timeout)


# =============================================================================
# Knowledge RAG Tools
# =============================================================================


@mcp.tool()
async def knowledge_index_directory(
    directory: str,
    recursive: bool = True,
    force_reindex: bool = False,
) -> str:
    """
    Index or update knowledge directory for semantic search.

    Supports: .md (markdown), .py (Python), .ipynb (Jupyter notebooks)

    Args:
        directory: Absolute path to knowledge directory
        recursive: Recursively index subdirectories (default: True)
        force_reindex: Force full reindex (default: False)

    Returns:
        JSON with indexing results (processed files, chunks, status)
    """
    return await indexer.index_directory(directory, recursive, force_reindex)


@mcp.tool()
async def knowledge_search(
    directory: str,
    query: str,
    tags: list[str] | None = None,
    metadata_filters: dict | None = None,
    limit: int = 10,
    threshold: float = 0.5,
) -> str:
    """
    Search knowledge base with semantic similarity and filters.

    Searches across .md, .py, and .ipynb files.

    Args:
        directory: Absolute path to indexed knowledge directory
        query: Search query text
        tags: Filter by tags (e.g., ["#backtest", "#strategy"]) - AND logic
        metadata_filters: Filter by metadata (e.g., {"sharpe > 1.5": None, "file_type": "py"})
        limit: Maximum results to return (default: 10)
        threshold: Minimum similarity score 0-1 (default: 0.5)

    Returns:
        JSON with search results (text, filename, path, score, metadata)
    """
    return await searcher.search_documents(directory, query, tags, metadata_filters, limit, threshold)


@mcp.tool()
async def knowledge_list_indexes() -> str:
    """
    List all indexed knowledge directories with statistics.

    Returns:
        JSON with list of indexes (directory, collection, file_count, last_updated)
    """
    return await storage.list_all_indexes()


@mcp.tool()
async def knowledge_refresh_index(
    directory: str | None = None,
    recursive: bool = True,
) -> str:
    """
    Manually force refresh of knowledge index.

    Args:
        directory: Directory to refresh (None = refresh all)
        recursive: Recursively check subdirectories

    Returns:
        JSON with refresh results
    """
    return await indexer.refresh_index(directory, recursive)


@mcp.tool()
async def knowledge_get_tags(directory: str) -> str:
    """
    Extract all unique tags from indexed documents with counts.

    Args:
        directory: Absolute path to indexed directory

    Returns:
        JSON with tags and counts (e.g., {"#backtest": 42, "#strategy": 38})
    """
    return await searcher.get_all_tags(directory)


@mcp.tool()
async def knowledge_get_metadata_fields(directory: str) -> str:
    """
    List available metadata fields for filtering with examples.

    Args:
        directory: Absolute path to indexed directory

    Returns:
        JSON with field names, types, and example values
    """
    return await searcher.get_metadata_fields(directory)


@mcp.tool()
async def knowledge_drop_index(directory: str) -> str:
    """
    Drop index and remove all cached data for a directory.

    Args:
        directory: Absolute path to directory

    Returns:
        JSON with status
    """
    return await storage.drop_index(directory)


@mcp.tool()
async def knowledge_list_knowledges() -> str:
    """
    List all registered knowledge bases from ~/.aix/knowledges.yaml.

    Shows which knowledge bases are registered, whether they exist,
    and whether they have been indexed.

    Returns:
        JSON with knowledge bases information including paths, descriptions,
        tags, existence status, and index status
    """
    return await registry.list_knowledges()


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Run the MCP server."""
    transport = config.mcp.transport

    if transport == "http":
        # - HTTP transport for remote access
        mcp.run(transport="http", port=config.mcp.http_port)
    else:
        # - Default: stdio transport for Claude Code
        mcp.run()


if __name__ == "__main__":
    main()
