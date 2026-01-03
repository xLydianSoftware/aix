# XLMCP Implementation Overview

## Architecture

XLMCP is an MCP (Model Context Protocol) server providing Claude Code with 32 tools for:
- **Jupyter Integration** (16 tools) - Interact with Jupyter notebooks and kernels
- **Knowledge RAG Search** (8 tools) - Semantic search over knowledge files (.md, .py, .ipynb)
- **Project Management** (8 tools) - Track projects with logs, context, and metadata

### Technology Stack

- **FastMCP 2.13+** - MCP server framework
- **Jupyter Client** - Notebook and kernel interaction
- **LlamaIndex** - Document loading, parsing, chunking
- **PyMilvus** - Vector database with local embeddings (768-dim, no API costs)
- **Click** - CLI framework
- **Pydantic** - Data validation and configuration

## Module Structure

```
src/xlmcp/
├── cli/
│   └── __init__.py           # Click-based CLI (start/stop/status/ls + project commands)
├── tools/
│   ├── jupyter/
│   │   ├── client.py         # Jupyter API client
│   │   ├── kernel.py         # Kernel management
│   │   └── notebook.py       # Notebook operations
│   ├── rag/
│   │   ├── indexer.py        # Document indexing & auto-refresh
│   │   ├── searcher.py       # Semantic search with filters
│   │   ├── storage.py        # Milvus collections & tracking
│   │   ├── metadata.py       # YAML frontmatter & hashtag extraction
│   │   ├── models.py         # Pydantic data models
│   │   └── registry.py       # Knowledge bases registry
│   └── projects/
│       ├── models.py         # Project, LogEntry, ProjectContext models
│       ├── storage.py        # File I/O for projects
│       └── manager.py        # Project management logic
├── config.py                 # Configuration (Jupyter, MCP, RAG)
├── server.py                 # MCP server with tool registration
└── utils.py                  # Utility functions

tests/xlmcp/
├── test_rag_indexing.py      # Indexing tests
├── test_rag_metadata.py      # Metadata extraction tests
└── test_rag_search.py        # Search tests
```

## RAG Implementation

### Document Processing Pipeline

1. **Discovery**: List all knowledge files (`.md`, `.py`, `.ipynb`) (recursive)
2. **Change Detection**: MD5 hash + mtime comparison
3. **Loading**:
   - Markdown: LlamaIndex `SimpleDirectoryReader`
   - Python: Direct text extraction with AST parsing
   - Jupyter: JSON parsing for cells + outputs
4. **Parsing**:
   - Markdown: `MarkdownNodeParser` (preserves structure)
   - Python/Jupyter: Keep as-is (already structured)
5. **Chunking**: `TokenTextSplitter` (512 tokens, 100 overlap)
6. **Metadata Extraction**:
   - Markdown: YAML frontmatter + inline hashtags
   - Python: Module docstring, classes, functions, imports (AST)
   - Jupyter: Kernel spec, cell counts, markdown tags (JSON)
7. **Embedding**: PyMilvus DefaultEmbeddingFunction (768-dim)
8. **Storage**: Milvus collection per directory
9. **Tracking**: JSON file with file hashes and timestamps

### Storage Architecture

```
~/.aix/knowledge/
├── projects-xfiles/          # Sanitized directory name
│   ├── milvus.db             # Milvus Lite database
│   └── tracking.json         # File change tracking
└── another-directory/
    ├── milvus.db
    └── tracking.json
```

**Tracking File Format:**
```json
{
  "last_checked": 1701234567.89,
  "files": {
    "/absolute/path/file.md": ["md5_hash", mtime]
  }
}
```

### Metadata Extraction

**YAML Frontmatter:**
```yaml
---
tags: [backtest, strategy]
Type: BACKTEST
strategy: mean-reversion
sharpe: 1.85
cagr: 24.5
drawdown: -12.3
author: John Doe
created: 2024-01-15
---
```

**Inline Hashtags:**
```markdown
Testing #strategy with #mean-reversion approach.
```

**Combined:** Both sources merged, HTML color codes filtered out.

### Search Implementation

**Filter Building:**
- **Tags**: `tags_str like '%#tag%' and tags_str like '%#tag2%'`
- **Metadata**: `sharpe > 1.5 and type_field == 'BACKTEST'`
- **Combined**: Both filters with AND logic

**Search Process:**
1. Auto-refresh check (if interval elapsed)
2. Encode query with embedding function
3. Build filter expression
4. Execute Milvus vector search
5. Apply similarity threshold
6. Parse metadata JSON
7. Return ranked results

### Incremental Indexing

