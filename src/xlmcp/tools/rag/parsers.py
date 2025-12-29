"""
File-type-specific parsers for knowledge files.
"""

import ast
import json
import re
from pathlib import Path

from xlmcp.tools.rag.models import DocumentMetadata, FileType


class PythonParser:
    """
    Parser for Python source files.
    """

    @staticmethod
    def extract_metadata(file_path: str) -> DocumentMetadata:
        """
        Extract metadata from Python file using AST parsing.

        Extracts:
        - Module docstring
        - Class names
        - Function names (top-level)
        - Import statements
        - __main__ block detection
        - Hashtags from docstring

        Args:
            file_path: Path to Python file

        Returns:
            DocumentMetadata with Python-specific fields
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                source = f.read()
        except (FileNotFoundError, UnicodeDecodeError):
            return DocumentMetadata(file_type=FileType.PYTHON.value)

        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError:
            # - File has syntax errors, return minimal metadata
            return DocumentMetadata(file_type=FileType.PYTHON.value)

        # - Extract module docstring
        module_docstring = ast.get_docstring(tree)

        # - Extract classes, functions, imports
        classes = []
        functions = []
        imports = []
        has_main = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.FunctionDef):
                # - Only top-level functions (col_offset == 0)
                if node.col_offset == 0:
                    functions.append(node.name)
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
            elif isinstance(node, ast.If):
                # - Check for if __name__ == "__main__":
                if isinstance(node.test, ast.Compare):
                    if (
                        hasattr(node.test.left, "id")
                        and node.test.left.id == "__name__"
                    ):
                        has_main = True

        # - Extract hashtags from docstring
        tags = []
        if module_docstring:
            tag_pattern = r"#[a-zA-Z][a-zA-Z0-9_-]*"
            tags = list(set(re.findall(tag_pattern, module_docstring)))

        # - Module name from file path
        module_name = Path(file_path).stem

        return DocumentMetadata(
            file_type=FileType.PYTHON.value,
            module_name=module_name,
            classes=classes if classes else None,
            functions=functions if functions else None,
            imports=list(set(imports)) if imports else None,
            has_main=has_main if has_main else None,
            tags=tags if tags else None,
            custom={"docstring": module_docstring} if module_docstring else None,
        )

    @staticmethod
    def extract_text(file_path: str) -> str:
        """
        Extract text content from Python file.

        Returns entire file as text for indexing.

        Args:
            file_path: Path to Python file

        Returns:
            Full file content
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except (FileNotFoundError, UnicodeDecodeError):
            return ""


class JupyterParser:
    """
    Parser for Jupyter notebook files.
    """

    @staticmethod
    def extract_metadata(file_path: str) -> DocumentMetadata:
        """
        Extract metadata from Jupyter notebook.

        Extracts:
        - Kernel spec name
        - Cell counts (total, code, markdown)
        - Tags from markdown cells

        Args:
            file_path: Path to .ipynb file

        Returns:
            DocumentMetadata with Jupyter-specific fields
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                nb = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return DocumentMetadata(file_type=FileType.JUPYTER.value)

        # - Extract kernel spec
        kernel_spec = nb.get("metadata", {}).get("kernelspec", {}).get("name")

        # - Count cells
        cells = nb.get("cells", [])
        total_cells = len(cells)
        code_cells = sum(1 for c in cells if c.get("cell_type") == "code")
        markdown_cells = sum(1 for c in cells if c.get("cell_type") == "markdown")

        # - Extract hashtags from markdown cells (using shared extraction logic)
        from xlmcp.tools.rag.metadata import extract_inline_hashtags

        tags = []
        for cell in cells:
            if cell.get("cell_type") == "markdown":
                # - Join source lines if it's a list
                source = cell.get("source", [])
                if isinstance(source, list):
                    source = "".join(source)
                # - Use shared extraction logic (handles HTML/CSS removal and filtering)
                cell_tags = extract_inline_hashtags(source)
                tags.extend(cell_tags)

        # - Deduplicate tags
        tags = list(set(tags)) if tags else None

        return DocumentMetadata(
            file_type=FileType.JUPYTER.value,
            kernel_spec=kernel_spec,
            cell_count=total_cells,
            code_cell_count=code_cells,
            markdown_cell_count=markdown_cells,
            tags=tags,
        )

    @staticmethod
    def _is_plot_output(text: str) -> bool:
        """
        Check if text is a plot/figure representation.

        Args:
            text: Text to check

        Returns:
            True if text appears to be a plot output
        """
        if not text:
            return False

        # - Convert to string if list
        if isinstance(text, list):
            text = "".join(text)

        text_lower = text.lower()

        # - Check for figure patterns
        if text.startswith("<Figure size"):
            return True

        # - Check for plotly patterns
        if "plotly" in text_lower:
            return True

        # - Check for matplotlib figure references
        if "matplotlib.figure.Figure" in text:
            return True

        return False

    @staticmethod
    def extract_text(file_path: str, skip_outputs: bool = False) -> str:
        """
        Extract text content from Jupyter notebook.

        Includes:
        - Code cells (source)
        - Markdown cells (source)
        - Text outputs (stdout, text/plain, text/html) - unless skip_outputs=True

        Excludes:
        - Images (image/png, image/jpeg)
        - Plotly/interactive widgets (application/vnd.jupyter.widget-view+json)
        - Figure representations (text starting with "<Figure size")
        - Error tracebacks

        Args:
            file_path: Path to .ipynb file
            skip_outputs: If True, only index cell sources (not outputs)

        Returns:
            Combined text content from cells and outputs
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                nb = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return ""

        text_parts = []
        cells = nb.get("cells", [])

        for idx, cell in enumerate(cells):
            cell_type = cell.get("cell_type")

            # - Get source (can be list or string)
            source = cell.get("source", [])
            if isinstance(source, list):
                source = "".join(source)

            # - Add cell source
            if cell_type in ("code", "markdown") and source.strip():
                text_parts.append(f"# Cell {idx + 1} ({cell_type}):\n{source}\n")

            # - Extract text outputs from code cells (unless skip_outputs is True)
            if cell_type == "code" and not skip_outputs:
                outputs = cell.get("outputs", [])
                for output in outputs:
                    output_type = output.get("output_type")

                    if output_type == "stream":
                        # - stdout/stderr
                        text = output.get("text", [])
                        if isinstance(text, list):
                            text = "".join(text)
                        if text.strip():
                            text_parts.append(f"# Output (stream):\n{text}\n")

                    elif output_type in ("execute_result", "display_data"):
                        data = output.get("data", {})

                        # - Skip interactive widgets (plotly, ipywidgets)
                        if "application/vnd.jupyter.widget-view+json" in data:
                            continue

                        # - Skip images
                        if any(k.startswith("image/") for k in data.keys()):
                            continue

                        # - Include HTML outputs (tables, formatted results)
                        if "text/html" in data:
                            html_text = data["text/html"]
                            if isinstance(html_text, list):
                                html_text = "".join(html_text)
                            if html_text.strip():
                                text_parts.append(f"# Output (html):\n{html_text}\n")

                        # - Include text/plain but skip figure representations
                        if "text/plain" in data:
                            plain_text = data["text/plain"]
                            if isinstance(plain_text, list):
                                plain_text = "".join(plain_text)

                            # - Skip if it's a plot/figure output
                            if not JupyterParser._is_plot_output(plain_text):
                                if plain_text.strip():
                                    text_parts.append(
                                        f"# Output (text):\n{plain_text}\n"
                                    )

        return "\n".join(text_parts)
