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

# ---------------------------------------------------------------- stat cards
if counts:
    def stat(ic: str, color: str, n, label: str, sub: str) -> str:
        return (f"<div class='sf-stat'><div class='ic' style='background:{color}22;color:{color}'>{icon(ic, 26)}</div>"
                f"<div><div class='n'>{n}</div><div class='l'>{label}</div><div class='x'>{sub}</div></div></div>")
    blocked = ", ".join(counts["blocked_ids"]) or "None"
    html_block(f"""
      <div class='sf-stats'>
        {stat('database', '#7B93FF', counts['record_count'], 'Roadmap Items', 'From Airtable')}
        {stat('warning', CORAL, counts['high_count'], 'High Priority', '@here threshold &gt; 5')}
        {stat('ban', RED, counts['blocked_count'], 'Blocked Items', html.escape(blocked))}
        {stat('clock', '#5B9CFF', counts['stale_count'], 'Stale Items', f'No update in {STALE_DAYS}+ days')}
        <div class='sf-stat ok'><div class='ic' style='color:{GREEN}'>{icon('check', 34)}</div>
          <div style='flex:1'><div class='k'>Scheduled Run</div><div class='n'>{hour_txt}</div>
          <div class='x'>Daily · n8n Cloud</div>
          <a href='{n8n_home}' target='_blank'>Open n8n →</a></div></div>
      </div>
    """)

# ---------------------------------------------------------------- workflow
html_block("<div id='workflow' class='sf-anchor'></div>")
with st.container(key="card_workflow"):
    html_block(f"""
      <div class='sf-h'><h2>The workflow</h2>
      <a class='sf-btn' href='{n8n_home}' target='_blank'>Open in n8n {icon('external', 16)}</a></div>
      <div class='sf-cap'>The exact n8n flow, generated from the exported workflow — all {n_nodes} nodes and every
      connection. Deterministic (teal), LLM (coral), I/O (blue); dashed = the OpenAI model feeding each agent.</div>
    """)
    if main_wf:
        st.graphviz_chart(to_dot(main_wf), width="stretch")
    else:
        st.info(f"Export the main workflow to `workflows/{MAIN_WF.name}` to draw it here.")

st.write("")
c_pipe, c_insp, c_rel = st.columns([1.05, 1, 1], gap="medium")

with c_pipe, st.container(key="card_pipeline", height="stretch"):
    rows = "".join(
        f"<div class='sf-row'>{chip(name, color)}<span class='r'>{html.escape(role.format(hour=hour_txt))}</span></div>"
        for name, color, role in N8N_STAGES)
    html_block(f"""
      <div class='sf-h'><h3>The pipeline</h3></div>
      <div class='sf-cap sm'>{len(N8N_STAGES)} stages, colored by what each one is. Deterministic ends bracket
      the multi-agent middle.</div>{rows}
    """)

with c_insp, st.container(key="card_inspector", height="stretch"):
    html_block("""
      <div id='inspector' class='sf-anchor'></div>
      <div class='sf-h'><h3>Inspect a node</h3></div>
      <div class='sf-cap sm'>Pick any node to see its real configuration — the exact code, prompt, or condition
      from the exported workflow.</div>
    """)
    if main_wf:
        nodes = {n["name"]: n for n in main_wf.get("nodes", [])}
        names = sorted(nodes, key=lambda k: nodes[k].get("position", [0, 0])[0])
        choice = st.selectbox("Node", names, label_visibility="collapsed")
        n = nodes[choice]
        html_block(f"<div class='sf-type'>Type: <code>{html.escape(n.get('type', ''))}</code> · version "
                   f"<code>{n.get('typeVersion', '')}</code></div>")
        p = n.get("parameters", {})
        if "jsCode" in p:
            st.code(p["jsCode"], language="javascript", height=330)
        elif "text" in p and n["type"].endswith("chainLlm"):
            sys_msgs = p.get("messages", {}).get("messageValues", [])
            body = (f"# System message\n{sys_msgs[0].get('message', '')}\n\n" if sys_msgs else "") + \
                   f"# Prompt (user message)\n{p['text']}"
            st.code(body, language="markdown", height=330, wrap_lines=True)
        elif "conditions" in p:
            st.code(json.dumps(p["conditions"], indent=2), language="json", height=330)
        else:
            st.code(json.dumps(p, indent=2), language="json", height=330)
        with st.expander("Full workflow JSON"):
            st.json(main_wf, expanded=False)

