# StatusForge — LangGraph version

The n8n workflow's architecture, expressed as a **LangGraph `StateGraph`** so the
orchestration is real, inspectable code. The n8n workflow is the *shipped automation*;
this is the *agent core* — supervisor → specialists → synthesizer.

**One intentional divergence:** on invalid LLM output this graph **self-corrects** (loops
back to `summarize` with the error, up to 3×, then raises), whereas the n8n workflow
**fails loud and alerts** via its error-workflow. Two valid reliability strategies — not
the same mechanism, and this README doesn't pretend they are.

## Design rule (the load-bearing decision)

**Counts and the `@here` decision are deterministic; the LLM only narrates; the output is
validated back against the counts; failure self-corrects, then fails loudly.**

- `validate_and_count` (in `digest_core.py`) is the single source of truth for every number.
- The specialists (progress/risk/dependency) and the synthesizer only produce prose/JSON.
- `validate_llm_output` rejects any digest whose item counts disagree with the deterministic
  counts — the model literally cannot alter the numbers.
- On validation failure the graph loops back to `summarize` with the error (self-correction),
  up to 3 times, then routes to a `fail` node that **raises** — no silent no-post.

## Run it

```bash
cd python
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
copy .env.example .env                               # add OPENAI_API_KEY
python run_digest.py
```

Prints the counts + validated digest and writes **`graph.png`** / `graph.mmd`. With
`SLACK_BOT_TOKEN` + `SLACK_CHANNEL_ID` set it posts to Slack; otherwise it dry-runs.

## The orchestration (see graph.png)

```
START → count → progress ┐
               └ risk ────┴→ supervisor ─(YES)→ dependency ┐
                                  │ (NO)                    │
                                  └──────────────────────────┴→ summarize
                                                                 │  ▲ (retry: self-correction)
                                     validate_llm ─(ok)→ build_blocks → route_mention
                                          │ (fail x3 → raise)          ╱(mention)  ╲(normal)
                                          ▼                       add_here          post → END
```

Conditional edges: **supervisor** YES/NO (fuzzy routing), **self-correction** loop on
validation failure, and the **`@here`** branch (deterministic).

## Where LangChain / LangGraph show up

| Piece | Framework | File |
|---|---|---|
| `StateGraph`, nodes, conditional edges, loop, fan-out/fan-in | **LangGraph** | `agent_graph.py` |
| `ChatPromptTemplate` (system + human) for every agent | **LangChain** | `agent_prompts.py` |
| `ChatOpenAI`, `prompt \| llm` invoke | **LangChain** | `agent_graph.py` |
| Deterministic counting / validation / Block Kit | plain Python | `digest_core.py` |

## Submission contents

`agent_graph.py`, `agent_prompts.py`, `digest_core.py`, `run_digest.py`,
`requirements.txt`, `.env.example`, the rendered **`graph.png`**, and this README.

_Add execution screenshots here_: the terminal output of `run_digest.py` (counts + digest)
and `graph.png`, plus the n8n canvas + a posted Slack message.
