"""
Metadata extraction from knowledge files.
Handles YAML frontmatter, inline hashtags, Python AST parsing, and Jupyter notebooks.
"""

import json
import re
from pathlib import Path
from typing import Any

import frontmatter

from xlmcp.tools.rag.models import DocumentEntity, DocumentMetadata, FileType
from xlmcp.tools.rag.parsers import JupyterParser, PythonParser


def extract_inline_hashtags(text: str) -> list[str]:
    """
    Extract inline hashtags from markdown text.

    Pattern: #[a-zA-Z][a-zA-Z0-9_-]*
    Excludes code blocks, inline code, HTML tags, and CSS.

    Args:
        text: Markdown content

    Returns:
        List of unique hashtags (including #)
    """
    # - Remove code blocks (``` ... ```)
    text = re.sub(r"```[\s\S]*?```", "", text)

    # - Remove inline code (` ... `)
    text = re.sub(r"`[^`]*`", "", text)

    # - Remove HTML/XML tags completely (including style attributes)
    # - This removes <tag attr="value">content</tag> and <tag attr="value" />
    text = re.sub(r"<[^>]+>", "", text)

    # - Remove CSS style blocks
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)

    # - Remove inline style attributes that might have been left (style="...")
    text = re.sub(r"""\bstyle\s*=\s*['"][^'"]*['"]""", "", text, flags=re.IGNORECASE)

    # - Find hashtags: # followed by letter, then letters/numbers/hyphens/underscores
    pattern = r"#[a-zA-Z][a-zA-Z0-9_-]*"
    tags = re.findall(pattern, text)

    # - Filter out hex color codes and false positives
    def is_hex_color(tag: str) -> bool:
        """Check if tag looks like a hex color code."""
        # - Remove the # prefix
        without_hash = tag[1:] if tag.startswith('#') else tag
        # - Check if it's only hex digits and has valid length (3, 4, 6, or 8)
        if re.match(r'^[a-fA-F0-9]+$', without_hash, re.IGNORECASE):
            return len(without_hash) in (3, 4, 6, 8)
        return False

    def is_heading_marker(tag: str) -> bool:
        """Check if tag looks like a markdown heading marker (#h0, #h1, etc.)."""
        without_hash = tag[1:] if tag.startswith('#') else tag
        # - Match h followed by digits (e.g., h0, h1, h2, h10)
        return bool(re.match(r'^h\d+$', without_hash, re.IGNORECASE))

    def is_valid_tag(tag: str) -> bool:
        """Check if tag is valid (not a color, not a heading, not too short)."""
        if len(tag) <= 2:  # Too short (just # + 1 char)
            return False
        if is_hex_color(tag):
            return False
        if is_heading_marker(tag):
            return False
        return True

    tags = [tag for tag in tags if is_valid_tag(tag)]

    # - Return unique tags (case-sensitive)
    return list(set(tags))


