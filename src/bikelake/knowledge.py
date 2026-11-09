"""Approved knowledge for an AI agent: what changed, who has to approve it, and what disagrees.

Each page in knowledge/sources/<owner>/ is split into one chunk per concept: a `## ` heading,
then a `term:` line naming a glossary term. The glossary names each concept's owner; the owner's
approved chunk is the definition, and the agent answers only from definitions. Other pages can
copy a fact, which the check compares with the definition, or point to it with
`{{ term: kind }}` (e.g. `{{ near_new_lane: meters }}`), which fills in the approved fact.

    bikelake-knowledge check [--write]      report; --write saves wording-only changes as approved
    bikelake-knowledge approve <chunk ...>  the owner approves the current version (--all for every chunk)
    bikelake-knowledge fix <chunk>          the owner accepts the suggested fix for a stale copy
    bikelake-knowledge ask <term>           what the agent would answer
    bikelake-knowledge show <chunk>         a page's text as readers see it, references filled in
    bikelake-knowledge demo                 walk through one change, in a temporary copy
"""

import argparse
import hashlib
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
KNOWLEDGE = REPO / "knowledge"
SEMANTIC = REPO / "dbt" / "models" / "marts" / "_semantic.yml"

# Facts are the parts of a sentence that change its meaning: amounts, durations, dates.
# A change that keeps every fact is a wording change and needs no one.
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
SHORT_MONTHS = {m[:3]: m for m in MONTHS} | {"Sept": "September"}
NUMBER_WORDS = {w: str(i) for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}
UNITS = {"m": "meters", "meter": "meters", "meters": "meters", "km": "kilometers", "%": "percent", "percent": "percent"}
for unit in ("minute", "hour", "day", "week", "month", "year"):
    UNITS[unit] = UNITS[unit + "s"] = unit + "s"

FACT = re.compile(
    rf"(?P<date>\b(?P<month>{'|'.join(MONTHS + sorted(SHORT_MONTHS))})\.?(?:\s+(?P<day>\d{{1,2}})(?!\d))?(?:,?\s+(?P<year>(?:19|20)\d{{2}}))?\b)"
    r"|(?P<money>\$\d[\d,]*(?:\.\d+)?)"
    rf"|(?P<amount>(?:\b(?P<n>\d[\d,]*(?:\.\d+)?)|\b(?P<word>{'|'.join(NUMBER_WORDS)}))\s*(?P<unit>{'|'.join(sorted(UNITS, key=len, reverse=True))})(?!\w))"
    r"|(?P<bare_year>\b(?:19|20)\d{2}\b)"
)
REFERENCE = re.compile(r"\{\{\s*(\w+)\s*:\s*(\w+)\s*\}\}")


def _fact(m: re.Match) -> str:
    if m["date"]:
        return " ".join(p for p in (SHORT_MONTHS.get(m["month"], m["month"]), m["day"], m["year"]) if p)
    if m["money"]:
        return m["money"].replace(",", "")
    if m["amount"]:
        n = m["n"].replace(",", "") if m["n"] else NUMBER_WORDS[m["word"]]
        return f"{n} {UNITS[m['unit']]}"
    return m["bare_year"]


def facts(text: str) -> set[str]:
    """Normalized facts: 'about two days, since 2020' -> {'2 days', '2020'}. References aren't facts."""
    return {_fact(m) for m in FACT.finditer(text)}


def kind(fact: str) -> str:
    """What a fact measures, so '50 meters' is compared with '75 meters' and not with '2 years'."""
    if fact.startswith("$"):
        return "money"
    if re.fullmatch(r"(?:19|20)\d{2}", fact):
        return "year"
    number, _, unit = fact.partition(" ")
    return unit if re.fullmatch(r"[\d.]+", number) else "date"


def disagreeing(stated: set[str], definition: set[str]) -> list[str]:
    """Facts a page states that the definition doesn't, for the kinds of fact the definition has."""
    kinds = {kind(f) for f in definition}
    return sorted(f for f in stated if kind(f) in kinds and f not in definition)


def same_kind(facts: set[str], like: list[str]) -> list[str]:
    """The definition's facts of the same kinds as `like`: what it says instead."""
    kinds = {kind(f) for f in like}
    return sorted(f for f in facts if kind(f) in kinds)


@dataclass
class Chunk:
    id: str  # owner/page#term
    owner: str
    term: str
    title: str
    text: str
    path: Path

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()[:12]

    @property
    def facts(self) -> set[str]:
        return facts(self.text)


@dataclass
class Finding:
    kind: str  # wording only | new | needs review | removed | conflict | broken reference | out of sync | unknown term
    message: str
    term: str = ""
    owners: list[str] = field(default_factory=list)


