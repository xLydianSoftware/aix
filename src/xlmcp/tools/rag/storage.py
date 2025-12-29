"""
Storage layer for RAG functionality.
Handles Milvus clients, collections, and tracking files.
"""

import json
import re
from pathlib import Path

from pymilvus import MilvusClient  # noqa: E402

from xlmcp.config import get_config  # noqa: E402

# - Global clients cache: {sanitized_dir_name: MilvusClient}
_clients: dict[str, MilvusClient] = {}

# - Embedding function (singleton)
_embedding_fn = None


def get_embedding_function():
    """
    Get or create the embedding function singleton.
    """
    global _embedding_fn
    if _embedding_fn is None:
        from pymilvus import model

        _embedding_fn = model.DefaultEmbeddingFunction()
    return _embedding_fn


def sanitize_directory_name(dir_path: str) -> str:
    """
    Convert directory path to sanitized cache name.

    Examples:
        /home/quant0/projects/xfiles → projects-xfiles
        /home/user/docs/research → docs-research
    """
    # - Get absolute path
    abs_path = Path(dir_path).expanduser().resolve()

    # - Take last 2 path components (or all if less than 2)
    parts = abs_path.parts
    if len(parts) >= 2:
        name_parts = parts[-2:]
    else:
        name_parts = parts

    # - Join with hyphen and sanitize
    name = "-".join(name_parts)

    # - Replace non-alphanumeric with hyphen
    name = re.sub(r"[^a-zA-Z0-9]+", "-", name)

    # - Remove leading/trailing hyphens
    name = name.strip("-")

    return name.lower()


def get_collection_name(directory: str) -> str:
    """
    Get collection name for directory.
    Milvus requires only letters, numbers, and underscores.
    """
    sanitized = sanitize_directory_name(directory)
    # - Replace hyphens with underscores for Milvus compatibility
    sanitized = sanitized.replace("-", "_")
    return f"knowledge_{sanitized}"


def get_cache_directory(directory: str) -> Path:
    """
    Get cache directory path for a knowledge directory.
    """
    config = get_config()
    sanitized = sanitize_directory_name(directory)
    cache_path = config.rag.cache_dir / sanitized
    cache_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return cache_path


def get_milvus_client(directory: str) -> MilvusClient:
    """
    Get or create Milvus client for directory (singleton per directory).
    """
    sanitized = sanitize_directory_name(directory)

    if sanitized not in _clients:
        cache_dir = get_cache_directory(directory)
        db_path = cache_dir / "milvus.db"
        _clients[sanitized] = MilvusClient(str(db_path))

    return _clients[sanitized]


def cleanup_clients():
    """
    Close all cached Milvus clients and cleanup embedding function.

    Call this at the end of CLI commands to avoid cleanup delays.
    """
    global _clients, _embedding_fn

    # - Close all Milvus clients
    for client in _clients.values():
        try:
            client.close()
        except Exception:
            pass
    _clients.clear()

    # - Cleanup embedding function
    if _embedding_fn is not None:
        try:
            # - Force cleanup of embedding model
            del _embedding_fn
        except Exception:
            pass
        _embedding_fn = None


def ensure_collection(client: MilvusClient, collection_name: str):
    """
    Ensure collection exists with correct schema.
    """
    if client.has_collection(collection_name):
        return

    # - Create collection with 768-dim vectors (PyMilvus DefaultEmbeddingFunction)
    client.create_collection(collection_name, dimension=768, auto_id=True)


def get_tracking_file_path(directory: str) -> Path:
    """
    Get tracking file path for directory.
    """
    cache_dir = get_cache_directory(directory)
    return cache_dir / "tracking.json"


def load_tracking_file(directory: str) -> dict:
    """
    Load tracking data for directory.

    Returns:
        {
            "last_checked": timestamp,
            "files": {
                "/absolute/path/file.md": ["md5_hash", mtime]
            }
        }
    """
    tracking_path = get_tracking_file_path(directory)

    if not tracking_path.exists():
        return {"last_checked": 0, "files": {}}

    try:
        with open(tracking_path) as f:
            data = json.load(f)
            # - Ensure structure
            if "last_checked" not in data:
                data["last_checked"] = 0
            if "files" not in data:
                data["files"] = {}
            return data
    except (json.JSONDecodeError, PermissionError):
        return {"last_checked": 0, "files": {}}


def save_tracking_file(directory: str, data: dict):
    """
    Save tracking data for directory.
    """
    tracking_path = get_tracking_file_path(directory)

    with open(tracking_path, "w") as f:
        json.dump(data, f, indent=2)


async def list_all_indexes() -> str:
    """
    List all indexed knowledge directories with statistics.

    Returns:
        JSON with list of indexes
    """
    config = get_config()
    cache_dir = config.rag.cache_dir

    if not cache_dir.exists():
        return json.dumps({"indexes": []}, indent=2)

    indexes = []

    for subdir in cache_dir.iterdir():
        if not subdir.is_dir():
            continue

        # - Load tracking file
        tracking_path = subdir / "tracking.json"
        if not tracking_path.exists():
            continue

        try:
            with open(tracking_path) as f:
                tracking = json.load(f)

            files = tracking.get("files", {})
            file_count = len(files)
            last_checked = tracking.get("last_checked", 0)

            # - Extract original directory from file paths
            original_dir = None
            if files:
                # - Get first file path and extract common parent
                first_file = next(iter(files.keys()))
                file_path = Path(first_file)
                # - Find the common parent directory
                # - Assume all files share a common root directory
                original_dir = str(file_path.parent)
                # - Try to find the shortest common path
                for file in list(files.keys())[:10]:  # Check first 10 files
                    fp = Path(file)
                    # - Find common parts
                    try:
                        common = Path(*[p for p, q in zip(file_path.parts, fp.parts) if p == q])
                        if len(common.parts) < len(Path(original_dir).parts):
                            original_dir = str(common)
                    except ValueError:
                        pass

            indexes.append(
                {
                    "cache_name": subdir.name,
                    "directory": original_dir,
                    "file_count": file_count,
                    "last_checked": last_checked,
                    "cache_path": str(subdir),
                }
            )
        except (json.JSONDecodeError, PermissionError):
            continue

    return json.dumps({"indexes": indexes}, indent=2)


async def drop_index(directory: str) -> str:
    """
    Drop index and remove all cached data for directory.

    Args:
        directory: Absolute path to directory

    Returns:
        JSON with status
    """
    try:
        collection_name = get_collection_name(directory)
        client = get_milvus_client(directory)

        # - Drop collection if exists
        if client.has_collection(collection_name):
            client.drop_collection(collection_name)

        # - Remove from clients cache
        sanitized = sanitize_directory_name(directory)
        if sanitized in _clients:
            del _clients[sanitized]

        # - Remove cache directory
        cache_dir = get_cache_directory(directory)
        if cache_dir.exists():
            import shutil

            shutil.rmtree(cache_dir)

        return json.dumps({"status": "success", "message": f"Dropped index for {directory}"}, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
