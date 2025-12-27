# Reindex Optimization Guide

## Problem Summary

**Original issue**: 350,534 chunks from 829 files taking 3+ hours to embed

**Root causes**:
1. Chunk size too small (512 tokens) → too many chunks
2. Jupyter notebooks include outputs (HTML tables, stdout) → content bloat
3. No file size limits → processing everything
4. No progress visibility during embedding

## Solutions Applied

### Code Changes

1. **Added embedding progress** - Shows batch progress during embedding generation
2. **Added file size filtering** - Skip files larger than configurable limit
3. **Added skip outputs option** - Option to skip notebook outputs entirely

### Configuration Options

Add to `/home/quant0/devs/aix/.env`:

```bash
# ============================================================
# RAG Chunk Size - MOST IMPORTANT
# ============================================================
# - Recommended: 2048 (reduces chunks by 4x)
# - Aggressive: 4096 (reduces chunks by 8x)
RAG_CHUNK_SIZE=2048
RAG_CHUNK_OVERLAP=256

# ============================================================
# File Size Limit
# ============================================================
# - Skip files larger than this (in MB)
# - Default: 10MB
# - Recommended: 5MB for faster indexing
RAG_MAX_FILE_SIZE_MB=5

# ============================================================
# Skip Notebook Outputs
# ============================================================
# - If true: only index code/markdown cells (not outputs)
# - Dramatically reduces chunk count for notebooks
# - Trade-off: won't search output content
RAG_SKIP_NOTEBOOK_OUTPUTS=true
```

## Expected Impact

### Scenario 1: Chunk Size 2048 + Skip Outputs

```
Before:  829 files → 350,534 chunks → 3+ hours
After:   829 files → ~20,000 chunks → ~15-20 minutes
```

**Reduction**: ~94% fewer chunks

### Scenario 2: Chunk Size 4096 + Skip Outputs + 5MB Limit

```
Before:  829 files → 350,534 chunks → 3+ hours
After:   ~700 files → ~10,000 chunks → ~8-10 minutes
```

**Reduction**: ~97% fewer chunks

## Recommended Configuration

**For xincubator (large project with many notebooks)**:

```bash
# - Large chunks (code-friendly)
RAG_CHUNK_SIZE=4096
RAG_CHUNK_OVERLAP=512

# - Skip large files
RAG_MAX_FILE_SIZE_MB=5

# - Skip notebook outputs (only index code)
RAG_SKIP_NOTEBOOK_OUTPUTS=true
```

**Why this works**:
- 4KB chunks are better for code (keep functions intact)
- Skipping outputs focuses on actual code/documentation
- Filtering large files avoids generated/build artifacts

## Testing

1. **Stop current reindex** (if still running):
   ```bash
   # Find process
   ps aux | grep "xlmcp reindex"

   # Kill it
   kill <PID>
   ```

2. **Update configuration**:
   ```bash
   vim ~/devs/aix/.env
   # Add the recommended settings above
   ```

3. **Clear old index** (force fresh start):
   ```bash
   rm -rf ~/.aix/knowledge/projects-xincubator/
   ```

4. **Reindex with new settings**:
   ```bash
   xlmcp reindex xincubator --force
   ```

5. **Monitor progress**:
   - You'll now see embedding progress: "Embeddings: 5000/10000 (50%)"
   - Should complete in 10-20 minutes instead of 3+ hours

## What Gets Indexed

**With `RAG_SKIP_NOTEBOOK_OUTPUTS=true`**:
- ✅ Python files (source code)
- ✅ Markdown files (documentation)
- ✅ Jupyter notebook code cells
- ✅ Jupyter notebook markdown cells
- ❌ Jupyter notebook outputs (stdout, tables, plots)

**Trade-off**: You can still search for code and documentation, but won't find text in outputs. For most use cases (finding code patterns, strategies, documentation), this is acceptable.

## Performance Expectations

**Chunk counts**:
- Markdown: ~5-10 chunks per file
- Python: ~10-20 chunks per file (with 4KB chunks)
- Jupyter (no outputs): ~15-30 chunks per notebook
- Jupyter (with outputs): ~400+ chunks per notebook ❌

**Embedding speed** (approximate):
- 1,000 chunks: ~30 seconds
- 10,000 chunks: ~5 minutes
- 50,000 chunks: ~25 minutes
- 350,000 chunks: ~3+ hours ❌

## Next Steps

1. Apply recommended configuration
2. Reindex xincubator with `--force`
3. Verify chunk count is reasonable (< 50k)
4. Test search quality
5. Adjust `RAG_CHUNK_SIZE` if needed:
   - Too small → too many chunks, slow indexing
   - Too large → poor search granularity

## Additional Optimizations (Future)

- Parallel file processing (currently sequential)
- Smarter content deduplication
- File type-specific chunk sizes
- Incremental embedding updates
