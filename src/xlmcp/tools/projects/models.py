"""
Data models for project management.
"""

from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    """
    A single log entry in a project log.
    """

    timestamp: datetime = Field(default_factory=datetime.now)
    content: str = Field(description="Log entry content")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")

    def to_markdown(self) -> str:
        """
        Convert log entry to markdown format.
        """
        timestamp_str = self.timestamp.strftime("%Y-%m-%d")
        tags_str = f" [{', '.join(self.tags)}]" if self.tags else ""
        return f"## {timestamp_str}{tags_str}\n{self.content}\n"


class ProjectMetadata(BaseModel):
    """
    Project metadata stored in description.md frontmatter.
    """

    name: str = Field(description="Project name")
    created: datetime = Field(default_factory=datetime.now)
    updated: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="active", description="Project status (active, archived, completed)")
    tags: list[str] = Field(default_factory=list, description="Project tags")
    type: str | None = Field(default=None, description="Project type (strategy, research, etc.)")
    related_projects: list[str] = Field(default_factory=list, description="Related project names")


class ProjectContext(BaseModel):
    """
    Machine-readable project context.
    """

    project: str = Field(description="Project name")
    last_updated: datetime = Field(default_factory=datetime.now)
    working_files: list[str] = Field(default_factory=list, description="Currently active files")
    active_research: list[str] = Field(default_factory=list, description="Active research topics")
    blockers: list[str] = Field(default_factory=list, description="Current blockers")
    next_steps: list[str] = Field(default_factory=list, description="Next steps")
    knowledge_bases: list[str] = Field(default_factory=list, description="Related knowledge bases")
    related_projects: list[str] = Field(default_factory=list, description="Related projects")


class Project(BaseModel):
    """
    A project representation.
    """

    name: str = Field(description="Project name (used as directory name)")
    path: Path = Field(description="Absolute path to project directory")
    metadata: ProjectMetadata = Field(description="Project metadata")
    description: str = Field(default="", description="Project description")

    @property
    def description_file(self) -> Path:
        """Path to description.md file."""
        return self.path / "description.md"

    @property
    def log_file(self) -> Path:
        """Path to log.md file."""
        return self.path / "log.md"

    @property
    def context_file(self) -> Path:
        """Path to context.json file."""
        return self.path / "context.json"

    def exists(self) -> bool:
        """Check if project directory exists."""
        return self.path.exists()
