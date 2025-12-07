"""
Indexing logic for markdown documents.
Handles change detection, document processing, and auto-refresh.
"""

import hashlib
import json
import os
import time
from pathlib import Path

from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import MarkdownNodeParser
from llama_index.core.text_splitter import TokenTextSplitter

from xmcp.config import get_config, validate_path
from xmcp.tools.rag import metadata as metadata_module
from xmcp.tools.rag import storage


def get_file_hash_and_mtime(file_path: str) -> tuple[str, float]:
    """
    Get MD5 hash and modification time for file.

    Args:
        file_path: Path to file

    Returns:
        (md5_hash, mtime)
    """
    with open(file_path, "rb") as f:
        file_hash = hashlib.md5(f.read()).hexdigest()

    mtime = os.path.getmtime(file_path)

    return file_hash, mtime


def list_md_files(directory: str, recursive: bool = True) -> list[str]:
    """
    List all markdown files in directory.

    Args:
        directory: Directory path
        recursive: Recursively search subdirectories

    Returns:
        List of absolute paths to .md files
    """
    md_files = []
    directory = Path(directory)

    if recursive:
        for root, dirs, files in os.walk(directory):
            # - Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for file in files:
                if file.endswith(".md") and not file.startswith("."):
                    md_files.append(str(Path(root) / file))
    else:
        for file in directory.iterdir():
            if file.is_file() and file.suffix == ".md" and not file.name.startswith("."):
                md_files.append(str(file))

    return md_files


def get_changed_files(directory: str, recursive: bool = True) -> list[str]:
    """
    Get list of changed/new markdown files compared to tracking file.

    Args:
        directory: Directory path
        recursive: Recursively check subdirectories

    Returns:
        List of file paths that are new or changed
    """
    tracking_data = storage.load_tracking_file(directory)
    tracked_files = tracking_data.get("files", {})

    changed_files = []
    all_md_files = list_md_files(directory, recursive)

    for file_path in all_md_files:
        if file_path not in tracked_files:
            # - New file
            changed_files.append(file_path)
            continue

        try:
            current_hash, current_mtime = get_file_hash_and_mtime(file_path)
        except (FileNotFoundError, PermissionError):
            # - File no longer accessible
            continue

        stored_hash, stored_mtime = tracked_files[file_path]

        if current_hash != stored_hash or current_mtime != stored_mtime:
            # - File changed
            changed_files.append(file_path)

    return changed_files


def should_auto_refresh(directory: str) -> bool:
    """
    Check if auto-refresh interval has elapsed.

    Args:
        directory: Directory path

    Returns:
        True if should refresh
    """
    config = get_config()

    if not config.rag.auto_refresh:
        return False

    tracking_data = storage.load_tracking_file(directory)
    last_checked = tracking_data.get("last_checked", 0)
    now = time.time()

    elapsed = now - last_checked

    return elapsed >= config.rag.auto_refresh_interval