with c_rel, st.container(key="card_reliability", height="stretch"):
    rungs = "".join(
        f"<div class='sf-rung'><div class='num'>{i}</div>"
        f"<div class='tile' style='background:{c}22;color:{c}'>{icon(ic, 22)}</div>"
        f"<div><b>{t}</b><span>{a}</span></div></div>"
        for i, (ic, c, t, a) in enumerate(LADDER, 1))
    html_block(f"""
      <div id='reliability' class='sf-anchor'></div>
      <div class='sf-h'><h3>Reliability — a four-rung failure ladder</h3></div>
      {rungs}
      <div class='sf-note'>{icon('shield', 26)}All numbers are computed deterministically and validated
      before anything is posted.</div>
    """)

# ---------------------------------------------------------------- error handler
st.write("")
with st.container(key="card_error"):
    html_block("""
      <div class='sf-h'><h2>The error-handler workflow</h2></div>
      <div class='sf-cap'>A separate n8n workflow. Any failure in the main run triggers it — it alerts
      #digest-admin, and if Slack itself is down it falls back to email.</div>
    """)
    if err_wf:
        st.graphviz_chart(to_dot(err_wf, nodesep=0.35, ranksep=0.6), width="stretch")
    html_block("<div class='sf-cap sm'>Test it directly — invokes the error-handler workflow (in production it "
               "fires automatically on any failed run). Posts a test alert to #digest-admin. "
               "Webhook URLs live under <b>Webhook settings</b> in the sidebar.</div>")
    ec1, ec2 = st.columns([1, 3])
    if ec1.button("▶  Test the error workflow", use_container_width=True):
        with st.spinner("Triggering the error handler…"):
            try:
                trigger(err_url, 60)
                st.success("Error handler triggered — check **#digest-admin** in Slack.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not reach it: {e}\n\nAdd a Webhook Trigger (path `test-error`) to the "
                         "Digest Error Handler workflow, connect it to the Slack node, and publish.")
    if err_wf:
        with st.expander("Error-handler workflow JSON"):
            st.json(err_wf, expanded=False)

# ---------------------------------------------------------------- LangGraph
st.write("")
html_block("<div id='langgraph' class='sf-anchor'></div>")
with st.container(key="card_langgraph"):
    html_block("""
      <div class='sf-h'><h2>LangGraph architecture</h2></div>
      <div class='sf-cap'>The same agent core as explicit, testable code — a <code>StateGraph</code> with conditional
      edges and a self-correction loop.</div>
    """)
    g1, g2 = st.columns([1.1, 1], gap="large")
    with g1:
        if GRAPH_PNG.exists():
            st.image(str(GRAPH_PNG), width="stretch")
        else:
            st.info("Run `python run_digest.py` once to generate graph.png.")
    with g2:
        html_block("<div class='sf-h'><h3>Nodes</h3></div><div style='display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 16px'>"
                   + "".join(chip(nm, c) for nm, c in LG_NODES) + "</div>")
        st.markdown("n8n's LLM nodes are LangChain under the hood, but the framework stays hidden inside the canvas. "
                    "This standalone `StateGraph` makes the same architecture **explicit, version-controlled, and "
                    "unit-testable**. n8n ships the reliable daily automation; LangGraph adds a **self-correction "
                    "loop** (retry ≤3, then raise) where n8n instead fails loud and alerts — two valid reliability idioms.")
        st.write("")
        run_lg = st.button("▶  Run the pipeline", type="primary")
        st.caption("Executes the real LangGraph over the sample CSV. Needs OPENAI_API_KEY in python/.env.")

    if run_lg:
        with st.spinner("Running the LangGraph agent…"):
            try:
                from agent_graph import build_graph  # deferred: needs the API key
                st.session_state["result"] = build_graph().invoke({"records": load_records()})
            except Exception as e:  # noqa: BLE001
                st.session_state["result"] = None
                st.error(f"Run failed — check OPENAI_API_KEY in python/.env.\n\n{type(e).__name__}: {e}")

    result = st.session_state.get("result")
    if result and result.get("digest"):
        d = result["digest"]
        st.markdown("#### Executive Summary")
        st.info(d["executive_summary"])
        st.markdown(f"#### 🔥 High Priority ({len(d['high_priority_items'])})")
        for i, it in enumerate(d["high_priority_items"], 1):
            st.markdown(f"**{i}. {it['feature']}**  `{it['item_id']}` · {it.get('owner', '—')} "
                        f"· {it.get('target_quarter', '—')}  \n{it['why_it_matters']}")
        st.markdown(f"#### ⛔ Blocked ({len(d['blocked_items'])})")
        for it in d["blocked_items"]:
            st.markdown(f"**{it['feature']}**  `{it['item_id']}` · {it.get('owner', '—')}  \n"
                        f"Blocker: {it['blocker']}  \n➡️ {it['suggested_action']}")
        st.markdown("#### ✅ Recommendations")
        for r in d["recommendations"]:
            st.markdown(f"- {r}")
        with st.expander("Raw digest JSON"):
            st.json(d)
    elif result and not result.get("digest"):
        st.warning(f"Pipeline ran but produced no digest: {result.get('error')}")

