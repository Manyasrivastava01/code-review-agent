"""Tests for Content-Hash caching mechanism."""

import tempfile
from pathlib import Path
from src.schemas import Finding
from src.router.cache import ReviewCache


def test_cache_miss_then_hit():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_cache.db")
        cache = ReviewCache(db_path=db_path)

        file_content = "def add(a, b): return a + b"
        diff = "@@ -0,0 +1 @@\n+def add(a, b): return a + b"
        model = "claude-3-5-haiku-20241022"

        chash = cache.compute_hash(file_content, diff, model)

        # 1. Initially must be a Cache MISS
        assert cache.get(chash) is None

        sample_findings = [
            Finding(
                tool="llm-haiku",
                rule_id="TYPE_HINT",
                category="style",
                severity="info",
                message="Missing type hints",
                file_path="math.py",
                line_number=1,
            )
        ]

        # 2. Store in cache
        cache.set(chash, "math.py", model, sample_findings)

        # 3. Subsequent check must be a Cache HIT
        cached_result = cache.get(chash)
        assert cached_result is not None
        assert len(cached_result) == 1
        assert cached_result[0].rule_id == "TYPE_HINT"
        assert cached_result[0].message == "Missing type hints"