# Approved knowledge

An AI agent should only answer from definitions their owners approved. This is a small version of that, using this project's bike data definitions. The owners and the 50 → 75 meter change below are made up; the definitions and numbers are real.

## How it works

Each concept is a markdown section with an owner ([`sources/lane-analysis/new-lanes.md`](sources/lane-analysis/new-lanes.md)):

```markdown
---
owner: lane-analysis
---

## Near a new lane
term: near_new_lane

A crash counts as near a new protected lane if it happened within about 50 meters (half a block) of the lane segment.
```

When the owner approves it, its facts (here, 50 meters) are saved in [`approved.yml`](approved.yml).

Two commands:

- **`check`** runs on every change. If only the wording changed, it passes. If a fact changed, the owner has to approve it. If another page or a dbt metric still has the old fact, it's flagged.
- **`ask`** shows what the agent is allowed to say about a concept: the owner's approved text, nothing else. There's no AI in it.

The dbt metrics name the concepts they use (`glossary_terms: [near_new_lane]` in [`_semantic.yml`](../dbt/models/marts/_semantic.yml)), so a changed definition flags them too.

## Example: 50 meters becomes 75

What's in the screenshots:

- `sed -i ...` edits the page, standing in for the owner changing it.
- `uv run bikelake-knowledge check`, `ask`, `approve`, and `fix` are this project's commands ([`src/bikelake/knowledge.py`](../src/bikelake/knowledge.py)). `uv run` runs them in the project's Python environment.
- `mf query` is MetricFlow, the open-source engine behind dbt's semantic layer. It turns a metric name into SQL and runs it on Trino.

The owner changes the number. `check` sends it to them, and `ask` still says 50:

![](img/3-fact-change.png)

The owner approves. `ask` now says 75. The FAQ (another owner's page) and a dbt metric still say 50, so they're flagged. The FAQ gets a suggested fix: a placeholder that fills in the approved number.

![](img/4-approved.png)

The FAQ owner accepts the fix. From now on the FAQ follows the definition:

![](img/5-faq-fixed.png)

This is the metric that depends on the definition, run with MetricFlow on the real data. `new_lane_injury_change` is the change in cyclists hurt within 50 meters of new lanes, 2 years after vs. before: up 17%, against 1.7% citywide. If the definition really changed to 75 meters, this is the number that would move, which is why `check` flags the metric.

![](img/6-bike-metrics.png)

## Run it

```bash
uv run bikelake-knowledge check
uv run bikelake-knowledge ask near_new_lane
uv run bikelake-knowledge demo    # the example above, in a temporary copy
```

## What's missing for a real setup

- A schedule. The check runs by hand and in GitHub Actions. A real one would be a Dagster job that asks the source systems (like WordPress or SharePoint) which pages changed since the last run, and only re-reads those.
- A language model comparing meaning. Facts are found by pattern (numbers with units, dates, dollar amounts), so "half a block" is missed, and a policy can change meaning without a number changing ("full-time students" becomes "all students"). A model could compare the two versions and say whether a fact changed, like the LLM judge in [the eval](../evals/).
- A place for owners to approve. Here approval is a command. In a catalog like OpenMetadata, each office could be the reviewer for its glossary terms, so a changed term waits as a draft until they approve it.
- A real agent. `ask` takes a concept, not a question. An agent would match the question to a concept, then answer from the approved text, for example through an MCP tool.
