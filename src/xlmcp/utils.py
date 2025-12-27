"""
Utility functions for xlmcp.
"""

import inspect


def list_server_tools() -> list[dict]:
    """
    List all MCP tools registered in the server.

    Returns:
        List of dicts with tool name and description
    """
    from xlmcp.server import mcp

    tools = []

    # - Try to get tools from tool manager
    if hasattr(mcp, '_tool_manager') and hasattr(mcp._tool_manager, '_tools'):
        tool_dict = mcp._tool_manager._tools
        for name, tool in sorted(tool_dict.items()):
            desc = ""
            if hasattr(tool, 'description'):
                desc = tool.description.split('\n')[0][:60]
            tools.append({
                "name": name,
                "description": desc
            })
    else:
        # - Alternative: scan server module for decorated functions
        from xlmcp import server

        for name, obj in inspect.getmembers(server):
            if inspect.iscoroutinefunction(obj) and not name.startswith('_'):
                if obj.__doc__ and (name.startswith('jupyter_') or name.startswith('markdown_')):
                    doc_lines = obj.__doc__.strip().split('\n')
                    desc = doc_lines[0].strip() if doc_lines else ""
                    tools.append({
                        "name": name,
                        "description": desc
                    })

    return tools


def print_tools_list(tools: list[dict]):
    """
    Pretty print list of tools.

    Args:
        tools: List of tool dicts from list_server_tools()
    """
    print(f"\n{'='*80}")
    print("XLMCP Server Tools")
    print(f"{'='*80}\n")
    print(f"Total Tools: {len(tools)}\n")

    for i, tool in enumerate(tools, 1):
        print(f"{i:2d}. {tool['name']}")
        if tool['description']:
            print(f"    {tool['description']}")
        print()

    print(f"{'='*80}\n")
