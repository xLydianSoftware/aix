"""Kernel management and code execution tools for MCP."""

import json

from xlmcp.tools.jupyter.client import get_client


async def list_kernels() -> str:
    """
    List all running kernels.

    Returns:
        JSON string with list of active kernels
    """
    client = get_client()
    kernels = await client.list_kernels()

    result = []
    for k in kernels:
        result.append({
            "id": k.get("id"),
            "name": k.get("name"),
            "state": k.get("execution_state"),
            "connections": k.get("connections", 0),
        })

    return json.dumps({"kernels": result, "count": len(result)}, indent=2)


async def start_kernel(kernel_name: str = "python3") -> str:
    """
    Start a new kernel.

    Args:
        kernel_name: Name of the kernel spec (default: python3)

    Returns:
        JSON string with new kernel info
    """
    client = get_client()
    kernel = await client.start_kernel(kernel_name)

    return json.dumps({
        "success": True,
        "kernel_id": kernel.get("id"),
        "name": kernel.get("name"),
        "state": kernel.get("execution_state"),
    }, indent=2)


async def stop_kernel(kernel_id: str) -> str:
    """
    Stop a running kernel.

    Args:
        kernel_id: ID of the kernel to stop

    Returns:
        JSON string with result
    """
    client = get_client()
    success = await client.stop_kernel(kernel_id)

    return json.dumps({
        "success": success,
        "message": f"Kernel {kernel_id} stopped" if success else f"Failed to stop kernel {kernel_id}",
    })


async def restart_kernel(kernel_id: str) -> str:
    """
    Restart a kernel.

    Args:
        kernel_id: ID of the kernel to restart

    Returns:
        JSON string with result
    """
    client = get_client()
    kernel = await client.restart_kernel(kernel_id)

    return json.dumps({
        "success": True,
        "kernel_id": kernel.get("id"),
        "state": kernel.get("execution_state"),
        "message": "Kernel restarted",
    }, indent=2)


async def interrupt_kernel(kernel_id: str) -> str:
    """
    Interrupt a running kernel (stop current execution).

    Args:
        kernel_id: ID of the kernel to interrupt

    Returns:
        JSON string with result
    """
    client = get_client()
    success = await client.interrupt_kernel(kernel_id)

    return json.dumps({
        "success": success,
        "message": f"Kernel {kernel_id} interrupted" if success else f"Failed to interrupt kernel {kernel_id}",
    })


async def execute_code(
    kernel_id: str,
    code: str,
    timeout: float | None = None,
) -> str:
    """
    Execute code in a running kernel.

    Args:
        kernel_id: ID of the kernel to execute in
        code: Python code to execute
        timeout: Execution timeout in seconds (default: from config)

    Returns:
        JSON string with execution result and outputs
    """
    client = get_client()
    result = await client.execute_code(kernel_id, code, timeout)

    # - Format outputs for display
    formatted_outputs = []
    for output in result.get("outputs", []):
        if output["type"] == "stream":
            formatted_outputs.append({
                "type": "stream",
                "name": output.get("name"),
                "text": output.get("text"),
            })
        elif output["type"] == "execute_result":
            data = output.get("data", {})
            # - Prefer text/plain for MCP output
            text = data.get("text/plain", str(data))
            formatted_outputs.append({
                "type": "result",
                "text": text,
                "execution_count": output.get("execution_count"),
            })
        elif output["type"] == "display_data":
            data = output.get("data", {})
            formatted_outputs.append({
                "type": "display",
                "text": data.get("text/plain", ""),
                "has_image": "image/png" in data,
                "has_html": "text/html" in data,
            })

    response = {
        "status": result["status"],
        "outputs": formatted_outputs,
    }

    if result.get("error"):
        response["error"] = {
            "name": result["error"].get("ename"),
            "value": result["error"].get("evalue"),
            "traceback": result["error"].get("traceback", []),
        }

    return json.dumps(response, indent=2)


