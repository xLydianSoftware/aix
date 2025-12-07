# Markdown RAG Implementation Summary

## Overview

Successfully implemented markdown document search capabilities for the xmcp server. The system now supports semantic search, tag filtering, metadata filtering, and auto-refresh functionality.

## Implementation Completed

### 1. Dependencies Added
- `llama-index>=0.12.45` - Document loading, parsing, chunking
- `pymilvus[model,milvus_lite]>=2.5.11` - Vector DB with local embeddings
- `python-frontmatter>=1.0.0` - YAML frontmatter parsing

### 2. Configuration (src/xmcp/config.py)
New `RAGConfig` class with environment variables:
- `RAG_CACHE_DIR` - Cache directory (default: ~/.aix/knowledge)
- `RAG_CHUNK_SIZE` - Token chunk size (default: 512)
- `RAG_CHUNK_OVERLAP` - Chunk overlap (default: 100)
- `RAG_AUTO_REFRESH` - Enable auto-refresh (default: true)
- `RAG_AUTO_REFRESH_INTERVAL` - Check interval in seconds (default: 300)
- `RAG_DEFAULT_SEARCH_LIMIT` - Max search results (default: 10)
- `RAG_DEFAULT_SIMILARITY_THRESHOLD` - Min similarity score (default: 0.5)

### 3. RAG Module Structure
```
src/xmcp/tools/rag/
├── __init__.py          # Exports
├── models.py            # DocumentMetadata, DocumentEntity, SearchResultItem
├── storage.py           # Milvus clients, collections, tracking files
├── metadata.py          # YAML frontmatter & hashtag extraction
├── indexer.py           # Indexing & auto-refresh
└── searcher.py          # Search with filters
```

### 4. MCP Tools Registered (7 tools)

#### markdown_index_directory
Index or update markdown directory with auto-detection of changes.
```python
await markdown_index_directory(
    directory="/home/quant0/projects/xfiles",
    recursive=True,
    force_reindex=False
)
```

#### markdown_search
Semantic search with tag and metadata filtering.
```python
await markdown_search(
    directory="/home/quant0/projects/xfiles",
    query="mean-reversion strategy entries",
    tags=["#idea", "#strategy"],
    metadata_filters={"sharpe > 1.5": None, "Type": "BACKTEST"},
    limit=10,
    threshold=0.5
)
```

#### markdown_list_indexes
List all indexed directories with statistics.

#### markdown_refresh_index
Manually force refresh of index.

#### markdown_get_tags
Extract all unique tags with counts.

#### markdown_get_metadata_fields
List available metadata fields for filtering.

#### markdown_drop_index
Drop index and remove cached data.

## Features

### Semantic Search
- Uses PyMilvus DefaultEmbeddingFunction (768-dim vectors)
- Local embeddings, no API costs
- Fast search with cosine similarity

### Tag Filtering
- Extracts tags from YAML frontmatter
- Finds inline hashtags (#idea, #strategy, #backtest, etc.)
- Filters out HTML color codes (#f86d2d)
- Combines frontmatter + inline tags

### Metadata Filtering
- Parses YAML frontmatter
- Supports numeric fields (sharpe, cagr, drawdown)
- Supports string fields (Type, strategy, author)
- Custom filter expressions (e.g., "sharpe > 1.5")

### Multiple Directories
- Each directory gets separate Milvus collection
- Cached in ~/.aix/knowledge/<sanitized-name>/
- Independent lifecycle (index, search, drop)

### Incremental Indexing
- MD5 hash + mtime change detection
- Only reindex changed/new files
- Tracking file per directory

### Auto-Refresh
- Configurable check interval (default: 5 min)
- Check-on-search with throttling
- No background threads (simple)

## Test Results

**Test Directory**: /home/quant0/projects/xfiles/Studies (5 files)

**Indexing Performance**:
- Processed: 5 files
- Total chunks: 181
- Time: ~13 seconds

**Search Results** (query: "stochastic calculus"):
```json
{
  "results_count": 3,
  "results": [
    {
      "text": "## 4. Introduction to Stochastic Calculus",
      "filename": "SC01_Continuous_Processes_Brownian_Motion.md",
      "score": 0.134
    },
    {
      "text": "## 5. Itô's Formula: The Fundamental Theorem of Stochastic Calculus",
      "filename": "SC01_Continuous_Processes_Brownian_Motion.md",
      "score": 0.2229
    },
    {
      "text": "## 6. Solving Stochastic Differential Equations",
      "filename": "SC01_Continuous_Processes_Brownian_Motion.md",
      "score": 0.3387
    }
  ]
}
```

## Use Cases

### 1. Find mentions of mean-reversion strategies
```python
await markdown_search(
    directory="/home/quant0/projects/xfiles",
    query="mean-reversion strategy entries",
    limit=10
)
```

### 2. Find all ideas tagged #idea related to strategy entries
```python
await markdown_search(
    directory="/home/quant0/projects/xfiles",
    query="strategy entries",
    tags=["#idea"],
    limit=10
)
```

### 3. Find high-Sharpe backtests
```python
await markdown_search(
    directory="/home/quant0/projects/xfiles",
    query="backtests",
    metadata_filters={"sharpe > 1.5": None, "Type": "BACKTEST"},
    limit=10
)
```

### 4. Make brief essay about risk management
```python
# First search for all risk management content
results = await markdown_search(
    directory="/home/quant0/projects/xfiles",
    query="risk management",
    limit=50
)
# Then aggregate results into essay
```

## Next Steps

1. Index full /home/quant0/projects/xfiles directory (778 files)
2. Test with real use cases
3. Monitor performance and adjust chunk size if needed
4. Add more metadata fields as needed

## Files Modified/Created

**Modified**:
- /home/quant0/devs/aix/pyproject.toml
- /home/quant0/devs/aix/src/xmcp/config.py
- /home/quant0/devs/aix/src/xmcp/server.py

**Created**:
- /home/quant0/devs/aix/src/xmcp/tools/rag/__init__.py
- /home/quant0/devs/aix/src/xmcp/tools/rag/models.py
- /home/quant0/devs/aix/src/xmcp/tools/rag/storage.py
- /home/quant0/devs/aix/src/xmcp/tools/rag/metadata.py
- /home/quant0/devs/aix/src/xmcp/tools/rag/indexer.py
- /home/quant0/devs/aix/src/xmcp/tools/rag/searcher.py
- /home/quant0/devs/aix/tests/xmcp/test_rag.py

## Notes

- All markdown indexing honors `JUPYTER_ALLOWED_DIRS` configuration for security
- Cache directory permissions: 0700 (user only)
- Milvus collection names: only letters, numbers, underscores (hyphens converted)
- Empty frontmatter handled gracefully
- Malformed YAML catches exceptions, continues with inline tags
