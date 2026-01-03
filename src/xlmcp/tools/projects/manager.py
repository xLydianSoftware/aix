"""
Project management core logic.
"""

import json
from datetime import datetime

from xlmcp.tools.projects import storage
from xlmcp.tools.projects.models import Project, ProjectMetadata, LogEntry, ProjectContext


async def create_project(
    name: str, description: str = "", tags: list[str] | None = None, project_type: str | None = None
) -> str:
    """
    Create a new project.

    Args:
        name: Project name (used as directory name)
        description: Project description
        tags: Project tags
        project_type: Project type (strategy, research, etc.)

    Returns:
        JSON with status and project info
    """
    try:
        # - Check if project already exists
        existing = storage.load_project(name)
        if existing is not None:
            return json.dumps(
                {"status": "error", "message": f"Project '{name}' already exists at {existing.path}"}, indent=2
            )

        # - Create project
        project_path = storage.get_project_path(name)
        metadata = ProjectMetadata(
            name=name, status="active", tags=tags or [], type=project_type, related_projects=[]
        )

        project = Project(name=name, path=project_path, metadata=metadata, description=description)

        # - Save project
        storage.save_project(project)

        # - Create initial log entry
        initial_log = LogEntry(content=f"Project '{name}' created.", tags=["created"])
        storage.append_log_entry(project, initial_log)

        return json.dumps(
            {
                "status": "success",
                "message": f"Project '{name}' created successfully",
                "project": {"name": name, "path": str(project.path), "type": project_type, "tags": tags or []},
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


async def list_projects() -> str:
    """
    List all projects.

    Returns:
        JSON with list of projects
    """
    try:
        project_names = storage.list_all_projects()
        projects_info = []

        for name in project_names:
            project = storage.load_project(name)
            if project:
                projects_info.append(
                    {
                        "name": project.name,
                        "status": project.metadata.status,
                        "type": project.metadata.type,
                        "tags": project.metadata.tags,
                        "created": project.metadata.created.isoformat(),
                        "updated": project.metadata.updated.isoformat(),
                        "path": str(project.path),
                    }
                )

        return json.dumps({"status": "success", "projects": projects_info, "total": len(projects_info)}, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


async def get_project(name: str) -> str:
    """
    Get detailed information about a project.

    Args:
        name: Project name

    Returns:
        JSON with project details including description and recent logs
    """
    try:
        project = storage.load_project(name)
        if not project:
            return json.dumps({"status": "error", "message": f"Project '{name}' not found"}, indent=2)

        # - Get recent logs
        recent_logs = storage.read_project_log(project, limit=5)
        logs_info = [
            {"timestamp": log.timestamp.isoformat(), "tags": log.tags, "content": log.content[:200] + "..." if len(log.content) > 200 else log.content}
            for log in recent_logs
        ]

        # - Get context if exists
        context = storage.load_context(project)
        if context:
            # - Serialize datetime to ISO format
            context_dict = context.model_dump()
            if "last_updated" in context_dict:
                context_dict["last_updated"] = context.last_updated.isoformat()
            context_info = context_dict
        else:
            context_info = None

        return json.dumps(
            {
                "status": "success",
                "project": {
                    "name": project.name,
                    "path": str(project.path),
                    "status": project.metadata.status,
                    "type": project.metadata.type,
                    "tags": project.metadata.tags,
                    "created": project.metadata.created.isoformat(),
                    "updated": project.metadata.updated.isoformat(),
                    "description": project.description,
                    "recent_logs": logs_info,
                    "context": context_info,
                },
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


async def update_description(name: str, description: str) -> str:
    """
    Update project description.

    Args:
        name: Project name
        description: New description

    Returns:
        JSON with status
    """
    try:
        project = storage.load_project(name)
        if not project:
            return json.dumps({"status": "error", "message": f"Project '{name}' not found"}, indent=2)

        project.description = description
        storage.save_project(project)

        # - Log the update
        log_entry = LogEntry(content=f"Updated project description.", tags=["update"])
        storage.append_log_entry(project, log_entry)

        return json.dumps({"status": "success", "message": "Description updated successfully"}, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


async def add_log_entry(name: str, content: str, tags: list[str] | None = None) -> str:
    """
    Add a log entry to project.

    Args:
        name: Project name
        content: Log entry content
        tags: Optional tags for categorization

    Returns:
        JSON with status
    """
    try:
        project = storage.load_project(name)
        if not project:
            return json.dumps({"status": "error", "message": f"Project '{name}' not found"}, indent=2)

        log_entry = LogEntry(content=content, tags=tags or [])
        storage.append_log_entry(project, log_entry)

        return json.dumps(
            {
                "status": "success",
                "message": "Log entry added",
                "entry": {"timestamp": log_entry.timestamp.isoformat(), "tags": log_entry.tags},
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


async def read_log(name: str, limit: int = 10) -> str:
    """
    Read recent log entries from project.

    Args:
        name: Project name
        limit: Maximum number of entries to return (default: 10)

    Returns:
        JSON with log entries
    """
    try:
        project = storage.load_project(name)
        if not project:
            return json.dumps({"status": "error", "message": f"Project '{name}' not found"}, indent=2)

        entries = storage.read_project_log(project, limit=limit)
        entries_info = [
            {"timestamp": entry.timestamp.isoformat(), "tags": entry.tags, "content": entry.content}
            for entry in entries
        ]

        return json.dumps({"status": "success", "project": name, "entries": entries_info, "total": len(entries_info)}, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


async def set_context(
    name: str,
    working_files: list[str] | None = None,
    active_research: list[str] | None = None,
    blockers: list[str] | None = None,
    next_steps: list[str] | None = None,
    knowledge_bases: list[str] | None = None,
) -> str:
    """
    Set or update project context.

    Args:
        name: Project name
        working_files: Currently active files
        active_research: Active research topics
        blockers: Current blockers
        next_steps: Next steps
        knowledge_bases: Related knowledge bases

    Returns:
        JSON with status
    """
    try:
        project = storage.load_project(name)
        if not project:
            return json.dumps({"status": "error", "message": f"Project '{name}' not found"}, indent=2)

        # - Load existing context or create new
        context = storage.load_context(project) or ProjectContext(project=name)

        # - Update fields (only update if provided)
        if working_files is not None:
            context.working_files = working_files
        if active_research is not None:
            context.active_research = active_research
        if blockers is not None:
            context.blockers = blockers
        if next_steps is not None:
            context.next_steps = next_steps
        if knowledge_bases is not None:
            context.knowledge_bases = knowledge_bases

        # - Save context
        storage.save_context(project, context)

        return json.dumps({"status": "success", "message": "Context updated successfully"}, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


async def get_context(name: str) -> str:
    """
    Get project context.

    Args:
        name: Project name

    Returns:
        JSON with project context
    """
    try:
        project = storage.load_project(name)
        if not project:
            return json.dumps({"status": "error", "message": f"Project '{name}' not found"}, indent=2)

        context = storage.load_context(project)
        if not context:
            return json.dumps(
                {"status": "success", "project": name, "context": None, "message": "No context found"}, indent=2
            )

        return json.dumps({"status": "success", "project": name, "context": context.model_dump()}, indent=2)

    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)