async def get_or_create_kernel_for_notebook(notebook_path: str) -> str:
    """
    Get existing kernel for a notebook or create a new session.

    Args:
        notebook_path: Path to the notebook

    Returns:
        JSON string with kernel info
    """
    client = get_client()

    # - Check for existing session
    session = await client.get_session_for_notebook(notebook_path)

    if session:
        kernel = session.get("kernel", {})
        return json.dumps({
            "status": "existing",
            "session_id": session.get("id"),
            "kernel_id": kernel.get("id"),
            "kernel_name": kernel.get("name"),
            "kernel_state": kernel.get("execution_state"),
        }, indent=2)

    # - Get kernel name from notebook metadata
    nb_data = await client.get_notebook(notebook_path)
    content = nb_data.get("content", {})
    kernel_name = content.get("metadata", {}).get("kernelspec", {}).get("name", "python3")

    # - Create new session with correct kernel
    session = await client.create_session(notebook_path, kernel_name=kernel_name)
    kernel = session.get("kernel", {})

    return json.dumps({
        "status": "created",
        "session_id": session.get("id"),
        "kernel_id": kernel.get("id"),
        "kernel_name": kernel.get("name"),
        "kernel_state": kernel.get("execution_state"),
    }, indent=2)


async def execute_notebook_cell(
    notebook_path: str,
    cell_index: int,
    timeout: float | None = None,
    save_outputs: bool = True,
) -> str:
    """
    Execute a specific cell in a notebook.

    This will:
    1. Get or create a kernel session for the notebook
    2. Read the cell content
    3. Execute the code
    4. Save outputs to notebook (if save_outputs=True)
    5. Return the output

    Args:
        notebook_path: Path to the notebook
        cell_index: Index of the cell to execute (0-based)
        timeout: Execution timeout in seconds
        save_outputs: Whether to save outputs to notebook file (default: True)

    Returns:
        JSON string with execution result
    """
    client = get_client()

    # - Get notebook content
    nb_data = await client.get_notebook(notebook_path)
    content = nb_data.get("content", {})
    cells = content.get("cells", [])

    if cell_index < 0 or cell_index >= len(cells):
        return json.dumps({"error": f"Cell index {cell_index} out of range (0-{len(cells)-1})"})

    cell = cells[cell_index]

    if cell.get("cell_type") != "code":
        return json.dumps({
            "status": "skipped",
            "message": f"Cell {cell_index} is a {cell.get('cell_type')} cell, not code",
        })

    # - Get or create kernel (using notebook's kernel metadata)
    session = await client.get_session_for_notebook(notebook_path)
    if not session:
        kernel_name = content.get("metadata", {}).get("kernelspec", {}).get("name", "python3")
        session = await client.create_session(notebook_path, kernel_name=kernel_name)

    kernel_id = session.get("kernel", {}).get("id")
    if not kernel_id:
        return json.dumps({"error": "Could not get kernel for notebook"})

    # - Execute the cell
    code = cell.get("source", "")
    result = await client.execute_code(kernel_id, code, timeout)

    # - Save outputs to notebook if requested
    if save_outputs:
        # - Convert outputs to notebook format
        nb_outputs = []
        for output in result.get("outputs", []):
            if output["type"] == "stream":
                nb_outputs.append({
                    "output_type": "stream",
                    "name": output.get("name", "stdout"),
                    "text": output.get("text", ""),
                })
            elif output["type"] == "execute_result":
                nb_outputs.append({
                    "output_type": "execute_result",
                    "data": output.get("data", {}),
                    "metadata": {},
                    "execution_count": output.get("execution_count"),
                })
            elif output["type"] == "display_data":
                nb_outputs.append({
                    "output_type": "display_data",
                    "data": output.get("data", {}),
                    "metadata": output.get("metadata", {}),
                })
            elif output["type"] == "error":
                nb_outputs.append({
                    "output_type": "error",
                    "ename": output.get("ename", "Error"),
                    "evalue": output.get("evalue", ""),
                    "traceback": output.get("traceback", []),
                })

        # - Handle error output
        if result.get("error"):
            nb_outputs.append({
                "output_type": "error",
                "ename": result["error"].get("ename", "Error"),
                "evalue": result["error"].get("evalue", ""),
                "traceback": result["error"].get("traceback", []),
            })

        # - Update cell outputs and execution count
        cells[cell_index]["outputs"] = nb_outputs
        cells[cell_index]["execution_count"] = len([c for c in cells[:cell_index+1] if c.get("cell_type") == "code"])

        # - Save notebook
        await client.save_notebook(notebook_path, content)

    return json.dumps({
        "cell_index": cell_index,
        "status": result["status"],
        "outputs": result.get("outputs", []),
        "error": result.get("error"),
        "saved_to_notebook": save_outputs,
    }, indent=2)
