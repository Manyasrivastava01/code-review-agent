"""GitHub Pull Request Commenter entrypoint.

Invokes the full deterministic review pipeline (Ruff, Bandit, Semgrep)
and posts summary and inline comments.
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from src.run_review import run_pr_review


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Post review comments to a GitHub PR.")
    parser.add_argument(
        "--repo",
        type=str,
        default=os.getenv("GITHUB_REPOSITORY", "Manyasrivastava01/test-repo"),
        help="Repository in format owner/repo",
    )
    parser.add_argument(
        "--pr",
        type=int,
        default=int(os.getenv("PR_NUMBER", "1")),
        help="Pull request number",
    )
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    run_pr_review(repo_name=args.repo, pr_number=args.pr, token=token)


if __name__ == "__main__":
    main()
