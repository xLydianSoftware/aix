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


def resolve_directory(name_or_path: str) -> str | None:
    """
    Resolve knowledge base name or path to directory path.

    Priority:
    1. If looks like path (has / or ~), use as-is
    2. Check if it's a knowledge base name in knowledges.yaml
    3. Fall back to cache directory name (for backwards compatibility)

    Args:
        name_or_path: Knowledge base name, cache name, or full path

    Returns:
        Original directory path, or None if not found
    """
    import asyncio
    from xlmcp.tools.rag import storage, registry
    from pathlib import Path

    # - If it looks like a path (has / or ~), use it as-is
    if '/' in name_or_path or name_or_path.startswith('~'):
        return str(Path(name_or_path).expanduser().resolve())

    # - First, check knowledge base registry (priority)
    try:
        knowledges = registry.load_knowledges()

        if name_or_path in knowledges:
            info = knowledges[name_or_path]
            # - Return first path (for single path KBs)
            # - For multi-path KBs, return the first one (search will cover all)
            paths = info.get('paths', [])
            if paths:
                return paths[0]  # - Already expanded by load_knowledges()

    except Exception:
        pass

    # - Fall back to cache directory name lookup
    try:
        result_json = asyncio.run(storage.list_all_indexes())
        result = json.loads(result_json)
        indexes = result.get('indexes', [])

        for idx in indexes:
            if idx.get('cache_name') == name_or_path:
                return idx.get('directory')

    except Exception:
        pass

    return None


@cli.group()
def knowledge():
    """
    Test and manage knowledge base RAG tools.

    Examples:
      xlmcp knowledge search "trading strategies" xfiles-library
      xlmcp knowledge search "trading strategies" ~/projects/xfiles
      xlmcp knowledge list
      xlmcp knowledge tags xfiles-library
      xlmcp knowledge tags ~/projects/xfiles
      xlmcp knowledge index ~/projects/xfiles
    """
    pass