async def index_directory(directory: str, recursive: bool = True, force_reindex: bool = False) -> str:
    """
    Index or update markdown directory.

    Args:
        directory: Absolute path to markdown directory
        recursive: Recursively index subdirectories
        force_reindex: Force full reindex (drop and recreate)

    Returns:
        JSON with indexing results
    """
    try:
        # - Validate directory path
        validated_dir = validate_path(directory)
        directory = str(validated_dir)

        config = get_config()
        collection_name = storage.get_collection_name(directory)
        client = storage.get_milvus_client(directory)
        embedding_fn = storage.get_embedding_function()

        # - Track start time
        start_time = time.time()

        if force_reindex:
            # - Drop existing collection
            if client.has_collection(collection_name):
                client.drop_collection(collection_name)

            storage.ensure_collection(client, collection_name)

            # - Get all files
            all_files = list_md_files(directory, recursive)
            files_to_process = all_files
            mode = "Full reindex"

        else:
            # - Incremental update
            changed_files = get_changed_files(directory, recursive)

            if not changed_files:
                return json.dumps(
                    {"status": "success", "message": "Already up to date", "processed_files": 0, "total_chunks": 0},
                    indent=2,
                )

            # - Ensure collection exists
            storage.ensure_collection(client, collection_name)

            # - Delete old chunks for changed files
            for file_path in changed_files:
                try:
                    client.delete(collection_name=collection_name, filter=f'path == "{file_path}"')
                except Exception:
                    # - File might not have been indexed before
                    pass

            files_to_process = changed_files
            mode = "Incremental update"

        # - Load markdown documents
        documents = SimpleDirectoryReader(input_files=files_to_process, required_exts=[".md"]).load_data()

        if not documents:
            return json.dumps(
                {"status": "success", "message": "No documents to index", "processed_files": 0, "total_chunks": 0},
                indent=2,
            )

        # - Build file_path -> metadata mapping
        file_metadata = {}
        for file_path in files_to_process:
            try:
                file_metadata[file_path] = metadata_module.extract_metadata(file_path)
            except Exception:
                # - Skip files with metadata extraction errors
                continue

        # - Parse markdown structure
        nodes = MarkdownNodeParser().get_nodes_from_documents(documents)

        # - Split into chunks
        chunked_nodes = TokenTextSplitter(
            chunk_size=config.rag.chunk_size, chunk_overlap=config.rag.chunk_overlap
        ).get_nodes_from_documents(nodes)

        # - Filter empty chunks
        chunked_nodes = [node for node in chunked_nodes if node.text.strip()]

        if not chunked_nodes:
            return json.dumps(
                {
                    "status": "success",
                    "message": "No content to index (all chunks empty)",
                    "processed_files": len(files_to_process),
                    "total_chunks": 0,
                },
                indent=2,
            )

        # - Extract text for embedding
        texts = [node.text for node in chunked_nodes]

        # - Generate embeddings
        vectors = embedding_fn.encode_documents(texts)

        # - Build entity dicts
        data = []
        for vector, node in zip(vectors, chunked_nodes):
            file_path = node.metadata.get("file_path")
            filename = node.metadata.get("file_name")

            # - Get metadata for this file
            doc_metadata = file_metadata.get(file_path)
            if not doc_metadata:
                # - Fallback to empty metadata
                doc_metadata = metadata_module.DocumentMetadata()

            # - Build entity dict
            entity_dict = metadata_module.build_entity_dict(node.text, doc_metadata, filename, file_path)
            entity_dict["vector"] = vector

            data.append(entity_dict)

        # - Insert into Milvus
        insert_result = client.insert(collection_name=collection_name, data=data)

        # - Update tracking file
        tracking_data = storage.load_tracking_file(directory)
        tracking_data["last_checked"] = time.time()

        if "files" not in tracking_data:
            tracking_data["files"] = {}

        for file_path in files_to_process:
            try:
                tracking_data["files"][file_path] = list(get_file_hash_and_mtime(file_path))
            except (FileNotFoundError, PermissionError):
                # - Skip files that became inaccessible
                pass

        storage.save_tracking_file(directory, tracking_data)

        # - Calculate elapsed time
        elapsed_time = time.time() - start_time

        return json.dumps(
            {
                "status": "success",
                "message": mode,
                "processed_files": len(files_to_process),
                "total_chunks": len(chunked_nodes),
                "elapsed_seconds": round(elapsed_time, 2),
                "files": [os.path.basename(f) for f in files_to_process[:10]],  # First 10 files
            },
            indent=2,
        )

    except PermissionError as e:
        return json.dumps({"status": "error", "message": f"Permission denied: {e}"}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


async def refresh_index(directory: str | None = None, recursive: bool = True) -> str:
    """
    Manually force refresh of markdown index.

    Args:
        directory: Directory to refresh (None = refresh all)
        recursive: Recursively check subdirectories

    Returns:
        JSON with refresh results
    """
    if directory:
        # - Refresh single directory
        return await index_directory(directory, recursive, force_reindex=False)
    else:
        # - Refresh all indexed directories
        indexes_json = await storage.list_all_indexes()
        indexes_data = json.loads(indexes_json)

        results = []
        for index_info in indexes_data.get("indexes", []):
            cache_name = index_info["cache_name"]
            # - TODO: Need to reverse-engineer directory from cache_name
            # - For now, skip this functionality
            pass

        return json.dumps({"status": "error", "message": "Refresh all not implemented yet"}, indent=2)


async def auto_refresh_if_needed(directory: str, recursive: bool = True):
    """
    Auto-refresh index if interval elapsed.

    Args:
        directory: Directory path
        recursive: Recursively check subdirectories
    """
    if should_auto_refresh(directory):
        await index_directory(directory, recursive, force_reindex=False)
