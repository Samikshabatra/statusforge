"""StatusForge dashboard — an agentic roadmap digest for Slack.

One page, sidebar-navigated:
  Overview        hero, Slack preview (from the sample data), deterministic counts
  n8n Workflow    the exact exported workflow, drawn as one diagram; pipeline; node inspector; reliability
  Error handler   the separate failure workflow + a test trigger
  LangGraph       the agent core; renders graph.png and RUNS the real pipeline live
  Roadmap Data    the sample Airtable export with computed staleness
  Docs            README / walkthrough / build guide

Run from the python/ folder:  streamlit run app.py
(Needs OPENAI_API_KEY in python/.env only for the live "Run the pipeline" button.)
The earlier single-page UI is kept as app_legacy.py.
"""
from __future__ import annotations

import csv
import html
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from digest_core import STALE_DAYS, validate_and_count
from ui_theme import AMBER, CORAL, CSS, DET, GREEN, IO, LLM, RED, SLACK_MARK, VIOLET, icon
from workflow_dot import to_dot

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CSV_PATH = ROOT / "roadmap_airtable_export.csv"
GRAPH_PNG = HERE / "graph.png"
MAIN_WF = ROOT / "workflows" / "Roadmap Slack Digest.json"
ERR_WF = ROOT / "workflows" / "Digest Error Handler.json"

st.set_page_config(page_title="StatusForge", page_icon="⚒️", layout="wide", initial_sidebar_state="expanded")

# On Streamlit Cloud there is no .env — expose configured secrets as env vars so
# ChatOpenAI (which reads OPENAI_API_KEY) and the webhook defaults work.
try:
    for _k in ("OPENAI_API_KEY", "OPENAI_MODEL", "N8N_WEBHOOK_URL", "N8N_ERROR_WEBHOOK_URL"):
        if _k in st.secrets:
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass


def html_block(s: str) -> None:
    """Render raw HTML. Lines are flattened so Markdown never mistakes indentation for a code block."""
    st.markdown(" ".join(line.strip() for line in s.strip().splitlines()), unsafe_allow_html=True)


def chip(text: str, color: str) -> str:
    return (f"<span class='sf-chip' style='color:{color};border-color:{color}99;background:{color}14'>"
            f"{html.escape(text)}</span>")