def _sections(body: str) -> list[tuple[str, str, str]]:
    """(title, term, text) for each `## ` section of a page body."""
    out = []
    for section in re.split(r"^## ", body, flags=re.M)[1:]:
        title, rest = section.split("\n", 1)
        term_line, text = rest.strip().split("\n", 1)
        out.append((title.strip(), term_line.removeprefix("term:").strip(), " ".join(text.split())))
    return out


def read_chunks(root: Path = KNOWLEDGE) -> dict[str, Chunk]:
    chunks = {}
    for path in sorted((root / "sources").glob("*/*.md")):
        _, front, body = path.read_text().split("---", 2)
        owner = yaml.safe_load(front)["owner"]
        for title, term, text in _sections(body):
            chunk_id = f"{owner}/{path.stem}#{term}"
            chunks[chunk_id] = Chunk(chunk_id, owner, term, title, text, path)
    return chunks


def read_glossary(root: Path = KNOWLEDGE) -> dict[str, dict]:
    return yaml.safe_load((root / "glossary.yml").read_text())


def read_approved(root: Path = KNOWLEDGE) -> dict[str, dict]:
    path = root / "approved.yml"
    return (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}


def write_approved(approved: dict[str, dict], root: Path = KNOWLEDGE) -> None:
    class Dumper(yaml.SafeDumper):
        pass

    Dumper.add_representer(str, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style=">" if len(s) > 80 else None))
    header = "# Written by `bikelake-knowledge approve`, `fix`, and `check --write`. The agent answers only from this file.\n\n"
    (root / "approved.yml").write_text(header + yaml.dump(approved, Dumper=Dumper, sort_keys=True, allow_unicode=True, width=100))


def record(chunk: Chunk, by: str) -> dict:
    return {
        "owner": chunk.owner,
        "term": chunk.term,
        "text": chunk.text,
        "facts": sorted(chunk.facts),
        "hash": chunk.hash,
        "approved": date.today().isoformat(),
        "by": by,
    }


def metric_terms(semantic: Path = SEMANTIC) -> list[tuple[dict, list[str]]]:
    """dbt metrics that name glossary terms in config.meta.glossary_terms."""
    out = []
    for metric in yaml.safe_load(semantic.read_text())["metrics"]:
        terms = ((metric.get("config") or {}).get("meta") or {}).get("glossary_terms", [])
        if terms:
            out.append((metric, terms))
    return out


def definitions(glossary: dict, approved: dict) -> dict[str, set[str]]:
    """Each term's approved facts, from its owner's chunks only."""
    out: dict[str, set[str]] = {}
    for rec in approved.values():
        if glossary.get(rec["term"], {}).get("owner") == rec["owner"]:
            out.setdefault(rec["term"], set()).update(rec["facts"])
    return out


def resolve(term: str, fact_kind: str, defined: dict[str, set[str]]) -> str | None:
    """The one approved fact of this kind in the term's definition, or None."""
    found = [f for f in defined.get(term, ()) if kind(f) == fact_kind]
    return found[0] if len(found) == 1 else None


def render(text: str, defined: dict[str, set[str]]) -> str:
    """Fill in `{{ term: kind }}` references from the approved definitions."""
    return REFERENCE.sub(lambda m: resolve(m[1], m[2], defined) or m[0], text)


def suggest_fix(chunk: Chunk, bad: list[str], defined: dict[str, set[str]]) -> str | None:
    """Replace each stale copied fact with a reference to the definition, so it can't go stale again."""
    def replace(m: re.Match) -> str:
        fact = _fact(m)
        if fact in bad and resolve(chunk.term, kind(fact), defined):
            return f"{{{{ {chunk.term}: {kind(fact)} }}}}"
        return m[0]

    fixed = FACT.sub(replace, chunk.text)
    return fixed if not disagreeing(facts(fixed), defined[chunk.term]) else None


