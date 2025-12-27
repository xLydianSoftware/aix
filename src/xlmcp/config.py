"""
Configuration for XLMCP server.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# - Load environment variables
# Priority: 1) Current directory .env, 2) ~/.aix/xlmcp/.env, 3) Environment variables
_local_env = Path(".env")
_global_env = Path.home() / ".aix" / "xlmcp" / ".env"

if _local_env.exists():
    load_dotenv(_local_env)
elif _global_env.exists():
    load_dotenv(_global_env)
else:
    # - No .env file found, use environment variables only
    load_dotenv(override=False)


def get_env_str(key: str, default: str) -> str:
    """Get string from environment."""
    return os.getenv(key, default)


def get_env_int(key: str, default: int) -> int:
    """Get int from environment."""
    return int(os.getenv(key, str(default)))


def get_env_float(key: str, default: float) -> float:
    """Get float from environment."""
    return float(os.getenv(key, str(default)))


def get_env_bool(key: str, default: bool) -> bool:
    """Get bool from environment."""
    return os.getenv(key, str(default).lower()).lower() == "true"


def get_env_path(key: str, default: str) -> Path:
    """Get path from environment."""
    return Path(os.getenv(key, default)).expanduser()


def get_env_paths(key: str, default: str) -> list[Path]:
    """Get list of paths from environment."""
    return [Path(p.strip()).expanduser() for p in os.getenv(key, default).split(",")]


class JupyterConfig(BaseModel):
    """JupyterHub configuration."""

    model_config = {"arbitrary_types_allowed": True}

    server_url: str = get_env_str("JUPYTER_SERVER_URL", "http://localhost:8888")
    api_token: str = get_env_str("JUPYTER_API_TOKEN", "")
    notebook_dir: Path = get_env_path("JUPYTER_NOTEBOOK_DIR", "~/")
    allowed_dirs: list[Path] = get_env_paths("JUPYTER_ALLOWED_DIRS", "~/")
    ws_timeout: float = get_env_float("JUPYTER_WS_TIMEOUT", 30.0)
    exec_timeout: float = get_env_float("JUPYTER_EXEC_TIMEOUT", 300.0)


class MCPConfig(BaseModel):
    """MCP server configuration."""

    name: str = "xlmcp-jupyter"
    transport: str = get_env_str("MCP_TRANSPORT", "stdio")
    http_port: int = get_env_int("MCP_HTTP_PORT", 8765)
    max_output_tokens: int = get_env_int("MCP_MAX_OUTPUT_TOKENS", 25000)


class RAGConfig(BaseModel):
    """RAG configuration."""

    model_config = {"arbitrary_types_allowed": True}

    cache_dir: Path = get_env_path("RAG_CACHE_DIR", "~/.aix/knowledge")
    chunk_size: int = get_env_int("RAG_CHUNK_SIZE", 512)
    chunk_overlap: int = get_env_int("RAG_CHUNK_OVERLAP", 100)
    auto_refresh: bool = get_env_bool("RAG_AUTO_REFRESH", True)
    auto_refresh_interval: int = get_env_int("RAG_AUTO_REFRESH_INTERVAL", 300)
    default_search_limit: int = get_env_int("RAG_DEFAULT_SEARCH_LIMIT", 10)
    default_similarity_threshold: float = get_env_float("RAG_DEFAULT_SIMILARITY_THRESHOLD", 0.5)
    max_file_size_mb: int = get_env_int("RAG_MAX_FILE_SIZE_MB", 10)  # Skip files > 10MB
    skip_notebook_outputs: bool = get_env_bool("RAG_SKIP_NOTEBOOK_OUTPUTS", False)


class Config(BaseModel):
    """Combined configuration."""

    model_config = {"arbitrary_types_allowed": True}

    jupyter: JupyterConfig = JupyterConfig()
    mcp: MCPConfig = MCPConfig()
    rag: RAGConfig = RAGConfig()


# - Global config instance
config = Config()


def get_config() -> Config:
    """Get configuration instance."""
    return config


def validate_path(path: str | Path) -> Path:
    """Validate that path is within allowed directories."""
    path = Path(path).expanduser().resolve()

    for allowed in config.jupyter.allowed_dirs:
        allowed = allowed.expanduser().resolve()
        try:
            path.relative_to(allowed)
            return path
        except ValueError:
            continue

    raise PermissionError(f"Access denied: {path} is outside allowed directories")
