"""Extract changed lines from Git diffs and filter findings to modified lines only."""

import re
from typing import Mapping, Set, Sequence
from src.schemas import Finding


def parse_diff_added_lines(patch: str) -> set[int]:
    """Parse a unified git diff patch hunk and return the set of modified/added line numbers.

    A diff hunk starts with @@ -start,count +start,count @@.
    Lines starting with '+' (excluding '+++') are added/modified lines in the new file.
    Lines starting with ' ' (context) increment the new line counter.
    Lines starting with '-' only affect the old file.
    """
    added_lines: set[int] = set()
    if not patch:
        return added_lines

    current_new_line = 0
    hunk_header_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    for line in patch.splitlines():
        hunk_match = hunk_header_re.match(line)
        if hunk_match:
            current_new_line = int(hunk_match.group(1))
            continue

        if current_new_line == 0:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            added_lines.add(current_new_line)
            current_new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            # Deletion in old file; does not advance new line counter
            pass
        else:
            # Context line present in both
            current_new_line += 1

    return added_lines


def filter_findings_by_diff(
    findings: Sequence[Finding],
    changed_lines_by_file: Mapping[str, Set[int]],
) -> list[Finding]:
    """Retain only findings that touch lines actively changed or added in the PR diff."""
    filtered: list[Finding] = []

    for finding in findings:
        norm_path = finding.file_path.replace("\\", "/").lstrip("./")
        changed_lines = changed_lines_by_file.get(norm_path, set())

        # If the finding line is in the added/modified diff lines
        if finding.line_number in changed_lines:
            filtered.append(finding)
        else:
            print(
                f"Filtered out {finding.tool} finding ({finding.rule_id}) on {norm_path}:{finding.line_number} "
                f"(not in PR changed lines: {sorted(list(changed_lines))})"
            )

    return filtered
