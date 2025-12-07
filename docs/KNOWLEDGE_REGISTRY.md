# Knowledge Bases Registry

## Overview

The knowledge bases registry (`~/.aix/knowledges.yaml`) allows you to define and manage known markdown knowledge directories for easy reference and search.

## Registry File Location

```
~/.aix/knowledges.yaml
```

## File Format

```yaml
knowledges:
  <name>:
    path: <absolute_path_or_with_tilde>
    description: "Brief description"
    tags: [tag1, tag2, tag3]  # Optional
```

## Example Configuration

```yaml
knowledges:
  quantlib:
    path: ~/projects/xfiles/Library
    description: "Quantitative library - books, papers, research articles"
    tags: [library, research, papers]

  backtests:
    path: ~/projects/xfiles/Research/backtests
    description: "Backtest results with performance metrics"
    tags: [backtests, results, performance]

  stochastic:
    path: ~/projects/xfiles/Studies/Options
    description: "Stochastic calculus and options pricing theory"
    tags: [studies, options, mathematics]
```

## MCP Tool

### markdown_list_knowledges

Lists all registered knowledge bases with their status.

**Returns:**
```json
{
  "status": "success",
  "registry_file": "/home/user/.aix/knowledges.yaml",
  "knowledges": {
    "quantlib": {
      "path": "/home/user/projects/xfiles/Library",
      "description": "Quantitative library - books, papers, research articles",
      "tags": ["library", "research", "papers"],
      "exists": true,
      "indexed": false
    },
    "backtests": {
      "path": "/home/user/projects/xfiles/Research/backtests",
      "description": "Backtest results with performance metrics",
      "tags": ["backtests", "results", "performance"],
      "exists": true,
      "indexed": true
    }
  }
}
```

**Status Fields:**
- `exists`: Whether the directory exists on filesystem
- `indexed`: Whether the directory has been indexed by RAG

## Usage Examples

### 1. List All Knowledge Bases

```python
await markdown_list_knowledges()
```

Shows all registered knowledge bases with their paths, descriptions, and status.

### 2. Index a Knowledge Base

```python
# Get the path from registry, then index it
await markdown_index_directory("~/projects/xfiles/Library", recursive=True)
```

### 3. Search a Knowledge Base

```python
await markdown_search(
    directory="~/projects/xfiles/Library",
    query="mean reversion strategies",
    tags=["#strategy"],
    limit=10
)
```

## Benefits

### 1. Centralized Registry
- All knowledge bases defined in one place
- Easy to see what's available
- No need to remember paths

### 2. Discovery
- See which knowledge bases exist
- Check which ones are indexed
- Browse by tags and descriptions

### 3. Documentation
- Each knowledge base has a description
- Tags for categorization
- Self-documenting system

### 4. Validation
- Checks if paths exist
- Shows index status
- Helps identify missing or broken paths

## Adding New Knowledge Bases

Edit `~/.aix/knowledges.yaml` and add a new entry:

```yaml
knowledges:
  # ... existing entries ...

  myknowledge:
    path: ~/path/to/markdown/files
    description: "Description of this knowledge base"
    tags: [tag1, tag2]
```

Then index it:

```python
await markdown_index_directory("~/path/to/markdown/files", recursive=True)
```

## Python API

```python
from xmcp.tools.rag.registry import load_knowledges, get_knowledge_path

# Load all knowledge bases
knowledges = load_knowledges()

# Get path for a specific knowledge base
path = get_knowledge_path("quantlib")
```

## Integration with Other Tools

The registry can be used by:
- Custom scripts to iterate over all knowledge bases
- Batch indexing tools
- Search interfaces
- Documentation generators

## Best Practices

1. **Use Descriptive Names**: Choose clear, memorable names
2. **Add Good Descriptions**: Explain what the knowledge base contains
3. **Tag Appropriately**: Use tags for categorization
4. **Keep Paths Updated**: Remove or update broken paths
5. **Document Purpose**: Use description to explain the purpose

## Example Workflow

```bash
# 1. Add knowledge base to registry
vim ~/.aix/knowledges.yaml

# 2. List to verify
await markdown_list_knowledges()

# 3. Index it
await markdown_index_directory("~/path/from/registry", recursive=True)

# 4. Search it
await markdown_search(
    directory="~/path/from/registry",
    query="your search query",
    limit=10
)
```

## Current Registered Knowledge Bases

Run `markdown_list_knowledges()` to see current registry or view:
```
~/.aix/knowledges.yaml
```
