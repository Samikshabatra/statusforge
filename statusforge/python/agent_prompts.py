"""LangChain prompt templates. Each specialist/synthesizer node is a real
`ChatPromptTemplate | ChatOpenAI` chain. Literal JSON braces are escaped as {{ }}.
"""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

# --- Specialist agents -------------------------------------------------------------

PROGRESS = ChatPromptTemplate.from_messages([
    ("system", "You are a delivery/progress analyst. Assess momentum from roadmap status "
               "data: what's advancing, what's stalled. 2-3 sentences of prose, no JSON."),
    ("human", "Items:\n{records_block}\n\nStatus distribution: {status_distribution}\n"
              "Stale items (14+ days): {stale_count}\n\n"
              "In 2-3 sentences: what's advancing, what's stalled (trust the STALE flags), "
              "and the velocity signal."),
])

RISK = ChatPromptTemplate.from_messages([
    ("system", "You are a risk analyst. Surface delivery risks: blocked work, concentration "
               "on one owner, time-sensitive exposure. 2-3 sentences of prose, no JSON."),
    ("human", "Items:\n{records_block}\n\n{high_count} High priority, {blocked_count} Blocked "
              "({blocked_ids}).\n\nIn 2-3 sentences: the biggest risks."),
])

DEPENDENCY = ChatPromptTemplate.from_messages([
    ("system", "You are a dependency analyst. For the blocked items, identify what each is "
               "waiting on to unblock and any cross-item dependency. 2-3 sentences, no JSON."),
    ("human", "Blocked items:\n{blocked_block}\n\nIn 2-3 sentences: what each is waiting on "
              "and any cross-item dependency affecting sequencing."),
])

# --- Supervisor (LLM router): fuzzy judgment, not a count -> YES/NO -----------------

SUPERVISOR = ChatPromptTemplate.from_messages([
    ("system", "You route a roadmap-digest pipeline. Decide whether a deeper dependency "
               "analysis of blocked items is warranted. Answer one word: YES or NO."),
    ("human", "High-priority items:\n{high_block}\nBlocked among them: {blocked_ids}\n\n"
              "If any high-priority item has a blocker involving a review, another team, or a "
              "prerequisite, respond YES. If all are clear/self-contained, respond NO. "
              "One word only: YES or NO."),
])

# --- Synthesizer -------------------------------------------------------------------

_SUMMARY_SYSTEM = """You are a Senior Product Manager writing the daily roadmap digest.
Rules: (1) PRE-COMPUTED COUNTS are deterministic — never recalculate or contradict them.
(2) Rank high-priority items by urgency. (3) Blocked items get their own section.
(4) Concise, Slack-ready, no markdown headers. (5) Respond ONLY with JSON matching the schema."""

_SUMMARY_HUMAN = """Roadmap ({record_count} valid items):
{records_block}

PRE-COMPUTED COUNTS (use as-is):
- High priority: {high_count}
- Blocked: {blocked_count} ({blocked_ids})
- Stale (14+ days): {stale_count}
- Status: {status_distribution}

SPECIALIST ANALYSES (incorporate; never contradict the counts):
- Progress: {progress}
- Risk: {risk}
- Dependencies: {dependency}
{correction}
Lead with the High-priority picture; progress/status is secondary. Write:
1. executive_summary — 2-3 sentences, High-priority first.
2. high_priority_items — exactly {high_count}, ranked, each with why_it_matters.
3. blocked_items — exactly {blocked_count}, each with blocker + suggested_action.
4. recommendations — 2-4 specific, actionable.

Return ONLY raw JSON, no fences, with exactly:
{{
  "executive_summary": "string",
  "high_priority_items": [{{ "item_id": "string", "feature": "string", "owner": "string", "target_quarter": "string", "why_it_matters": "string" }}],
  "blocked_items": [{{ "item_id": "string", "feature": "string", "owner": "string", "blocker": "string", "suggested_action": "string" }}],
  "recommendations": ["string"]
}}"""

SUMMARIZE = ChatPromptTemplate.from_messages([("system", _SUMMARY_SYSTEM), ("human", _SUMMARY_HUMAN)])

CORRECTION = ("\nYour previous attempt FAILED validation: {error}\n"
              "Re-think and return corrected JSON with exactly the required item counts.\n")
