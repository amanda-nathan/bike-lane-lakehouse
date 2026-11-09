# Approved knowledge

An AI agent should only answer from definitions their owners approved. This folder holds those definitions as markdown, and `bikelake-knowledge check` compares every change with the approved version and says who has to look at it.

The definitions and numbers come from this project. The owners (`lane-analysis`, `count-analysis`, `trip-analysis`, `website`) and the change from 50 to 75 meters below are made up to show how the check works.

## The pages

One folder per owner in [`sources/`](sources/). Each `## ` section is one concept, named by its `term:`.

[`sources/lane-analysis/new-lanes.md`](sources/lane-analysis/new-lanes.md):

```markdown
---
owner: lane-analysis
---

## Near a new lane
term: near_new_lane

A crash counts as near a new protected lane if it happened within about 50 meters (half a block) of the lane segment. We compare the 2 years before the lane went in with the 2 years after.
```

[`glossary.yml`](glossary.yml) says `lane-analysis` owns `near_new_lane`, so this section is the definition. The agent answers from it.

The FAQ, owned by `website`, repeats the same fact ([`sources/website/faq.md`](sources/website/faq.md)):

```markdown
## How close is "near" a new lane?
term: near_new_lane

Within about 50 meters of the new lane segment.
```

## What gets saved on approval

[`approved.yml`](approved.yml) keeps each approved section with a hash and the facts pulled out of it:

```yaml
lane-analysis/new-lanes#near_new_lane:
  facts:
  - 2 years
  - 50 meters
  hash: 0b23ea5c268f
  owner: lane-analysis
  term: near_new_lane
  text: A crash counts as near a new protected lane if it happened within about 50 meters ...
```

## The dbt metric that depends on it

In [`_semantic.yml`](../dbt/models/marts/_semantic.yml), the metric names the concept:

```yaml
- name: new_lane_injury_change
  description: (after - before) / before, for cyclists hurt within about 50 meters (half a block) of new protected lanes.
  config:
    meta:
      glossary_terms: [near_new_lane]
```

## What the check does

1. Same hash: nothing changed.
2. New hash, same facts: rewording. It's approved automatically.
3. A fact changed: the owner has to approve it. Until then the agent keeps the approved version.
4. A copy on another owner's page disagrees with the definition: that owner gets a suggested fix. The fix replaces the number with `{{ near_new_lane: meters }}`, which is filled in from the definition, so the copy can't go stale again.
5. A dbt metric that names the concept disagrees with it: the metric is flagged.

Facts are numbers with units, dollar amounts, months, and years, found with regular expressions in [`src/bikelake/knowledge.py`](../src/bikelake/knowledge.py).

## Example: 50 meters becomes 75

Rewording the page passes on its own:

![](img/2-wording-change.png)

Changing 50 to 75 goes to the owner, and the agent still says 50:

![](img/3-fact-change.png)

After the owner approves, the agent says 75. The FAQ and the dbt metric still say 50, so both are flagged:

![](img/4-approved.png)

The website owner accepts the fix. The FAQ file now has the placeholder, and readers see 75:

![](img/5-faq-fixed.png)

The metric itself, from the real data. Cyclists hurt within 50 meters of new lanes went up 17%, against 1.7% citywide:

![](img/6-bike-metrics.png)

## Run it

```bash
uv run bikelake-knowledge check             # exits 1 if someone needs to look at something
uv run bikelake-knowledge ask near_new_lane # the approved answer for a concept
uv run bikelake-knowledge demo              # the example above, in a temporary copy
```

[`knowledge.yml`](../.github/workflows/knowledge.yml) runs the check on every change to a page or a metric.

## Limits

- Facts written as words ("half a block", "fifty meters") aren't found.
- Only sections with the same `term:` are compared.
- The metric check reads the metric's description, not its SQL. The lane model uses a 0.0005-degree buffer, which would have to change too.
- `ask` takes a concept, not a question. Matching a question to a concept would be the agent's job.
