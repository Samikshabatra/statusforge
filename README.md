# ⚒️ StatusForge

**An agentic Slack digest for product roadmaps — shipped two ways.**

Every day, StatusForge pulls the roadmap table out of Airtable, runs it through a
multi-agent LLM pipeline (progress + risk analysis → conditional dependency check →
ranked executive summary), validates the model's output against deterministic counts,
and posts a formatted digest to Slack — with an automatic failure ladder if anything
breaks.

The same architecture is built **twice**, on purpose:

| | What it is | Where |
|---|---|---|
| 🔧 **n8n workflow** | The shipped, production automation — runs on a schedule, posts to Slack, alerts on failure | [`workflows/`](./workflows) |
| 🕸️ **LangGraph agent** | The identical orchestration expressed as a real, version-controlled `StateGraph` — supervisor → specialists → synthesizer | [`python/`](./python) |

**Live demo (Streamlit):** https://statusforge-hnr6zkh3p4ajcoglkwu7dh.streamlit.app/

---

## Why two implementations?

n8n is what actually runs in production — reliable, scheduled, low-maintenance. But a
visual canvas hides the *agentic* part of the pipeline inside opaque LLM nodes. The
LangGraph version pulls that reasoning out into inspectable, testable Python: the same
supervisor → specialist → synthesizer graph, as code.

They intentionally diverge on **one thing** — how they handle a model that produces
invalid output:

- **n8n**: fails loud, routes to a separate error-handler workflow, alerts `#digest-admin`, falls back to email if Slack itself is down.
- **LangGraph**: retries by looping back to the summarizer with the validation error (self-correction, up to 3 attempts), *then* raises the same way.

Both are valid reliability strategies for the same failure. Neither README pretends they're identical.

## The one design rule everything else follows

> **Counts and the `@here` decision are deterministic. The LLM only narrates. The
> narration is validated back against the counts.**

Concretely: a plain-Python function (`validate_and_count` / `digest_core.py`) is the
single source of truth for every number in the digest — item counts, high-priority
count, blocked count, staleness, and the `@here` mention decision (`high_count > 5`).
The LLM agents only ever produce prose and structured JSON *about* those numbers.
`validate_llm_output` cross-checks the model's item lists against the deterministic
counts and rejects the digest if they disagree — the model literally cannot alter what
gets reported.

## Architecture

```
Airtable → Validate + Count (deterministic) ──┬─→ Progress Agent (LLM)   ┐
                                                └─→ Risk Analysis Agent (LLM) ┘
                                                            │
                                                       Supervisor (LLM)
                                                 "need a dependency pass?"
                                                       YES ╱      ╲ NO
                                        Dependency Agent (LLM)     │
                                                       └──────┬────┘
                                                     Summarize & Rank (LLM)
                                                              │
                                          Validate LLM Output (deterministic) ──fail──┐
                                                              │ ok                self-correct / alert
                                                    Build Slack Blocks (deterministic)
                                                              │
                                             High Count > 5? ─┴─→ Prepend @here
                                                              │
                                                    Post Digest → #roadmap-digest
```

The exact rendered graph (from the LangGraph run) is at
[`python/graph.png`](./python/graph.png) / [`python/graph.mmd`](./python/graph.mmd).

## Where LangChain / LangGraph actually show up

| Piece | Framework | File |
|---|---|---|
| `StateGraph`, nodes, conditional edges, retry loop, fan-out/fan-in | **LangGraph** | `python/agent_graph.py` |
| `ChatPromptTemplate` (system + human) for every agent | **LangChain** | `python/agent_prompts.py` |
| `ChatOpenAI`, `prompt \| llm` invoke | **LangChain** | `python/agent_graph.py` |
| Deterministic counting / validation / Slack Block Kit | plain Python (no framework) | `python/digest_core.py` |

## Repository structure

