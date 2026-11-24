"""Deduplication engine for merging overlapping findings across tools and specialists."""

from typing import Sequence
from src.schemas import Finding, SeverityLevel, ConfidenceLevel

SEVERITY_ORDER: dict[SeverityLevel, int] = {
    "info": 1,
    "warning": 2,
    "error": 3,
    "critical": 4,
}

CONFIDENCE_ORDER: dict[ConfidenceLevel, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


def deduplicate_findings(findings: Sequence[Finding]) -> list[Finding]:
    """Merge duplicate and overlapping findings on the same file and line.
    
    If multiple tools/agents flag the same line for similar issues, merge them:
    - Pick highest severity and confidence.
    - Combine tool credits (e.g. 'bandit + specialist-security').
    - Keep suggested fix if present.
    """
    if not findings:
        return []

    # Group findings by (file_path, line_number)
    grouped: dict[tuple[str, int], list[Finding]] = {}
    for f in findings:
        key = (f.file_path, f.line_number)
        grouped.setdefault(key, []).append(f)

    deduped: list[Finding] = []

    for (file_path, line_number), cluster in grouped.items():
        if len(cluster) == 1:
            deduped.append(cluster[0])
            continue

        # Sort cluster by severity (highest first), then confidence
        cluster.sort(
            key=lambda x: (
                SEVERITY_ORDER.get(x.severity, 1),
                CONFIDENCE_ORDER.get(x.confidence or "medium", 2),
            ),
            reverse=True,
        )

        primary = cluster[0]

        # Combine all unique tools that spotted this
        contributing_tools = list(dict.fromkeys(f.tool for f in cluster))
        combined_tools = " + ".join(contributing_tools)

        # Grab best suggested fix from cluster
        best_fix = next((f.suggested_fix for f in cluster if f.suggested_fix), primary.suggested_fix)

        merged = Finding(
            tool=combined_tools,
            rule_id=primary.rule_id,
            category=primary.category,
            severity=primary.severity,
            confidence=primary.confidence,
            message=primary.message,
            file_path=file_path,
            line_number=line_number,
            end_line_number=primary.end_line_number,
            column=primary.column,
            code_snippet=primary.code_snippet,
            url=primary.url,
            suggested_fix=best_fix,
        )
        deduped.append(merged)

    # Sort final findings by file and line number
    deduped.sort(key=lambda x: (x.file_path, x.line_number))
    return deduped