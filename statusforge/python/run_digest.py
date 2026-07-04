"""Entry point: load the roadmap CSV, run the LangGraph agent, print the result, and
save a picture of the graph (graph.png / graph.mmd) for the write-up and live demo.

    python run_digest.py

Env (via .env): OPENAI_API_KEY required. SLACK_BOT_TOKEN + SLACK_CHANNEL_ID optional
(if set, it actually posts; otherwise it does a dry run and just prints).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from dotenv import load_dotenv

from agent_graph import build_graph

load_dotenv()

CSV_PATH = Path(__file__).resolve().parent.parent / "roadmap_airtable_export.csv"


def load_records() -> list[dict]:
    """Read the CSV into Airtable-style rows. The known-malformed RM-111 row (unquoted
    commas in Description) parses with its required fields intact, so counts are safe —
    the same dirty-data resilience the pipeline is built for."""
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return [dict(row) for row in csv.DictReader(f)]


def main() -> None:
    graph = build_graph()

    # Save the orchestration diagram — this is your "depiction" of the LangGraph.
    Path("graph.mmd").write_text(graph.get_graph().draw_mermaid(), encoding="utf-8")
    try:
        Path("graph.png").write_bytes(graph.get_graph().draw_mermaid_png())
        print("Saved graph.png + graph.mmd")
    except Exception as e:  # png rendering needs network (mermaid.ink); text always works
        print(f"Saved graph.mmd (png skipped: {e})")

    result = graph.invoke({"records": load_records()})

    counts = result["counts"]
    print(f"\nrecords={counts['record_count']}  high={counts['high_count']}  "
          f"blocked={counts['blocked_count']}  mention_here={counts['mention_here']}  "
          f"summarize_attempts={result.get('attempts')}")

    if result.get("digest"):
        print("\n=== DIGEST ===")
        print(json.dumps(result["digest"], indent=2))
    else:
        print("\nFAILED after retries:", result.get("error"))


if __name__ == "__main__":
    main()