**Change Detection:**
```python
def get_changed_files(directory: str) -> list[str]:
    tracking = load_tracking_file(directory)
    changed = []
    for file_path in list_md_files(directory):
        current_hash, current_mtime = get_file_hash_and_mtime(file_path)
        stored = tracking.get(file_path)
        if not stored or stored[0] != current_hash:
            changed.append(file_path)
    return changed
```

**Update Process:**
1. Detect changed files
2. Delete old chunks: `client.delete(filter=f"path == '{file_path}'")`
3. Reindex changed files only
4. Update tracking file

### Auto-Refresh

**Strategy:** Check-on-search with throttling
- No background threads
- Check timestamp on search
- If interval elapsed, check for changes
- Reindex if changes detected

**Configuration:**
- `RAG_AUTO_REFRESH`: Enable/disable
- `RAG_AUTO_REFRESH_INTERVAL`: Check interval (default: 300s)

## MCP Tools

### Jupyter Tools (16)

**Notebook Operations:**
- `jupyter_list_notebooks` - List notebooks in directory
- `jupyter_get_notebook_info` - Get metadata and cell summary
- `jupyter_read_cell` / `jupyter_read_all_cells` - Read content
- `jupyter_append_cell` / `jupyter_insert_cell` - Add cells
- `jupyter_update_cell` / `jupyter_delete_cell` - Modify cells

**Kernel Management:**
- `jupyter_list_kernels` - List running kernels
- `jupyter_start_kernel` / `jupyter_stop_kernel` - Start/stop
- `jupyter_restart_kernel` / `jupyter_interrupt_kernel` - Control

**Execution:**
- `jupyter_execute_code` - Execute code in kernel
- `jupyter_connect_notebook` - Connect to notebook's kernel
- `jupyter_execute_cell` - Execute specific cell

### RAG Tools (8)

**Indexing:**
- `knowledge_index_directory` - Index directory with change detection (.md, .py, .ipynb)
- `knowledge_refresh_index` - Force refresh of index

**Searching:**
- `knowledge_search` - Semantic search with filters

**Discovery:**
- `knowledge_list_knowledges` - List registered knowledge bases
- `knowledge_list_indexes` - List indexed directories
- `knowledge_get_tags` - Extract unique tags with counts
- `knowledge_get_metadata_fields` - List filterable fields

**Management:**
- `knowledge_drop_index` - Remove index and cache

## Project Management Implementation

### Architecture

Projects provide persistent context and logging for research/development workflows:
- **Description** - Project metadata (YAML frontmatter) + markdown description
- **Logs** - Daily summaries with bullet points (chronological, grouped by date)
- **Context** - Machine-readable state (working files, next steps, blockers)

### Storage Structure

```
~/.aix/projects/
├── aix-development/
│   ├── description.md    # YAML frontmatter + description
│   ├── log.md           # Daily logs with bullet points
│   └── context.json     # Working files, next steps, blockers
└── storm-optimization/
    ├── description.md
    ├── log.md
    └── context.json
```

### Data Models

**Project Metadata** (YAML frontmatter in description.md):
```python
class ProjectMetadata:
    name: str
    created: datetime
    updated: datetime
    status: str = "active"  # active, archived, completed
    tags: list[str] = []
    type: str | None = None  # strategy, research, infrastructure, etc.
    related_projects: list[str] = []
```

**Log Entry**:
```python
class LogEntry:
    timestamp: datetime
    content: str
    tags: list[str] = []
```

**Project Context** (context.json):
```python
class ProjectContext:
    project: str
    last_updated: datetime
    working_files: list[str] = []
    active_research: list[str] = []
    blockers: list[str] = []
    next_steps: list[str] = []
    knowledge_bases: list[str] = []
    related_projects: list[str] = []
```

### Log Format

**Daily sections with bullet points** (avoids duplicate date headers):

```markdown
# Project Log

## 2026-01-03
- Updated log timestamp format to date-only
- Reviewed Obsidian Smart Connections scoring function
- Updated project description with documentation links

## 2026-01-02 [architecture, search, projects]
**Projects System Implementation:**
- Implemented complete projects management system
- Added CLI commands with colorized output
```

**Append Logic:**
1. Check if today's section exists
2. If yes → add as bullet point under existing section
3. If no → create new section with date header

### MCP Tools

**Project Lifecycle:**
- `project_create(name, description, tags, type)` - Create new project
- `project_list()` - List all projects with status
- `project_get(name)` - Get project details + recent logs + context
- `project_update_description(name, description)` - Update description

**Logging:**
- `project_add_log(name, content, tags)` - Add timestamped log entry
- `project_read_log(name, limit)` - Read recent logs (most recent first)

