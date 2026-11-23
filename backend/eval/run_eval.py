"""Run the evaluation questions through the agent loop (not HTTP) and score the answers.

    uv run python -m eval.run_eval --label baseline          # run + write eval/results/baseline.json + docs/EVAL.md
    uv run python -m eval.run_eval --truth-only              # print the ground truth, no LLM, no API key needed
    uv run python -m eval.run_eval --report                  # just regenerate docs/EVAL.md from saved runs
    uv run python -m eval.run_eval --only lookup-1 spatial-1 # subset

Needs the REAL data in the database and ANTHROPIC_API_KEY. Not part of `make test`.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

import yaml  # noqa: E402
from django.conf import settings  # noqa: E402

from agent.loop import make_client, run_agent  # noqa: E402
from agent.prompts import SYSTEM_TEMPLATE, build_system_prompt  # noqa: E402
from energy.textnorm import normalize_name  # noqa: E402
from energy.tools import anthropic_tool_definitions  # noqa: E402
from eval import ground_truth  # noqa: E402

HERE = Path(__file__).parent
RESULTS = HERE / "results"
REPORT = settings.REPO_ROOT / "docs" / "EVAL.md"
EXACT_KEYS = {"units", "population", "year"}
CATEGORIES = ["lookup", "ranking", "spatial", "timeseries", "edge"]

_NUM = re.compile(r"\d[\d.,]*\d|\d")


# ---------- number extraction / matching ----------
def numbers_in(text: str) -> list[float]:
    """All numbers in `text`, tolerant of 1,234.5 / 1.234,5 / 9.854 formats.

    A lone "9.854" is ambiguous (decimal in English, thousands in German), so both readings are returned.
    """
    vals: list[float] = []
    for s in _NUM.findall(text.replace("\u202f", "").replace("\u00a0", "")):
        if "," in s and "." in s:
            dec = "," if s.rfind(",") > s.rfind(".") else "."
            thousands = "." if dec == "," else ","
            vals.append(float(s.replace(thousands, "").replace(dec, ".")))
        elif "," in s:
            if re.fullmatch(r"\d{1,3}(,\d{3})+", s):
                vals.append(float(s.replace(",", "")))  # 9,854 -> 9854 (English thousands)
            else:
                vals.append(float(s.replace(",", ".")))  # 103,8 -> 103.8 (German decimal)
        elif "." in s:
            vals.append(float(s))
            if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
                vals.append(float(s.replace(".", "")))  # 9.854 -> 9854 (German thousands)
        else:
            vals.append(float(s))
    return vals


def number_matches(expected: float, text: str, exact: bool) -> bool:
    """exact: integer equality (counts). Otherwise within 1% (also accepting kW<->MW phrasing)."""
    for v in numbers_in(text):
        if exact:
            if abs(v - expected) < 0.5:
                return True
        elif expected == 0:
            if abs(v) < 0.05:
                return True
        elif any(abs(c - expected) / abs(expected) <= 0.01 for c in (v, v * 1000, v / 1000)):
            return True
    return False


# ---------- scoring ----------
GERMAN_MARKERS = [" ist ", " die ", " der ", " das ", " und ", " sind ", "leistung", "installiert", " wurden ", " mit "]
FIGURE = re.compile(r"\d[\d.,]*\s*(mw|gw|kw|mwh|kwh|einheiten|units|cent|ct|€|eur)\b", re.I)


def score(q: dict, truth: dict, answer: str, tools_called: list[str]) -> dict:
    checks: dict[str, dict] = {}
    low = f" {answer.lower()} "

    def add(name: str, ok: bool, detail: str = ""):
        checks[name] = {"ok": ok, "detail": detail}

    exact_keys = EXACT_KEYS | set(q.get("exact_keys", []))
    for key in q.get("expect_numbers", []):
        exp = float(truth[key])
        add(f"number:{key}", number_matches(exp, answer, key in exact_keys), f"expected {exp:,.4g}")
    if q.get("expect_names"):
        names = truth[q["expect_names"]]
        missing = [n for n in names if normalize_name(n) not in normalize_name(answer)]
        add("names", not missing, f"missing {missing}" if missing else f"all {len(names)} present")
    if q.get("expected_tools"):
        missing = [t for t in q["expected_tools"] if t not in tools_called]
        add("tools", not missing, f"missing {missing}; called {tools_called}" if missing else "")
    if q.get("forbid_tools"):
        bad = [t for t in tools_called if t in q["forbid_tools"]]
        add("no_forbidden_tools", not bad, f"called {bad}" if bad else "")
    for group in q.get("must_mention_any", []):
        add("caveat:" + "/".join(group), any(p.lower() in low for p in group), f"none of {group}")
    if q.get("language") == "de":
        hits = sum(m in low for m in GERMAN_MARKERS)
        add("language_de", hits >= 3, f"{hits} German markers")
    if q.get("out_of_scope"):
        add(
            "declines_without_figures",
            not FIGURE.search(answer) and not tools_called,
            "answer contains figures or tools were called",
        )
    return {"passed": all(c["ok"] for c in checks.values()), "checks": checks}


# ---------- running ----------
def load_questions(only: list[str] | None) -> list[dict]:
    qs = yaml.safe_load((HERE / "questions.yaml").read_text())
    return [q for q in qs if not only or q["id"] in only]


def compute_truth(q: dict) -> dict:
    t = q["truth"]
    return getattr(ground_truth, t["fn"])(**t.get("args", {}))


async def ask(question: str, client, system_prompt: str) -> dict:
    started = time.monotonic()
    text, tools, usage, errors, stop = [], [], {}, [], None
    async for etype, data in run_agent([{"role": "user", "content": question}], system_prompt, client):
        if etype == "text_delta":
            text.append(data["text"])
        elif etype == "tool_call":
            tools.append(data["name"])
        elif etype == "error":
            errors.append(data["message"])
        elif etype == "message_end":
            usage, stop = data["usage"], data["stop_reason"]
    return {"answer": "".join(text), "tools": tools, "usage": usage, "errors": errors, "stop_reason": stop,
            "latency_s": round(time.monotonic() - started, 2)}  # fmt: skip


def prompt_fingerprint() -> str:
    blob = SYSTEM_TEMPLATE + json.dumps(anthropic_tool_definitions(), sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:10]


def run(label: str, only: list[str] | None) -> None:
    client = make_client()
    if client is None:
        sys.exit("ANTHROPIC_API_KEY is not set in .env - cannot run the eval.")
    system_prompt = build_system_prompt()
    questions = load_questions(only)
    items = []
    for q in questions:
        truth = compute_truth(q)
        r = asyncio.run(ask(q["question"], client, system_prompt))
        s = score(q, truth, r["answer"], r["tools"])
        if r["errors"]:
            s["passed"] = False
            s["checks"]["no_errors"] = {"ok": False, "detail": "; ".join(r["errors"])}
        items.append({"id": q["id"], "category": q["category"], "question": q["question"], "truth": truth, **r, **s})
        print(
            f"{'PASS' if s['passed'] else 'FAIL'}  {q['id']:22s} {r['latency_s']:5.1f}s  tools={r['tools']}", flush=True
        )
    RESULTS.mkdir(exist_ok=True)
    out = {"label": label, "model": settings.ANTHROPIC_MODEL, "timestamp": datetime.now().isoformat(timespec="seconds"),
           "prompt_fingerprint": prompt_fingerprint(), "items": items}  # fmt: skip
    (RESULTS / f"{label}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    write_report()
    print(f"\n{sum(i['passed'] for i in items)}/{len(items)} passed. Report: {REPORT}")


# ---------- report ----------
def rate(items: list[dict]) -> str:
    return f"{sum(i['passed'] for i in items)}/{len(items)} ({100 * sum(i['passed'] for i in items) / max(len(items), 1):.0f}%)"


def write_report() -> None:
    runs = sorted((json.loads(p.read_text()) for p in RESULTS.glob("*.json")), key=lambda r: r["timestamp"])
    if not runs:
        return
    L = ["# Evaluation", "",
         "25 questions in 5 categories, run through the agent loop against the real data. Expected values are computed "
         "from the database by `backend/eval/ground_truth.py` (hand-written SQL, independent of the tools), never typed in.",
         "", "Checks: **numeric accuracy** (counts exact, other figures within 1%), **tool correctness**, **caveat compliance**, "
         "**out-of-scope handling**, **language**. A question passes only if every applicable check passes.", "",
         "## Runs", "", "| Run | Model | Date | Prompt/tools hash | Overall | " + " | ".join(c.title() for c in CATEGORIES) + " | Avg latency | Avg tokens (in/out) |",
         "|---|---|---|---|---|" + "---|" * len(CATEGORIES) + "---|---|"]  # fmt: skip
    for r in runs:
        it = r["items"]
        avg_lat = sum(i["latency_s"] for i in it) / len(it)
        tin = sum(i["usage"].get("input_tokens", 0) for i in it) / len(it)
        tout = sum(i["usage"].get("output_tokens", 0) for i in it) / len(it)
        cats = [rate([i for i in it if i["category"] == c]) for c in CATEGORIES]
        L.append(f"| {r['label']} | {r['model']} | {r['timestamp'][:10]} | `{r['prompt_fingerprint']}` | **{rate(it)}** | "
                 + " | ".join(cats) + f" | {avg_lat:.1f} s | {tin:,.0f} / {tout:,.0f} |")  # fmt: skip
    changes = HERE / "CHANGES.md"
    if changes.exists():
        L += ["", "## What changed between runs", "", changes.read_text().strip()]
    for r in runs[-2:] if len(runs) > 1 else runs:
        L += ["", f"## Details: `{r['label']}`", ""]
        fails = [i for i in r["items"] if not i["passed"]]
        if not fails:
            L.append("All questions passed.")
        for i in fails:
            L += [f"### ❌ {i['id']}: {i['question']}", ""]
            for name, c in i["checks"].items():
                if not c["ok"]:
                    L.append(f"- **{name}** failed. {c['detail']}")
            L += [f"- Truth: `{json.dumps(i['truth'], ensure_ascii=False)}`", f"- Tools called: {i['tools']}",
                  f"- Answer: > {i['answer'].strip()[:600].replace(chr(10), ' ')}", ""]  # fmt: skip
    REPORT.write_text("\n".join(L) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--truth-only", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        write_report()
        return
    if a.truth_only:
        for q in load_questions(a.only):
            print(f"{q['id']:22s} {json.dumps(compute_truth(q), ensure_ascii=False, default=str)}")
        return
    run(a.label, a.only)


if __name__ == "__main__":
    main()
