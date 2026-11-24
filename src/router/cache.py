"""SQLite-backed Content-Hash Cache for skipping redundant LLM reviews."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from src.schemas import Finding

DEFAULT_CACHE_DB = "audit.db"


class ReviewCache:
    """Exact-match content-hash cache for PR review results."""

    def __init__(self, db_path: str = DEFAULT_CACHE_DB):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_cache (
                    content_hash TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    model TEXT NOT NULL,
                    findings_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def compute_hash(file_content: str, pr_diff: str, model: str) -> str:
        """Generate deterministic SHA-256 hash representing the exact code state reviewed."""
        payload = f"MODEL:{model}\nDIFF:{pr_diff}\nCONTENT:{file_content}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, content_hash: str) -> Optional[list[Finding]]:
        """Retrieve cached findings if an exact match exists."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT findings_json FROM review_cache WHERE content_hash = ?",
                (content_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            raw_list = json.loads(row[0])
            return [Finding(**item) for item in raw_list]
        finally:
            conn.close()

    def set(
        self,
        content_hash: str,
        file_path: str,
        model: str,
        findings: list[Finding],
    ):
        """Store review findings in cache keyed by content hash."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            findings_json = json.dumps([f.model_dump() for f in findings])
            now = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO review_cache (
                    content_hash, file_path, model, findings_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (content_hash, file_path, model, findings_json, now))
            conn.commit()
        finally:
            conn.close()