**Context:**
- `project_set_context(name, ...)` - Update working files/next steps/blockers
- `project_get_context(name)` - Get current project state

### CLI Commands

```bash
# Create project
xlmcp project create aix-development --type infrastructure --description "..."

# List projects
xlmcp project list

# Show details
xlmcp project show aix-development

# Add log entry
xlmcp project log aix-development "Implemented FDI adaptive SuperTrend"

# View logs
xlmcp project logs aix-development --limit 20
```

**Features:**
- Colorized output (cyan headers, yellow timestamps, green/red status)
- Status indicators (active/archived/completed)
- Last update timestamps
- Tag display

### Use Cases

**Strategy Development:**
- Track implementation progress
- Log backtest results with configs
- Store context (working files, next optimizations)
- Link to knowledge bases (strategies, indicators)

**Research Workflows:**
- Document experiment results
- Track paper reading progress
- Store research questions and hypotheses
- Link related research streams

**Infrastructure Projects:**
- Log implementation milestones
- Track architectural decisions
- Document performance optimizations
- Maintain project context across sessions

## Configuration System

### Environment Variables

**Jupyter:**
- `JUPYTER_SERVER_URL` - Server URL
- `JUPYTER_API_TOKEN` - Auth token
- `JUPYTER_ALLOWED_DIRS` - Security whitelist
- `JUPYTER_WS_TIMEOUT` / `JUPYTER_EXEC_TIMEOUT` - Timeouts

**RAG:**
- `RAG_CACHE_DIR` - Index storage location
- `RAG_CHUNK_SIZE` / `RAG_CHUNK_OVERLAP` - Chunking params
- `RAG_AUTO_REFRESH` / `RAG_AUTO_REFRESH_INTERVAL` - Auto-refresh
- `RAG_DEFAULT_SEARCH_LIMIT` / `RAG_DEFAULT_SIMILARITY_THRESHOLD` - Search defaults

**MCP:**
- `MCP_TRANSPORT` - stdio or http
- `MCP_HTTP_PORT` - HTTP port if applicable
- `MCP_MAX_OUTPUT_TOKENS` - Output limit

### Knowledge Registry

**File:** `~/.aix/knowledges.yaml`

**Format:**
```yaml
knowledges:
  quantlib:
    path: ~/projects/xfiles/Library
    description: "Quantitative library - books, papers, research articles"
    tags: [library, research, papers]
```

**Features:**
- Centralized directory registry
- Path validation
- Index status checking
- Tag-based categorization

## CLI Implementation

**Framework:** Click (decorator-based)

**Commands:**
- `xlmcp start [-f]` - Start server (background/foreground)
- `xlmcp stop` - Stop server (SIGTERM → SIGKILL)
- `xlmcp restart` - Restart server
- `xlmcp status` - Show PID, uptime, status
- `xlmcp ls` - List all 32 tools
- `xlmcp project <subcommand>` - Project management (create, list, show, log, logs)

**Process Management:**
- PID detection: `pgrep -f "xlmcp.server"`
- Background launch: `subprocess.Popen(..., start_new_session=True)`
- Graceful shutdown with fallback kill

## Security

- **Path Validation**: All file operations check `JUPYTER_ALLOWED_DIRS`
- **Token Auth**: Jupyter API requires token
- **Cache Permissions**: 0700 (user only)
- **Timeout Limits**: Prevent runaway executions
- **No Remote Code**: All code execution is in user's Jupyter environment

## Performance Characteristics

**Indexing:**
- ~3.6 files/second (with embedding generation)
- ~36 chunks/file average
- ~2.5s/file including I/O

**Search:**
- <100ms query latency
- Scales with collection size
- Threshold filtering reduces results

**Memory:**
- ~500MB-1GB during indexing
- ~200MB base server footprint
- Milvus Lite in-process

## Testing

**Test Coverage:**
- Indexing: Force, incremental, change detection
- Metadata: Frontmatter, hashtags, color filtering
- Search: Basic, tags, metadata, combined filters
- Error handling: Permissions, missing files, malformed data

**Test Data:** Nested 3-level structure (6 files, realistic frontmatter)

## Future Enhancements

**Knowledge RAG:**
- Batch indexing across all knowledge bases
- Search result ranking customization
- Support for other document formats (PDF, DOCX)
- Incremental embedding updates (avoid recomputing)
- Search history and analytics

**Project Management:**
- Auto-logging hooks (git commits, backtests, file changes)
- Project templates for common workflows
- Search across project logs
- Project archival and restoration
- Context snapshots at milestones
- Cross-project search and analytics