```
statusforge/
├── README.md                     ← you are here
├── roadmap_airtable_export.csv   ← sample data (mirrors the live Airtable base)
├── workflows/
│   ├── Roadmap Slack Digest.json      ← the main n8n workflow (exported)
│   └── Digest Error Handler.json      ← the error-handler workflow (exported)
├── python/
│   ├── README.md                 ← deep dive on the LangGraph implementation
│   ├── app.py                    ← Streamlit dashboard (overview, workflow, inspector, LangGraph, data, docs)
│   ├── app_legacy.py             ← the previous two-tab Streamlit demo
│   ├── ui_theme.py               ← dashboard CSS, icons and hero backdrop
│   ├── workflow_dot.py           ← draws the n8n workflows straight from their JSON exports
│   ├── agent_graph.py             ← the StateGraph: nodes + conditional edges
│   ├── agent_prompts.py           ← ChatPromptTemplate for every agent
│   ├── digest_core.py             ← deterministic core (counts, validation, Block Kit)
│   ├── run_digest.py               ← CLI entry point; renders graph.png
│   ├── requirements.txt
│   └── .env.example
├── tests/
│   └── test_digest_core.py        ← unit tests for the deterministic core
└── docs/assets/                   ← screenshots referenced below
```

> **Note on this repo's layout:** everything currently sits one level down inside a
> `statusforge/` folder at the repo root (an artifact of the initial upload). Functionally
> this doesn't break anything — but for submission, flattening it so `README.md`,
> `workflows/`, `python/`, and `roadmap_airtable_export.csv` sit directly at the repo
> root (instead of inside a nested `statusforge/statusforge/…`) will make the repo read
> cleanly the moment a reviewer opens it. See the **Cleanup checklist** at the bottom.

## Running it

```bash
cd python
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
copy .env.example .env        # add your OPENAI_API_KEY
python run_digest.py
```

This prints the deterministic counts + the validated digest JSON, and writes
`graph.png` / `graph.mmd`. If `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` are also set, it
posts the digest live; otherwise it dry-runs and just prints.

To run the interactive dashboard instead:

```bash
cd python
streamlit run app.py
```

To run the unit tests:

```bash
cd python
pip install pytest
pytest ../tests -v
```

## Data

`roadmap_airtable_export.csv` is a sample export mirroring the schema of the live
Airtable base (`Item ID, Feature, Status, Priority, Owner, Target Quarter, Description,
Last Updated`). One row is intentionally malformed (unquoted commas in `Description`)
to demonstrate that `validate_and_count` handles dirty data without breaking the counts.

## Failure handling (n8n)

| Failure | Response |
|---|---|
| A node fails transiently | Per-node retry, 3× with backoff |
| A node fails hard | The **Digest Error Handler** workflow fires, alerting `#digest-admin` |
| Slack itself is unreachable | Falls back to email |
| The model breaks the output schema | `Validate LLM Output` throws → routed to the error workflow |

## Screenshots

**The main workflow — 15 stages, Airtable → agents → Slack:**

![n8n main workflow](./docs/assets/n8n-main-workflow.png)

**The error-handler workflow — Slack alert with Gmail fallback:**

![n8n error handler](./docs/assets/n8n-error-handler-workflow.png)

**A posted digest in `#roadmap-digest` — executive summary + ranked high-priority items:**

![Digest executive summary](./docs/assets/slack-digest-executive-summary.png)

**...continued — blocked items with suggested actions, and recommendations:**

![Digest blocked items and recommendations](./docs/assets/slack-digest-blocked-recommendations.png)

**The `#digest-admin` audit log — successful runs and a caught failed run, side by side:**

![digest-admin log](./docs/assets/slack-digest-admin-log.png)

## Cleanup checklist before final submission

A few small things worth fixing before this goes in front of a reviewer:

- [ ] **Flatten the folder structure** — move `python/`, `workflows/`, `roadmap_airtable_export.csv`, `.gitignore`, and this `README.md` up so they sit directly at the repo root, rather than nested inside an extra `statusforge/` folder.
- [ ] **Redact the personal email in `workflows/Digest Error Handler.json`** — the Gmail fallback node's `sendTo` field currently has a real personal email address hardcoded. Replace it with a placeholder (e.g. `your-alert-inbox@example.com`) before the JSON goes into a public repo, or better, note in the README that it should be set via an n8n environment variable / credential instead of inline.
- [ ] **Add a top-level `.gitignore`** covering `.env`, `__pycache__/`, `.venv/`, and `.streamlit/secrets.toml` (the one in `python/.gitignore` should move to repo root if flattening).
- [ ] Double-check no other webhook URLs, tokens, or personal identifiers are exported inside the workflow JSON files (n8n credential *references* are fine — they're just IDs/names, not secrets — but scan for anything hardcoded in node parameters).

---

*For the deeper technical write-up of the LangGraph implementation specifically —
including the exact node-by-node design rationale — see [`python/README.md`](./python/README.md).*
