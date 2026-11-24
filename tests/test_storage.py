"""Tests for SQLite audit storage and comment idempotency."""

import tempfile
from pathlib import Path
from src.schemas import Finding
from src.storage import AuditStorage


def test_idempotency_prevents_duplicate_records():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_audit.db")
        storage = AuditStorage(db_path=db_path)

        finding = Finding(
            tool="bandit",
            rule_id="B105",
            category="security",
            severity="critical",
            message="Hardcoded password",
            file_path="app.py",
            line_number=3,
        )

        repo = "Manyasrivastava01/test-repo"
        pr = 1
        sha = "abc1234"

        # 1. First record should succeed
        assert storage.is_already_posted(repo, pr, finding.fingerprint) is False
        first_insert = storage.record_posted_finding(repo, pr, sha, finding)
        assert first_insert is True

        # 2. Check should now show already posted
        assert storage.is_already_posted(repo, pr, finding.fingerprint) is True

        # 3. Re-push attempt with same finding must return False (idempotent rejection)
        second_insert = storage.record_posted_finding(repo, pr, "sha_after_repush", finding)
        assert second_insert is False