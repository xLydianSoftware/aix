"""
Data models for RAG functionality.
"""

from typing import Any

from pydantic import BaseModel


class DocumentMetadata(BaseModel):
    """
    Metadata extracted from markdown frontmatter and content.
    """

    tags: list[str] = []
    created: str | None = None
    author: str | None = None
    type_field: str | None = None
    strategy: str | None = None
    sharpe: float | None = None
    cagr: float | None = None
    drawdown: float | None = None
    custom: dict[str, Any] = {}

    model_config = {"validate_assignment": True}


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

    model_config = {"validate_assignment": True}


class SearchResultItem(BaseModel):
    """Single search result with score and metadata."""

    text: str
    filename: str
    path: str
    score: float
    metadata: DocumentMetadata

    model_config = {"validate_assignment": True}
