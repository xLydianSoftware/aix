"""
Data models for RAG functionality.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class FileType(Enum):
    """
    Supported file types for knowledge indexing.
    """

    MARKDOWN = "md"
    PYTHON = "py"
    JUPYTER = "ipynb"

    @classmethod
    def from_extension(cls, ext: str) -> "FileType | None":
        """
        Get FileType from file extension (with or without dot).

        Args:
            ext: File extension (e.g., 'md', '.md', 'py', '.py', '.pyx', 'ipynb', '.ipynb')

        Returns:
            FileType if recognized, None otherwise
        """
        # - Remove leading dot and convert to lowercase
        ext = ext.lstrip(".").lower()

        # - Build mapping dict with additional extensions
        ext_map = {ft.value: ft for ft in cls}

        # - Add Cython (.pyx) as Python file type
        ext_map['pyx'] = cls.PYTHON

        return ext_map.get(ext)


class DocumentMetadata(BaseModel):
    """
    Metadata extracted from knowledge files (markdown, Python, Jupyter notebooks).
    """

    model_config = ConfigDict(validate_default=False)

    # - Common metadata (all file types)
    file_type: str | None = None  # "md", "py", "ipynb"
    tags: list[str] | None = None
    created: str | None = None
    author: str | None = None
    type_field: str | None = None

    # - Markdown-specific (from frontmatter)
    strategy: str | None = None
    sharpe: float | None = None
    cagr: float | None = None
    drawdown: float | None = None

    # - Python-specific metadata
    module_name: str | None = None  # Module name from file
    classes: list[str] | None = None  # Class names defined
    functions: list[str] | None = None  # Function names defined
    imports: list[str] | None = None  # Import statements
    has_main: bool | None = None  # Has __main__ block

    # - Jupyter-specific metadata
    kernel_spec: str | None = None  # Kernel spec name
    cell_count: int | None = None  # Total cells
    code_cell_count: int | None = None  # Code cells
    markdown_cell_count: int | None = None  # Markdown cells

    # - Custom fields
    custom: dict[str, Any] | None = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.tags is None:
            object.__setattr__(self, 'tags', [])
        if self.custom is None:
            object.__setattr__(self, 'custom', {})


class DocumentEntity(BaseModel):
    """
    Entity stored in Milvus collection.
    Includes both flat fields for filtering and full metadata as JSON.
    """

    text: str
    filename: str
    path: str

    # - Flattened metadata for filtering
    tags_str: str = "[]"
    type_field: str | None = None
    strategy: str | None = None
    sharpe: float | None = None
    cagr: float | None = None
    drawdown: float | None = None

    # - Full metadata as JSON
    metadata_json: str = "{}"


class SearchResultItem(BaseModel):
    """Single search result with score and metadata."""

    text: str
    filename: str
    path: str
    score: float
    metadata: DocumentMetadata
