"""End-to-end automated reviewer combining deterministic tools, parallel specialists, critic, policy, and idempotency."""

import argparse
import asyncio
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
from src.agent.specialists import run_specialists_parallel
from src.agent.critic import CriticAgent
from src.deduplication import deduplicate_findings
from src.policy import load_policy, evaluate_policy
from src.storage import AuditStorage


def run_pr_review(repo_name: str, pr_number: int, token: str):
    """Run complete Phase D multi-agent review on a Pull Request."""
    auth = Auth.Token(token)
    g = Github(auth=auth)
    storage = AuditStorage()
    policy = load_policy()

    try:
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        commit = repo.get_commit(pr.head.sha)

        print(f"\n==================================================")
        print(f"Reviewing PR #{pr.number}: {pr.title}")
        print(f"Repo: {repo_name} | Head SHA: {pr.head.sha[:7]}")
        print(f"Policy: '{policy.policy_name}'")
        print(f"==================================================\n")

        # 1. Inspect changed files & diff hunks
        pr_files = list(pr.get_files())
        changed_lines_by_file: dict[str, set[int]] = {}
        files_to_scan: list[str] = []
        combined_diff_by_file: dict[str, str] = {}

        all_findings: list[Finding] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            resolved_temp = Path(temp_dir).resolve()
            for file in pr_files:
                if file.status == "removed":
                    continue

                norm_path = file.filename.replace("\\", "/")
                patch = file.patch or ""
                added_lines = parse_diff_added_lines(patch)
                changed_lines_by_file[norm_path] = added_lines
                combined_diff_by_file[norm_path] = patch

                # Fetch or use local file content
                if os.path.exists(file.filename):
                    files_to_scan.append(file.filename)
                else:
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

            # Stage 1: Deterministic Analyzers (Bandit, Ruff, Semgrep)
            print(f"\n[Stage 1] Scanning {len(files_to_scan)} file(s) with deterministic analyzers...")
            raw_deterministic = run_all_analyzers(files_to_scan)

            for f in raw_deterministic:
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
                all_findings.append(f)

            # Stage 2: Specialist Agents (Security, Correctness, Performance) in Parallel
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key and not api_key.startswith("your_"):
                print(f"\n[Stage 2] Running 3 Specialist Agents in parallel on changed files...")
                for norm_path, patch in combined_diff_by_file.items():
                    if not patch:
                        continue
                    try:
                        specialist_results = asyncio.run(
                            run_specialists_parallel(
                                repo_dir=str(resolved_temp) if os.path.exists(temp_dir) else ".",
                                pr_diff=patch,
                                target_file=norm_path,
                            )
                        )
                        for sf in specialist_results:
                            sf.file_path = norm_path
                            all_findings.append(sf)
                    except Exception as err:
                        print(f"Notice: Specialist agent run skipped ({err})")
            else:
                print(f"\n[Stage 2] Skipping live LLM specialists (ANTHROPIC_API_KEY not configured).")

        # Stage 3: Filter strictly to lines touched by PR diff
        print(f"\n[Stage 3] Filtering findings to lines touched by PR diff...")
        diff_findings = filter_findings_by_diff(all_findings, changed_lines_by_file)
        print(f"  -> Retained {len(diff_findings)} finding(s) on active diff lines")

        # Stage 4: Deduplicate overlapping findings
        print(f"\n[Stage 4] Deduplicating findings across tools & agents...")
        deduped_findings = deduplicate_findings(diff_findings)
        print(f"  -> {len(deduped_findings)} unique finding(s) after deduplication")

        # Stage 5: Critic Agent (False-Positive Filter)
        if api_key and not api_key.startswith("your_") and deduped_findings:
            print(f"\n[Stage 5] Critic Agent evaluating findings for false positives...")
            try:
                critic = CriticAgent()
                accepted_findings, rejected_findings = critic.filter_findings(
                    findings=deduped_findings,
                    pr_diff="\n\n".join(combined_diff_by_file.values()),
                )
                print(f"  -> Critic accepted {len(accepted_findings)}, rejected {len(rejected_findings)} false positive(s)")
            except Exception as err:
                print(f"Notice: Critic filtering skipped ({err}). Retaining deduplicated findings.")
                accepted_findings = deduped_findings
        else:
            accepted_findings = deduped_findings

        # Stage 6: Policy Engine & Merge Status Check
        print(f"\n[Stage 6] Evaluating policy gates...")
        decision = evaluate_policy(accepted_findings, policy)
        print(f"  -> Policy Decision: {'PASSED' if decision.passed else 'BLOCKED'}")
        for reason in decision.reasons:
            print(f"     * {reason}")

        # Post GitHub commit status check (blocks or clears merge button)
        try:
            status_state = "success" if decision.passed else "failure"
            status_desc = decision.summary[:135]
            commit.create_status(
                state=status_state,
                context=policy.status_check_context,
                description=status_desc,
            )
            print(f"GitHub Status Check set to: {status_state.upper()} ({policy.status_check_context})")
        except GithubException as ge:
            print(f"Notice: Could not post commit status check: {ge}")

        # Stage 7: Idempotent Inline Review Comments
        print(f"\n[Stage 7] Posting inline review comments (with idempotency check)...")
        posted_count = 0
        skipped_count = 0

        for finding in accepted_findings:
            if storage.is_already_posted(repo_name, pr.number, finding.fingerprint):
                print(f"  -> [SKIP] Already posted: {finding.rule_id} on {finding.file_path}:{finding.line_number}")
                skipped_count += 1
                continue

            try:
                print(f"  -> [POST] [{finding.tool.upper()}] {finding.rule_id} on {finding.file_path}:{finding.line_number}")
                pr.create_review_comment(
                    body=finding.to_markdown(),
                    commit=commit,
                    path=finding.file_path,
                    line=finding.line_number,
                    side="RIGHT",
                )
                storage.record_posted_finding(repo_name, pr.number, pr.head.sha, finding)
                posted_count += 1
            except GithubException as ge:
                print(f"  Note: Failed to post inline comment ({ge.data.get('message', str(ge))})")

        # Stage 8: Post PR Summary Comment
        storage.record_review_run(
            repo_name=repo_name,
            pr_number=pr.number,
            commit_sha=pr.head.sha,
            policy_passed=decision.passed,
            total_findings=len(accepted_findings),
        )

        status_badge = "✅ **PASS: Clear to Merge**" if decision.passed else "❌ **BLOCKED: Policy Violations**"
        summary_body = (
            f"### 🤖 Autonomous Code Review Agent — Summary Report\n\n"
            f"- **Commit**: `{pr.head.sha[:7]}`\n"
            f"- **Policy Gate**: {status_badge}\n"
            f"- **Findings**: {len(accepted_findings)} actionable (New: {posted_count}, Skipped Duplicates: {skipped_count})\n"
            f"- **Policy Summary**: {decision.summary}\n\n"
        )
        if decision.reasons:
            summary_body += "**Blocking Violations:**\n"
            for r in decision.reasons:
                summary_body += f"- {r}\n"

        pr.create_issue_comment(summary_body)
        print("Summary comment posted to PR.")
        print("\nAll review stages completed successfully!")

    finally:
        g.close()


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run complete code review agent on a PR.")
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
