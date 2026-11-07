# Eval results

![Hard questions answered fully right, by model and setup](../docs/img/eval_hard_questions.png)

Claude answered each question through the MCP server two ways: with SQL tools only, or with the dbt metrics preferred. An answer counts as right when its number matches the reference SQL and it makes the caveat the question needs. Claude Opus 5.5 grades the caveat.

| Model | Questions | Runs | SQL only | Semantic layer first |
|---|---|---|---|---|
| Opus 5.5 | 20 easy | 1 | 20/20 | 20/20 |
| Opus 5.5 | 10 hard | 3 | 30/30 | 30/30 |
| Haiku 5.5 | 10 hard | 3 | 26/30 | 29/30 |
| Haiku 5.5 | 20 easy | 3 | 56/60 | 57/60 |

Haiku's misses on the easy set are rounding (0.4 for 0.404).

## What it showed

- **Opus got everything right either way.** With documented tables, the semantic layer didn't change its accuracy.
- **Haiku is where the semantic layer helped.** Asked whether new lanes make streets more dangerous, SQL-only Haiku never mentioned that more people ride after a lane opens, in 3 of 3 runs. With the metric, that caveat came along.
- **The eval caught mistakes on my side.** Two answers I first marked wrong were better than my key. One compared summer and fall together, the seasons counted in both years. The other noticed that `fct_nyc_new_lane_safety` counts a crash once for every nearby segment, recounted Staten Island by distinct crash (3 after, 1 before, not 13 and 1), and got +200% instead of +1,200%. Both are now accepted answers, and the results were re-graded. The double count is a known issue in that mart.

The hard questions are in [questions_hard.yml](questions_hard.yml). Each one has a trap: a partial year, mixed seasons, two locations with the same street name, a 12-month data window, or numbers too small to mean anything.

## Cost

| Run | Answers | Cost |
|---|---|---|
| Opus, easy | 40 | $4.14 |
| Opus, hard | 60 | $7.69 |
| Haiku, hard | 60 | $0.48 |
| Haiku, easy | 120 | $0.29 |
| Smoke tests | 6 | $0.42 |
| **Total** | **286** | **$13.02** |

Includes grading. Priced at list rates ($4 / $20 per million input / output tokens for Opus 5.5, $0.10 / $0.50 for Haiku 5.5). Paid from the monthly API credits included with a Claude Max plan.

## Running it

```bash
uv run --group eval python evals/run_eval.py --dry-run                                   # expected answers, free
uv run --group eval python evals/run_eval.py --questions questions_hard.yml --repeats 3  # about $8 on Opus
uv run --group eval python evals/run_eval.py --model claude-haiku-5-5                    # about $0.10
uv run --group eval python evals/run_eval.py --regrade evals/results/<file>.json         # after changing the key
uv run --group docs python docs/charts.py                                                # redraw the chart
```

Needs `ANTHROPIC_API_KEY` in `.env` and the stack running. Raw answers and grades are in [results/](results/).

## Next

- Fix the double count: a mart with one row per crash near a new lane.
- Spot-check the model grader against my own reading of a sample of answers.
- Questions with no single right number, where the right answer is "the data can't say".
