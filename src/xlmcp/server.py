"""
XLMCP Server - MCP Server for JupyterHub and Knowledge Integration
"""

import asyncio
import sys
import warnings

# - Suppress Pydantic warning from llama-index library
warnings.filterwarnings("ignore", category=Warning, message=".*validate_default.*")

from fastmcp import FastMCP  # noqa: E402

from xlmcp.config import get_config  # noqa: E402
from xlmcp.tools.jupyter import kernel, notebook  # noqa: E402
from xlmcp.tools.rag import indexer, registry, searcher, storage  # noqa: E402

# - Create MCP server
config = get_config()
mcp = FastMCP(config.mcp.name)


# =============================================================================
# Helper Functions
# =============================================================================


def resolve_knowledge_directory(name_or_path: str) -> str:
    """
    Resolve knowledge base name or path to directory path.

    Supports:
    - Absolute/relative paths (returns as-is after expansion)
    - Knowledge base names from knowledges.yaml
    - Cache directory names (backward compatibility)

    Args:
        name_or_path: Knowledge base name, cache name, or directory path

    Returns:
        Resolved directory path

    Raises:
        ValueError: If knowledge base/directory not found
    """
    from pathlib import Path

    # - If it looks like a path, use it directly
    if '/' in name_or_path or name_or_path.startswith('~'):
        return str(Path(name_or_path).expanduser().resolve())

    # - Check if it's a knowledge base name in registry
    knowledges = registry.load_knowledges()
    if name_or_path in knowledges:
        paths = knowledges[name_or_path].get('paths', [])
        if paths:
            return paths[0]  # - Return first path for multi-path KBs

    # - Fall back to treating it as a path
    return str(Path(name_or_path).expanduser().resolve())


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
        directory: Knowledge base name (from knowledges.yaml) or absolute path to knowledge directory
        recursive: Recursively index subdirectories (default: True)
        force_reindex: Force full reindex (default: False)

    Returns:
        JSON with indexing results (processed files, chunks, status)
    """
    # - Resolve KB name or path to directory
    resolved_dir = resolve_knowledge_directory(directory)
    return await indexer.index_directory(resolved_dir, recursive, force_reindex)


@mcp.tool()
async def knowledge_search(
    query: str,
    directory: str | None = None,
    tags: list[str] | None = None,
    metadata_filters: dict | None = None,
    limit: int = 10,
    threshold: float = 0.5,
) -> str:
    """
    Search knowledge base with semantic similarity and filters.

    Searches across .md, .py, and .ipynb files.

    Args:
        query: Search query text
        directory: Knowledge base name or path (None = search all registered KBs)
        tags: Filter by tags (e.g., ["#backtest", "#strategy"]) - AND logic
        metadata_filters: Filter by metadata (e.g., {"sharpe > 1.5": None, "file_type": "py"})
        limit: Maximum results to return (default: 10)
        threshold: Minimum similarity score 0-1 (default: 0.5)

    Returns:
        JSON with search results (text, filename, path, score, metadata)
    """
    import json

    # - If no directory specified, search all registered knowledge bases
    if directory is None:
        knowledges = registry.load_knowledges()
        if not knowledges:
            return json.dumps({"status": "error", "message": "No knowledge bases registered"}, indent=2)

        # - Aggregate results from all KBs
        all_results = []
        for kb_name, kb_info in knowledges.items():
            for kb_path in kb_info.get('paths', []):
                try:
                    result_json = await searcher.search_documents(kb_path, query, tags, metadata_filters, limit, threshold)
                    result = json.loads(result_json)
                    if result.get('status') == 'success' and result.get('results'):
                        # - Add KB name to each result
                        for r in result['results']:
                            r['knowledge_base'] = kb_name
                        all_results.extend(result['results'])
                except Exception:
                    continue

        # - Sort by score and limit
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        all_results = all_results[:limit]

        return json.dumps({
            "status": "success",
            "query": query,
            "results": all_results,
            "total": len(all_results)
        }, indent=2)

    # - Resolve KB name or path to directory
    resolved_dir = resolve_knowledge_directory(directory)
    return await searcher.search_documents(resolved_dir, query, tags, metadata_filters, limit, threshold)


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
        directory: Knowledge base name (from knowledges.yaml), absolute path, or None to refresh all
        recursive: Recursively check subdirectories

    Returns:
        JSON with refresh results
    """
    # - Resolve KB name or path to directory (if provided)
    resolved_dir = resolve_knowledge_directory(directory) if directory else None
    return await indexer.refresh_index(resolved_dir, recursive)