# ---------------------------------------------------------------- roadmap data
st.write("")
html_block("<div id='data' class='sf-anchor'></div>")
with st.container(key="card_data"):
    html_block(f"""
      <div class='sf-h'><h2>Roadmap data</h2></div>
      <div class='sf-cap'>The sample Airtable export ({CSV_PATH.name}) as the deterministic core sees it —
      staleness is computed, not stored.</div>
    """)
    if counts:
        st.dataframe(
            [{"Item": r["item_id"], "Feature": r["feature"], "Status": r["status"], "Priority": r["priority"],
              "Owner": r["owner"], "Quarter": r["target_quarter"], "Last updated": r["last_updated"],
              "Days since update": r["days_since_update"], "Stale": r["stale"]} for r in counts["records"]],
            hide_index=True,
        )

# ---------------------------------------------------------------- docs
st.write("")
html_block("<div id='docs' class='sf-anchor'></div>")
with st.container(key="card_docs"):
    html_block("<div class='sf-h'><h2>Docs</h2></div>"
               "<div class='sf-cap'>The project write-ups, straight from the repo.</div>")
    readme = next((p for p in (ROOT / "README.md", ROOT.parent / "README.md") if p.exists()), ROOT / "README.md")
    doc_files = [("README", readme), ("Walkthrough", ROOT / "docs" / "WALKTHROUGH.md"),
                 ("Build guide", ROOT / "BUILD-GUIDE.md")]
    doc_files = [(t, p) for t, p in doc_files if p.exists()]
    if doc_files:
        for tab, (_, p) in zip(st.tabs([t for t, _ in doc_files]), doc_files):
            with tab, st.container(height=460):
                st.markdown(p.read_text(encoding="utf-8"))

# Streamlit intercepts in-page links, so the sidebar nav scrolls to its section itself.
# mousedown (window, capture) runs before Streamlit's own click handling can swallow the event.
st.html("""
<script>
if (!window.__sfNav) {
  window.__sfNav = true;
  const anchorOf = (e) => {
    const a = e.target.closest && e.target.closest('a[href^="#"]');
    return a && document.getElementById(a.getAttribute('href').slice(1)) ? a : null;
  };
  window.addEventListener('mousedown', (e) => {
    const a = anchorOf(e);
    if (!a || e.button !== 0) return;
    document.getElementById(a.getAttribute('href').slice(1)).scrollIntoView({block: 'start'});
    document.querySelectorAll('.sf-nav a').forEach(x => x.classList.toggle('active', x === a));
  }, true);
  window.addEventListener('click', (e) => { if (anchorOf(e)) { e.preventDefault(); e.stopPropagation(); } }, true);
}
</script>
""", unsafe_allow_javascript=True)
