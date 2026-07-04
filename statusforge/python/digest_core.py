"""Deterministic core of StatusForge (the roadmap digest pipeline) — pure Python.

Framework-agnostic functions (no n8n, no LLM SDK). This is the same logic the n8n
Code nodes run, expressed as plain CPython so it can be unit-tested and reused as the
nodes of the LangGraph version. The design rule holds here too: counting and the
@here / validation decisions are deterministic; the LLM only writes prose.

Mapping to the n8n Code nodes:
    validate_and_count   <- snippet 1 "Validate + Count"
    parse_llm_json +
    validate_llm_output  <- snippet 5 "Validate LLM Output"
    build_slack_blocks   <- snippet 6 "Build Slack Blocks"
    prepend_here         <- snippet 7 "Prepend @here"
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

REQUIRED_FIELDS = ("Feature", "Priority", "Status", "Owner")
STALE_DAYS = 14


def _days_since(date_str: str) -> int | None:
    """Days since an ISO (YYYY-MM-DD) date string, or None if unparseable."""
    if not date_str:
        return None
    try:
        d = datetime.fromisoformat(str(date_str).strip()[:10]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - d).days


def validate_and_count(records: list[dict]) -> dict:
    """Validate raw Airtable records and compute the deterministic counts.

    Raises ValueError on empty / all-invalid input so the caller fails loudly instead
    of posting an empty digest.
    """
    if not records:
        raise ValueError("Airtable returned 0 records — aborting digest run.")

    valid: list[dict] = []
    skipped: list[dict] = []

    for record in records:
        fields = record.get("fields", record)  # Airtable v1 nests under "fields"; v2 flattens
        missing = [
            k for k in REQUIRED_FIELDS
            if fields.get(k) is None or str(fields.get(k)).strip() == ""
        ]
        if missing:
            skipped.append({
                "item_id": fields.get("Item ID", record.get("id", "unknown")),
                "missing_fields": missing,
            })
        else:
            days = _days_since(fields.get("Last Updated", ""))
            valid.append({
                "item_id": fields.get("Item ID", record.get("id")),
                "record_id": record.get("id", ""),
                "feature": fields["Feature"],
                "status": fields["Status"],
                "priority": fields["Priority"],
                "owner": fields["Owner"],
                "target_quarter": fields.get("Target Quarter", ""),
                "description": fields.get("Description", ""),
                "last_updated": fields.get("Last Updated", ""),
                "days_since_update": days,
                "stale": days is not None and days > STALE_DAYS,
            })

    if not valid:
        raise ValueError("All records failed field validation — aborting digest run.")

    high_count = sum(1 for r in valid if str(r["priority"]).strip().lower() == "high")
    blocked_items = [r for r in valid if str(r["status"]).strip().lower() == "blocked"]
    stale_items = [r for r in valid if r["stale"]]

    status_distribution: dict[str, int] = {}
    for r in valid:
        status_distribution[r["status"]] = status_distribution.get(r["status"], 0) + 1

    return {
        "records": valid,
        "record_count": len(valid),
        "skipped_count": len(skipped),
        "skipped": skipped,
        "high_count": high_count,
        "blocked_count": len(blocked_items),
        "blocked_ids": [r["item_id"] for r in blocked_items],
        "stale_count": len(stale_items),
        "stale_ids": [r["item_id"] for r in stale_items],
        "status_distribution": status_distribution,
        "mention_here": high_count > 5,  # the @here decision, made deterministically
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def parse_llm_json(raw: str) -> dict:
    """Strip optional markdown fences from a model response and parse the JSON."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


