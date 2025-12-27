"""
Knowledge bases registry management.
"""

import json
import os
from pathlib import Path

import yaml


def get_knowledges_file() -> Path:
    """
    Get path to knowledges.yaml file.

    Returns:
        Path to ~/.aix/knowledges.yaml
    """
    return Path.home() / ".aix" / "knowledges.yaml"


def load_knowledges() -> dict:
    """
    Load knowledge bases from registry file.

    Supports both single path and multiple paths:
    - path: ~/single/directory
    - paths: [~/dir1, ~/dir2]

    Returns:
        Dict of knowledge bases with expanded paths
    """
    knowledges_file = get_knowledges_file()

    if not knowledges_file.exists():
        return {}

    try:
        with open(knowledges_file) as f:
            data = yaml.safe_load(f)

        if not data or "knowledges" not in data:
            return {}

        # - Expand paths with ~ and make absolute
        knowledges = {}
        for name, info in data["knowledges"].items():
            if not isinstance(info, dict):
                continue

            # - Support both 'path' (single) and 'paths' (multiple)
            paths = []
            if "paths" in info:
                # - Multiple paths
                path_list = info["paths"]
                if isinstance(path_list, list):
                    paths = [str(Path(p).expanduser().resolve()) for p in path_list]
            elif "path" in info:
                # - Single path (backward compatibility)
                expanded_path = Path(info["path"]).expanduser().resolve()
                paths = [str(expanded_path)]

            if paths:
                knowledges[name] = {
                    "paths": paths,
                    "description": info.get("description", ""),
                    "tags": info.get("tags", [])
                }

        return knowledges

    except Exception:
        return {}


async def list_knowledges() -> str:
    """
    List all registered knowledge bases.

    Returns:
        JSON with knowledge bases information (including multiple paths per knowledge)
    """
    knowledges = load_knowledges()

    if not knowledges:
        return json.dumps(
            {
                "status": "info",
                "message": "No knowledge bases registered",
                "registry_file": str(get_knowledges_file()),
                "knowledges": {}
            },
            indent=2
        )

    # - Check which ones exist and are indexed
    from xlmcp.tools.rag import storage

    result = {}
    for name, info in knowledges.items():
        paths = info["paths"]

        # - Check status for each path
        path_statuses = []
        for path in paths:
            exists = Path(path).exists()

            # - Check if indexed
            indexed = False
            if exists:
                collection_name = storage.get_collection_name(path)
                client = storage.get_milvus_client(path)
                indexed = client.has_collection(collection_name)

            path_statuses.append({
                "path": path,
                "exists": exists,
                "indexed": indexed
            })

        result[name] = {
            "paths": path_statuses,
            "description": info["description"],
            "tags": info["tags"]
        }

    return json.dumps(
        {
            "status": "success",
            "registry_file": str(get_knowledges_file()),
            "knowledges": result
        },
        indent=2
    )


def get_knowledge_paths(name: str) -> list[str] | None:
    """
    Get paths for a registered knowledge base by name.

    Args:
        name: Knowledge base name

    Returns:
        List of path strings or None if not found
    """
    knowledges = load_knowledges()

    if name in knowledges:
        return knowledges[name]["paths"]

    return None


def get_knowledge_path(name: str) -> str | None:
    """
    Get first path for a registered knowledge base by name.

    Deprecated: Use get_knowledge_paths() for multi-path support.

    Args:
        name: Knowledge base name

    Returns:
        First path string or None if not found
    """
    paths = get_knowledge_paths(name)
    return paths[0] if paths else None
