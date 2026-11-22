"""End-to-end automated reviewer combining deterministic tools and diff filtering."""

import argparse
import os
import sys
import tempfile
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from github import Github, Auth
from github.GithubException import GithubException

from src.schemas import Finding
from src.diff_filter import parse_diff_added_lines, filter_findings_by_diff
from src.analyzers.runner import run_all_analyzers


def run_pr_review(repo_name: str, pr_number: int, token: str):
    """Run full deterministic review on a Pull Request."""
    auth = Auth.Token(token)
    g = Github(auth=auth)

    try:
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        commit = repo.get_commit(pr.head.sha)

        print(f"\n==================================================")
        print(f"Reviewing PR #{pr.number}: {pr.title}")
        print(f"Repo: {repo_name} | Head SHA: {pr.head.sha[:7]}")
        print(f"==================================================\n")

        # 1. Inspect changed files & diff hunks
        pr_files = list(pr.get_files())
        changed_lines_by_file: dict[str, set[int]] = {}
        files_to_scan: list[str] = []

        # We create a working directory for files if not already on disk
        with tempfile.TemporaryDirectory() as temp_dir:
            for file in pr_files:
                if file.status == "removed":
                    continue

                norm_path = file.filename.replace("\\", "/")
                added_lines = parse_diff_added_lines(file.patch or "")
                changed_lines_by_file[norm_path] = added_lines

                # If the file exists in current checkout (e.g. In CI), use it directly
                if os.path.exists(file.filename):
                    files_to_scan.append(file.filename)
                else:
                    # Download file content at pr.head.sha for local evaluation
                    try:
                        content_file = repo.get_contents(file.filename, ref=pr.head.sha)
                        local_path = os.path.join(temp_dir, file.filename)
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        with open(local_path, "wb") as f:
                            f.write(content_file.decoded_content)
                        files_to_scan.append(local_path)
                    except Exception as e:
                        print(f"Notice: Could not fetch content for {file.filename}: {e}")

            if not files_to_scan:
                print("No files eligible for scanning.")
                return

            print(f"Scanning {len(files_to_scan)} file(s) with deterministic analyzers...")
            raw_findings = run_all_analyzers(files_to_scan)

            # Map temp paths back to repository relative paths
            normalized_findings: list[Finding] = []
            resolved_temp = Path(temp_dir).resolve()
            for f in raw_findings:
                f_path = Path(f.file_path).resolve()
                try:
                    rel_to_temp = f_path.relative_to(resolved_temp)
                    path = str(rel_to_temp).replace("\\", "/")
                except ValueError:
                    try:
                        rel_to_cwd = f_path.relative_to(Path.cwd().resolve())
                        path = str(rel_to_cwd).replace("\\", "/")
                    except ValueError:
                        path = f.file_path.replace("\\", "/")

                f.file_path = path.lstrip("./")
                normalized_findings.append(f)

        print(f"\nTotal raw findings from all tools: {len(normalized_findings)}")

        # 2. Filter findings strictly to lines touched by PR diff
        actionable_findings = filter_findings_by_diff(normalized_findings, changed_lines_by_file)
        print(f"Actionable findings on changed lines: {len(actionable_findings)}")

        # 3. Post summary comment
        tool_counts: dict[str, int] = {}
        for f in actionable_findings:
            tool_counts[f.tool] = tool_counts.get(f.tool, 0) + 1

        breakdown = ", ".join(f"{tool}: {count}" for tool, count in tool_counts.items()) or "None"
        summary_text = (
            "### 🤖 Deterministic Code Review Report\n\n"
            f"- **Commit**: `{pr.head.sha[:7]}`\n"
            f"- **Files Scanned**: {len(files_to_scan)}\n"
            f"- **Actionable Findings**: {len(actionable_findings)} ({breakdown})\n\n"
        )
        if not actionable_findings:
            summary_text += "✅ **No issues detected on the changed lines!**"
        else:
            summary_text += "⚠️ **Issues detected on modified lines. See inline comments below.**"

        pr.create_issue_comment(summary_text)
        print("Summary comment posted to PR.")

        # 4. Post inline review comments
        for finding in actionable_findings:
            try:
                print(f"Posting inline comment: [{finding.tool.upper()}] {finding.rule_id} on {finding.file_path}:{finding.line_number}")
                pr.create_review_comment(
                    body=finding.to_markdown(),
                    commit=commit,
                    path=finding.file_path,
                    line=finding.line_number,
                    side="RIGHT",
                )
            except GithubException as ge:
                # e.g., if line comment already exists or line isn't commentable
                print(f"  Note: Failed to post inline comment ({ge.data.get('message', str(ge))})")

        print("\nReview run completed successfully!")

    finally:
        g.close()


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run deterministic analyzers and review a PR.")
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