def parse_float_safe(value: Any) -> float | None:
    """
    Safely parse float from frontmatter value.
    """
    if value is None:
        return None

    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_frontmatter(file_path: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from markdown file.

    Args:
        file_path: Path to markdown file

    Returns:
        (frontmatter_dict, content)
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            post = frontmatter.load(f)
            return dict(post.metadata), post.content
    except (FileNotFoundError, PermissionError, UnicodeDecodeError):
        # - Return empty frontmatter if file can't be read
        return {}, ""
    except Exception:
        # - Catch any frontmatter parsing errors
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            return {}, content
        except Exception:
            return {}, ""


def extract_metadata(file_path: str) -> DocumentMetadata:
    """
    Extract complete metadata from knowledge file.

    Dispatches to file-type-specific parsers:
    - .md -> Markdown parser (YAML frontmatter + hashtags)
    - .py -> Python parser (AST + docstrings)
    - .ipynb -> Jupyter parser (JSON + cells)

    Args:
        file_path: Path to knowledge file

    Returns:
        DocumentMetadata with all extracted fields
    """
    # - Detect file type from extension
    ext = Path(file_path).suffix.lstrip(".")
    file_type = FileType.from_extension(ext)

    if file_type == FileType.PYTHON:
        return PythonParser.extract_metadata(file_path)
    elif file_type == FileType.JUPYTER:
        return JupyterParser.extract_metadata(file_path)
    elif file_type == FileType.MARKDOWN:
        return _extract_markdown_metadata(file_path)
    else:
        # - Unknown file type
        return DocumentMetadata()


def _extract_markdown_metadata(file_path: str) -> DocumentMetadata:
    """
    Extract complete metadata from markdown file.

    Combines YAML frontmatter and inline hashtags.

    Args:
        file_path: Path to markdown file

    Returns:
        DocumentMetadata with all extracted fields
    """
    fm_data, content = parse_frontmatter(file_path)

    # - Extract inline hashtags from content (already filtered)
    inline_tags = extract_inline_hashtags(content)

    # - Get frontmatter tags (could be list or string)
    fm_tags = fm_data.get("tags", [])
    if isinstance(fm_tags, str):
        # - Handle comma-separated tags
        fm_tags = [tag.strip() for tag in fm_tags.split(",")]
    elif not isinstance(fm_tags, list):
        fm_tags = []

    # - Normalize frontmatter tags (add # if missing)
    normalized_fm_tags = []
    for tag in fm_tags:
        tag = tag.strip()
        if tag and not tag.startswith("#"):
            tag = f"#{tag}"
        if tag:
            normalized_fm_tags.append(tag)

    # - Filter frontmatter tags (same rules as inline tags)
    # - This removes hex colors, heading markers, and very short tags
    filtered_fm_tags = []
    for tag in normalized_fm_tags:
        # - Reuse the filtering logic from extract_inline_hashtags
        without_hash = tag[1:] if tag.startswith('#') else tag

        # - Skip if too short
        if len(tag) <= 2:
            continue

        # - Skip if hex color (3, 4, 6, or 8 hex digits)
        if re.match(r'^[a-fA-F0-9]+$', without_hash, re.IGNORECASE) and len(without_hash) in (3, 4, 6, 8):
            continue

        # - Skip if heading marker (h0, h1, etc.)
        if re.match(r'^h\d+$', without_hash, re.IGNORECASE):
            continue

        filtered_fm_tags.append(tag)

    # - Combine and deduplicate tags
    all_tags = list(set(filtered_fm_tags + inline_tags))
    all_tags.sort()  # Sort for consistency

    # - Extract other metadata fields
    # - Handle "Type" field (reserved keyword) -> type_field
    type_value = fm_data.get("Type") or fm_data.get("type")

    # - Build metadata object
    metadata = DocumentMetadata(
        file_type=FileType.MARKDOWN.value,
        tags=all_tags,
        created=str(fm_data.get("Created") or fm_data.get("created") or ""),
        author=str(fm_data.get("Author") or fm_data.get("author") or ""),
        type_field=str(type_value) if type_value else None,
        strategy=str(fm_data.get("strategy") or "") or None,
        sharpe=parse_float_safe(fm_data.get("sharpe")),
        cagr=parse_float_safe(fm_data.get("cagr")),
        drawdown=parse_float_safe(fm_data.get("drawdown")),
        custom={},
    )

    # - Store other frontmatter fields in custom
    skip_fields = {
        "tags",
        "Created",
        "created",
        "Author",
        "author",
        "Type",
        "type",
        "strategy",
        "sharpe",
        "cagr",
        "drawdown",
    }
    for key, value in fm_data.items():
        if key not in skip_fields:
            metadata.custom[key] = value

    return metadata


def build_entity_dict(chunk: str, metadata: DocumentMetadata, filename: str, path: str) -> dict:
    """
    Build Milvus entity dict from chunk and metadata.

    Args:
        chunk: Text chunk content
        metadata: Document metadata
        filename: File name
        path: Absolute file path

    Returns:
        Dict ready for Milvus insertion (without vector - added separately)
    """
    return {
        "text": chunk,
        "filename": filename,
        "path": path,
        # - Flattened metadata for filtering
        "tags_str": json.dumps(metadata.tags),
        "type_field": metadata.type_field,
        "strategy": metadata.strategy,
        "sharpe": metadata.sharpe,
        "cagr": metadata.cagr,
        "drawdown": metadata.drawdown,
        # - Full metadata as JSON
        "metadata_json": metadata.model_dump_json(),
    }
