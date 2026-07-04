"""Streamlit demo for StatusForge — an agentic roadmap digest for Slack.

Two tabs, one architecture:
  • n8n Workflow      — the shipped automation (pipeline, failure ladder, exported JSON)
  • LangGraph          — the agent core; renders graph.png and RUNS the real pipeline live

Run from the python/ folder:  streamlit run app.py
(Needs OPENAI_API_KEY in python/.env only for the live "Run the pipeline" button.)
"""
from __future__ import annotations

import csv
import json
import os
import urllib.request
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CSV_PATH = ROOT / "roadmap_airtable_export.csv"
GRAPH_PNG = HERE / "graph.png"

DET, LLM, IO, MUTED = "#2FBF9F", "#E9603F", "#4C6BEF", "#6b7280"

st.set_page_config(page_title="StatusForge", page_icon="⚒️", layout="wide")

# On Streamlit Cloud there is no .env — expose configured secrets as env vars so
# ChatOpenAI (which reads OPENAI_API_KEY) and the webhook defaults work.
try:
    for _k in ("OPENAI_API_KEY", "OPENAI_MODEL", "N8N_WEBHOOK_URL", "N8N_ERROR_WEBHOOK_URL"):
        if _k in st.secrets:
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass


def badge(text: str, color: str) -> str:
    return (f"<span style='background:{color}1a;border:1px solid {color};color:{color};"
            f"padding:2px 9px;border-radius:6px;font-size:12px;"
            f"font-family:ui-monospace,monospace'>{text}</span>")


def load_records() -> list[dict]:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def find_workflow_json() -> Path | None:
    """First workflow JSON that isn't the error handler — robust to renaming."""
    for folder in (ROOT / "workflows", ROOT):
        for p in sorted(folder.glob("*.json")):
            if "error handler" not in p.name.lower():
                return p
    return None


# ---------------------------------------------------------------- header
st.title("⚒️ StatusForge")
st.caption("Airtable → deterministic core → multi-agent LLM → Slack. "
           "Two implementations of one architecture.")
st.markdown(
    badge("Deterministic (code)", DET) + " &nbsp; "
    + badge("LLM reasoning", LLM) + " &nbsp; " + badge("External I/O", IO),
    unsafe_allow_html=True,
)
st.write("")

tab_n8n, tab_lg = st.tabs(["🔧  n8n Workflow", "🕸️  LangGraph Architecture"])

# ---------------------------------------------------------------- TAB 1: n8n
N8N_DOT = r'''
digraph G {
  rankdir=LR; bgcolor="transparent"; pad=0.2; nodesep=0.32; ranksep=0.5;
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10,
        color="#2b2b2b", penwidth=1.1, fontcolor="#14202b"];
  edge [color="#8791a6", fontname="Helvetica", fontsize=9, fontcolor="#9aa4b8", arrowsize=0.7];

  webhook  [label="Webhook",                    fillcolor="#cdd7ff"];
  sched    [label="Schedule Trigger",           fillcolor="#cdd7ff"];
  search   [label="Search records\n(Airtable)", fillcolor="#cdd7ff"];
  post     [label="Post Digest\n(Slack)",       fillcolor="#cdd7ff"];
  logadmin [label="Log to admin\n(Slack)",      fillcolor="#cdd7ff"];

  count    [label="Validate + Count",           fillcolor="#b6f0e2"];
  merge    [label="Merge",                      fillcolor="#b6f0e2"];
  ifsup    [label="Need another\nanalysis? (IF)", fillcolor="#b6f0e2"];
  vout     [label="Validate LLM Output",        fillcolor="#b6f0e2"];
  build    [label="Build Slack Blocks",         fillcolor="#b6f0e2"];
  ifhere   [label="High Count > 5 (IF)",        fillcolor="#b6f0e2"];
  prehere  [label="Prepend @here",              fillcolor="#b6f0e2"];

  prog     [label="Progress Agent",             fillcolor="#ffd3c7"];
  risk     [label="Risk Analysis Agent",        fillcolor="#ffd3c7"];
  sup      [label="Supervisor",                 fillcolor="#ffd3c7"];
  dep      [label="Dependency Agent",           fillcolor="#ffd3c7"];
  summ     [label="Summarize & Rank",           fillcolor="#ffd3c7"];

  sched -> search; webhook -> search; search -> count;
  count -> prog; count -> risk; prog -> merge; risk -> merge;
  merge -> sup; sup -> ifsup;
  ifsup -> dep [label="YES"]; ifsup -> summ [label="NO"]; dep -> summ;
  summ -> vout; vout -> build; build -> ifhere;
  ifhere -> prehere [label="true"]; ifhere -> post [label="false"];
  prehere -> post; post -> logadmin;
}
'''

