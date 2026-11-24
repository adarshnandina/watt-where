Model for all runs: `claude-haiku-5-5` (the cheap development model). Each run is a single pass; the model is not deterministic, so treat differences of one question as noise-level evidence. That is why the final configuration was run twice.

| Step | Run | Result | What changed |
|---|---|---|---|
| 1 | `baseline` | 22/25 | First run of the initial prompt and tools. |
| 2 | `baseline-fixed-eval` | 24/25 | **Eval fixes only, same prompt.** Two of the three baseline failures were mistakes in my eval, not in the app: (a) *edge-5-sql*: the model correctly applied the documented default "units in operation" (87 units) but my ground-truth SQL counted units of every status (159), so the truth now uses the same default; (b) *time-2* ("added in 2022"): the number was right and `capacity_summary` with date filters is a valid way to answer, so any of `capacity_timeseries`/`capacity_summary` now counts. |
| 3 | `improved` | 25/25 | **Prompt and tool-description fix** for the one real failure (*time-4*, "installed at the end of 2020"). The model used `capacity_summary` with a date filter, which only sees units still operating today, so it silently ignored capacity decommissioned since then (6,216 MW vs. a true 6,267 MW; it landed inside the 1% tolerance by luck, but the method was wrong). The system prompt now routes historical-total and growth questions to `capacity_timeseries`, and the `capacity_summary` description says it shows the current state only. |
| 4 | `improved-rerun` | 25/25 | Same configuration again, to check stability. |

**Lesson:** the first thing the eval taught me was about the eval itself. Failures need triage (bad question? bad ground truth? bad prompt?) before any prompt change. The one genuine failure was a *method* error that a numeric tolerance alone would have hidden, which is why the tool-correctness check exists.

**Other thing a live run found that fake-client tests could not:** the model can return `thinking` content blocks, which must be passed back unchanged after a tool call. The loop crashed on them until fixed (`test_thinking_blocks_are_passed_back_unchanged_after_tool_use`).