def check(root: Path = KNOWLEDGE, semantic: Path = SEMANTIC, write: bool = False) -> list[Finding]:
    glossary, approved, live = read_glossary(root), read_approved(root), read_chunks(root)
    linked = metric_terms(semantic)
    metrics_for = {t: sorted(m["name"] for m, terms in linked if t in terms) for t in glossary}
    findings = []

    # 1. Did each page change since its owner approved it?
    for chunk in live.values():
        if chunk.term not in glossary:
            findings.append(Finding("unknown term", f"{chunk.id} uses '{chunk.term}', which isn't in the glossary.", chunk.term, [chunk.owner]))
            continue
        old = approved.get(chunk.id)
        if old is None:
            findings.append(Finding("new", f"{chunk.id} has never been approved. Ask {chunk.owner}.", chunk.term, [chunk.owner]))
        elif old["hash"] == chunk.hash:
            continue
        elif set(old["facts"]) == chunk.facts:
            findings.append(Finding("wording only", f"{chunk.id}: same facts ({', '.join(old['facts']) or 'none'}), approved automatically.", chunk.term, [chunk.owner]))
            if write:
                approved[chunk.id] = record(chunk, by="automatic, wording only")
        else:
            was, now = set(old["facts"]), chunk.facts
            message = (
                f"{chunk.id}: {', '.join(sorted(was - now)) or 'nothing'} -> {', '.join(sorted(now - was)) or 'nothing'}. "
                f"Ask {chunk.owner}. The agent keeps the approved version until then."
            )
            if metrics_for.get(chunk.term) and glossary[chunk.term]["owner"] == chunk.owner:
                message += f"\n    Metrics to re-check after approval: {', '.join(metrics_for[chunk.term])}"
            findings.append(Finding("needs review", message, chunk.term, [chunk.owner]))
    for chunk_id in approved.keys() - live.keys():
        rec = approved[chunk_id]
        findings.append(Finding("removed", f"{chunk_id} is gone from its page. Ask {rec['owner']}.", rec["term"], [rec["owner"]]))

    # 2. Does a copy on another owner's page, or a dbt metric, say something the definition doesn't?
    defined = definitions(glossary, approved)
    for chunk in live.values():
        owner = glossary.get(chunk.term, {}).get("owner")
        for m in REFERENCE.finditer(chunk.text):
            if resolve(m[1], m[2], defined) is None:
                findings.append(Finding("broken reference", f"{chunk.id}: {m[0]} doesn't match exactly one approved fact.", chunk.term, [chunk.owner]))
        if owner and owner != chunk.owner and chunk.term in defined:
            if bad := disagreeing(chunk.facts, defined[chunk.term]):
                fix = suggest_fix(chunk, bad, defined)
                findings.append(
                    Finding(
                        "conflict",
                        f"{chunk.id} says {', '.join(bad)}; {owner}'s approved definition says "
                        f"{', '.join(same_kind(defined[chunk.term], bad))}. The agent answers from {owner}'s definition, "
                        f"not this copy. Ask {chunk.owner} to fix it."
                        + (f"\n    Suggested fix (bikelake-knowledge fix {chunk.id}): {fix}" if fix else ""),
                        chunk.term,
                        [chunk.owner],
                    )
                )
    for metric, terms in linked:
        text = " ".join([metric.get("label", ""), metric.get("description", "")] + metric["config"]["meta"].get("caveats", []))
        for term in terms:
            if term not in glossary:
                findings.append(Finding("unknown term", f"metric {metric['name']} links '{term}', which isn't in the glossary.", term))
            elif term in defined and (bad := disagreeing(facts(text), defined[term])):
                findings.append(
                    Finding(
                        "out of sync",
                        f"metric {metric['name']} says {', '.join(bad)}; {glossary[term]['owner']}'s approved definition of {term} says "
                        f"{', '.join(same_kind(defined[term], bad))}. Update the metric (and its model), then run dbt build and the evals.",
                        term,
                        [glossary[term]["owner"]],
                    )
                )

    if write and any(f.kind == "wording only" for f in findings):
        write_approved(approved, root)
    return findings


def approve(chunk_ids: list[str], root: Path = KNOWLEDGE) -> None:
    approved, live = read_approved(root), read_chunks(root)
    for chunk_id in chunk_ids or live.keys() | approved.keys():
        if chunk_id in live:
            approved[chunk_id] = record(live[chunk_id], by=live[chunk_id].owner)
        elif chunk_id in approved:
            del approved[chunk_id]  # the owner took it off the page
        else:
            raise SystemExit(f"no chunk {chunk_id}. Chunks: {', '.join(sorted(live))}")
    write_approved(approved, root)


def fix(chunk_id: str, root: Path = KNOWLEDGE) -> str:
    """The copy's owner accepts the suggested fix: the page is rewritten and approved. Returns the new text."""
    glossary, live = read_glossary(root), read_chunks(root)
    chunk = live.get(chunk_id) or sys.exit(f"no chunk {chunk_id}")
    defined = definitions(glossary, read_approved(root))
    bad = disagreeing(chunk.facts, defined.get(chunk.term, set()))
    fixed = suggest_fix(chunk, bad, defined) if bad else None
    if fixed is None:
        sys.exit(f"no suggested fix for {chunk_id}")
    page = chunk.path.read_text()
    front, body = page[: page.index("## ")], page[page.index("## ") :]
    sections = [(t, term, fixed if term == chunk.term else text) for t, term, text in _sections(body)]
    chunk.path.write_text(front + "\n".join(f"## {t}\nterm: {term}\n\n{text}\n" for t, term, text in sections))
    approve([chunk_id], root)
    return fixed


