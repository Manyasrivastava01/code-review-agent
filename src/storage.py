"""SQLite storage for review audit logs, idempotency tracking, and cost logging."""

import contextlib
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from src.schemas import Finding

DEFAULT_DB_PATH = "audit.db"


class AuditStorage:
    """Manages SQLite database for audit trails and comment idempotency."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextlib.contextmanager
    def _get_connection(self):
        """Context manager that guarantees connection is closed after use."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Create necessary tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Posted findings table for idempotency
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posted_findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_name TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    commit_sha TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    tool TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    posted_at TEXT NOT NULL,
                    UNIQUE(repo_name, pr_number, fingerprint)
                )
            """)

            # 2. PR Review runs audit log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_name TEXT NOT NULL,
                    pr_number INTEGER NOT NULL,
                    commit_sha TEXT NOT NULL,
                    policy_passed INTEGER NOT NULL,
                    total_findings INTEGER NOT NULL,
                    run_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def is_already_posted(self, repo_name: str, pr_number: int, fingerprint: str) -> bool:
        """Check if a finding with this fingerprint was already posted on this PR."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM posted_findings
                WHERE repo_name = ? AND pr_number = ? AND fingerprint = ?
            """, (repo_name, pr_number, fingerprint))
            return cursor.fetchone() is not None

    def record_posted_finding(
        self,
        repo_name: str,
        pr_number: int,
        commit_sha: str,
        finding: Finding,
    ) -> bool:
        """Record a posted finding in SQLite. Returns True if recorded, False if already exists."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now(timezone.utc).isoformat()
                cursor.execute("""
                    INSERT INTO posted_findings (
                        repo_name, pr_number, commit_sha, fingerprint,
                        file_path, line_number, tool, rule_id, severity, message, posted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    repo_name,
                    pr_number,
                    commit_sha,
                    finding.fingerprint,
                    finding.file_path,
                    finding.line_number,
                    finding.tool,
                    finding.rule_id,
                    finding.severity,
                    finding.message,
                    now,
                ))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            # Already posted (violates UNIQUE constraint)
            return False

    def record_review_run(
        self,
        repo_name: str,
        pr_number: int,
        commit_sha: str,
        policy_passed: bool,
        total_findings: int,
    ):
        """Record metadata about a completed review run."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                INSERT INTO review_runs (
                    repo_name, pr_number, commit_sha, policy_passed, total_findings, run_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (repo_name, pr_number, commit_sha, 1 if policy_passed else 0, total_findings, now))
            conn.commit()