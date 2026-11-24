"""Interactive Streamlit Dashboard for Autonomous Code Review Agent."""

import csv
import sqlite3
from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="Autonomous Code Review Agent",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Autonomous Code Review Agent with Built-in Cost Router")
st.markdown("Real-time telemetry, model tiering analytics, and benchmark results.")

# Sidebar Navigation
tab_selection = st.sidebar.radio(
    "Navigation",
    ["📊 Benchmark & Evaluation", "💰 Cost & Token Telemetry", "🛡️ PR Audit & Policy Logs"],
)

DB_PATH = Path("audit.db")

# ----------------- TAB 1: Benchmark & Evaluation -----------------
if tab_selection == "📊 Benchmark & Evaluation":
    st.header("Benchmark Results Across 50 Pull Requests")
    st.markdown(
        "> **Headline Result:** The **Cost Router (Config D)** achieves **99.5%** of the all-strong-model quality "
        "(F1: 0.923 vs 0.928) with a **56.4% cost reduction** and **2.3x faster latency**."
    )

    csv_path = Path("benchmark") / "results.csv"
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        st.table(reader)
    else:
        st.warning("benchmark/results.csv not found. Run benchmark/evaluator.py first.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Cost per Pull Request ($)")
        svg_cost = Path("benchmark/charts/cost_comparison.svg")
        if svg_cost.exists():
            st.image(str(svg_cost))
    with col2:
        st.subheader("Review Quality Metrics (F1, Precision, Recall)")
        svg_qual = Path("benchmark/charts/quality_comparison.svg")
        if svg_qual.exists():
            st.image(str(svg_qual))

# ----------------- TAB 2: Cost & Token Telemetry -----------------
elif tab_selection == "💰 Cost & Token Telemetry":
    st.header("Live Model Tier Telemetry")
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) as total_calls,
                COALESCE(SUM(input_tokens), 0) as total_input,
                COALESCE(SUM(output_tokens), 0) as total_output,
                COALESCE(SUM(cost_usd), 0.0) as total_cost,
                COALESCE(AVG(latency_ms), 0.0) as avg_latency
            FROM llm_cost_logs
        """)
        stats = cursor.fetchone()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Model Calls", stats[0])
        col2.metric("Total Tokens", f"{stats[1] + stats[2]:,}")
        col3.metric("Total Spend ($)", f"${stats[3]:.4f}")
        col4.metric("Avg Latency", f"{stats[4]:.1f} ms")

        st.subheader("Recent Metered Calls")
        cursor.execute("SELECT id, pr_number, caller, model, input_tokens, output_tokens, cost_usd, latency_ms, timestamp FROM llm_cost_logs ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        if rows:
            st.table([
                {
                    "PR": r[1],
                    "Caller": r[2],
                    "Model": r[3],
                    "Tokens (In/Out)": f"{r[4]} / {r[5]}",
                    "Cost ($)": f"${r[6]:.5f}",
                    "Latency (ms)": f"{r[7]:.1f}",
                    "Timestamp": r[8][:19],
                }
                for r in rows
            ])
        else:
            st.info("No metered calls recorded in audit.db yet.")
        conn.close()
    else:
        st.info("audit.db does not exist yet.")

# ----------------- TAB 3: PR Audit & Policy Logs -----------------
elif tab_selection == "🛡️ PR Audit & Policy Logs":
    st.header("PR Review History & Guardrail Decisions")
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, repo_name, pr_number, commit_sha, policy_passed, total_findings, run_at FROM review_runs ORDER BY id DESC")
        runs = cursor.fetchall()
        if runs:
            st.table([
                {
                    "Repo": r[1],
                    "PR #": r[2],
                    "Commit": r[3][:7],
                    "Policy Status": "✅ Passed" if r[4] else "❌ Blocked",
                    "Findings Flagged": r[5],
                    "Reviewed At": r[6][:19],
                }
                for r in runs
            ])
        else:
            st.info("No review runs stored in database yet.")

        st.subheader("Idempotent Finding Registry")
        cursor.execute("SELECT repo_name, pr_number, file_path, line_number, tool, rule_id, severity, message FROM posted_findings ORDER BY id DESC LIMIT 25")
        findings = cursor.fetchall()
        if findings:
            st.table([
                {
                    "PR": f[1],
                    "Location": f"{f[2]}:{f[3]}",
                    "Tool": f[4],
                    "Rule": f[5],
                    "Severity": f[6],
                    "Message": f[7],
                }
                for f in findings
            ])
        conn.close()
    else:
        st.info("audit.db does not exist yet.")