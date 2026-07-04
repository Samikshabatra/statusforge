"""The LangGraph orchestration — the full supervisor -> specialists -> summarizer graph,
expressed as real, inspectable code. Run run_digest.py to render graph.png.

Shares the n8n workflow's architecture and its core design rule, with ONE intentional
divergence in the reliability strategy: on invalid LLM output THIS graph self-corrects
(loops back to `summarize` with the error, up to MAX_ATTEMPTS) then raises. The n8n
workflow instead fails loud and routes straight to its error-workflow — no retry loop.
Both are valid: n8n leans on its error-workflow pattern; this shows the self-correcting
variant. They are NOT identical, and neither claims to be.

    START -> count -> progress ┐
                     └ risk ────┴-> supervisor --(YES)--> dependency ┐
                                          │  (NO)                    │
                                          └──────────────────────────┴-> summarize
                                                                          │  ▲
                                             (retry: self-correction) ────┘  │  (ok)
                                                                             ▼
                                        validate_llm --(ok)--> build_blocks --> route_mention
                                             │ (fail after 3)                  ╱(mention)  ╲(normal)
                                             ▼                            add_here          post -> END
                                            END

Design rule (same as n8n): counts + the @here decision are DETERMINISTIC (digest_core);
LLMs only reason. The supervisor's YES/NO and the self-correction loop are conditional edges.
"""
from __future__ import annotations

import os
from typing import TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from agent_prompts import CORRECTION, DEPENDENCY, PROGRESS, RISK, SUMMARIZE, SUPERVISOR
from digest_core import (
    build_slack_blocks,
    prepend_here,
    validate_and_count,
    validate_llm_output,
)

load_dotenv()  # load .env before the model is created (import-time)
MAX_ATTEMPTS = 3
llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0.2)


class DigestState(TypedDict, total=False):
    records: list[dict]
    counts: dict
    progress: str
    risk: str
    dependency: str
    need_dependency: bool
    digest_raw: str
    digest: dict
    error: str
    attempts: int
    payload: dict
    posted: bool


# --- render helpers ----------------------------------------------------------------

def _records_block(records: list[dict]) -> str:
    return "\n".join(" | ".join([
        r["item_id"], r["feature"], f"Status: {r['status']}", f"Priority: {r['priority']}",
        f"Owner: {r['owner']}",
        f"Updated {r['days_since_update']}d ago" + (" (STALE)" if r["stale"] else ""),
        r["description"],
    ]) for r in records)


def _high_block(records: list[dict]) -> str:
    return "\n".join(" | ".join([r["item_id"], r["feature"], f"Status: {r['status']}", r["description"]])
                     for r in records if str(r["priority"]).strip().lower() == "high")


def _blocked_block(records: list[dict]) -> str:
    return "\n".join(" | ".join([r["item_id"], r["feature"], f"Owner: {r['owner']}", r["description"]])
                     for r in records if str(r["status"]).strip().lower() == "blocked")


def _dist(counts: dict) -> str:
    return ", ".join(f"{k}: {v}" for k, v in counts["status_distribution"].items())


# --- nodes -------------------------------------------------------------------------

def count_node(state: DigestState) -> DigestState:
    return {"counts": validate_and_count(state["records"]), "attempts": 0,
            "error": "", "dependency": "Not analyzed."}


def progress_node(state: DigestState) -> DigestState:
    c = state["counts"]
    msg = PROGRESS.format_messages(records_block=_records_block(c["records"]),
                                   status_distribution=_dist(c), stale_count=c["stale_count"])
    return {"progress": llm.invoke(msg).content}


def risk_node(state: DigestState) -> DigestState:
    c = state["counts"]
    msg = RISK.format_messages(records_block=_records_block(c["records"]), high_count=c["high_count"],
                               blocked_count=c["blocked_count"], blocked_ids=", ".join(c["blocked_ids"]))
    return {"risk": llm.invoke(msg).content}


def supervisor_node(state: DigestState) -> DigestState:
    """LLM router — a fuzzy judgment (is dependency analysis warranted?), not a count."""
    c = state["counts"]
    msg = SUPERVISOR.format_messages(high_block=_high_block(c["records"]),
                                     blocked_ids=", ".join(c["blocked_ids"]))
    decision = (llm.invoke(msg).content or "").strip().upper()
    return {"need_dependency": decision.startswith("YES")}


