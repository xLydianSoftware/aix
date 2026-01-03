"""
Storage layer for project management.
Handles file I/O for projects.
"""

import json
from datetime import datetime
from pathlib import Path

from xlmcp.tools.projects.models import Project, ProjectMetadata, ProjectContext, LogEntry


def get_projects_dir() -> Path:
    """
    Get projects directory path.
    Creates directory if it doesn't exist.
    """
    projects_dir = Path.home() / ".aix" / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    return projects_dir


def get_project_path(name: str) -> Path:
    """Get path to specific project directory."""
    return get_projects_dir() / name


def load_project(name: str) -> Project | None:
    """
    Load project from disk.

    Args:
        name: Project name

    Returns:
        Project object or None if not found
    """
    project_path = get_project_path(name)
    if not project_path.exists():
        return None

    description_file = project_path / "description.md"
    if not description_file.exists():
        return None

    # - Read description.md
    content = description_file.read_text()

    # - Parse frontmatter (simple YAML-like parsing)
    metadata_dict = {}
    description = content

    if content.startswith("---\n"):
        parts = content.split("---\n", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            description = parts[2].strip()

            # - Parse frontmatter lines
            for line in frontmatter.strip().split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    # - Parse lists
                    if value.startswith("[") and value.endswith("]"):
                        value = [v.strip() for v in value[1:-1].split(",") if v.strip()]

                    metadata_dict[key] = value

    # - Create metadata with defaults
    metadata = ProjectMetadata(
        name=name,
        created=datetime.fromisoformat(metadata_dict.get("created", datetime.now().isoformat())),
        updated=datetime.fromisoformat(metadata_dict.get("updated", datetime.now().isoformat())),
        status=metadata_dict.get("status", "active"),
        tags=metadata_dict.get("tags", []) if isinstance(metadata_dict.get("tags"), list) else [],
        type=metadata_dict.get("type"),
        related_projects=metadata_dict.get("related_projects", [])
        if isinstance(metadata_dict.get("related_projects"), list)
        else [],
    )

    return Project(name=name, path=project_path, metadata=metadata, description=description)


def save_project(project: Project) -> None:
    """
    Save project to disk.

    Args:
        project: Project to save
    """
    # - Create project directory
    project.path.mkdir(parents=True, exist_ok=True, mode=0o700)

    # - Update timestamp
    project.metadata.updated = datetime.now()

    # - Build frontmatter
    frontmatter = f"""---
name: {project.metadata.name}
created: {project.metadata.created.isoformat()}
updated: {project.metadata.updated.isoformat()}
status: {project.metadata.status}
tags: [{', '.join(project.metadata.tags)}]
type: {project.metadata.type or ''}
related_projects: [{', '.join(project.metadata.related_projects)}]
---
"""

    # - Write description.md
    content = frontmatter + "\n" + project.description
    project.description_file.write_text(content)


def append_log_entry(project: Project, entry: LogEntry) -> None:
    """
    Append log entry to project log.

    If an entry for today already exists, adds as bullet point under that section.
    Otherwise creates a new date section.

    Args:
        project: Project to append to
        entry: Log entry to append
    """
    log_file = project.log_file

    # - Create log file if it doesn't exist
    if not log_file.exists():
        log_file.write_text("# Project Log\n\n")

    # - Read current content
    content = log_file.read_text()

    # - Get today's date string
    today_str = entry.timestamp.strftime("%Y-%m-%d")
    tags_str = f" [{', '.join(entry.tags)}]" if entry.tags else ""
    section_header = f"## {today_str}{tags_str}"

    # - Check if today's section already exists
    if f"## {today_str}" in content:
        # - Append as bullet point under existing section
        lines = content.split("\n")
        insert_index = -1

        # - Find the line with today's date section
        for i, line in enumerate(lines):
            if line.startswith(f"## {today_str}"):
                # - Find the next section or end of file
                insert_index = i + 1
                # - Skip to end of this section (before next ## or end of file)
                while insert_index < len(lines) and not lines[insert_index].startswith("## "):
                    insert_index += 1
                break

        # - Insert bullet point before next section
        if insert_index > 0:
            lines.insert(insert_index, f"- {entry.content}")
            log_file.write_text("\n".join(lines))
    else:
        # - Create new section
        with log_file.open("a") as f:
            f.write(f"\n{section_header}\n- {entry.content}\n")


def read_project_log(project: Project, limit: int = 10) -> list[LogEntry]:
    """
    Read recent log entries from project.

    Args:
        project: Project to read from
        limit: Maximum number of entries to return

    Returns:
        List of log entries (most recent first)
    """
    log_file = project.log_file
    if not log_file.exists():
        return []

    content = log_file.read_text()

    # - Parse markdown entries (simple parsing)
    entries = []
    lines = content.split("\n")

    current_entry = None
    current_content = []

    for line in lines:
        if line.startswith("## "):
            # - Save previous entry
            if current_entry is not None:
                current_entry.content = "\n".join(current_content).strip()
                entries.append(current_entry)

            # - Parse timestamp and tags
            header = line[3:].strip()
            tags = []

            if "[" in header and "]" in header:
                tags_start = header.index("[")
                tags_end = header.index("]")
                tags_str = header[tags_start + 1 : tags_end]
                tags = [t.strip() for t in tags_str.split(",") if t.strip()]
                header = header[:tags_start].strip()

            # - Parse timestamp (support both date-only and date-time formats)
            try:
                timestamp = datetime.strptime(header, "%Y-%m-%d")
            except ValueError:
                try:
                    # - Backward compatibility: support old HH:MM format
                    timestamp = datetime.strptime(header, "%Y-%m-%d %H:%M")
                except ValueError:
                    timestamp = datetime.now()

            current_entry = LogEntry(timestamp=timestamp, tags=tags, content="")
            current_content = []
        elif current_entry is not None:
            current_content.append(line)

    # - Save last entry
    if current_entry is not None:
        current_entry.content = "\n".join(current_content).strip()
        entries.append(current_entry)

    # - Return most recent entries first
    entries.reverse()
    return entries[:limit]


def save_context(project: Project, context: ProjectContext) -> None:
    """
    Save project context to context.json.

    Args:
        project: Project to save context for
        context: Context to save
    """
    context.last_updated = datetime.now()
    project.context_file.write_text(context.model_dump_json(indent=2))


def load_context(project: Project) -> ProjectContext | None:
    """
    Load project context from context.json.

    Args:
        project: Project to load context for

    Returns:
        ProjectContext or None if not found
    """
    if not project.context_file.exists():
        return None

    try:
        data = json.loads(project.context_file.read_text())
        return ProjectContext(**data)
    except Exception:
        return None


def list_all_projects() -> list[str]:
    """
    List all project names.

    Returns:
        List of project names
    """
    projects_dir = get_projects_dir()
    return [p.name for p in projects_dir.iterdir() if p.is_dir() and (p / "description.md").exists()]