ERR_DOT = r'''
digraph E {
  rankdir=LR; bgcolor="transparent"; pad=0.2; nodesep=0.35; ranksep=0.6;
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10,
        color="#2b2b2b", fontcolor="#14202b"];
  edge [color="#8791a6", fontname="Helvetica", fontsize=9, fontcolor="#9aa4b8", arrowsize=0.7];
  trig  [label="Error Trigger",               fillcolor="#cdd7ff"];
  slack [label="Slack alert\n(#digest-admin)", fillcolor="#cdd7ff"];
  gmail [label="Email fallback\n(Gmail)",     fillcolor="#cdd7ff"];
  trig -> slack;
  slack -> gmail [label="if Slack fails", style="dashed"];
}
'''

N8N_STAGES = [
    ("Schedule Trigger", IO, "Runs daily at 09:00 IST"),
    ("Search records · Airtable", IO, "Pulls all roadmap rows"),
    ("Validate + Count", DET, "Counts, staleness, the @here flag — the source of truth"),
    ("Progress Agent  ∥  Risk Analysis Agent", LLM, "Two specialists, run in parallel"),
    ("Merge", DET, "Waits for both, then continues"),
    ("Supervisor", LLM, "Fuzzy judgment: is a dependency analysis warranted? → YES / NO"),
    ("Need another analysis?  (IF)", DET, "Routes on the supervisor's word — no model here"),
    ("Dependency Agent", LLM, "Conditional — runs only on YES"),
    ("Summarize & Rank", LLM, "Folds every analysis into the digest JSON"),
    ("Validate LLM Output", DET, "Cross-checks item counts vs the deterministic counts; throws on mismatch"),
    ("Build Slack Blocks", DET, "Block Kit, Airtable deep-links, owner @-mentions"),
    ("High Count > 5?  (IF)", DET, "The @here decision, made from the computed count"),
    ("Prepend @here", DET, "Adds the literal <!here> token on the true branch"),
    ("Post Digest · Slack", IO, "One message to #roadmap-digest"),
    ("Log to admin · Slack", IO, "Success line to #digest-admin — the run audit log"),
]

LADDER = [
    ("Transient blip", "per-node retry, 3× with backoff"),
    ("Node fails hard", "error workflow → Slack alert to #digest-admin"),
    ("Slack itself down", "email fallback via Gmail"),
    ("Model breaks the schema", "validation throws → error workflow"),
]

