# 0007 Approved knowledge, checked by facts

`knowledge/` holds pages owned by different owners, split into one section per concept, each tagged with a glossary term. An agent answers only from `knowledge/approved.yml`.

A change is sorted by what it does to the facts in a section (amounts, durations, dates), not by whether the text changed. A wording change keeps every fact, so it's approved automatically; asking owners to approve every reworded sentence would train them to approve without reading. A changed fact always goes to the owner, and the agent keeps the approved version until the owner approves.

Each concept has one owner in the glossary, and the owner's approved section is the definition. The agent answers only from definitions, so a stale copy on another page never reaches it. The check flags the copy to its owner with a suggested fix rather than rewriting it, because each owner is accountable for its own pages. The fix replaces the copied fact with a reference (`{{ term: kind }}`) filled in from the definition, so the copy can't go stale again.

dbt metrics name the concepts they depend on in `config.meta.glossary_terms`, so the knowledge and the semantic layer share one key. When a definition changes, the same check flags the metrics whose descriptions or caveats no longer match.

Facts are extracted with patterns rather than a language model, so the check is free, fast, and gives the same answer every run, which is what a CI check needs. Its limits are in `knowledge/README.md`.
