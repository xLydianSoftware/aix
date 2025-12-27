"""
Tests for RAG search functionality.
"""

import json
import os
import shutil
from pathlib import Path

import pytest

from xlmcp.tools.rag import indexer, searcher

# - Test data directory
TEST_DATA_DIR = str(Path(__file__).parent.parent / "data" / "knowledge1")
TEST_CACHE_DIR = "/tmp/test_xmcp_rag_cache"


@pytest.fixture(autouse=True)
def setup_environment():
    """Set up test environment variables and clean cache."""
    # - Set environment variables
    os.environ["JUPYTER_ALLOWED_DIRS"] = f"{TEST_DATA_DIR},/tmp"
    os.environ["RAG_CACHE_DIR"] = TEST_CACHE_DIR

    # - Clean cache before test
    if Path(TEST_CACHE_DIR).exists():
        shutil.rmtree(TEST_CACHE_DIR)

    yield

    # - Clean cache after test
    if Path(TEST_CACHE_DIR).exists():
        shutil.rmtree(TEST_CACHE_DIR)


@pytest.fixture
async def indexed_directory():
    """Fixture to ensure directory is indexed before tests."""
    await indexer.index_directory(TEST_DATA_DIR, recursive=True, force_reindex=True)
    return TEST_DATA_DIR


@pytest.mark.asyncio
async def test_search_basic(indexed_directory):
    """Test basic semantic search."""
    result = await searcher.search_documents(
        indexed_directory, query="stochastic calculus", limit=5, threshold=0.0
    )
    data = json.loads(result)

    # - Verify success
    assert data["status"] == "success"
    assert data["query"] == "stochastic calculus"

    # - Verify results returned
    assert data["results_count"] >= 0
    assert "results" in data


@pytest.mark.asyncio
async def test_search_with_tags(indexed_directory):
    """Test search with tag filtering."""
    result = await searcher.search_documents(
        indexed_directory, query="strategy", tags=["#backtest"], limit=5, threshold=0.0
    )
    data = json.loads(result)

    # - Verify success
    assert data["status"] == "success"

    # - Verify all results have #backtest tag
    for item in data["results"]:
        metadata_tags = item["metadata"]["tags"]
        assert "#backtest" in metadata_tags


@pytest.mark.asyncio
async def test_search_with_metadata_filters(indexed_directory):
    """Test search with metadata filtering."""
    result = await searcher.search_documents(
        indexed_directory,
        query="backtest",
        metadata_filters={"sharpe > 2.0": None},
        limit=5,
        threshold=0.0,
    )
    data = json.loads(result)

    # - Verify success
    assert data["status"] == "success"

    # - Verify results match filter
    for item in data["results"]:
        sharpe = item["metadata"]["sharpe"]
        if sharpe is not None:
            assert sharpe > 2.0


@pytest.mark.asyncio
async def test_search_combined_filters(indexed_directory):
    """Test search with combined tag and metadata filters."""
    result = await searcher.search_documents(
        indexed_directory,
        query="mean reversion",
        tags=["#strategy"],
        metadata_filters={"Type": "BACKTEST"},
        limit=5,
        threshold=0.0,
    )
    data = json.loads(result)

    # - Verify success
    assert data["status"] == "success"

    # - Verify results match both filters
    for item in data["results"]:
        assert "#strategy" in item["metadata"]["tags"]
        assert item["metadata"]["type_field"] == "BACKTEST"


@pytest.mark.asyncio
async def test_search_result_structure(indexed_directory):
    """Test that search results have correct structure."""
    result = await searcher.search_documents(indexed_directory, query="risk management", limit=1, threshold=0.0)
    data = json.loads(result)

    # - Verify success
    assert data["status"] == "success"

    if data["results_count"] > 0:
        item = data["results"][0]

        # - Verify required fields
        assert "text" in item
        assert "filename" in item
        assert "path" in item
        assert "score" in item
        assert "metadata" in item

        # - Verify metadata structure
        metadata = item["metadata"]
        assert "tags" in metadata
        assert isinstance(metadata["tags"], list)


@pytest.mark.asyncio
async def test_get_all_tags(indexed_directory):
    """Test tag extraction."""
    result = await searcher.get_all_tags(indexed_directory)
    data = json.loads(result)

    # - Verify success
    assert data["status"] == "success"
    assert "tags" in data

    # - Verify tags is a dict
    assert isinstance(data["tags"], dict)

    # - Verify expected tags present
    expected_tags = ["#backtest", "#qubx", "#strategy", "#idea", "#risk-management"]
    tags = data["tags"]

    for expected_tag in expected_tags:
        assert expected_tag in tags
        assert tags[expected_tag] > 0


@pytest.mark.asyncio
async def test_get_metadata_fields(indexed_directory):
    """Test metadata field extraction."""
    result = await searcher.get_metadata_fields(indexed_directory)
    data = json.loads(result)

    # - Verify success
    assert data["status"] == "success"
    assert "fields" in data

    # - Verify expected fields
    fields = data["fields"]
    expected_fields = ["type_field", "strategy", "sharpe", "cagr", "drawdown"]

    for field_name in expected_fields:
        assert field_name in fields
        assert "type" in fields[field_name]
        assert "examples" in fields[field_name]


@pytest.mark.asyncio
async def test_search_not_indexed():
    """Test search on non-indexed directory."""
    # - Use /tmp which is in allowed dirs but create a subdirectory that's not indexed
    non_indexed_dir = "/tmp/non_indexed_dir_test"
    Path(non_indexed_dir).mkdir(exist_ok=True)

    try:
        result = await searcher.search_documents(non_indexed_dir, query="test", limit=5)
        data = json.loads(result)

        # - Verify error (either "not indexed" or "permission denied" is acceptable)
        assert data["status"] == "error"
        assert "not indexed" in data["message"].lower() or "permission denied" in data["message"].lower()

    finally:
        if Path(non_indexed_dir).exists():
            shutil.rmtree(non_indexed_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
