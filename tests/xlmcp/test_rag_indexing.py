"""
Tests for RAG indexing functionality.
"""

import json
import os
import shutil
from pathlib import Path

import pytest

from xlmcp.tools.rag import indexer

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


@pytest.mark.asyncio
async def test_index_directory_force_reindex():
    """Test full reindex of directory."""
    result = await indexer.index_directory(TEST_DATA_DIR, recursive=True, force_reindex=True)
    data = json.loads(result)

    # - Verify success
    assert data["status"] == "success"
    assert data["message"] == "Full reindex"

    # - Verify file count (6 markdown files)
    assert data["processed_files"] == 6

    # - Verify chunks created
    assert data["total_chunks"] > 0

    # - Verify elapsed time is reasonable
    assert data["elapsed_seconds"] > 0
    assert data["elapsed_seconds"] < 60  # Should complete in under 60 seconds


@pytest.mark.asyncio
async def test_index_directory_incremental():
    """Test incremental update (no changes)."""
    # - First index
    await indexer.index_directory(TEST_DATA_DIR, recursive=True, force_reindex=True)

    # - Second index (should detect no changes)
    result = await indexer.index_directory(TEST_DATA_DIR, recursive=True, force_reindex=False)
    data = json.loads(result)

    # - Verify already up to date
    assert data["status"] == "success"
    assert data["message"] == "Already up to date"
    assert data["processed_files"] == 0
    assert data["total_chunks"] == 0


@pytest.mark.asyncio
async def test_index_directory_with_changes():
    """Test incremental update with new file."""
    # - First index
    await indexer.index_directory(TEST_DATA_DIR, recursive=True, force_reindex=True)

    # - Create new file
    new_file = Path(TEST_DATA_DIR) / "test_new.md"
    new_file.write_text("# New Test File\n\nThis is new content with #test tag.")

    try:
        # - Second index (should detect change)
        result = await indexer.index_directory(TEST_DATA_DIR, recursive=True, force_reindex=False)
        data = json.loads(result)

        # - Verify incremental update
        assert data["status"] == "success"
        assert data["message"] == "Incremental update"
        assert data["processed_files"] == 1
        assert data["total_chunks"] > 0

    finally:
        # - Clean up
        if new_file.exists():
            new_file.unlink()


@pytest.mark.asyncio
async def test_index_directory_permission_error():
    """Test indexing with invalid directory path."""
    invalid_dir = "/invalid/path/that/does/not/exist"

    result = await indexer.index_directory(invalid_dir, recursive=True)
    data = json.loads(result)

    # - Verify error
    assert data["status"] == "error"
    assert "Permission denied" in data["message"] or "not/exist" in data["message"]


@pytest.mark.asyncio
async def test_get_changed_files():
    """Test change detection logic."""
    # - First index
    await indexer.index_directory(TEST_DATA_DIR, recursive=True, force_reindex=True)

    # - Check for changes (should be none)
    changed_files = indexer.get_changed_files(TEST_DATA_DIR, recursive=True)
    assert len(changed_files) == 0

    # - Modify a file
    test_file = Path(TEST_DATA_DIR) / "strategies" / "backtests" / "test_backtest.md"
    original_content = test_file.read_text()

    try:
        test_file.write_text(original_content + "\n\n## New Section\n\nAdded content.")

        # - Check for changes (should detect 1 file)
        changed_files = indexer.get_changed_files(TEST_DATA_DIR, recursive=True)
        assert len(changed_files) == 1
        assert str(test_file) in changed_files

    finally:
        # - Restore original content
        test_file.write_text(original_content)


@pytest.mark.asyncio
async def test_list_md_files():
    """Test markdown file listing."""
    md_files = indexer.list_md_files(TEST_DATA_DIR, recursive=True)

    # - Verify count
    assert len(md_files) == 6

    # - Verify all are .md files
    for file_path in md_files:
        assert file_path.endswith(".md")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
