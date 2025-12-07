"""
XMCP CLI - Command line interface for managing xmcp MCP server.
"""

import os
import signal
import subprocess
import sys
import time

import click

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


def main():
    """Main CLI entry point."""
    cli()


if __name__ == '__main__':
    main()