with tab_n8n:
    st.subheader("Run the live workflow")
    st.caption("Fires the real n8n workflow via its webhook — it fetches Airtable, runs the "
               "agents, and posts the digest to #roadmap-digest. (Requires a Webhook Trigger "
               "in the workflow and the workflow published.)")
    webhook_url = st.text_input(
        "n8n webhook URL",
        value=os.getenv("N8N_WEBHOOK_URL", "https://samikshabatra.app.n8n.cloud/webhook/run-digest"),
    )
    if st.button("▶  Run the n8n workflow now", type="primary"):
        with st.spinner("Triggering n8n…"):
            try:
                req = urllib.request.Request(
                    webhook_url, data=b"{}", method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=120) as r:
                    body = r.read().decode()
                st.success("Triggered — the workflow is running. Check **#roadmap-digest** in Slack in a few seconds.")
                if body.strip():
                    with st.expander("Webhook response"):
                        st.code(body)
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not reach the webhook: {e}\n\nIs the Webhook Trigger added and the "
                         f"workflow published? URL: {webhook_url}")

    st.divider()
    st.subheader("The workflow")
    st.caption("The exact n8n flow — deterministic (teal), LLM (coral), I/O (blue). Drag to pan, scroll to zoom.")
    st.graphviz_chart(N8N_DOT, use_container_width=True)

    st.divider()
    st.subheader("The pipeline")
    st.caption("15 stages, colored by what each one is. Deterministic ends bracket the multi-agent middle.")
    for name, color, role in N8N_STAGES:
        st.markdown(
            f"<div style='margin:4px 0'>{badge(name, color)} "
            f"<span style='color:{MUTED};font-size:14px'>&nbsp; {role}</span></div>",
            unsafe_allow_html=True,
        )

    st.divider()
    st.subheader("Inspect a node")
    st.caption("Pick any node to see its real configuration — the exact code, prompt, or condition from the exported workflow.")
    wf = find_workflow_json()
    if wf:
        data = json.loads(wf.read_text(encoding="utf-8"))
        nodes = {n["name"]: n for n in data.get("nodes", [])}
        names = sorted(nodes, key=lambda k: nodes[k].get("position", [0, 0])[0])
        choice = st.selectbox("Node", names, label_visibility="collapsed")
        n = nodes[choice]
        st.markdown(f"**Type:** `{n.get('type', '')}`  ·  version `{n.get('typeVersion', '')}`")
        p = n.get("parameters", {})
        if "jsCode" in p:
            st.caption("Code node — the exact JavaScript it runs:")
            st.code(p["jsCode"], language="javascript")
        elif "text" in p:  # LLM chain node
            sys_msgs = p.get("messages", {}).get("messageValues", [])
            if sys_msgs:
                st.caption("System message:")
                st.code(sys_msgs[0].get("message", ""))
            st.caption("Prompt (user message):")
            st.code(p["text"])
        elif "conditions" in p:
            st.caption("Condition:")
            st.json(p["conditions"])
        else:
            st.caption("Parameters:")
            st.json(p)
        with st.expander("Full workflow JSON"):
            st.json(data)
    else:
        st.info("Drop your exported workflow JSON into the repo root (or a `workflows/` folder) to inspect its nodes here.")

    st.divider()
    st.subheader("Reliability — a four-rung failure ladder")
    cols = st.columns(4)
    for c, (title, action) in zip(cols, LADDER):
        c.markdown(f"**{title}**")
        c.caption(f"→ {action}")

    st.divider()
    st.subheader("The error-handler workflow")
    st.caption("A separate n8n workflow. Any failure in the main run triggers it — it alerts "
               "#digest-admin, and if Slack itself is down it falls back to email.")
    st.graphviz_chart(ERR_DOT, use_container_width=True)

    st.caption("Test it directly — invokes the error-handler workflow (in production it fires "
               "automatically on any failed run). Posts a test alert to #digest-admin.")
    e_url = st.text_input(
        "Error-handler webhook URL",
        value=os.getenv("N8N_ERROR_WEBHOOK_URL", "https://samikshabatra.app.n8n.cloud/webhook/test-error"),
        key="err_url",
    )
    if st.button("▶  Test the error workflow"):
        with st.spinner("Triggering the error handler…"):
            try:
                req = urllib.request.Request(
                    e_url, data=b"{}", method="POST", headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=60) as r:
                    r.read()
                st.success("Error handler triggered — check **#digest-admin** in Slack.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not reach it: {e}\n\nAdd a Webhook Trigger (path `test-error`) to the "
                         "Digest Error Handler workflow, connect it to the Slack node, and publish.")

    err_wf = ROOT / "workflows" / "Digest Error Handler.json"
    if err_wf.exists():
        with st.expander("Error-handler workflow JSON"):
            st.json(json.loads(err_wf.read_text(encoding="utf-8")))

    shot = ROOT / "docs" / "assets" / "n8n-canvas.png"
    if shot.exists():
        st.image(str(shot), caption="n8n canvas", width="stretch")