@knowledge.command()
@click.option('--all', 'reindex_all', is_flag=True, help='Reindex all registered knowledge bases')
@click.option('--force', is_flag=True, help='Force full reindex (ignore change detection)')
@click.option('--jobs', '-j', type=int, default=-1, help='Number of parallel jobs (-1 = all CPUs)')
@click.argument('name', required=False)
def reindex(name: str | None, reindex_all: bool, force: bool, jobs: int):
    """
    Reindex knowledge base(s) from ~/.aix/knowledges.yaml registry.

    Examples:
      xlmcp knowledge reindex quantlib          Reindex specific knowledge base
      xlmcp knowledge reindex --all             Reindex all registered knowledge bases
      xlmcp knowledge reindex --all --force     Force full reindex of all
      xlmcp knowledge reindex --all -j 4        Reindex with 4 parallel jobs
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
    elif name:
        if name not in knowledges:
            click.echo(f"✗ Knowledge base '{name}' not found in registry")
            click.echo(f"\nAvailable: {', '.join(knowledges.keys())}")
            sys.exit(1)
        to_reindex = [(name, knowledges[name])]
    else:
        click.echo("✗ Please specify a knowledge base or use --all")
        click.echo(f"\nAvailable: {', '.join(knowledges.keys())}")
        click.echo("\nExamples:")
        click.echo("  xlmcp knowledge reindex quantlib")
        click.echo("  xlmcp knowledge reindex --all")
        sys.exit(1)

    # - Import indexer
    try:
        from xlmcp.tools.rag import indexer
    except ImportError as e:
        click.echo(f"✗ Error importing RAG indexer: {e}")
        click.echo("  Make sure xlmcp is properly installed")
        sys.exit(1)

    # - Helper function to reindex single knowledge base
    def reindex_single(kb_name: str, info: dict) -> dict:
        """Reindex a single knowledge base (may have multiple paths) and return result."""
        if not isinstance(info, dict):
            return {"name": kb_name, "status": "error", "message": "Invalid configuration"}

        # - Support both 'paths' (multiple) and 'path' (single)
        paths = []
        if "paths" in info:
            paths = info["paths"]
        elif "path" in info:
            paths = [str(Path(info["path"]).expanduser().resolve())]
        else:
            return {"name": kb_name, "status": "error", "message": "No path(s) configured"}

        # - Progress callback (only show for single knowledge base or parallel execution)
        def progress_callback(msg: str):
            """Report progress with knowledge base prefix."""
            if len(to_reindex) == 1:
                # - Single KB: show progress directly
                click.echo(f"  {msg}")
            else:
                # - Multiple KBs: prefix with name (for parallel clarity)
                click.echo(f"  [{kb_name}] {msg}")

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
                "name": kb_name,
                "status": "success" if not errors else "partial",
                "files": total_files,
                "chunks": total_chunks,
                "paths": indexed_paths,
                "errors": errors if errors else None
            }
        else:
            return {
                "name": kb_name,
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
            delayed(reindex_single)(kb_name, info) for kb_name, info in to_reindex
        )
    else:
        # - Single execution - add header
        kb_name, info = to_reindex[0]
        click.echo(f"Knowledge base: {kb_name}")
        click.echo()
        results = [reindex_single(kb_name, info) for kb_name, info in to_reindex]

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


@knowledge.command()
@click.argument('query')
@click.option('--kb', multiple=True, help='Knowledge base(s) to search (default: all)')
@click.option('--limit', '-n', default=10, help='Maximum number of results')
@click.option('--threshold', '-t', default=0.5, help='Similarity threshold (0.0-1.0)')
@click.option('--tags', multiple=True, help='Filter by tags')
def search(query: str, kb: tuple, limit: int, threshold: float, tags: tuple):
    """
    Search knowledge bases with semantic query.

    By default searches ALL registered knowledge bases.
    Use --kb to search specific knowledge bases.

    Examples:
      xlmcp knowledge search "mean reversion strategies"
      xlmcp knowledge search "backtest results" --kb library
      xlmcp knowledge search "risk management" --kb library --kb backtests
      xlmcp knowledge search "momentum" --tags strategy --limit 5
    """
    import asyncio
    from xlmcp.tools.rag import storage, searcher, registry
    from pathlib import Path
    import json

    try:
        # - Import color functions
        from xlmcp.utils import cyan, green, yellow

        # - If specific KBs requested, resolve them
        if kb:
            directories = []
            for kb_name in kb:
                resolved_dir = resolve_directory(kb_name)
                if not resolved_dir:
                    click.echo(f"✗ Not found: '{kb_name}'")
                    click.echo(f"  Use 'xlmcp knowledge list' to see available knowledge bases")
                    sys.exit(1)
                directories.append(resolved_dir)

            click.echo(f"Searching '{cyan(query)}' in {', '.join(kb)}...\n")
        else:
            # - Search all registered KBs
            directories = None
            click.echo(f"Searching '{cyan(query)}' in {cyan('all knowledge bases', bold=True)}...\n")

        # - Run search
        if directories:
            # - Search specific directories
            all_results = []
            for directory in directories:
                result_json = asyncio.run(searcher.search_documents(
                    directory=directory,
                    query=query,
                    tags=list(tags) if tags else None,
                    metadata_filters=None,
                    limit=limit,
                    threshold=threshold
                ))
                result = json.loads(result_json)
                if result.get('status') == 'success' and result.get('results'):
                    all_results.extend(result['results'])

            # - Sort by score and limit
            all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
            all_results = all_results[:limit]

            result = {
                'status': 'success',
                'results': all_results,
                'total': len(all_results)
            }
        else:
            # - Search all KBs using server logic
            knowledges = registry.load_knowledges()
            if not knowledges:
                click.echo("No knowledge bases registered in ~/.aix/knowledges.yaml")
                sys.exit(1)

            all_results = []
            for kb_name, kb_info in knowledges.items():
                for kb_path in kb_info.get('paths', []):
                    try:
                        result_json = asyncio.run(searcher.search_documents(
                            directory=kb_path,
                            query=query,
                            tags=list(tags) if tags else None,
                            metadata_filters=None,
                            limit=limit,
                            threshold=threshold
                        ))
                        res = json.loads(result_json)
                        if res.get('status') == 'success' and res.get('results'):
                            for r in res['results']:
                                r['knowledge_base'] = kb_name
                            all_results.extend(res['results'])
                    except Exception:
                        continue

            # - Sort by score and limit
            all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
            all_results = all_results[:limit]

            result = {
                'status': 'success',
                'results': all_results,
                'total': len(all_results)
            }

        # - Display results
        if result.get('error'):
            click.echo(f"✗ Error: {result['error']}")
            sys.exit(1)

        results = result.get('results', [])
        click.echo(f"Found {green(str(len(results)))} results (threshold: {threshold}):\n")

        for i, r in enumerate(results, 1):
            filename = r.get('filename', r.get('file_path', r.get('file', 'Unknown')))
            kb_name = r.get('knowledge_base', '')

            if kb_name:
                click.echo(f"{i}. {cyan(filename)} [{yellow(kb_name)}]")
            else:
                click.echo(f"{i}. {cyan(filename)}")

            click.echo(f"   Score: {r.get('score', 0):.3f}")

            if r.get('tags'):
                tags_str = ', '.join(r['tags'])
                click.echo(f"   Tags: {tags_str}")

            content = r.get('text', r.get('content', ''))[:200]
            click.echo(f"   Content: {content}...")
            click.echo()

    except Exception as e:
        click.echo(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        # - Cleanup Milvus clients to avoid exit delay
        storage.cleanup_clients()


@knowledge.command(name='list')
def list_indexes():
    """List registered knowledge bases and their index status."""
    import asyncio
    from xlmcp.tools.rag import storage, registry
    from pathlib import Path

    try:
        # - Load registered knowledge bases from knowledges.yaml
        # - Use load_knowledges() directly - it already returns expanded string paths
        knowledges = registry.load_knowledges()

        if not knowledges:
            click.echo("No knowledge bases registered in ~/.aix/knowledges.yaml")
            click.echo("\nCreate ~/.aix/knowledges.yaml with your knowledge bases.")
            return

        # - Get indexed directories for status checking
        indexes_json = asyncio.run(storage.list_all_indexes())
        indexes_result = json.loads(indexes_json)
        indexed_dirs = {idx.get('directory'): idx for idx in indexes_result.get('indexes', [])}

        # - Import color functions
        from xlmcp.utils import cyan, green, red, yellow, blue, magenta  # noqa: I001

        click.echo(f"{cyan('Knowledge bases', bold=True)} ({len(knowledges)}):\n")

        for name, info in knowledges.items():
            click.echo(f"  • {red(name, bold=True)}")

            # - Get paths (already expanded by load_knowledges())
            paths = info.get('paths', [])

            if info.get('description'):
                click.echo(f"    Description: {magenta(info['description'])}")

            # - Show paths and index status
            if paths:
                for path in paths:
                    if path in indexed_dirs:
                        idx_info = indexed_dirs[path]
                        files = idx_info.get('file_count', 0)
                        last_checked = idx_info.get('last_checked', 0)
                        if last_checked > 0:
                            from datetime import datetime
                            dt = datetime.fromtimestamp(last_checked)
                            status = green(f"✓ Indexed ({files} files, {dt.strftime('%Y-%m-%d %H:%M')})")
                        else:
                            status = green(f"✓ Indexed ({files} files)")
                    else:
                        status = yellow("✗ Not indexed")

                    click.echo(f"    Path: {blue(path)}")
                    click.echo(f"    Status: {status}")

            if info.get('tags'):
                tags_str = ', '.join(info['tags'])
                click.echo(f"    Tags: {cyan(tags_str)}")

            click.echo()

    except Exception as e:
        click.echo(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@knowledge.command()
@click.option('--kb', multiple=True, help='Knowledge base(s) to get tags from (default: all)')
def tags(kb: tuple):
    """
    Get all tags from knowledge bases.

    By default aggregates tags from ALL registered knowledge bases.
    Use --kb to get tags from specific knowledge bases.

    Examples:
      xlmcp knowledge tags
      xlmcp knowledge tags --kb library
      xlmcp knowledge tags --kb library --kb backtests
    """
    import asyncio
    from xlmcp.tools.rag import storage, searcher, registry

    try:
        # - Import color functions
        from xlmcp.utils import cyan, green, yellow

        # - If specific KBs requested, aggregate from them
        if kb:
            all_tags = {}
            for kb_name in kb:
                resolved_dir = resolve_directory(kb_name)
                if not resolved_dir:
                    click.echo(f"✗ Not found: '{kb_name}'")
                    click.echo("  Use 'xlmcp knowledge list' to see available knowledge bases")
                    sys.exit(1)

                result_json = asyncio.run(searcher.get_all_tags(resolved_dir))
                result = json.loads(result_json)

                if result.get('status') == 'success' and result.get('tags'):
                    for tag, count in result['tags'].items():
                        all_tags[tag] = all_tags.get(tag, 0) + count

            click.echo(f"Tags in {cyan(', '.join(kb), bold=True)}:\n")
        else:
            # - Aggregate tags from all registered KBs
            knowledges = registry.load_knowledges()
            if not knowledges:
                click.echo("No knowledge bases registered in ~/.aix/knowledges.yaml")
                sys.exit(1)

            all_tags = {}
            for kb_name, kb_info in knowledges.items():
                for kb_path in kb_info.get('paths', []):
                    try:
                        result_json = asyncio.run(searcher.get_all_tags(kb_path))
                        result = json.loads(result_json)
                        if result.get('status') == 'success' and result.get('tags'):
                            for tag, count in result['tags'].items():
                                all_tags[tag] = all_tags.get(tag, 0) + count
                    except Exception:
                        continue

            click.echo(f"Tags in {cyan('all knowledge bases', bold=True)}:\n")

        if not all_tags:
            click.echo("  (No tags found)")
        else:
            # - Sort by count
            sorted_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)
            for tag, count in sorted_tags:
                click.echo(f"  {cyan(tag)}: {count}")

        click.echo(f"\nTotal: {green(str(len(all_tags)))} unique tags")

    except Exception as e:
        click.echo(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        # - Cleanup Milvus clients to avoid exit delay
        storage.cleanup_clients()


@knowledge.command()
@click.argument('directory')
@click.option('--force', is_flag=True, help='Force reindex')
def index(directory: str, force: bool):
    """Index a directory for knowledge search."""
    import asyncio
    from xlmcp.tools.rag import indexer

    try:
        click.echo(f"Indexing {directory}...")
        if force:
            click.echo("(Force reindex enabled)")

        result_json = asyncio.run(indexer.index_directory(
            directory=directory,
            recursive=True,
            force_reindex=force
        ))

        result = json.loads(result_json)

        if result.get('error'):
            click.echo(f"✗ Error: {result['error']}")
            sys.exit(1)

        click.echo("\n✓ Indexed successfully!")
        click.echo(f"  Files processed: {result.get('files_processed', 0)}")
        click.echo(f"  Documents created: {result.get('documents_created', 0)}")
        click.echo(f"  Time: {result.get('time_seconds', 0):.2f}s")

    except Exception as e:
        click.echo(f"✗ Error: {e}")
        sys.exit(1)


@knowledge.command()
def knowledges():
    """List registered knowledge bases from ~/.aix/knowledges.yaml."""
    import asyncio
    from xlmcp.tools.rag import registry

    try:
        result_json = asyncio.run(registry.list_knowledges())
        result = json.loads(result_json)

        kbs = result.get('knowledges', {})

        if not kbs:
            click.echo("No knowledge bases registered in ~/.aix/knowledges.yaml")
            return

        click.echo(f"Registered knowledge bases ({len(kbs)}):\n")

        for name, info in kbs.items():
            click.echo(f"  {name}")
            click.echo(f"    Path: {info.get('path') or info.get('paths')}")
            click.echo(f"    Description: {info.get('description', 'N/A')}")
            if info.get('tags'):
                click.echo(f"    Tags: {', '.join(info['tags'])}")
            click.echo(f"    Status: {info.get('status', 'Unknown')}")
            click.echo()

    except Exception as e:
        click.echo(f"✗ Error: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == '__main__':
    main()
