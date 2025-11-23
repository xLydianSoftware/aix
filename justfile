set windows-shell := ["C:\\Program Files\\Git\\bin\\sh.exe", "-c"]

# - Show available commands
help:
	@just --list --unsorted

# - Run tests
test:
	pytest tests -v

# - Run tests with coverage
test-cov:
	pytest tests -v --cov=src/xmcp --cov-report=term --cov-report=html

# - Lint code with ruff
lint:
	ruff check src/xmcp

# - Format code with ruff
fmt:
	ruff format src/xmcp

# - Build package
build:
	rm -rf dist build
	python -m build

# - Install in development mode
dev-install:
	pip install -e ".[dev]"

# - Update version (patch/minor/major)
update-version part="patch":
	@echo "Updating version ({{part}})..."
	@python -c "import toml; \
		f = 'pyproject.toml'; \
		d = toml.load(f); \
		v = d['project']['version'].split('.'); \
		i = {'major': 0, 'minor': 1, 'patch': 2}['{{part}}']; \
		v[i] = str(int(v[i]) + 1); \
		v = [v[0], v[1] if i < 1 else '0', v[2] if i < 2 else '0']; \
		d['project']['version'] = '.'.join(v); \
		toml.dump(d, open(f, 'w')); \
		print(f\"Version updated to {d['project']['version']}\")"

# - Publish to PyPI (requires main branch)
publish: build test
	@if [ "$$(git symbolic-ref --short -q HEAD)" = "main" ]; then \
		twine upload dist/*; \
	else \
		echo ">>> Not in main branch!"; \
	fi

# - Publish to PyPI without branch check (dev)
dev-publish: build
	twine upload dist/*

# - Publish to TestPyPI
test-publish: build
	twine upload --repository testpypi dist/*

# - Register MCP server with Claude Code
mcp-register:
	claude mcp add xmcp -- python -m xmcp.server

# - Unregister MCP server
mcp-unregister:
	claude mcp remove xmcp

# - Check MCP server status
mcp-status:
	claude mcp list

# - Show current Jupyter server info
jupyter-info:
	@jupyter server list 2>/dev/null || echo "No Jupyter server running"

# - Clean build artifacts
clean:
	rm -rf dist build *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
