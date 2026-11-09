"""The knowledge check: wording changes pass, fact changes wait for the owner, stale copies are caught and fixed. No stack needed."""

import shutil

import pytest

from bikelake.knowledge import KNOWLEDGE, SEMANTIC, approve, ask, check, facts, fix, show

LANE = "lane-analysis/new-lanes#near_new_lane"
FAQ = "website/faq#near_new_lane"


@pytest.fixture
def repo(tmp_path):
    shutil.copytree(KNOWLEDGE, tmp_path / "knowledge")
    shutil.copy(SEMANTIC, tmp_path / "_semantic.yml")
    return tmp_path / "knowledge", tmp_path / "_semantic.yml"


def edit(path, old, new):
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))


def kinds(findings):
    return sorted(f.kind for f in findings)


def test_committed_knowledge_is_clean():
    assert check() == []


def test_facts():
    assert facts("within about fifty meters") == set()  # only number words up to twelve
    assert facts("about two days, since 2020") == {"2 days", "2020"}
    assert facts("from Jan 2015 to October 2024, $2.95 a ride") == {"January 2015", "October 2024", "$2.95"}
    assert facts("you may ride") == set()


def test_wording_change_passes_and_is_saved(repo):
    root, semantic = repo
    edit(root / "sources/lane-analysis/new-lanes.md", "A crash counts as near", "We call a crash near")
    assert kinds(check(root, semantic, write=True)) == ["wording only"]
    assert check(root, semantic) == []
    assert ask("near_new_lane", root).startswith("We call a crash near")


def test_fact_change_waits_for_the_owner(repo):
    root, semantic = repo
    edit(root / "sources/lane-analysis/new-lanes.md", "about 50 meters", "about 75 meters")
    findings = check(root, semantic, write=True)
    assert kinds(findings) == ["needs review"]
    assert findings[0].owners == ["lane-analysis"]
    assert "new_lane_injury_change" in findings[0].message
    assert "50 meters" in ask("near_new_lane", root)


def test_approved_change_flags_copies_and_metrics(repo):
    root, semantic = repo
    edit(root / "sources/lane-analysis/new-lanes.md", "about 50 meters", "about 75 meters")
    approve([LANE], root)
    findings = check(root, semantic)
    assert kinds(findings) == ["conflict", "out of sync"]
    conflict = next(f for f in findings if f.kind == "conflict")
    assert conflict.owners == ["website"]
    assert "{{ near_new_lane: meters }}" in conflict.message  # the suggested fix
    assert "75 meters" in ask("near_new_lane", root)  # the owner's definition, not the stale copy

    assert fix(FAQ, root) == "Within about {{ near_new_lane: meters }} of the new lane segment."
    edit(semantic, "about 50 meters", "about 75 meters")
    assert check(root, semantic) == []
    assert show(FAQ, root) == "Within about 75 meters of the new lane segment."


def test_reference_follows_the_definition(repo):
    root, semantic = repo
    edit(root / "sources/lane-analysis/new-lanes.md", "about 50 meters", "about 75 meters")
    approve([LANE], root)
    fix(FAQ, root)
    edit(root / "sources/lane-analysis/new-lanes.md", "about 75 meters", "about 60 meters")
    approve([LANE], root)
    assert show(FAQ, root) == "Within about 60 meters of the new lane segment."
    assert kinds(check(root, semantic)) == ["out of sync"]  # only the metric; the FAQ needed nothing


def test_broken_reference(repo):
    root, semantic = repo
    edit(root / "sources/website/faq.md", "about 50 meters", "about {{ near_new_lane: minutes }}")
    approve([FAQ], root)
    assert kinds(check(root, semantic)) == ["broken reference"]


def test_new_unknown_and_removed(repo):
    root, semantic = repo
    page = root / "sources/trip-analysis/trips.md"
    page.write_text(page.read_text().split("## Trip length")[0] + "## Docks\nterm: docks\n\nStations have about 19 docks.\n")
    assert kinds(check(root, semantic)) == ["removed", "unknown term"]


def test_unapproved_term_has_no_answer(repo):
    root, semantic = repo
    (root / "approved.yml").unlink()
    assert ask("near_new_lane", root).startswith("There's no approved answer")
