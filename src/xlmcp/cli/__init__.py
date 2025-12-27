"""
XLMCP CLI - Command line interface for managing xlmcp MCP server.
"""

import json
import os
import signal
import subprocess
import sys
import time
import warnings

import click

# - Suppress Pydantic warning from llama-index library
warnings.filterwarnings("ignore", category=Warning, message=".*validate_default.*")

from xlmcp.utils import list_server_tools, print_tools_list


def get_server_pid() -> int | None:
    """
    Get PID of running xlmcp server process.

    Returns:
        PID or None if not running
    """
    try:
        result = subprocess.run(
            ["pgrep", "-f", "xlmcp.server"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split('\n')[0])
        return None
    except Exception:
        return None


def is_server_running() -> bool:
    """Check if xlmcp server is running."""
    return get_server_pid() is not None


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """
    XLMCP CLI - Manage xlmcp MCP server.

    Examples:
      xlmcp start          Start server in background
      xlmcp stop           Stop server
      xlmcp restart        Restart server
      xlmcp status         Show server status
      xlmcp ls             List available tools
      xlmcp start -f       Start server in foreground
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.option('-f', '--foreground', is_flag=True, help='Run server in foreground')
def start(foreground: bool):
    """Start xlmcp MCP server."""
    if is_server_running():
        click.echo("✓ xlmcp server is already running")
        click.echo(f"  PID: {get_server_pid()}")
        return

    click.echo("Starting xlmcp server...")

    if foreground:
        # - Run in foreground
        from xlmcp.server import main
        main()
    else:
        # - Run in background
        subprocess.Popen(
            [sys.executable, "-m", "xlmcp.server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        time.sleep(1)  # Give it time to start

        if is_server_running():
            click.echo("✓ xlmcp server started")
            click.echo(f"  PID: {get_server_pid()}")
        else:
            click.echo("✗ Failed to start xlmcp server")
            sys.exit(1)


@cli.command()
def stop():
    """Stop xlmcp MCP server."""
    pid = get_server_pid()

    if pid is None:
        click.echo("✓ xlmcp server is not running")
        return

    click.echo(f"Stopping xlmcp server (PID: {pid})...")

    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)

        # - Check if stopped
        if not is_server_running():
            click.echo("✓ xlmcp server stopped")
        else:
            click.echo("✗ Server did not stop gracefully, forcing...")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
            if not is_server_running():
                click.echo("✓ xlmcp server killed")
            else:
                click.echo("✗ Failed to stop server")
                sys.exit(1)
    except ProcessLookupError:
        click.echo("✓ xlmcp server stopped")
    except Exception as e:
        click.echo(f"✗ Error stopping server: {e}")
        sys.exit(1)


@cli.command()
def restart():
    """Restart xlmcp MCP server."""
    click.echo("Restarting xlmcp server...\n")
    ctx = click.get_current_context()
    ctx.invoke(stop)
    time.sleep(0.5)
    ctx.invoke(start)


@cli.command()
def status():
    """Show xlmcp server status."""
    pid = get_server_pid()

    click.echo(f"\n{'='*60}")
    click.echo("XLMCP Server Status")
    click.echo(f"{'='*60}\n")

    if pid:
        click.echo("Status:  ✓ Running")
        click.echo(f"PID:     {pid}")

        # - Get process info
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "etime=,cmd="],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 0:
                    parts = lines[0].strip().split(None, 1)
                    if len(parts) >= 1:
                        click.echo(f"Uptime:  {parts[0]}")
                    if len(parts) >= 2:
                        click.echo(f"Command: {parts[1]}")
        except Exception:
            pass
    else:
        click.echo("Status:  ✗ Not running")

    click.echo(f"\n{'='*60}\n")


@cli.command(name='ls')
def list_command():
    """List all available MCP tools."""
    try:
        tools = list_server_tools()
        print_tools_list(tools)
    except Exception as e:
        click.echo(f"✗ Error listing tools: {e}")
        click.echo("  Make sure xlmcp is properly installed")
        sys.exit(1)


# - Alias for 'ls'
@cli.command(name='list', hidden=True)
def list_alias():
    """List all available MCP tools (alias for ls)."""
    ctx = click.get_current_context()
    ctx.invoke(list_command)


@cli.command()
@click.option('--all', 'reindex_all', is_flag=True, help='Reindex all registered knowledge bases')
@click.option('--force', is_flag=True, help='Force full reindex (ignore change detection)')
@click.option('--jobs', '-j', type=int, default=-1, help='Number of parallel jobs (-1 = all CPUs)')
@click.argument('knowledge', required=False)
def reindex(knowledge: str | None, reindex_all: bool, force: bool, jobs: int):
    """
    Reindex knowledge base(s).

    Examples:
      xlmcp reindex quantlib          Reindex specific knowledge base
      xlmcp reindex --all             Reindex all registered knowledge bases
      xlmcp reindex --all --force     Force full reindex of all
      xlmcp reindex --all -j 4        Reindex with 4 parallel jobs
    """
    import asyncio
    from pathlib import Path

    # - Load knowledge registry
    knowledges_file = Path.home() / ".aix" / "knowledges.yaml"

    if not knowledges_file.exists():
        click.echo(f"✗ Knowledge registry not found: {knowledges_file}")
        click.echo("  Create ~/.aix/knowledges.yaml first")
        sys.exit(1)

    try:
        import yaml
        with open(knowledges_file) as f:
            data = yaml.safe_load(f)

        if not data or "knowledges" not in data:
            click.echo("✗ Invalid knowledge registry format")
            sys.exit(1)

        knowledges = data["knowledges"]

    except Exception as e:
        click.echo(f"✗ Error loading knowledge registry: {e}")
        sys.exit(1)

    # - Determine which knowledge bases to reindex
    to_reindex = []

    if reindex_all:
        to_reindex = list(knowledges.items())
    elif knowledge:
        if knowledge not in knowledges:
            click.echo(f"✗ Knowledge base '{knowledge}' not found in registry")
            click.echo(f"\nAvailable: {', '.join(knowledges.keys())}")
            sys.exit(1)
        to_reindex = [(knowledge, knowledges[knowledge])]
    else:
        click.echo("✗ Please specify a knowledge base or use --all")
        click.echo(f"\nAvailable: {', '.join(knowledges.keys())}")
        click.echo("\nExamples:")
        click.echo("  xlmcp reindex quantlib")
        click.echo("  xlmcp reindex --all")
        sys.exit(1)

    # - Import indexer
    try:
        from xlmcp.tools.rag import indexer
    except ImportError as e:
        click.echo(f"✗ Error importing RAG indexer: {e}")
        click.echo("  Make sure xlmcp is properly installed")
        sys.exit(1)

    # - Helper function to reindex single knowledge base
    def reindex_single(name: str, info: dict) -> dict:
        """Reindex a single knowledge base (may have multiple paths) and return result."""
        if not isinstance(info, dict):
            return {"name": name, "status": "error", "message": "Invalid configuration"}

        # - Support both 'paths' (multiple) and 'path' (single)
        paths = []
        if "paths" in info:
            paths = info["paths"]
        elif "path" in info:
            paths = [str(Path(info["path"]).expanduser().resolve())]
        else:
            return {"name": name, "status": "error", "message": "No path(s) configured"}

        # - Progress callback (only show for single knowledge base or parallel execution)
        def progress_callback(msg: str):
            """Report progress with knowledge base prefix."""
            if len(to_reindex) == 1:
                # - Single KB: show progress directly
                click.echo(f"  {msg}")
            else:
                # - Multiple KBs: prefix with name (for parallel clarity)
                click.echo(f"  [{name}] {msg}")

        # - Reindex each path
        total_files = 0
        total_chunks = 0
        indexed_paths = []
        errors = []

        for path_str in paths:
            path = Path(path_str).expanduser().resolve()

            if not path.exists():
                errors.append(f"Path does not exist: {path}")
                continue

            try:
                result = asyncio.run(indexer.index_directory(
                    directory=str(path),
                    recursive=True,
                    force_reindex=force,
                    progress_callback=progress_callback
                ))

                # - Parse result
                result_data = json.loads(result)

                if result_data.get("status") == "success":
                    # - Extract stats from result
                    total_files += result_data.get('processed_files', 0)
                    total_chunks += result_data.get('total_chunks', 0)
                    indexed_paths.append(str(path))
                else:
                    errors.append(f"{path}: {result_data.get('message', 'Unknown error')}")

            except Exception as e:
                errors.append(f"{path}: {str(e)}")

        # - Return combined result
        if indexed_paths:
            return {
                "name": name,
                "status": "success" if not errors else "partial",
                "files": total_files,
                "chunks": total_chunks,
                "paths": indexed_paths,
                "errors": errors if errors else None
            }
        else:
            return {
                "name": name,
                "status": "error",
                "message": "; ".join(errors) if errors else "No paths indexed"
            }

    # - Reindex each knowledge base
    click.echo(f"\n{'='*60}")
    click.echo(f"Reindexing {len(to_reindex)} knowledge base(s)")
    if force:
        click.echo("Mode: Force full reindex")
    if len(to_reindex) > 1:
        click.echo(f"Parallel jobs: {jobs if jobs > 0 else 'all CPUs'}")
    click.echo(f"{'='*60}\n")

    # - Run reindexing (parallel if multiple knowledge bases)
    if len(to_reindex) > 1:
        # - Parallel execution
        from joblib import Parallel, delayed

        results = Parallel(n_jobs=jobs, verbose=0)(
            delayed(reindex_single)(name, info) for name, info in to_reindex
        )
    else:
        # - Single execution - add header
        name, info = to_reindex[0]
        click.echo(f"Knowledge base: {name}")
        click.echo()
        results = [reindex_single(name, info) for name, info in to_reindex]

    # - Display results
    total_success = 0
    total_failed = 0

    for result in results:
        name = result["name"]
        status = result["status"]

        if status in ("success", "partial"):
            click.echo(f"✓ {name}: {result['files']} files, {result['chunks']} chunks")
            paths = result.get('paths', [])
            if len(paths) == 1:
                click.echo(f"  Path: {paths[0]}")
            else:
                click.echo(f"  Paths ({len(paths)}):")
                for p in paths:
                    click.echo(f"    - {p}")

            # - Show errors if partial success
            if status == "partial" and result.get('errors'):
                click.echo("  Errors:")
                for err in result['errors']:
                    click.echo(f"    - {err}")

            total_success += 1
        else:
            click.echo(f"✗ {name}: {result.get('message', 'Unknown error')}")
            total_failed += 1

        click.echo()

    # - Summary
    click.echo(f"{'='*60}")
    click.echo(f"Reindex complete: {total_success} success, {total_failed} failed")
    click.echo(f"{'='*60}\n")

    if total_failed > 0:
        sys.exit(1)


@cli.command()
def kernels():
    """
    List active Jupyter kernels.

    Shows running kernels with their IDs, names, states, and connection counts.
    """
    import asyncio

    try:
        from xlmcp.tools.jupyter import kernel

        # - Call async kernel.list_kernels()
        result_json = asyncio.run(kernel.list_kernels())

        # - Parse result
        result = json.loads(result_json)

        kernels_list = result.get("kernels", [])
        count = result.get("count", 0)

        click.echo(f"\n{'='*60}")
        click.echo(f"Active Jupyter Kernels ({count})")
        click.echo(f"{'='*60}\n")

        if count == 0:
            click.echo("No active kernels")
        else:
            for k in kernels_list:
                click.echo(f"Kernel ID:    {k.get('id')}")
                click.echo(f"Name:         {k.get('name')}")
                click.echo(f"State:        {k.get('state')}")
                click.echo(f"Connections:  {k.get('connections')}")
                click.echo()

        click.echo(f"{'='*60}\n")

    except Exception as e:
        click.echo(f"✗ Error listing kernels: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == '__main__':
    main()
