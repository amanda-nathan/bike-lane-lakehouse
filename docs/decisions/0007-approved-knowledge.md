# 0007 Approved knowledge, checked by its facts

`knowledge/` has pages from different owners. Each section is one concept, tagged with a glossary term, and the agent only answers from what the owners approved (`knowledge/approved.yml`).

A change is judged by its facts (numbers, dates, amounts), not just by whether the text changed. Rewording goes through on its own. If owners had to approve every reworded sentence, they'd start approving without reading. A changed fact always goes to the owner.

Each concept has one owner. Other pages that mention it are copies, and the agent never answers from a copy. When a copy goes stale, its owner gets a suggested fix instead of having their page rewritten for them. The fix points the copy at the definition, so it can't go stale again.

dbt metrics list the concepts they depend on in `config.meta.glossary_terms`, so the same check covers the knowledge and the semantic layer.

Facts are found with patterns instead of a language model, so the check is free and gives the same answer every time it runs, which matters for a CI check. Limits are in `knowledge/README.md`.
