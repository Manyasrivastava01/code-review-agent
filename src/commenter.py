"""GitHub Pull Request Commenter for posting summary and inline review comments."""

import argparse
import os
import sys
from dotenv import load_dotenv
from github import Github, Auth
from github.GithubException import GithubException


def post_summary_comment(pr, body: str):
    """Post a top-level summary comment on the PR conversation timeline."""
    print("Posting PR summary comment...")
    comment = pr.create_issue_comment(body)
    print(f"Summary comment posted! (ID: {comment.id})")
    return comment


def post_inline_comment(pr, repo, path: str, line: int, body: str):
    """Post an inline review comment on a specific line of a changed file.
    
    Note on GitHub diff line mapping:
    - commit: must be the latest commit (head.sha) of the PR.
    - line: line number in the new version of the file (side='RIGHT').
    - The target line must be part of the diff hunk, otherwise GitHub rejects
      with 422 Unprocessable Entity.
    """
    print(f"Posting inline review comment on {path}:{line}...")
    commit = repo.get_commit(pr.head.sha)
    comment = pr.create_review_comment(
        body=body,
        commit=commit,
        path=path,
        line=line,
        side="RIGHT",
    )
    print(f"Inline comment posted! (ID: {comment.id})")
    return comment


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

    auth = Auth.Token(token)
    g = Github(auth=auth)

    try:
        repo = g.get_repo(args.repo)
        pr = repo.get_pull(args.pr)

        # 1. Post top-level summary comment
        summary_body = (
            "### 🤖 Autonomous Code Review Agent — Summary\n\n"
            f"- **Target**: PR #{pr.number} (`{pr.title}`)\n"
            f"- **Head Commit**: `{pr.head.sha[:7]}`\n"
            "- **Status**: Preliminary automated check completed.\n"
            "- **Findings**: 1 potential security concern flagged below.\n"
        )
        post_summary_comment(pr, summary_body)

        # 2. Post inline review comment on line 3 of app.py
        inline_body = (
            "> [!CAUTION]\n"
            "> **CWE-798: Use of Hard-coded Credentials**\n"
            "> \n"
            "> Plain-text password `\"secret123\"` found in authentication check.\n"
            "> Use environment variables or a secret vault instead."
        )
        post_inline_comment(
            pr=pr,
            repo=repo,
            path="app.py",
            line=3,
            body=inline_body,
        )

        print("\nAll comments successfully posted! Check the PR on GitHub.")

    except GithubException as e:
        print(f"\nGitHub API Error: {e.status} {e.data}", file=sys.stderr)
        sys.exit(1)
    finally:
        g.close()


if __name__ == "__main__":
    main()