# ---------------------------------------------------------------- TAB 2: LangGraph
LG_NODES = [
    ("count", DET), ("progress", LLM), ("risk", LLM), ("supervisor", LLM),
    ("dependency", LLM), ("summarize", LLM), ("validate_llm", DET),
    ("build_blocks", DET), ("add_here", DET), ("post", IO), ("fail", MUTED),
]

with tab_lg:
    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("The graph")
        if GRAPH_PNG.exists():
            st.image(str(GRAPH_PNG), width="stretch")
        else:
            st.info("Run `python run_digest.py` once to generate graph.png.")
    with right:
        st.subheader("Nodes")
        st.caption("Same architecture as n8n. Conditional edges: supervisor YES/NO, "
                   "self-correction loop, and the @here fork.")
        st.markdown(
            " ".join(badge(n, c) for n, c in LG_NODES),
            unsafe_allow_html=True,
        )
        st.write("")
        st.markdown("n8n's LLM nodes are LangChain under the hood, but the framework stays hidden "
                    "inside the canvas. This standalone `StateGraph` makes the same architecture "
                    "**explicit, version-controlled, and unit-testable** — the honest way to show the "
                    "agent built *from code*, not just wired as nodes. n8n ships the reliable daily "
                    "automation; LangGraph is that architecture as portable, inspectable code, and it "
                    "adds a **self-correction loop** (retry ≤3, then raise) where n8n instead fails "
                    "loud and alerts — two valid reliability idioms.")

    st.divider()
    st.subheader("Run the pipeline live")
    st.caption("Executes the real LangGraph over the sample CSV. Needs OPENAI_API_KEY in python/.env.")

    if st.button("▶  Run the pipeline", type="primary"):
        with st.spinner("Running the LangGraph agent…"):
            try:
                from agent_graph import build_graph  # deferred: needs the API key
                result = build_graph().invoke({"records": load_records()})
                st.session_state["result"] = result
            except Exception as e:  # noqa: BLE001
                st.session_state["result"] = None
                st.error(f"Run failed — check OPENAI_API_KEY in python/.env.\n\n{type(e).__name__}: {e}")

    result = st.session_state.get("result")
    if result and result.get("digest"):
        c = result["counts"]
        m = st.columns(5)
        m[0].metric("Items", c["record_count"])
        m[1].metric("🔥 High", c["high_count"])
        m[2].metric("⛔ Blocked", c["blocked_count"])
        m[3].metric("🕒 Stale", c["stale_count"])
        m[4].metric("@here", "yes" if c["mention_here"] else "no")

        d = result["digest"]
        st.markdown("#### Executive Summary")
        st.info(d["executive_summary"])

        st.markdown(f"#### 🔥 High Priority ({len(d['high_priority_items'])})")
        for i, it in enumerate(d["high_priority_items"], 1):
            st.markdown(f"**{i}. {it['feature']}**  `{it['item_id']}` · {it.get('owner','—')} "
                        f"· {it.get('target_quarter','—')}  \n{it['why_it_matters']}")

        st.markdown(f"#### ⛔ Blocked ({len(d['blocked_items'])})")
        for it in d["blocked_items"]:
            st.markdown(f"**{it['feature']}**  `{it['item_id']}` · {it.get('owner','—')}  \n"
                        f"Blocker: {it['blocker']}  \n➡️ {it['suggested_action']}")

        st.markdown("#### ✅ Recommendations")
        for r in d["recommendations"]:
            st.markdown(f"- {r}")

        with st.expander("Raw digest JSON"):
            st.json(d)
    elif result and not result.get("digest"):
        st.warning(f"Pipeline ran but produced no digest: {result.get('error')}")
