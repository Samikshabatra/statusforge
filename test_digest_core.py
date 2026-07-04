"""Unit tests for the deterministic core (python/digest_core.py).

These test the parts of StatusForge that carry the actual reliability guarantee —
counting, validation, and the @here decision — none of which touch the network or an
LLM, so they run instantly and without any API key.

Run from the repo root:
    pip install pytest
    pytest tests -v

(Assumes `python/` is importable — either run from a repo root that has `python/` on
the path, or add a `conftest.py` / install the package. If needed:
    PYTHONPATH=python pytest tests -v
)
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from digest_core import (  # noqa: E402
    build_slack_blocks,
    parse_llm_json,
    prepend_here,
    validate_and_count,
    validate_llm_output,
)


def _record(item_id, feature, status, priority, owner, last_updated=None, **extra):
    fields = {
        "Item ID": item_id,
        "Feature": feature,
        "Status": status,
        "Priority": priority,
        "Owner": owner,
        "Last Updated": last_updated or datetime.now(timezone.utc).date().isoformat(),
        **extra,
    }
    return {"id": f"rec_{item_id}", "fields": fields}


# --------------------------------------------------------------------------- counting

def test_validate_and_count_basic_counts():
    records = [
        _record("RM-1", "Feature A", "In Progress", "High", "Ravi"),
        _record("RM-2", "Feature B", "Blocked", "High", "Priya"),
        _record("RM-3", "Feature C", "Not Started", "Medium", "Karan"),
    ]
    result = validate_and_count(records)
    assert result["record_count"] == 3
    assert result["high_count"] == 2
    assert result["blocked_count"] == 1
    assert result["blocked_ids"] == ["RM-2"]


def test_validate_and_count_empty_input_raises():
    with pytest.raises(ValueError):
        validate_and_count([])


def test_validate_and_count_skips_missing_required_fields():
    records = [
        _record("RM-1", "Feature A", "In Progress", "High", "Ravi"),
        {"id": "rec_bad", "fields": {"Item ID": "RM-2", "Feature": "", "Status": "Blocked",
                                      "Priority": "High", "Owner": "Priya"}},
    ]
    result = validate_and_count(records)
    assert result["record_count"] == 1
    assert result["skipped_count"] == 1


def test_validate_and_count_all_invalid_raises():
    records = [
        {"id": "rec_bad", "fields": {"Item ID": "RM-1", "Feature": "", "Status": "Blocked",
                                      "Priority": "High", "Owner": ""}},
    ]
    with pytest.raises(ValueError):
        validate_and_count(records)


def test_stale_flag_set_after_threshold():
    old_date = (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
    records = [_record("RM-1", "Old feature", "Not Started", "Low", "Karan", last_updated=old_date)]
    result = validate_and_count(records)
    assert result["stale_count"] == 1
    assert result["records"][0]["stale"] is True


def test_mention_here_true_only_above_five_high():
    records = [_record(f"RM-{i}", f"Feature {i}", "In Progress", "High", "Ravi") for i in range(6)]
    assert validate_and_count(records)["mention_here"] is True

    records = [_record(f"RM-{i}", f"Feature {i}", "In Progress", "High", "Ravi") for i in range(5)]
    assert validate_and_count(records)["mention_here"] is False


# --------------------------------------------------------------------------- validation

def _counts_stub(high_count=1, blocked_count=1):
    return {"high_count": high_count, "blocked_count": blocked_count}


def test_validate_llm_output_accepts_matching_counts():
    digest = {
        "executive_summary": "Everything is fine.",
        "high_priority_items": [{"item_id": "RM-1", "feature": "A", "why_it_matters": "Because."}],
        "blocked_items": [{"item_id": "RM-2", "feature": "B", "blocker": "x", "suggested_action": "y"}],
        "recommendations": ["Do the thing."],
    }
    out = validate_llm_output(digest, _counts_stub())
    assert out["executive_summary"] == "Everything is fine."


def test_validate_llm_output_rejects_count_mismatch():
    digest = {
        "executive_summary": "Summary.",
        "high_priority_items": [],  # deterministic count says 1 — mismatch
        "blocked_items": [{"item_id": "RM-2", "feature": "B", "blocker": "x", "suggested_action": "y"}],
        "recommendations": ["Do the thing."],
    }
    with pytest.raises(ValueError):
        validate_llm_output(digest, _counts_stub())


def test_validate_llm_output_rejects_missing_recommendations():
    digest = {
        "executive_summary": "Summary.",
        "high_priority_items": [{"item_id": "RM-1", "feature": "A", "why_it_matters": "Because."}],
        "blocked_items": [{"item_id": "RM-2", "feature": "B", "blocker": "x", "suggested_action": "y"}],
        "recommendations": [],
    }
    with pytest.raises(ValueError):
        validate_llm_output(digest, _counts_stub())


def test_parse_llm_json_strips_markdown_fences():
    raw = '```json\n{"a": 1}\n```'
    assert parse_llm_json(raw) == {"a": 1}


def test_validate_llm_output_accepts_raw_json_string():
    raw = (
        '{"executive_summary": "ok", '
        '"high_priority_items": [{"item_id": "RM-1", "feature": "A", "why_it_matters": "b"}], '
        '"blocked_items": [], "recommendations": ["do it"]}'
    )
    out = validate_llm_output(raw, _counts_stub(high_count=1, blocked_count=0))
    assert out["executive_summary"] == "ok"


# --------------------------------------------------------------------------- Slack blocks

def test_build_slack_blocks_includes_header_and_counts():
    counts = validate_and_count([
        _record("RM-1", "Feature A", "In Progress", "High", "Ravi"),
        _record("RM-2", "Feature B", "Blocked", "High", "Priya"),
    ])
    digest = {
        "executive_summary": "Summary.",
        "high_priority_items": [
            {"item_id": "RM-1", "feature": "Feature A", "why_it_matters": "x", "owner": "Ravi", "target_quarter": "Q3"},
            {"item_id": "RM-2", "feature": "Feature B", "why_it_matters": "y", "owner": "Priya", "target_quarter": "Q3"},
        ],
        "blocked_items": [
            {"item_id": "RM-2", "feature": "Feature B", "blocker": "x", "suggested_action": "y", "owner": "Priya"},
        ],
        "recommendations": ["Ship it."],
    }
    payload = build_slack_blocks(digest, counts)
    assert payload["blocks"][0]["type"] == "header"
    assert payload["high_count"] == 2
    assert payload["blocked_count"] == 1
    assert "2" in payload["notification_text"]


def test_prepend_here_adds_here_token_and_updates_notification():
    payload = {"blocks": [{"type": "divider"}], "notification_text": "Daily Roadmap Digest — 6 High"}
    out = prepend_here(payload, high_count=6)
    assert out["blocks"][0]["text"]["text"].startswith("<!here>")
    assert out["notification_text"].startswith("@here")
    # original payload's blocks are preserved after the new mention block
    assert out["blocks"][1] == {"type": "divider"}
