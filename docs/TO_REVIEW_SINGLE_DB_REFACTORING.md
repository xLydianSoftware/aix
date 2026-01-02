# Refactor: Single Milvus Database with Multiple Collections

## Overview

Refactor the Milvus storage layer from **multiple databases** (one per knowledge directory) to a **single database with multiple collections** for better performance and resource management.

## Current Architecture

```
~/.aix/knowledge/
├── xfiles-library/
│   ├── milvus.db          ← Separate DB
│   └── tracking.json
├── xfiles-backtests/
│   ├── milvus.db          ← Separate DB
│   └── tracking.json
└── xincubator-indicators/
    ├── milvus.db          ← Separate DB
    └── tracking.json
```

**Problems:**
- Multiple DB connections when searching across KBs
- More file overhead (each DB has metadata)
- Slower multi-KB searches
- More Milvus client instances

## Target Architecture

```
~/.aix/knowledge/
├── milvus.db              ← Single shared DB
│   ├── collection: knowledge_xfiles_library
│   ├── collection: knowledge_xfiles_backtests
│   └── collection: knowledge_xincubator_indicators
├── xfiles-library/
│   └── tracking.json      ← Tracking files stay separate
├── xfiles-backtests/
│   └── tracking.json
└── xincubator-indicators/
    └── tracking.json
```

**Benefits:**
- Single DB connection = faster searches
- Less file overhead
- Better resource management
- Standard Milvus usage pattern

## Implementation Plan

### Phase 1: Update Storage Layer

**File:** `src/xlmcp/tools/rag/storage.py`

#### 1.1 Change Global Client to Singleton

**Current (Lines 14-15):**
```python
_clients: dict[str, MilvusClient] = {}  # One per directory
_embedding_fn = None
```

**New:**
```python
_global_client: MilvusClient | None = None  # Single client
_embedding_fn = None
```

#### 1.2 Rewrite `get_milvus_client()`

**Current (Lines 85-96):**
```python
def get_milvus_client(directory: str) -> MilvusClient:
    sanitized = sanitize_directory_name(directory)
    if sanitized not in _clients:
        cache_dir = get_cache_directory(directory)
        db_path = cache_dir / "milvus.db"
        _clients[sanitized] = MilvusClient(str(db_path))
    return _clients[sanitized]
```

**New:**
```python
def get_milvus_client(directory: str | None = None) -> MilvusClient:
    """
    Get or create the global Milvus client.

    Args:
        directory: Ignored (kept for API compatibility)

    Returns:
        Global MilvusClient instance
    """
    global _global_client

    if _global_client is None:
        config = get_config()
        db_path = config.rag.cache_dir / "milvus.db"
        db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _global_client = MilvusClient(str(db_path))

    return _global_client
```

#### 1.3 Update `cleanup_clients()`

**Current (Lines 99-123):**
```python
def cleanup_clients():
    global _clients, _embedding_fn

    for client in _clients.values():
        try:
            client.close()
        except Exception:
            pass
    _clients.clear()

    # ... embedding cleanup
```

**New:**
```python
def cleanup_clients():
    """
    Close global Milvus client and cleanup embedding function.
    """
    global _global_client, _embedding_fn

    # - Close global client
    if _global_client is not None:
        try:
            _global_client.close()
        except Exception:
            pass
        _global_client = None

    # - Cleanup embedding function
    if _embedding_fn is not None:
        try:
            del _embedding_fn
        except Exception:
            pass
        _embedding_fn = None
```

#### 1.4 Update `drop_index()`

**Current (Lines 251-284):**
```python
async def drop_index(directory: str) -> str:
    # ... drop collection

    # - Remove from clients cache
    sanitized = sanitize_directory_name(directory)
    if sanitized in _clients:
        del _clients[sanitized]

    # - Remove cache directory
    shutil.rmtree(cache_dir)
```

**New:**
```python
async def drop_index(directory: str) -> str:
    # ... drop collection (same)

    # - Remove only tracking.json (keep cache dir for shared DB)
    tracking_file = cache_dir / "tracking.json"
    if tracking_file.exists():
        tracking_file.unlink()

    # - Note: Keep cache_dir (contains shared milvus.db)
```

#### 1.5 Update `get_cache_directory()`

**Keep mostly same, but note it's now for tracking files:**

```python
def get_cache_directory(directory: str) -> Path:
    """
    Get cache directory path for tracking files.

    Note: The Milvus DB is now at ~/.aix/knowledge/milvus.db (shared),
    but tracking.json files remain per-directory for organization.
    """
    config = get_config()
    sanitized = sanitize_directory_name(directory)
    cache_path = config.rag.cache_dir / sanitized
    cache_path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return cache_path
```

### Phase 2: Update list_all_indexes()

**File:** `src/xlmcp/tools/rag/storage.py` (Lines 184-249)

**Current approach:**
- Lists directories in `~/.aix/knowledge/`
- Each directory has its own `milvus.db`

**New approach:**
- Get list of collections from global Milvus client
- Match collections to tracking files
- Extract directory from collection name

