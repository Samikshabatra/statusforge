"""Turn an exported n8n workflow JSON into a Graphviz DOT diagram.

Every node and every connection comes from the export itself — nothing is hand-drawn —
so the picture is exactly the workflow that runs.
"""
from __future__ import annotations

import json

IO, DET, LLM, MODEL = "#cdd7ff", "#b6f0e2", "#ffd3c7", "#ffe9e2"

SERVICE = {
    "airtable": "Airtable", "slack": "Slack", "gmail": "Gmail",
}


def _short(node_type: str) -> str:
    return node_type.rsplit(".", 1)[-1]


def _fill(node_type: str) -> str:
    t = _short(node_type)
    if t == "lmChatOpenAi":
        return MODEL
    if t == "chainLlm":
        return LLM
    if t in ("code", "if", "merge"):
        return DET
    return IO


def _label(node: dict) -> str:
    t, p, name = _short(node["type"]), node.get("parameters", {}), node["name"]
    if t in SERVICE:
        return f"{name}\n({SERVICE[t]})"
    if t == "if":
        return f"{name} (IF)"
    if t == "scheduleTrigger":
        hour = ((p.get("rule", {}).get("interval") or [{}])[0]).get("triggerAtHour")
        return f"{name}\n(daily {hour:02d}:00)" if isinstance(hour, int) else name
    if t == "webhook":
        return f"{name}\n({p.get('httpMethod', 'GET')} /{p.get('path', '')})"
    if t == "lmChatOpenAi":
        m = p.get("model", {})
        return f"{name}\n({m.get('value', '') if isinstance(m, dict) else m})"
    return name


def _q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # a valid DOT double-quoted string


def to_dot(data: dict, nodesep: float = 0.25, ranksep: float = 0.4) -> str:
    nodes = {n["name"]: n for n in data.get("nodes", [])}
    lines = [
        "digraph G {",
        f'  rankdir=LR; bgcolor="transparent"; pad=0.2; nodesep={nodesep}; ranksep={ranksep};',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=13,',
        '        color="#2b2b2b", penwidth=1.2, fontcolor="#14202b", margin="0.12,0.06"];',
        '  edge [color="#8791a6", fontname="Helvetica", fontsize=10, fontcolor="#9aa4b8", arrowsize=0.75];',
    ]
    for name, n in nodes.items():
        extra = ', style="rounded,filled,dashed"' if n.get("disabled") else ""
        lines.append(f"  {_q(name)} [label={_q(_label(n))}, fillcolor=\"{_fill(n['type'])}\"{extra}];")

    same_rank = []
    for src, by_kind in data.get("connections", {}).items():
        s = nodes.get(src)
        if not s:
            continue
        for kind, outputs in by_kind.items():
            for i, targets in enumerate(outputs):
                for t in targets or []:
                    if t["node"] not in nodes:
                        continue
                    attrs = []
                    if kind != "main":
                        # model sub-node → the agent it powers; keep it in the agent's column
                        attrs += ['style="dashed"', 'color="#c98a78"', "arrowhead=none"]
                        same_rank.append((src, t["node"]))
                    elif _short(s["type"]) == "if":
                        attrs.append(f'label="{"true" if i == 0 else "false"}"')
                    elif s.get("onError") == "continueErrorOutput" and i == len(outputs) - 1:
                        svc = SERVICE.get(_short(s["type"]), "node")
                        attrs += [f'label="if {svc} fails"', 'style="dashed"']
                    a = f" [{', '.join(attrs)}]" if attrs else ""
                    lines.append(f"  {_q(src)} -> {_q(t['node'])}{a};")

    # a model that feeds several agents shares one column with all of them
    groups: dict[str, list[str]] = {}
    for model, agent in same_rank:
        groups.setdefault(model, []).append(agent)
    for model, agents in groups.items():
        lines.append(f"  {{ rank=same; {'; '.join(_q(x) for x in [agents[0], model, *agents[1:]])}; }}")
    lines.append("}")
    return "\n".join(lines)
