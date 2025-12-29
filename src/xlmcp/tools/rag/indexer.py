"""
Indexing logic for markdown documents.
Handles change detection, document processing, and auto-refresh.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

# - Suppress warnings from dependencies
import warnings
from pathlib import Path

# - Suppress transformers warning (we don't use transformer models)
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
warnings.filterwarnings("ignore", category=Warning, message=".*validate_default.*")
warnings.filterwarnings("ignore", category=Warning, message=".*pkg_resources.*")
warnings.filterwarnings("ignore", message=".*PyTorch.*TensorFlow.*Flax.*")

from llama_index.core import SimpleDirectoryReader  # noqa: E402
from llama_index.core.node_parser import MarkdownNodeParser  # noqa: E402
from llama_index.core.text_splitter import TokenTextSplitter  # noqa: E402

from xlmcp.config import get_config, validate_path  # noqa: E402
from xlmcp.tools.rag import metadata as metadata_module  # noqa: E402
from xlmcp.tools.rag import storage  # noqa: E402
from xlmcp.tools.rag.models import FileType  # noqa: E402


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


def list_knowledge_files(
    directory: str, recursive: bool = True, file_types: list[FileType] | None = None
) -> list[str]:
    """
    List all knowledge files in directory.

    Args:
        directory: Directory path
        recursive: Recursively search subdirectories
        file_types: File types to include (default: all supported types)

    Returns:
        List of absolute paths to knowledge files (.md, .py, .pyx, .ipynb)
    """
    if file_types is None:
        file_types = [FileType.MARKDOWN, FileType.PYTHON, FileType.JUPYTER]

    # - Build set of extensions to match
    extensions = {f".{ft.value}" for ft in file_types}

    # - Add Cython (.pyx) for Python file type
    if FileType.PYTHON in file_types:
        extensions.add(".pyx")

    knowledge_files = []
    directory = Path(directory)

    if recursive:
        for root, dirs, files in os.walk(directory):
            # - Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for file in files:
                if not file.startswith(".") and any(file.endswith(ext) for ext in extensions):
                    knowledge_files.append(str(Path(root) / file))
    else:
        for file in directory.iterdir():
            if file.is_file() and file.suffix in extensions and not file.name.startswith("."):
                knowledge_files.append(str(file))

    return knowledge_files


# - Backward compatibility alias (deprecated)
def list_md_files(directory: str, recursive: bool = True) -> list[str]:
    """
    Deprecated: Use list_knowledge_files() instead.
    List all markdown files in directory.
    """
    return list_knowledge_files(directory, recursive, [FileType.MARKDOWN])


def get_changed_files(directory: str, recursive: bool = True) -> list[str]:
    """
    Get list of changed/new knowledge files compared to tracking file.

    Args:
        directory: Directory path
        recursive: Recursively check subdirectories

    Returns:
        List of file paths that are new or changed
    """
    tracking_data = storage.load_tracking_file(directory)
    tracked_files = tracking_data.get("files", {})

    changed_files = []
    all_knowledge_files = list_knowledge_files(directory, recursive)

    for file_path in all_knowledge_files:
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


async def index_directory(
    directory: str,
    recursive: bool = True,
    force_reindex: bool = False,
    progress_callback: callable | None = None
) -> str:
    """
    Index or update knowledge directory.

    Supports .md, .py, and .ipynb files.

    Args:
        directory: Absolute path to knowledge directory
        recursive: Recursively index subdirectories
        force_reindex: Force full reindex (drop and recreate)
        progress_callback: Optional callback for progress updates (str) -> None

    Returns:
        JSON with indexing results
    """
    def _report(msg: str):
        """Report progress if callback provided."""
        if progress_callback:
            progress_callback(msg)
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
            _report("Dropping existing index...")
            if client.has_collection(collection_name):
                client.drop_collection(collection_name)

            storage.ensure_collection(client, collection_name)

            # - Get all knowledge files
            _report("Discovering files...")
            all_files = list_knowledge_files(directory, recursive)
            files_to_process = all_files
            mode = "Full reindex"
            _report(f"Found {len(files_to_process)} files to index")

        else:
            # - Incremental update
            _report("Checking for changes...")
            changed_files = get_changed_files(directory, recursive)

            if not changed_files:
                _report("Already up to date")
                return json.dumps(
                    {"status": "success", "message": "Already up to date", "processed_files": 0, "total_chunks": 0},
                    indent=2,
                )

            # - Ensure collection exists
            storage.ensure_collection(client, collection_name)

            # - Delete old chunks for changed files
            _report(f"Found {len(changed_files)} changed files")
            _report("Removing old chunks...")
            for file_path in changed_files:
                try:
                    client.delete(collection_name=collection_name, filter=f'path == "{file_path}"')
                except Exception:
                    # - File might not have been indexed before
                    pass

            files_to_process = changed_files
            mode = "Incremental update"

        # - Group files by type
        files_by_type = {FileType.MARKDOWN: [], FileType.PYTHON: [], FileType.JUPYTER: []}
        for file_path in files_to_process:
            ext = Path(file_path).suffix.lstrip(".")
            file_type = FileType.from_extension(ext)
            if file_type:
                files_by_type[file_type].append(file_path)

        # - Report file type distribution
        type_counts = []
        if files_by_type[FileType.MARKDOWN]:
            type_counts.append(f"{len(files_by_type[FileType.MARKDOWN])} .md")
        if files_by_type[FileType.PYTHON]:
            type_counts.append(f"{len(files_by_type[FileType.PYTHON])} .py/.pyx")
        if files_by_type[FileType.JUPYTER]:
            type_counts.append(f"{len(files_by_type[FileType.JUPYTER])} .ipynb")
        if type_counts:
            _report(f"File types: {', '.join(type_counts)}")

        # - Report chunk configuration
        _report(f"Chunk config: size={config.rag.chunk_size} tokens, overlap={config.rag.chunk_overlap} tokens")

        # - Load documents based on file type
        from llama_index.core import Document

        documents = []

        # - Load markdown files with SimpleDirectoryReader
        if files_by_type[FileType.MARKDOWN]:
            _report(f"Loading {len(files_by_type[FileType.MARKDOWN])} markdown files...")
            md_docs = SimpleDirectoryReader(
                input_files=files_by_type[FileType.MARKDOWN], required_exts=[".md"]
            ).load_data()
            documents.extend(md_docs)

        # - Load Python files (extract full text)
        if files_by_type[FileType.PYTHON]:
            _report(f"Loading {len(files_by_type[FileType.PYTHON])} Python files...")
            skipped_large = 0
            for py_file in files_by_type[FileType.PYTHON]:
                # - Check file size
                file_size_mb = Path(py_file).stat().st_size / (1024 * 1024)
                if file_size_mb > config.rag.max_file_size_mb:
                    skipped_large += 1
                    continue

                from xlmcp.tools.rag.parsers import PythonParser

                text = PythonParser.extract_text(py_file)
                doc = Document(text=text, metadata={"file_path": py_file, "file_name": Path(py_file).name})
                documents.append(doc)

            if skipped_large > 0:
                _report(f"  Skipped {skipped_large} Python files > {config.rag.max_file_size_mb}MB")

        # - Load Jupyter notebooks (extract cells + outputs)
        if files_by_type[FileType.JUPYTER]:
            _report(f"Loading {len(files_by_type[FileType.JUPYTER])} Jupyter notebooks...")
            skipped_large = 0
            for nb_file in files_by_type[FileType.JUPYTER]:
                # - Check file size
                file_size_mb = Path(nb_file).stat().st_size / (1024 * 1024)
                if file_size_mb > config.rag.max_file_size_mb:
                    skipped_large += 1
                    continue

                from xlmcp.tools.rag.parsers import JupyterParser

                text = JupyterParser.extract_text(nb_file, skip_outputs=config.rag.skip_notebook_outputs)
                doc = Document(text=text, metadata={"file_path": nb_file, "file_name": Path(nb_file).name})
                documents.append(doc)

            if skipped_large > 0:
                _report(f"  Skipped {skipped_large} Jupyter notebooks > {config.rag.max_file_size_mb}MB")

        if not documents:
            return json.dumps(
                {"status": "success", "message": "No documents to index", "processed_files": 0, "total_chunks": 0},
                indent=2,
            )

        # - Build file_path -> metadata mapping
        _report("Extracting metadata...")
        file_metadata = {}
        for file_path in files_to_process:
            try:
                file_metadata[file_path] = metadata_module.extract_metadata(file_path)
            except Exception:
                # - Skip files with metadata extraction errors
                continue

        # - Parse structure (only for markdown, keep Python/Jupyter as-is)
        _report("Parsing documents...")
        from llama_index.core.schema import TextNode

        nodes = []
        for doc in documents:
            file_path = doc.metadata.get("file_path")
            ext = Path(file_path).suffix.lstrip(".")

            if ext == "md":
                # - Use MarkdownNodeParser for markdown
                parsed = MarkdownNodeParser().get_nodes_from_documents([doc])
                nodes.extend(parsed)
            else:
                # - Keep as-is for Python/Jupyter (already structured)
                node = TextNode(text=doc.text, metadata=doc.metadata)
                nodes.append(node)

        # - Split into chunks
        _report(f"Chunking {len(nodes)} nodes...")
        chunked_nodes = TokenTextSplitter(
            chunk_size=config.rag.chunk_size, chunk_overlap=config.rag.chunk_overlap
        ).get_nodes_from_documents(nodes)

        # - Filter empty and very short chunks (minimum 50 characters)
        # - Very short chunks (like "Share this..." or "About the CD-ROM...") cause poor search results
        chunked_nodes = [node for node in chunked_nodes if len(node.text.strip()) >= 50]

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

        # - Generate embeddings with progress
        _report(f"Generating embeddings for {len(chunked_nodes)} chunks...")

        # - Batch processing for progress reporting
        batch_size = 1000
        vectors = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_vectors = embedding_fn.encode_documents(batch_texts)
            vectors.extend(batch_vectors)

            # - Report progress every batch
            processed = min(i + batch_size, len(texts))
            _report(f"  Embeddings: {processed}/{len(texts)} ({100 * processed // len(texts)}%)")

        _report(f"  Embeddings: {len(texts)}/{len(texts)} (100%) - Complete!")

        # - Build entity dicts
        _report("Building index entries...")
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
        _report(f"Inserting {len(data)} chunks into index...")
        insert_result = client.insert(collection_name=collection_name, data=data)

        # - Update tracking file
        _report("Updating tracking file...")
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
        _report(f"Completed in {elapsed_time:.1f}s")

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