def validate_llm_output(digest: dict | str, counts: dict) -> dict:
    """Validate the LLM digest shape and cross-check item counts against the
    deterministic core. Accepts either a parsed dict or the raw JSON string.
    Raises ValueError on any mismatch — the caller routes that to the error handler.
    """
    out = parse_llm_json(digest) if isinstance(digest, str) else digest

    def fail(msg: str) -> None:
        raise ValueError(f"LLM output validation failed: {msg}")

    if not isinstance(out, dict):
        fail("output is not an object")
    if not isinstance(out.get("executive_summary"), str) or not out["executive_summary"].strip():
        fail("executive_summary missing or empty")
    for key in ("high_priority_items", "blocked_items", "recommendations"):
        if not isinstance(out.get(key), list):
            fail(f"{key} is not an array")
    if not out["recommendations"]:
        fail("recommendations missing or empty")

    for it in out["high_priority_items"]:
        if not (it.get("item_id") and it.get("feature") and it.get("why_it_matters")):
            fail("a high_priority_item is missing item_id/feature/why_it_matters")
    for it in out["blocked_items"]:
        if not (it.get("item_id") and it.get("feature") and it.get("blocker") and it.get("suggested_action")):
            fail("a blocked_item is missing item_id/feature/blocker/suggested_action")

    if len(out["high_priority_items"]) != counts["high_count"]:
        fail(f"LLM listed {len(out['high_priority_items'])} high items, "
             f"deterministic count is {counts['high_count']}")
    if len(out["blocked_items"]) != counts["blocked_count"]:
        fail(f"LLM listed {len(out['blocked_items'])} blocked items, "
             f"deterministic count is {counts['blocked_count']}")

    return out


def build_slack_blocks(digest: dict, counts: dict) -> dict:
    """Assemble the Slack Block Kit payload from the validated digest + counts."""
    blocks: list[dict] = [
        {"type": "header",
         "text": {"type": "plain_text", "text": "📋 Daily Roadmap Digest", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"*{counts['record_count']}* items  •  🔥 *{counts['high_count']}* "
                    f"High priority  •  ⛔ *{counts['blocked_count']}* Blocked"}]},
        {"type": "divider"},
        {"type": "section",
         "text": {"type": "mrkdwn", "text": f"*Executive Summary*\n{digest['executive_summary']}"}},
        {"type": "divider"},
        {"type": "section",
         "text": {"type": "mrkdwn", "text": f"*🔥 High Priority ({counts['high_count']})*"}},
    ]

    for i, it in enumerate(digest["high_priority_items"], start=1):
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
            "text": f"*{i}. {it['feature']}*  (`{it['item_id']}` • "
                    f"{it.get('owner') or '—'} • {it.get('target_quarter') or '—'})\n"
                    f"{it['why_it_matters']}"}})

    if digest["blocked_items"]:
        blocks.append({"type": "divider"})
        blocks.append({"type": "section",
            "text": {"type": "mrkdwn", "text": f"*⛔ Blocked ({counts['blocked_count']})*"}})
        for it in digest["blocked_items"]:
            blocks.append({"type": "section", "text": {"type": "mrkdwn",
                "text": f"*{it['feature']}*  (`{it['item_id']}` • {it.get('owner') or '—'})\n"
                        f"Blocker: {it['blocker']}\n➡️ {it['suggested_action']}"}})

    blocks.append({"type": "divider"})
    blocks.append({"type": "section", "text": {"type": "mrkdwn",
        "text": "*✅ Recommendations*\n" + "\n".join(f"•  {r}" for r in digest["recommendations"])}})

    dist = "   |   ".join(f"{k}: *{v}*" for k, v in counts["status_distribution"].items())
    footer = f"Generated {counts['run_timestamp']}"
    if counts["skipped_count"] > 0:
        footer += f"  •  ⚠️ {counts['skipped_count']} invalid record(s) skipped"
    blocks.append({"type": "divider"})
    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn", "text": f"Status — {dist}"},
        {"type": "mrkdwn", "text": footer},
    ]})

    return {
        "blocks": blocks,
        "blocks_json": json.dumps({"blocks": blocks}),
        "high_count": counts["high_count"],
        "blocked_count": counts["blocked_count"],
        "notification_text": f"Daily Roadmap Digest — {counts['high_count']} "
                             f"High priority, {counts['blocked_count']} Blocked",
    }


def prepend_here(payload: dict, high_count: int) -> dict:
    """Prepend the <!here> mention block (true branch only). The literal <!here>
    token is what actually notifies the channel; plain "@here" text does nothing."""
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"<!here> *{high_count} items are High priority — attention needed.*"}},
        *payload["blocks"],
    ]
    return {
        **payload,
        "blocks": blocks,
        "blocks_json": json.dumps({"blocks": blocks}),
        "notification_text": f"@here {payload['notification_text']}",
    }
