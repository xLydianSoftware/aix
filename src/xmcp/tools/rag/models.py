"""
Data models for RAG functionality.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentMetadata(BaseModel):
    """
    Metadata extracted from markdown frontmatter and content.
    """

    model_config = ConfigDict(validate_default=False)

    tags: list[str] | None = None
    created: str | None = None
    author: str | None = None
    type_field: str | None = None
    strategy: str | None = None
    sharpe: float | None = None
    cagr: float | None = None
    drawdown: float | None = None
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