**Implementation:**
```python
async def list_all_indexes() -> str:
    """
    List all indexed directories from the shared Milvus database.
    """
    try:
        client = get_milvus_client()

        # - Get all collections with "knowledge_" prefix
        all_collections = client.list_collections()
        knowledge_collections = [c for c in all_collections if c.startswith("knowledge_")]

        indexes = []
        config = get_config()

        for collection_name in knowledge_collections:
            # - Get collection stats
            stats = client.get_collection_stats(collection_name)
            row_count = stats.get("row_count", 0)

            # - Try to find matching tracking file
            # - Collection name format: knowledge_projects_xfiles
            # - Need to find tracking file that maps to this collection

            # - Scan cache directories for tracking files
            cache_base = config.rag.cache_dir
            for tracking_dir in cache_base.iterdir():
                if not tracking_dir.is_dir():
                    continue

                tracking_file = tracking_dir / "tracking.json"
                if not tracking_file.exists():
                    continue

                # - Check if this tracking file's collection matches
                # - Derive collection name from tracking dir name
                expected_collection = get_collection_name_from_sanitized(tracking_dir.name)

                if expected_collection == collection_name:
                    # - Found matching tracking file
                    tracking_data = json.loads(tracking_file.read_text())

                    # - Extract directory from tracking data or reconstruct
                    # - Tracking files store absolute paths in "files" dict
                    files = tracking_data.get("files", {})
                    if files:
                        first_file = next(iter(files.keys()))
                        # - Extract directory from file path (approximate)
                        directory = str(Path(first_file).parent)
                    else:
                        directory = "Unknown"

                    indexes.append({
                        "collection": collection_name,
                        "directory": directory,
                        "file_count": len(files),
                        "chunk_count": row_count,
                        "last_checked": tracking_data.get("last_checked", 0),
                    })
                    break

        return json.dumps({"status": "success", "indexes": indexes}, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


def get_collection_name_from_sanitized(sanitized_name: str) -> str:
    """
    Get collection name from sanitized directory name.

    Example: "xfiles-library" → "knowledge_xfiles_library"
    """
    return f"knowledge_{sanitized_name.replace('-', '_')}"
```

### Phase 3: No Changes Needed

These modules continue to work unchanged:
- `src/xlmcp/tools/rag/indexer.py` - Uses `get_milvus_client(directory)` and `get_collection_name(directory)`
- `src/xlmcp/tools/rag/searcher.py` - Same
- `src/xlmcp/tools/rag/metadata.py` - Same

They call `get_milvus_client(directory)` which now returns the global client instead of a per-directory client. The `directory` parameter is still used to determine the **collection name**, just not the DB path.

### Phase 4: Migration Strategy (USER CHOICE: Fresh Start)

**No migration code needed.** User will reindex all knowledge bases after code changes.

**Steps:**
1. Deploy code changes
2. User runs: `xlmcp knowledge reindex --all --force`
3. Old DBs in subdirectories can be manually deleted:
   ```bash
   rm -rf ~/.aix/knowledge/*/milvus.db
   ```

**Benefits of this approach:**
- Simplest implementation (no migration code)
- Clean slate with new architecture
- Opportunity to apply new filters (50-char minimum, etc.)
- No risk of migration bugs

### Phase 5: Testing Plan

1. **Test single KB indexing:**
   ```bash
   xlmcp knowledge reindex library --force
   xlmcp knowledge search "test" --kb library
   ```

2. **Test multi-KB search:**
   ```bash
   xlmcp knowledge search "test"  # All KBs
   ```

3. **Test collection listing:**
   ```bash
   xlmcp knowledge list
   ```

4. **Verify DB structure:**
   ```bash
   ls -lh ~/.aix/knowledge/milvus.db
   # Should be single file with all collections
   ```

5. **Test cleanup:**
   ```bash
   xlmcp knowledge search "test"
   # Should exit quickly (no 10-second delay)
   ```

## Files to Modify

### Primary Changes
- `src/xlmcp/tools/rag/storage.py` (Lines 14-15, 85-96, 99-123, 184-249, 251-284)
  - Change global `_clients` dict to `_global_client` singleton
  - Rewrite `get_milvus_client()` to return global client
  - Update `cleanup_clients()` for single client
  - Rewrite `list_all_indexes()` to query collections from shared DB
  - Update `drop_index()` to only remove tracking files

### No Changes Needed
- `src/xlmcp/tools/rag/indexer.py` - Already uses `get_milvus_client()` abstraction
- `src/xlmcp/tools/rag/searcher.py` - Already uses `get_milvus_client()` abstraction
- `src/xlmcp/tools/rag/metadata.py` - No storage dependencies
- `src/xlmcp/cli/__init__.py` - No migration command needed

## Rollback Plan

If issues occur:
1. Keep old `*.db.bak` files
2. Rename back to `milvus.db`
3. Revert code changes

## Performance Benefits

- **Multi-KB search:** 3-5x faster (single connection vs multiple)
- **CLI exit time:** Already improved with cleanup, will be even faster
- **Resource usage:** Lower memory (one client vs many)
- **Disk space:** ~50-100MB saved (no per-DB overhead)
