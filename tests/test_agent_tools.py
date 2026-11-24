"""Tests for agent exploration tools."""

import tempfile
from pathlib import Path
from src.agent.tools import CodebaseTools


def test_codebase_tools():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a sample file
        test_file = Path(tmpdir) / "auth.py"
        test_file.write_text("def login(user, token):\n    return True\n", encoding="utf-8")

        tools = CodebaseTools(repo_dir=tmpdir, pr_diff="@@ -0,0 +1 @@\n+test")

        # 1. Test read_file
        content = tools.read_file("auth.py")
        assert "def login" in content

        # 2. Test search_code
        matches = tools.search_code("login")
        assert "auth.py:1: def login" in matches

        # 3. Test find_references
        refs = tools.find_references("login")
        assert "[DEF] auth.py:1 -> FunctionDef 'login'" in refs

        # 4. Test directory traversal protection
        safe_check = tools.read_file("../../secret.txt")
        assert "Access denied" in safe_check or "does not exist" in safe_check