def load_records() -> list[dict]:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def load_json(p: Path) -> dict | None:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def trigger(url: str, timeout: int) -> str:
    req = urllib.request.Request(url, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def schedule_hour(wf: dict | None) -> int | None:
    for n in (wf or {}).get("nodes", []):
        if n["type"].endswith("scheduleTrigger"):
            iv = (n.get("parameters", {}).get("rule", {}).get("interval") or [{}])[0]
            return iv.get("triggerAtHour")
    return None


N8N_STAGES = [
    ("Schedule Trigger", IO, "Runs daily at {hour}"),
    ("Webhook", IO, "On-demand run — the Run button posts here"),
    ("Search records · Airtable", IO, "Pulls all roadmap rows"),
    ("Validate + Count", DET, "Counts, staleness, the @here flag — the source of truth"),
    ("Progress Agent  |  Risk Analysis Agent", LLM, "Two specialists, run in parallel"),
    ("Merge All Analyses", DET, "Waits for both, then continues"),
    ("Supervisor", LLM, "Fuzzy judgment: is a dependency analysis warranted? → YES / NO"),
    ("Need another analysis? (IF)", DET, "Routes on the supervisor's word — no model here"),
    ("Dependency Agent", LLM, "Conditional — runs only on YES"),
    ("Summarize & Rank", LLM, "Folds every analysis into the digest JSON"),
    ("Validate LLM Output", DET, "Cross-checks item counts vs the deterministic counts; throws on mismatch"),
    ("Build Slack Blocks", DET, "Block Kit, Airtable deep-links, owner @-mentions"),
    ("High Count > 5 (IF)", DET, "The @here decision, made from the computed count"),
    ("Prepend @here", DET, "Adds the literal <!here> token on the true branch"),
    ("Post Digest · Slack", IO, "One message to #roadmap-digest"),
    ("Send a message · Slack", IO, "Success line to #digest-admin — the run audit log"),
]

LADDER = [
    ("zap", GREEN, "Transient blip", "Per-node retry, 3× with backoff"),
    ("warning", RED, "Node fails hard", "Error workflow → Slack alert to #digest-admin"),
    ("mail", VIOLET, "Slack itself down", "Email fallback via Gmail"),
    ("file", IO, "Model breaks the schema", "Validation throws → error workflow"),
]

LG_NODES = [
    ("count", DET), ("progress", LLM), ("risk", LLM), ("supervisor", LLM),
    ("dependency", LLM), ("summarize", LLM), ("validate_llm", DET),
    ("build_blocks", DET), ("add_here", DET), ("post", IO), ("fail", "#98a2b3"),
]

STATUS_DOT = {"blocked": RED, "in progress": AMBER, "not started": "#6b7488"}
STATUS_ORDER = {"blocked": 0, "in progress": 1, "not started": 2}

main_wf, err_wf = load_json(MAIN_WF), load_json(ERR_WF)
hour = schedule_hour(main_wf)
hour_txt = f"{hour:02d}:00" if isinstance(hour, int) else "—"
records = load_records() if CSV_PATH.exists() else []
try:
    counts = validate_and_count(records)
except ValueError:
    counts = None

st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------- sidebar
NAV = [("overview", "overview", "Overview"), ("workflow", "workflow", "n8n Workflow"),
       ("langgraph", "graph", "LangGraph Architecture"), ("data", "data", "Roadmap Data"),
       ("inspector", "inspect", "Node Inspector"), ("reliability", "shield", "Reliability"),
       ("docs", "docs", "Docs")]
with st.sidebar:
    links = "".join(
        f"<a href='#{a}' target='_self' class='{'active' if i == 0 else ''}'>{icon(ic)}{label}</a>"
        for i, (a, ic, label) in enumerate(NAV))
    html_block(f"""
      <div class='sf-brand'>{icon('logo', 28, 2.2)}StatusForge</div>
      <nav class='sf-nav'>{links}</nav>
      <div class='sf-side-card'><b>Automating product clarity.</b>
      <span>StatusForge turns roadmap data into verified intelligence for your team.</span></div>
    """)
    st.write("")
    with st.expander("Webhook settings"):
        webhook_url = st.text_input(
            "Run-digest webhook",
            value=os.getenv("N8N_WEBHOOK_URL", "https://samikshabatra.app.n8n.cloud/webhook/run-digest"))
        err_url = st.text_input(
            "Error-handler webhook",
            value=os.getenv("N8N_ERROR_WEBHOOK_URL", "https://samikshabatra.app.n8n.cloud/webhook/test-error"))

u = urlparse(webhook_url)
n8n_home = f"{u.scheme}://{u.netloc}" if u.netloc else "https://app.n8n.cloud"

# ---------------------------------------------------------------- top bar
n_nodes = len(main_wf["nodes"]) if main_wf else 0
html_block(f"""
  <div class='sf-top' id='overview'>
    <span class='sf-pill'><span class='sf-dot'></span>Workflow loaded · {n_nodes} nodes</span>
    <span class='sf-avatar'>SB</span>
  </div>
""")

# ---------------------------------------------------------------- hero
with st.container(key="hero"):
    left, mid, right, words = st.columns([1.28, 0.42, 0.86, 0.26], gap="medium")
    with left:
        html_block("""
          <div class='sf-eyebrow'>Airtable → deterministic core → multi-agent LLM → Slack</div>
          <div class='sf-title'>StatusForge</div>
          <div class='sf-sub'>Automated roadmap intelligence for modern product teams.</div>
          <div class='sf-desc'>Fetches roadmap data from Airtable, runs multi-agent LLM analysis
          and posts a verified digest to Slack.</div>
        """)
        b1, b2, _ = st.columns([1.25, 1, 0.1])
        run_clicked = b1.button("▶  Run the n8n workflow now", key="run", use_container_width=True)
        with b2:
            html_block(f"<a class='sf-ghost' href='#langgraph' target='_self'>{icon('arch', 18)}View Architecture</a>")
    with mid:
        html_block("""
          <div class='sf-quote'>"Less manual updates.<br>More meaningful progress."
          <svg width="110" height="44" viewBox="0 0 110 44" fill="none" stroke="currentColor" stroke-width="1.6"
          stroke-linecap="round"><path d="M14 8c-12 10-10 30 4 28 12-2 4-26-6-14-6 8 8 22 30 20 18-2 34-10 52-12"/>
          <path d="M96 24l8 6-10 4"/></svg></div>
        """)
    with right:
        if counts:
            high = [r for r in counts["records"] if str(r["priority"]).strip().lower() == "high"]
            high.sort(key=lambda r: STATUS_ORDER.get(str(r["status"]).lower(), 9))
            items = "".join(
                f"<div class='sf-item'><i style='background:{STATUS_DOT.get(str(r['status']).lower(), '#6b7488')}'></i>"
                f"<div><b>{html.escape(r['feature'])}</b><span>{html.escape(r['status'])} · {html.escape(r['owner'])}"
                f"</span></div><span class='sf-prio'>High</span></div>" for r in high[:3])
            more = f"<div class='sf-more'>+ {len(high) - 3} more items</div>" if len(high) > 3 else ""
            here = "<span class='sf-here'>@here</span>" if counts["mention_here"] else "<div style='height:10px'></div>"
            html_block(f"""
              <div class='sf-slack'>
                <div class='h'>{SLACK_MARK}# roadmap-digest <small>preview</small></div>
                {here}
                <div class='t'>Daily Roadmap Brief</div>
                <div class='d'>{datetime.now():%d %B %Y}</div>
                <div class='s'>{counts['high_count']} high-priority items require attention.</div>
                {items}{more}
                <div class='sf-foot'>Built from the sample data by the deterministic core</div>
              </div>
            """)
    with words:
        html_block("<div class='sf-words'>DATA<br>AGENTS<br>INSIGHTS<br>IMPACT</div>")

if run_clicked:
    with st.spinner("Triggering n8n…"):
        try:
            body = trigger(webhook_url, 120)
            st.success("Triggered — the workflow is running. Check **#roadmap-digest** in Slack in a few seconds.")
            if body.strip():
                with st.expander("Webhook response"):
                    st.code(body)
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not reach the webhook: {e}\n\nIs the workflow published? URL: {webhook_url}")

