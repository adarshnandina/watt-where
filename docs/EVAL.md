# Evaluation

25 questions in 5 categories, run through the agent loop against the real data. Expected values are computed from the database by `backend/eval/ground_truth.py` (hand-written SQL, independent of the tools), never typed in.

Checks: **numeric accuracy** (counts exact, other figures within 1%), **tool correctness**, **caveat compliance**, **out-of-scope handling**, **language**. A question passes only if every applicable check passes.

## Runs

| Run | Model | Date | Prompt/tools hash | Overall | Lookup | Ranking | Spatial | Timeseries | Edge | Avg latency | Avg tokens (in/out) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | claude-haiku-5-5 | 2026-11-24 | `bc08887bff` | **22/25 (88%)** | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 3/5 (60%) | 4/5 (80%) | 3.8 s | 1,644 / 488 |
| baseline-fixed-eval | claude-haiku-5-5 | 2026-11-24 | `bc08887bff` | **24/25 (96%)** | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 4/5 (80%) | 5/5 (100%) | 4.1 s | 2,019 / 520 |
| improved | claude-haiku-5-5 | 2026-11-24 | `0e06fc58f8` | **25/25 (100%)** | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 4.2 s | 2,193 / 532 |
| improved-rerun | claude-haiku-5-5 | 2026-11-24 | `0e06fc58f8` | **25/25 (100%)** | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) | 3.9 s | 1,831 / 479 |

## What changed between runs

Model for all runs: `claude-haiku-5-5` (the cheap development model). Each run is a single pass; the model is not deterministic, so treat differences of one question as noise-level evidence. That is why the final configuration was run twice.

| Step | Run | Result | What changed |
|---|---|---|---|
| 1 | `baseline` | 22/25 | First run of the initial prompt and tools. |
| 2 | `baseline-fixed-eval` | 24/25 | **Eval fixes only, same prompt.** Two of the three baseline failures were mistakes in my eval, not in the app: (a) *edge-5-sql*: the model correctly applied the documented default "units in operation" (87 units) but my ground-truth SQL counted units of every status (159), so the truth now uses the same default; (b) *time-2* ("added in 2022"): the number was right and `capacity_summary` with date filters is a valid way to answer, so any of `capacity_timeseries`/`capacity_summary` now counts. |
| 3 | `improved` | 25/25 | **Prompt and tool-description fix** for the one real failure (*time-4*, "installed at the end of 2020"). The model used `capacity_summary` with a date filter, which only sees units still operating today, so it silently ignored capacity decommissioned since then (6,216 MW vs. a true 6,267 MW; it landed inside the 1% tolerance by luck, but the method was wrong). The system prompt now routes historical-total and growth questions to `capacity_timeseries`, and the `capacity_summary` description says it shows the current state only. |
| 4 | `improved-rerun` | 25/25 | Same configuration again, to check stability. |

**Lesson:** the first thing the eval taught me was about the eval itself. Failures need triage (bad question? bad ground truth? bad prompt?) before any prompt change. The one genuine failure was a *method* error that a numeric tolerance alone would have hidden, which is why the tool-correctness check exists.

**Other thing a live run found that fake-client tests could not:** the model can return `thinking` content blocks, which must be passed back unchanged after a tool call. The loop crashed on them until fixed (`test_thinking_blocks_are_passed_back_unchanged_after_tool_use`).

## Details: `improved`

All questions passed.

## Details: `improved-rerun`

All questions passed.
