"""
JupyterHub/Jupyter Server client for REST API and WebSocket communication.
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

from xlmcp.config import get_config, validate_path


class JupyterClient:
    """Client for interacting with Jupyter Server via REST API and WebSocket."""

    def __init__(self):
        self.config = get_config().jupyter
        self._http_client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        return self.config.server_url.rstrip("/")

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_token:
            headers["Authorization"] = f"token {self.config.api_token}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=30.0,
            )
        return self._http_client

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # -------------------------------------------------------------------------
    # Kernel Management
    # -------------------------------------------------------------------------

    async def list_kernels(self) -> list[dict]:
        """List all running kernels."""
        client = await self._get_client()
        response = await client.get("/api/kernels")
        response.raise_for_status()
        return response.json()

    async def get_kernel(self, kernel_id: str) -> dict:
        """Get kernel info by ID."""
        client = await self._get_client()
        response = await client.get(f"/api/kernels/{kernel_id}")
        response.raise_for_status()
        return response.json()

    async def start_kernel(self, name: str = "python3") -> dict:
        """Start a new kernel."""
        client = await self._get_client()
        response = await client.post("/api/kernels", json={"name": name})
        response.raise_for_status()
        return response.json()

    async def stop_kernel(self, kernel_id: str) -> bool:
        """Stop a kernel."""
        client = await self._get_client()
        response = await client.delete(f"/api/kernels/{kernel_id}")
        return response.status_code == 204

    async def restart_kernel(self, kernel_id: str) -> dict:
        """Restart a kernel."""
        client = await self._get_client()
        response = await client.post(f"/api/kernels/{kernel_id}/restart")
        response.raise_for_status()
        return response.json()

    async def interrupt_kernel(self, kernel_id: str) -> bool:
        """Interrupt a running kernel."""
        client = await self._get_client()
        response = await client.post(f"/api/kernels/{kernel_id}/interrupt")
        return response.status_code == 204

    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------

    async def list_sessions(self) -> list[dict]:
        """List all sessions."""
        client = await self._get_client()
        response = await client.get("/api/sessions")
        response.raise_for_status()
        return response.json()

    async def get_session_for_notebook(self, notebook_path: str) -> dict | None:
        """Get session for a specific notebook."""
        sessions = await self.list_sessions()
        for session in sessions:
            if session.get("path") == notebook_path:
                return session
        return None

    async def create_session(
        self, notebook_path: str, kernel_name: str = "python3"
    ) -> dict:
        """Create a new session for a notebook."""
        client = await self._get_client()
        response = await client.post(
            "/api/sessions",
            json={
                "path": notebook_path,
                "type": "notebook",
                "name": Path(notebook_path).name,
                "kernel": {"name": kernel_name},
            },
        )
        response.raise_for_status()
        return response.json()

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        client = await self._get_client()
        response = await client.delete(f"/api/sessions/{session_id}")
        return response.status_code == 204

    # -------------------------------------------------------------------------
    # Code Execution via WebSocket
    # -------------------------------------------------------------------------

    async def execute_code(
        self,
        kernel_id: str,
        code: str,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """
        Execute code in a kernel via WebSocket.

        Returns dict with:
        - status: 'ok' or 'error'
        - outputs: list of output items (stdout, stderr, display_data, etc.)
        - error: error info if status='error'
        """
        timeout = timeout or self.config.exec_timeout

        # - Build WebSocket URL
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/kernels/{kernel_id}/channels"

        # - Add token to URL if needed
        if self.config.api_token:
            ws_url = f"{ws_url}?token={self.config.api_token}"

        # - Generate message ID
        msg_id = str(uuid.uuid4())

        # - Build execute_request message
        execute_request = {
            "header": {
                "msg_id": msg_id,
                "msg_type": "execute_request",
                "username": "xlmcp",
                "session": str(uuid.uuid4()),
                "date": datetime.utcnow().isoformat(),
                "version": "5.3",
            },
            "parent_header": {},
            "metadata": {},
            "content": {
                "code": code,
                "silent": False,
                "store_history": True,
                "user_expressions": {},
                "allow_stdin": False,
                "stop_on_error": True,
            },
            "buffers": [],
            "channel": "shell",
        }

        outputs: list[dict] = []
        result = {"status": "ok", "outputs": outputs, "error": None}

        try:
            async with websockets.connect(
                ws_url,
                additional_headers=self.headers if self.config.api_token else None,
            ) as ws:
                # - Send execute request
                await ws.send(json.dumps(execute_request))

                # - Collect responses until execute_reply
                start_time = asyncio.get_event_loop().time()

                while True:
                    # - Check timeout
                    if asyncio.get_event_loop().time() - start_time > timeout:
                        result["status"] = "error"
                        result["error"] = {"ename": "Timeout", "evalue": f"Execution timed out after {timeout}s"}
                        break

                    try:
                        msg_str = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        msg = json.loads(msg_str)
                    except asyncio.TimeoutError:
                        continue
                    except ConnectionClosed:
                        break

                    # - Only process messages for our request
                    parent_msg_id = msg.get("parent_header", {}).get("msg_id")
                    if parent_msg_id != msg_id:
                        continue

                    msg_type = msg.get("msg_type") or msg.get("header", {}).get("msg_type")
                    content = msg.get("content", {})

                    # - Handle different message types
                    if msg_type == "stream":
                        outputs.append({
                            "type": "stream",
                            "name": content.get("name", "stdout"),
                            "text": content.get("text", ""),
                        })

                    elif msg_type == "execute_result":
                        outputs.append({
                            "type": "execute_result",
                            "data": content.get("data", {}),
                            "execution_count": content.get("execution_count"),
                        })

                    elif msg_type == "display_data":
                        outputs.append({
                            "type": "display_data",
                            "data": content.get("data", {}),
                            "metadata": content.get("metadata", {}),
                        })

                    elif msg_type == "error":
                        result["status"] = "error"
                        result["error"] = {
                            "ename": content.get("ename", "Error"),
                            "evalue": content.get("evalue", "Unknown error"),
                            "traceback": content.get("traceback", []),
                        }

                    elif msg_type == "execute_reply":
                        # - Execution complete
                        if content.get("status") == "error":
                            result["status"] = "error"
                            result["error"] = {
                                "ename": content.get("ename", "Error"),
                                "evalue": content.get("evalue", "Unknown error"),
                                "traceback": content.get("traceback", []),
                            }
                        break

        except Exception as e:
            result["status"] = "error"
            result["error"] = {"ename": type(e).__name__, "evalue": str(e)}

        return result

    # -------------------------------------------------------------------------
    # Contents API (Notebooks, Files)
    # -------------------------------------------------------------------------

    async def get_contents(self, path: str = "") -> dict:
        """Get contents at path (file or directory listing)."""
        client = await self._get_client()
        response = await client.get(f"/api/contents/{path}")
        response.raise_for_status()
        return response.json()

    async def list_notebooks(self, directory: str = "") -> list[dict]:
        """List notebooks in a directory."""
        contents = await self.get_contents(directory)

        if contents.get("type") != "directory":
            return []

        notebooks = []
        for item in contents.get("content", []):
            if item.get("type") == "notebook":
                notebooks.append({
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "last_modified": item.get("last_modified"),
                })
            elif item.get("type") == "directory":
                # - Recursively list subdirectories
                sub_notebooks = await self.list_notebooks(item.get("path", ""))
                notebooks.extend(sub_notebooks)

        return notebooks

    async def get_notebook(self, path: str) -> dict:
        """Get notebook content."""
        client = await self._get_client()
        response = await client.get(f"/api/contents/{path}", params={"content": "1"})
        response.raise_for_status()
        return response.json()

    async def save_notebook(self, path: str, content: dict) -> dict:
        """Save notebook content."""
        client = await self._get_client()
        response = await client.put(
            f"/api/contents/{path}",
            json={"type": "notebook", "content": content},
        )
        response.raise_for_status()
        return response.json()


# - Global client instance
_client: JupyterClient | None = None


def get_client() -> JupyterClient:
    """Get or create JupyterClient instance."""
    global _client
    if _client is None:
        _client = JupyterClient()
    return _client
