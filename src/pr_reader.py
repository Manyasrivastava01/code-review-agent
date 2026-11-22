"""GitHub Pull Request fetcher using PyGithub."""

import argparse
import os
import sys
from dotenv import load_dotenv
from github import Github, Auth


def fetch_pull_request(repo_name: str, pr_number: int, token: str):
    """Fetch and print PR details, head SHA, and file diffs."""
    auth = Auth.Token(token)
    g = Github(auth=auth)

    print(f"Connecting to repository: {repo_name}...")
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    print("\n" + "=" * 60)
    print(f"PR #{pr.number}: {pr.title}")
    print(f"State: {pr.state} | Author: {pr.user.login}")
    print(f"Base SHA ({pr.base.ref}): {pr.base.sha}")
    print(f"Head SHA ({pr.head.ref}): {pr.head.sha}")
    print("=" * 60)

    files = pr.get_files()
    file_count = files.totalCount
    print(f"\nChanged files count: {file_count}\n")

    for idx, file in enumerate(files, start=1):
        print(f"[{idx}/{file_count}] File: {file.filename} ({file.status})")
        print(f"      + {file.additions} lines / - {file.deletions} lines (changes: {file.changes})")
        print("-" * 60)
        if file.patch:
            print(file.patch)
        else:
            print("      (No patch available - binary file or no line changes)")
        print("-" * 60 + "\n")

    g.close()


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Fetch PR diff and metadata from GitHub.")
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
        print("Create a Personal Access Token on GitHub and set it in your .env file or environment.", file=sys.stderr)
        sys.exit(1)

    fetch_pull_request(repo_name=args.repo, pr_number=args.pr, token=token)


if __name__ == "__main__":
    main()