@mcp.tool()
async def knowledge_get_tags(directory: str | None = None) -> str:
    """
    Extract all unique tags from indexed documents with counts.

    Args:
        directory: Knowledge base name or path (None = aggregate tags from all registered KBs)

    Returns:
        JSON with tags and counts (e.g., {"#backtest": 42, "#strategy": 38})
    """
    import json

    # - If no directory specified, aggregate tags from all registered knowledge bases
    if directory is None:
        knowledges = registry.load_knowledges()
        if not knowledges:
            return json.dumps({"status": "error", "message": "No knowledge bases registered"}, indent=2)

        # - Aggregate tags from all KBs
        all_tags = {}
        for kb_name, kb_info in knowledges.items():
            for kb_path in kb_info.get('paths', []):
                try:
                    result_json = await searcher.get_all_tags(kb_path)
                    result = json.loads(result_json)
                    if result.get('status') == 'success' and result.get('tags'):
                        # - Merge tag counts
                        for tag, count in result['tags'].items():
                            all_tags[tag] = all_tags.get(tag, 0) + count
                except Exception:
                    continue

        # - Sort by count descending
        sorted_tags = dict(sorted(all_tags.items(), key=lambda x: x[1], reverse=True))

        return json.dumps({
            "status": "success",
            "tags": sorted_tags,
            "total": len(sorted_tags)
        }, indent=2)

    # - Resolve KB name or path to directory
    resolved_dir = resolve_knowledge_directory(directory)
    return await searcher.get_all_tags(resolved_dir)


@mcp.tool()
async def knowledge_get_metadata_fields(directory: str | None = None) -> str:
    """
    List available metadata fields for filtering with examples.

    Args:
        directory: Knowledge base name or path (None = aggregate from all registered KBs)

    Returns:
        JSON with field names, types, and example values
    """
    import json

    # - If no directory specified, aggregate metadata from all registered knowledge bases
    if directory is None:
        knowledges = registry.load_knowledges()
        if not knowledges:
            return json.dumps({"status": "error", "message": "No knowledge bases registered"}, indent=2)

        # - Aggregate metadata fields from all KBs
        all_fields = {}
        for kb_name, kb_info in knowledges.items():
            for kb_path in kb_info.get('paths', []):
                try:
                    result_json = await searcher.get_metadata_fields(kb_path)
                    result = json.loads(result_json)
                    if result.get('status') == 'success' and result.get('fields'):
                        # - Merge fields (keep examples from any KB)
                        for field_name, field_info in result['fields'].items():
                            if field_name not in all_fields:
                                all_fields[field_name] = field_info
                except Exception:
                    continue

        return json.dumps({
            "status": "success",
            "fields": all_fields
        }, indent=2)

    # - Resolve KB name or path to directory
    resolved_dir = resolve_knowledge_directory(directory)
    return await searcher.get_metadata_fields(resolved_dir)


@mcp.tool()
async def knowledge_drop_index(directory: str) -> str:
    """
    Drop index and remove all cached data for a directory.

    Args:
        directory: Knowledge base name (from knowledges.yaml) or absolute path to directory

    Returns:
        JSON with status
    """
    # - Resolve KB name or path to directory
    resolved_dir = resolve_knowledge_directory(directory)
    return await storage.drop_index(resolved_dir)


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
