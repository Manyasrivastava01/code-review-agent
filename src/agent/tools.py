"""Agent inspection tools for exploring repository context."""

import ast
import os
import re
from pathlib import Path
from typing import Any, Optional


class CodebaseTools:
    """Provides safe filesystem and code-intelligence tools for the LLM agent."""

    def __init__(self, repo_dir: str, pr_diff: str = ""):
        self.repo_dir = Path(repo_dir).resolve()
        self.pr_diff = pr_diff

    def _safe_path(self, relative_path: str) -> Path:
        """Ensure path stays within the repository root (prevents directory traversal)."""
        target = (self.repo_dir / relative_path).resolve()
        if not target.is_relative_to(self.repo_dir):
            raise PermissionError(f"Access denied: path '{relative_path}' is outside repository root.")
        return target

    def read_file(self, file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
        """Read full file contents or a specific line range (1-indexed)."""
        try:
            target = self._safe_path(file_path)
            if not target.is_file():
                return f"Error: File '{file_path}' does not exist."

            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            start = max(1, start_line) if start_line else 1
            end = min(total_lines, end_line) if end_line else total_lines

            if start > total_lines:
                return f"Error: start_line {start} exceeds total lines ({total_lines})."

            selected = lines[start - 1 : end]
            numbered = [f"{i + start:4d} | {line}" for i, line in enumerate(selected)]
            return f"--- {file_path} (lines {start}-{end} of {total_lines}) ---\n" + "".join(numbered)
        except Exception as e:
            return f"Error reading file '{file_path}': {e}"

    def search_code(self, query: str, max_results: int = 15) -> str:
        """Search repository for a keyword or regex pattern."""
        matches = []
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error as e:
            return f"Error in search pattern: {e}"

        for root, dirs, files in os.walk(self.repo_dir):
            # Ignore git, venvs, and caches
            dirs[:] = [d for d in dirs if d not in {".git", ".venv", "__pycache__", ".pytest_cache"}]
            for file in files:
                if not file.endswith((".py", ".json", ".yaml", ".yml", ".md", ".toml")):
                    continue
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.repo_dir).as_posix()
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        for line_num, line in enumerate(f, start=1):
                            if pattern.search(line):
                                matches.append(f"{rel_path}:{line_num}: {line.strip()}")
                                if len(matches) >= max_results:
                                    return f"Found {len(matches)} matches (limit reached):\n" + "\n".join(matches)
                except Exception:
                    continue

        if not matches:
            return f"No matches found for '{query}'."
        return f"Found {len(matches)} match(es):\n" + "\n".join(matches)

    def get_diff(self) -> str:
        """Retrieve the PR diff being reviewed."""
        if not self.pr_diff:
            return "No PR diff available."
        return self.pr_diff

    def find_references(self, symbol: str) -> str:
        """Find definitions and references of a symbol across Python files."""
        results = []
        for root, dirs, files in os.walk(self.repo_dir):
            dirs[:] = [d for d in dirs if d not in {".git", ".venv", "__pycache__", ".pytest_cache"}]
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.repo_dir).as_posix()
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        code = f.read()
                    tree = ast.parse(code, filename=rel_path)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            if node.name == symbol:
                                results.append(f"[DEF] {rel_path}:{node.lineno} -> {type(node).__name__} '{symbol}'")
                        elif isinstance(node, ast.Name) and node.id == symbol:
                            results.append(f"[REF] {rel_path}:{node.lineno} -> identifier '{symbol}'")
                except Exception:
                    continue

        if not results:
            return f"No symbol references found for '{symbol}'."
        # Limit to 20 lines to keep token usage bounded
        return f"Found {len(results)} reference(s):\n" + "\n".join(results[:20])

    def execute_tool(self, name: str, args: dict[str, Any]) -> str:
        """Dispatch tool call by name."""
        if name == "read_file":
            return self.read_file(
                file_path=args.get("file_path", ""),
                start_line=args.get("start_line"),
                end_line=args.get("end_line"),
            )
        elif name == "search_code":
            return self.search_code(
                query=args.get("query", ""),
                max_results=args.get("max_results", 15),
            )
        elif name == "get_diff":
            return self.get_diff()
        elif name == "find_references":
            return self.find_references(symbol=args.get("symbol", ""))
        else:
            return f"Unknown tool: '{name}'"


# Claude tool definitions schema
AGENT_TOOLS_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read contents of a file in the repository. Optionally specify line ranges to read specific sections.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Relative path to file"},
                "start_line": {"type": "integer", "description": "Start line (1-indexed)"},
                "end_line": {"type": "integer", "description": "End line (1-indexed)"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "search_code",
        "description": "Search for code patterns, function definitions, or usages across the codebase.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Regex or keyword to search for"},
                "max_results": {"type": "integer", "description": "Maximum number of results (default 15)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_diff",
        "description": "Retrieve the full PR git diff to inspect additions, deletions, and context.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "find_references",
        "description": "Find AST definitions and references of a symbol (function, class, variable) across Python files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Name of the symbol to locate"},
            },
            "required": ["symbol"],
        },
    },
]