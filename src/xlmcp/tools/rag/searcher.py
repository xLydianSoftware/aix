"""
Search functionality for markdown documents.
Handles filter building, search execution, and tag/field extraction.
"""

import json

from xlmcp.config import get_config, validate_path
from xlmcp.tools.rag import indexer, storage
from xlmcp.tools.rag.models import DocumentMetadata, SearchResultItem


def build_tag_filter(tags: list[str]) -> str:
    """
    Build Milvus filter expression for tags.

    Args:
        tags: List of tags (e.g., ["#backtest", "#qubx"])

    Returns:
        Filter expression string (e.g., "tags_str like '%#backtest%' and tags_str like '%#qubx%'")
    """
    if not tags:
        return ""

    # - Build LIKE expressions for each tag (AND logic)
    conditions = [f"tags_str like '%{tag}%'" for tag in tags]

    return " and ".join(conditions)


def build_metadata_filter(filters: dict) -> str:
    """
    Build Milvus filter expression for metadata fields.

    Args:
        filters: Dict of filter expressions
                 Examples:
                   {"sharpe > 1.5": None, "Type": "BACKTEST"}
                   {"strategy": "OrderbookImbalance"}

    Returns:
        Filter expression string
    """
    if not filters:
        return ""

    conditions = []

    for key, value in filters.items():
        # - Check if key contains operator (>, <, >=, <=, !=)
        if any(op in key for op in [" > ", " < ", " >= ", " <= ", " != "]):
            # - Direct expression like "sharpe > 1.5"
            conditions.append(key)
        else:
            # - Field equality: Type=BACKTEST or strategy=OrderbookImbalance
            # - Handle "Type" -> "type_field" conversion
            field_name = "type_field" if key.lower() == "type" else key

            if value is None:
                continue
            elif isinstance(value, str):
                conditions.append(f'{field_name} == "{value}"')
            elif isinstance(value, (int, float)):
                conditions.append(f"{field_name} == {value}")

    return " and ".join(conditions)


def combine_filters(tag_filter: str, metadata_filter: str) -> str:
    """
    Combine tag and metadata filters with AND logic.

    Args:
        tag_filter: Tag filter expression
        metadata_filter: Metadata filter expression

    Returns:
        Combined filter expression
    """
    filters = []

    if tag_filter:
        filters.append(f"({tag_filter})")
    if metadata_filter:
        filters.append(f"({metadata_filter})")

    if not filters:
        return ""

    return " and ".join(filters)


