"""
XMCP CLI - Command line interface for managing xmcp MCP server.
"""

import os
import signal
import subprocess
import sys
import time
import warnings

import click

# - Suppress Pydantic warning from llama-index library
warnings.filterwarnings("ignore", category=Warning, message=".*validate_default.*")

from xmcp.utils import list_server_tools, print_tools_list


def get_server_pid() -> int | None:
    """
    Get PID of running xmcp server process.

    Returns:
        PID or None if not running
    """
    try:
        result = subprocess.run(
            ["pgrep", "-f", "xmcp.server"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split('\n')[0])
        return None
    except Exception:
        return None


def is_server_running() -> bool:
    """Check if xmcp server is running."""
    return get_server_pid() is not None


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """
    XMCP CLI - Manage xmcp MCP server.

    Examples:
      xmcp start          Start server in background
      xmcp stop           Stop server
      xmcp restart        Restart server
      xmcp status         Show server status
      xmcp ls             List available tools
      xmcp start -f       Start server in foreground
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.option('-f', '--foreground', is_flag=True, help='Run server in foreground')
def start(foreground: bool):
    """Start xmcp MCP server."""
    if is_server_running():
        click.echo("✓ xmcp server is already running")
        click.echo(f"  PID: {get_server_pid()}")
        return

    click.echo("Starting xmcp server...")

    if foreground:
        # - Run in foreground
        from xmcp.server import main
        main()
    else:
        # - Run in background
        subprocess.Popen(
            [sys.executable, "-m", "xmcp.server"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        time.sleep(1)  # Give it time to start

        if is_server_running():
            click.echo("✓ xmcp server started")
            click.echo(f"  PID: {get_server_pid()}")
        else:
            click.echo("✗ Failed to start xmcp server")
            sys.exit(1)


@cli.command()
def stop():
    """Stop xmcp MCP server."""
    pid = get_server_pid()

    if pid is None:
        click.echo("✓ xmcp server is not running")
        return

    click.echo(f"Stopping xmcp server (PID: {pid})...")

    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)

        # - Check if stopped
        if not is_server_running():
            click.echo("✓ xmcp server stopped")
        else:
            click.echo("✗ Server did not stop gracefully, forcing...")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
            if not is_server_running():
                click.echo("✓ xmcp server killed")
            else:
                click.echo("✗ Failed to stop server")
                sys.exit(1)
    except ProcessLookupError:
        click.echo("✓ xmcp server stopped")
    except Exception as e:
        click.echo(f"✗ Error stopping server: {e}")
        sys.exit(1)


@cli.command()
def restart():
    """Restart xmcp MCP server."""
    click.echo("Restarting xmcp server...\n")
    ctx = click.get_current_context()
    ctx.invoke(stop)
    time.sleep(0.5)
    ctx.invoke(start)


@cli.command()
def status():
    """Show xmcp server status."""
    pid = get_server_pid()

    click.echo(f"\n{'='*60}")
    click.echo("XMCP Server Status")
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
        click.echo("  Make sure xmcp is properly installed")
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
      xmcp reindex quantlib          Reindex specific knowledge base
      xmcp reindex --all             Reindex all registered knowledge bases
      xmcp reindex --all --force     Force full reindex of all
      xmcp reindex --all -j 4        Reindex with 4 parallel jobs
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
        click.echo("  xmcp reindex quantlib")
        click.echo("  xmcp reindex --all")
        sys.exit(1)

    # - Import indexer
    try:
        from xmcp.tools.rag import indexer
    except ImportError as e:
        click.echo(f"✗ Error importing RAG indexer: {e}")
        click.echo("  Make sure xmcp is properly installed")
        sys.exit(1)

    # - Helper function to reindex single knowledge base
    def reindex_single(name: str, info: dict) -> dict:
        """Reindex a single knowledge base and return result."""
        if isinstance(info, dict) and "path" in info:
            path = Path(info["path"]).expanduser().resolve()
        else:
            return {"name": name, "status": "error", "message": "Invalid configuration"}

        if not path.exists():
            return {"name": name, "status": "error", "message": f"Path does not exist: {path}"}

        try:
            result = asyncio.run(indexer.index_directory(
                directory=str(path),
                recursive=True,
                force_reindex=force
            ))

            # - Parse result
            import json
            result_data = json.loads(result)

            if result_data.get("status") == "success":
                stats = result_data.get("stats", {})
                return {
                    "name": name,
                    "status": "success",
                    "files": stats.get('processed_files', 0),
                    "chunks": stats.get('total_chunks', 0),
                    "path": str(path)
                }
            else:
                return {
                    "name": name,
                    "status": "error",
                    "message": result_data.get('message', 'Unknown error')
                }

        except Exception as e:
            return {"name": name, "status": "error", "message": str(e)}

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
        # - Single execution
        results = [reindex_single(name, info) for name, info in to_reindex]

    # - Display results
    total_success = 0
    total_failed = 0

    for result in results:
        name = result["name"]
        status = result["status"]

        if status == "success":
            click.echo(f"✓ {name}: {result['files']} files, {result['chunks']} chunks")
            click.echo(f"  Path: {result['path']}")
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


def main():
    """Main CLI entry point."""
    cli()


if __name__ == '__main__':
    main()
