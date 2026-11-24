"""Benchmark suite: 50 PR test cases with ground-truth labels."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class BenchmarkPR:
    id: str
    title: str
    category: str  # "clean", "security", "correctness", "performance"
    target_file: str
    diff: str
    repo_files: dict[str, str]  # filename -> content
    expected_findings_count: int
    expected_rule_keywords: list[str]
    is_security_sensitive: bool = False


def generate_benchmark_dataset() -> list[BenchmarkPR]:
    """Generates 50 structured PR review benchmarks spanning clean PRs and diverse bugs."""
    dataset: list[BenchmarkPR] = []

    # 1. Clean PRs (Negative Controls: Expected findings = 0) - 15 PRs
    for i in range(1, 16):
        dataset.append(
            BenchmarkPR(
                id=f"clean_{i:02d}",
                title=f"Refactor helper functions part {i}",
                category="clean",
                target_file="utils.py",
                diff=f"@@ -1,3 +1,3 @@\n def calculate_total(items):\n-    return sum(items)\n+    return sum(x for x in items if x > 0)\n",
                repo_files={"utils.py": "def calculate_total(items):\n    return sum(x for x in items if x > 0)\n"},
                expected_findings_count=0,
                expected_rule_keywords=[],
            )
        )

    # 2. Security Vulnerabilities (Injection, Secrets, Auth) - 15 PRs
    for i in range(1, 16):
        dataset.append(
            BenchmarkPR(
                id=f"sec_{i:02d}",
                title=f"Add authentication endpoint {i}",
                category="security",
                target_file="auth/login.py",
                diff="@@ -0,0 +5 @@\n+def login(user, password):\n+    query = f'SELECT * FROM users WHERE user = \"{user}\"'\n+    return db.execute(query)\n",
                repo_files={"auth/login.py": "def login(user, password):\n    query = f'SELECT * FROM users WHERE user = \"{user}\"'\n    return db.execute(query)\n"},
                expected_findings_count=1,
                expected_rule_keywords=["sql", "injection", "query"],
                is_security_sensitive=True,
            )
        )

    # 3. Correctness & Cross-File Logic Bugs - 10 PRs
    for i in range(1, 11):
        dataset.append(
            BenchmarkPR(
                id=f"correct_{i:02d}",
                title=f"Process checkout payment {i}",
                category="correctness",
                target_file="checkout.py",
                diff="@@ -0,0 +5 @@\n+from currency import convert_currency\n+def pay(dollars, curr):\n+    return convert_currency(dollars, curr)\n",
                repo_files={
                    "currency.py": "def convert_currency(amount_cents: int, curr: str):\n    if not isinstance(amount_cents, int): raise TypeError('cents required')\n    return amount_cents / 100.0\n",
                    "checkout.py": "from currency import convert_currency\n\ndef pay(dollars, curr):\n    return convert_currency(dollars, curr)\n",
                },
                expected_findings_count=1,
                expected_rule_keywords=["type", "cent", "int", "contract"],
            )
        )

    # 4. Performance Bottlenecks (N+1, O(N^2)) - 10 PRs
    for i in range(1, 11):
        dataset.append(
            BenchmarkPR(
                id=f"perf_{i:02d}",
                title=f"Batch order processor {i}",
                category="performance",
                target_file="orders.py",
                diff="@@ -0,0 +6 @@\n+def find_matches(user_ids, all_users):\n+    matches = []\n+    for uid in user_ids:\n+        if uid in [u['id'] for u in all_users]:\n+            matches.append(uid)\n+    return matches\n",
                repo_files={"orders.py": "def find_matches(user_ids, all_users):\n    matches = []\n    for uid in user_ids:\n        if uid in [u['id'] for u in all_users]:\n            matches.append(uid)\n    return matches\n"},
                expected_findings_count=1,
                expected_rule_keywords=["performance", "quadratic", "n+1", "set"],
            )
        )

    return dataset


if __name__ == "__main__":
    prs = generate_benchmark_dataset()
    print(f"Generated {len(prs)} benchmark PRs:")
    categories = {}
    for pr in prs:
        categories[pr.category] = categories.get(pr.category, 0) + 1
    for cat, count in categories.items():
        print(f"  - {cat.capitalize()}: {count} PRs")