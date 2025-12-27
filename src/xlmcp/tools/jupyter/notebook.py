"""
Notebook operation tools for MCP.
"""

import json

import nbformat

from xlmcp.config import validate_path
from xlmcp.tools.jupyter.client import get_client


async def list_notebooks(directory: str = "") -> str:
    """
    List all Jupyter notebooks in a directory.

    Args:
        directory: Directory path relative to Jupyter root (empty for root)

    Returns:
        JSON string with list of notebooks
    """
    client = get_client()
    notebooks = await client.list_notebooks(directory)
    return json.dumps({"notebooks": notebooks, "count": len(notebooks)}, indent=2)


async def get_notebook_info(notebook_path: str) -> str:
    """
    Get information about a notebook.

    Args:
        notebook_path: Path to the notebook

    Returns:
        JSON string with notebook metadata and cell summary
    """
    client = get_client()
    nb_data = await client.get_notebook(notebook_path)
    content = nb_data.get("content", {})

    cells = content.get("cells", [])
    cell_types = {}
    for cell in cells:
        ct = cell.get("cell_type", "unknown")
        cell_types[ct] = cell_types.get(ct, 0) + 1

    info = {
        "name": nb_data.get("name"),
        "path": nb_data.get("path"),
        "last_modified": nb_data.get("last_modified"),
        "kernel": content.get("metadata", {}).get("kernelspec", {}),
        "language": content.get("metadata", {}).get("language_info", {}),
        "total_cells": len(cells),
        "cell_types": cell_types,
    }
    return json.dumps(info, indent=2)


async def read_cell(notebook_path: str, cell_index: int) -> str:
    """
    Read content of a specific cell in a notebook.

    Args:
        notebook_path: Path to the notebook
        cell_index: Index of the cell (0-based)

    Returns:
        JSON string with cell content and metadata
    """
    client = get_client()
    nb_data = await client.get_notebook(notebook_path)
    content = nb_data.get("content", {})
    cells = content.get("cells", [])

    if cell_index < 0 or cell_index >= len(cells):
        return json.dumps({"error": f"Cell index {cell_index} out of range (0-{len(cells)-1})"})

    cell = cells[cell_index]
    return json.dumps({
        "index": cell_index,
        "type": cell.get("cell_type"),
        "source": cell.get("source"),
        "metadata": cell.get("metadata", {}),
        "outputs": cell.get("outputs", []) if cell.get("cell_type") == "code" else None,
        "execution_count": cell.get("execution_count"),
    }, indent=2)


async def read_all_cells(notebook_path: str) -> str:
    """
    Read all cells from a notebook.

    Args:
        notebook_path: Path to the notebook

    Returns:
        JSON string with all cells
    """
    client = get_client()
    nb_data = await client.get_notebook(notebook_path)
    content = nb_data.get("content", {})
    cells = content.get("cells", [])

    result = []
    for i, cell in enumerate(cells):
        result.append({
            "index": i,
            "type": cell.get("cell_type"),
            "source": cell.get("source"),
            "execution_count": cell.get("execution_count"),
        })

    return json.dumps({"cells": result, "total": len(result)}, indent=2)


async def append_cell(
    notebook_path: str,
    source: str,
    cell_type: str = "code",
) -> str:
    """
    Append a new cell to the notebook.

    Args:
        notebook_path: Path to the notebook
        source: Cell content
        cell_type: Type of cell ('code' or 'markdown')

    Returns:
        JSON string with result
    """
    client = get_client()
    nb_data = await client.get_notebook(notebook_path)
    content = nb_data.get("content", {})

    # - Create new cell
    if cell_type == "code":
        new_cell = nbformat.v4.new_code_cell(source)
    else:
        new_cell = nbformat.v4.new_markdown_cell(source)

    content["cells"].append(dict(new_cell))

    # - Save notebook
    await client.save_notebook(notebook_path, content)

    return json.dumps({
        "success": True,
        "message": f"Appended {cell_type} cell at index {len(content['cells']) - 1}",
        "cell_index": len(content["cells"]) - 1,
    })


async def insert_cell(
    notebook_path: str,
    cell_index: int,
    source: str,
    cell_type: str = "code",
) -> str:
    """
    Insert a new cell at a specific position.

    Args:
        notebook_path: Path to the notebook
        cell_index: Position to insert (0-based)
        source: Cell content
        cell_type: Type of cell ('code' or 'markdown')

    Returns:
        JSON string with result
    """
    client = get_client()
    nb_data = await client.get_notebook(notebook_path)
    content = nb_data.get("content", {})

    # - Create new cell
    if cell_type == "code":
        new_cell = nbformat.v4.new_code_cell(source)
    else:
        new_cell = nbformat.v4.new_markdown_cell(source)

    # - Insert at position
    content["cells"].insert(cell_index, dict(new_cell))

    # - Save notebook
    await client.save_notebook(notebook_path, content)

    return json.dumps({
        "success": True,
        "message": f"Inserted {cell_type} cell at index {cell_index}",
        "cell_index": cell_index,
    })


async def update_cell(
    notebook_path: str,
    cell_index: int,
    source: str,
) -> str:
    """
    Update content of an existing cell.

    Args:
        notebook_path: Path to the notebook
        cell_index: Index of the cell (0-based)
        source: New cell content

    Returns:
        JSON string with result
    """
    client = get_client()
    nb_data = await client.get_notebook(notebook_path)
    content = nb_data.get("content", {})
    cells = content.get("cells", [])

    if cell_index < 0 or cell_index >= len(cells):
        return json.dumps({"error": f"Cell index {cell_index} out of range"})

    cells[cell_index]["source"] = source

    # - Save notebook
    await client.save_notebook(notebook_path, content)

    return json.dumps({
        "success": True,
        "message": f"Updated cell at index {cell_index}",
    })


async def delete_cell(notebook_path: str, cell_index: int) -> str:
    """
    Delete a cell from the notebook.

    Args:
        notebook_path: Path to the notebook
        cell_index: Index of the cell to delete (0-based)

    Returns:
        JSON string with result
    """
    client = get_client()
    nb_data = await client.get_notebook(notebook_path)
    content = nb_data.get("content", {})
    cells = content.get("cells", [])

    if cell_index < 0 or cell_index >= len(cells):
        return json.dumps({"error": f"Cell index {cell_index} out of range"})

    deleted_cell = cells.pop(cell_index)

    # - Save notebook
    await client.save_notebook(notebook_path, content)

    return json.dumps({
        "success": True,
        "message": f"Deleted cell at index {cell_index}",
        "deleted_type": deleted_cell.get("cell_type"),
    })
