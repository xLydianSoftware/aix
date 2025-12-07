"""
Configuration for XMCP server.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# - Load environment variables
load_dotenv()


class JupyterConfig(BaseModel):
    """JupyterHub configuration."""

    # - JupyterHub server URL (e.g., http://localhost:8888)
    server_url: str = Field(default_factory=lambda: os.getenv("JUPYTER_SERVER_URL", "http://localhost:8888"))

    # - API token for authentication
    api_token: str = Field(default_factory=lambda: os.getenv("JUPYTER_API_TOKEN", ""))

    # - Default notebook directory
    notebook_dir: Path = Field(default_factory=lambda: Path(os.getenv("JUPYTER_NOTEBOOK_DIR", "~/")))

    # - Allowed directories (security - prevent access outside these)
    allowed_dirs: list[Path] = Field(
        default_factory=lambda: [
            Path(p.strip()).expanduser() for p in os.getenv("JUPYTER_ALLOWED_DIRS", "~/").split(",")
        ]
    )

    # - WebSocket timeout (seconds)
    ws_timeout: float = Field(default_factory=lambda: float(os.getenv("JUPYTER_WS_TIMEOUT", "30")))

    # - Execution timeout (seconds)
    exec_timeout: float = Field(default_factory=lambda: float(os.getenv("JUPYTER_EXEC_TIMEOUT", "300")))


class MCPConfig(BaseModel):
    """MCP server configuration."""

    # - Server name
    name: str = "xmcp-jupyter"

    # - Transport type: stdio or http
    transport: str = Field(default_factory=lambda: os.getenv("MCP_TRANSPORT", "stdio"))

    # - HTTP port (if transport=http)
    http_port: int = Field(default_factory=lambda: int(os.getenv("MCP_HTTP_PORT", "8765")))

    # - Max output tokens
    max_output_tokens: int = Field(default_factory=lambda: int(os.getenv("MCP_MAX_OUTPUT_TOKENS", "25000")))


class Config(BaseModel):
    """Combined configuration."""

    jupyter: JupyterConfig = Field(default_factory=JupyterConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)


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