def dependency_node(state: DigestState) -> DigestState:
    c = state["counts"]
    msg = DEPENDENCY.format_messages(blocked_block=_blocked_block(c["records"]))
    return {"dependency": llm.invoke(msg).content}


def summarize_node(state: DigestState) -> DigestState:
    c = state["counts"]
    correction = CORRECTION.format(error=state["error"]) if state.get("error") else ""
    msg = SUMMARIZE.format_messages(
        record_count=c["record_count"], records_block=_records_block(c["records"]),
        high_count=c["high_count"], blocked_count=c["blocked_count"],
        blocked_ids=", ".join(c["blocked_ids"]), stale_count=c["stale_count"],
        status_distribution=_dist(c), progress=state.get("progress", ""),
        risk=state.get("risk", ""), dependency=state.get("dependency", "Not analyzed."),
        correction=correction,
    )
    return {"digest_raw": llm.invoke(msg).content, "attempts": state.get("attempts", 0) + 1}


def validate_llm_node(state: DigestState) -> DigestState:
    try:
        return {"digest": validate_llm_output(state["digest_raw"], state["counts"]), "error": ""}
    except ValueError as e:
        return {"error": str(e)}


def build_blocks_node(state: DigestState) -> DigestState:
    return {"payload": build_slack_blocks(state["digest"], state["counts"])}


def add_here_node(state: DigestState) -> DigestState:
    return {"payload": prepend_here(state["payload"], state["counts"]["high_count"])}


def fail_node(state: DigestState) -> DigestState:
    """Loud failure: the LLM output never validated within the retry budget. Raise so
    the run visibly fails (mirroring the n8n error-workflow story) instead of silently
    posting nothing."""
    raise RuntimeError(
        f"Digest aborted — LLM output failed validation after {MAX_ATTEMPTS} attempts. "
        f"Last error: {state.get('error')}"
    )


def post_node(state: DigestState) -> DigestState:
    payload = state["payload"]
    token, channel = os.getenv("SLACK_BOT_TOKEN"), os.getenv("SLACK_CHANNEL_ID")
    if token and channel:
        import json
        import urllib.request
        req = urllib.request.Request(
            "https://slack.com/api/chat.postMessage",
            data=json.dumps({"channel": channel, "blocks": payload["blocks"],
                             "text": payload["notification_text"]}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as r:
            return {"posted": bool(json.load(r).get("ok"))}
    print("\n[dry run] " + payload["notification_text"])
    return {"posted": False}


# --- conditional edges -------------------------------------------------------------

def route_supervisor(state: DigestState) -> str:
    return "dependency" if state.get("need_dependency") else "summarize"


def route_after_validation(state: DigestState) -> str:
    if state.get("digest") and not state.get("error"):
        return "ok"
    return "fail" if state.get("attempts", 0) >= MAX_ATTEMPTS else "retry"


def route_mention(state: DigestState) -> str:
    return "mention" if state["counts"]["mention_here"] else "normal"


def build_graph():
    g = StateGraph(DigestState)
    for name, fn in [
        ("count", count_node), ("progress", progress_node), ("risk", risk_node),
        ("supervisor", supervisor_node), ("dependency", dependency_node),
        ("summarize", summarize_node), ("validate_llm", validate_llm_node),
        ("build_blocks", build_blocks_node), ("add_here", add_here_node), ("post", post_node),
        ("fail", fail_node),
    ]:
        g.add_node(name, fn)

    g.add_edge(START, "count")
    g.add_edge("count", "progress")   # fan-out to specialists
    g.add_edge("count", "risk")
    g.add_edge("progress", "supervisor")  # fan-in
    g.add_edge("risk", "supervisor")
    g.add_conditional_edges("supervisor", route_supervisor,
                            {"dependency": "dependency", "summarize": "summarize"})
    g.add_edge("dependency", "summarize")
    g.add_edge("summarize", "validate_llm")
    g.add_conditional_edges("validate_llm", route_after_validation,
                            {"ok": "build_blocks", "retry": "summarize", "fail": "fail"})
    g.add_edge("fail", END)
    g.add_conditional_edges("build_blocks", route_mention,
                            {"mention": "add_here", "normal": "post"})
    g.add_edge("add_here", "post")
    g.add_edge("post", END)
    return g.compile()