async def search_documents(
    directory: str,
    query: str,
    tags: list[str] | None = None,
    metadata_filters: dict | None = None,
    limit: int = 10,
    threshold: float = 0.5,
) -> str:
    """
    Search markdown documents with semantic similarity and filters.

    Args:
        directory: Absolute path to indexed markdown directory
        query: Search query text
        tags: Filter by tags (AND logic)
        metadata_filters: Filter by metadata fields
        limit: Maximum results to return
        threshold: Minimum similarity score (0-1)

    Returns:
        JSON with search results
    """
    try:
        # - Validate directory path
        validated_dir = validate_path(directory)
        directory = str(validated_dir)

        # - Auto-refresh if needed
        await indexer.auto_refresh_if_needed(directory)

        # - Get client and collection
        collection_name = storage.get_collection_name(directory)
        client = storage.get_milvus_client(directory)

        if not client.has_collection(collection_name):
            return json.dumps(
                {"status": "error", "message": f"Directory not indexed: {directory}. Please index first."}, indent=2
            )

        # - Get embedding function
        embedding_fn = storage.get_embedding_function()

        # - Encode query
        query_vectors = embedding_fn.encode_queries([query])

        # - Build filter expression
        tags = tags or []
        metadata_filters = metadata_filters or {}

        tag_filter = build_tag_filter(tags)
        meta_filter = build_metadata_filter(metadata_filters)
        combined_filter = combine_filters(tag_filter, meta_filter)

        # - Execute search
        search_params = {
            "collection_name": collection_name,
            "data": query_vectors,
            "limit": limit,
            "output_fields": ["text", "filename", "path", "metadata_json"],
        }

        if combined_filter:
            search_params["filter"] = combined_filter

        results = client.search(**search_params)

        # - Parse results
        search_results = []
        for res in results[0]:
            # - Calculate similarity score (Milvus returns distance, convert to similarity)
            # - For cosine distance: similarity = 1 - distance
            distance = res.get("distance", 1.0)
            score = 1.0 - distance

            # - Apply threshold
            if score < threshold:
                continue

            # - Parse metadata JSON
            metadata_json = res["entity"].get("metadata_json", "{}")
            try:
                metadata = DocumentMetadata.model_validate_json(metadata_json)
            except Exception:
                metadata = DocumentMetadata()

            # - Build result item
            result_item = SearchResultItem(
                text=res["entity"]["text"],
                filename=res["entity"]["filename"],
                path=res["entity"]["path"],
                score=round(score, 4),
                metadata=metadata,
            )

            search_results.append(result_item.model_dump())

        return json.dumps(
            {"status": "success", "query": query, "results_count": len(search_results), "results": search_results},
            indent=2,
        )

    except PermissionError as e:
        return json.dumps({"status": "error", "message": f"Permission denied: {e}"}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


async def get_all_tags(directory: str) -> str:
    """
    Extract all unique tags from indexed documents with counts.

    Args:
        directory: Absolute path to indexed directory

    Returns:
        JSON with tags and counts
    """
    try:
        # - Validate directory path
        validated_dir = validate_path(directory)
        directory = str(validated_dir)

        # - Get client and collection
        collection_name = storage.get_collection_name(directory)
        client = storage.get_milvus_client(directory)

        if not client.has_collection(collection_name):
            return json.dumps({"status": "error", "message": f"Directory not indexed: {directory}"}, indent=2)

        # - Query all tags_str fields
        results = client.query(collection_name=collection_name, filter="", output_fields=["tags_str"], limit=10000)

        # - Aggregate tags
        tag_counts = {}
        for res in results:
            tags_str = res.get("tags_str", "[]")
            try:
                tags = json.loads(tags_str)
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
            except json.JSONDecodeError:
                pass

        # - Sort by count descending
        sorted_tags = dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True))

        return json.dumps({"status": "success", "tags": sorted_tags}, indent=2)

    except PermissionError as e:
        return json.dumps({"status": "error", "message": f"Permission denied: {e}"}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


async def get_metadata_fields(directory: str) -> str:
    """
    List available metadata fields for filtering with examples.

    Args:
        directory: Absolute path to indexed directory

    Returns:
        JSON with field names, types, and example values
    """
    try:
        # - Validate directory path
        validated_dir = validate_path(directory)
        directory = str(validated_dir)

        # - Get client and collection
        collection_name = storage.get_collection_name(directory)
        client = storage.get_milvus_client(directory)

        if not client.has_collection(collection_name):
            return json.dumps({"status": "error", "message": f"Directory not indexed: {directory}"}, indent=2)

        # - Query sample documents
        results = client.query(
            collection_name=collection_name,
            filter="",
            output_fields=["type_field", "strategy", "sharpe", "cagr", "drawdown", "metadata_json"],
            limit=100,
        )

        # - Collect field info
        fields_info = {
            "type_field": {"type": "string", "examples": set()},
            "strategy": {"type": "string", "examples": set()},
            "sharpe": {"type": "float", "examples": set()},
            "cagr": {"type": "float", "examples": set()},
            "drawdown": {"type": "float", "examples": set()},
        }

        for res in results:
            for field_name in fields_info.keys():
                value = res.get(field_name)
                if value is not None:
                    fields_info[field_name]["examples"].add(str(value))

        # - Convert sets to lists (limited to 5 examples)
        for field_name in fields_info:
            examples = list(fields_info[field_name]["examples"])[:5]
            fields_info[field_name]["examples"] = examples

        return json.dumps({"status": "success", "fields": fields_info}, indent=2)

    except PermissionError as e:
        return json.dumps({"status": "error", "message": f"Permission denied: {e}"}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