def ask(term: str, root: Path = KNOWLEDGE) -> str:
    """The agent's answer: the owner's approved definition, or a referral when there isn't one."""
    glossary = read_glossary(root)
    if term not in glossary:
        return f"I don't have approved knowledge about '{term}'."
    label, owner = glossary[term]["label"], glossary[term]["owner"]
    approved = read_approved(root)
    defined = definitions(glossary, approved)
    answers = [r for r in approved.values() if r["term"] == term and r["owner"] == owner]
    if not answers:
        return f"There's no approved answer about '{label}' yet. Please ask {owner}."
    return "\n".join(f"{render(r['text'], defined)} (Approved by {owner}, {r['approved']}.)" for r in answers)


def show(chunk_id: str, root: Path = KNOWLEDGE) -> str:
    chunk = read_chunks(root).get(chunk_id) or sys.exit(f"no chunk {chunk_id}")
    return render(chunk.text, definitions(read_glossary(root), read_approved(root)))


def report(findings: list[Finding]) -> int:
    """Print findings; exit 1 if anything needs a person."""
    if not findings:
        print("ok: every chunk approved, copies agree, metrics agree with the glossary.")
    for f in findings:
        print(f"{f.kind:<13} {f.message}")
    return int(any(f.kind != "wording only" for f in findings))


def demo() -> None:
    """An owner changes a fact; a copy on another page and a dbt metric go stale and get fixed."""
    with tempfile.TemporaryDirectory() as tmp:
        root, semantic = Path(tmp) / "knowledge", Path(tmp) / "_semantic.yml"
        shutil.copytree(KNOWLEDGE, root)
        shutil.copy(SEMANTIC, semantic)
        page, faq_id = root / "sources/lane-analysis/new-lanes.md", "website/faq#near_new_lane"

        def edit(path: Path, old: str, new: str) -> None:
            path.write_text(path.read_text().replace(old, new, 1))

        def step(title: str, write: bool = False) -> None:
            print(f"\n=== {title}\n")
            report(check(root, semantic, write=write))
            print(f"\nagent, asked about near_new_lane:\n  {ask('near_new_lane', root)}")
            print(f"website FAQ shows:\n  {show(faq_id, root)}")

        step("0. Starting point")
        edit(page, "A crash counts as near a new protected lane if it happened within", "We count a crash as near a new protected lane when it's within")
        step("1. lane-analysis rewords its page. The facts stay the same.", write=True)
        edit(page, "about 50 meters (half a block)", "about 75 meters")
        step("2. lane-analysis changes 50 meters to 75 meters")
        approve(["lane-analysis/new-lanes#near_new_lane"], root)
        step("3. lane-analysis approves. The agent says 75; the FAQ copy and the dbt metric still say 50.")
        fix(faq_id, root)
        edit(semantic, "about 50 meters (half a block)", "about 75 meters")
        step("4. website accepts the suggested fix, and the metric description is updated")
        edit(page, "about 75 meters", "about 60 meters")
        approve(["lane-analysis/new-lanes#near_new_lane"], root)
        edit(semantic, "about 75 meters", "about 60 meters")
        step("5. lane-analysis changes it again, to 60 meters, and the metric is updated. Nobody touches the FAQ.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="bikelake-knowledge", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check").add_argument("--write", action="store_true", help="save wording-only changes as approved")
    approve_parser = sub.add_parser("approve")
    approve_parser.add_argument("chunks", nargs="*")
    approve_parser.add_argument("--all", action="store_true")
    sub.add_parser("fix").add_argument("chunk")
    sub.add_parser("ask").add_argument("term")
    sub.add_parser("show").add_argument("chunk")
    sub.add_parser("demo")
    args = parser.parse_args()

    if args.command == "check":
        sys.exit(report(check(write=args.write)))
    if args.command == "approve":
        if not args.chunks and not args.all:
            parser.error("name the chunks to approve, or pass --all")
        approve(args.chunks)
    if args.command == "fix":
        print(fix(args.chunk))
    if args.command == "ask":
        print(ask(args.term))
    if args.command == "show":
        print(show(args.chunk))
    if args.command == "demo":
        demo()


if __name__ == "__main__":
    main()
