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
            if isinstance(info, dict) and "path" in info:
                expanded_path = Path(info["path"]).expanduser().resolve()
                knowledges[name] = {
                    "path": str(expanded_path),
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
        JSON with knowledge bases information
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
    from xmcp.tools.rag import storage

    result = {}
    for name, info in knowledges.items():
        path = info["path"]
        exists = Path(path).exists()

        # - Check if indexed
        indexed = False
        if exists:
            collection_name = storage.get_collection_name(path)
            client = storage.get_milvus_client(path)
            indexed = client.has_collection(collection_name)

        result[name] = {
            "path": path,
            "description": info["description"],
            "tags": info["tags"],
            "exists": exists,
            "indexed": indexed
        }

    return json.dumps(
        {
            "status": "success",
            "registry_file": str(get_knowledges_file()),
            "knowledges": result
        },
        indent=2
    )


def get_knowledge_path(name: str) -> str | None:
    """
    Get path for a registered knowledge base by name.

    Args:
        name: Knowledge base name

    Returns:
        Path string or None if not found
    """
    knowledges = load_knowledges()

    if name in knowledges:
        return knowledges[name]["path"]

    return None
