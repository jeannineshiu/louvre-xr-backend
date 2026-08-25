"""Consistency checks on the Vision recogniser prompt.

The prompt's MUST HAVE criteria are matched strictly — "if even one required
feature is absent or unclear, return unknown" — so a wrong feature doesn't
degrade recognition, it makes that sculpture unrecognisable outright, and the
failure looks exactly like a bad photo. These checks can't verify the criteria
against reality (that needs eyes on the artwork), but they do catch the drift
that made the Miles Franklin entry unmatchable: criteria describing a different
material and pose from the knowledge base's own description of the same work.
"""

import re

import pytest

from exhibit_recognizer import SYSTEM_PROMPT
from exhibits_data import EXHIBITS

_NUMBER_WORDS = {
    10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
}

_ENTRY_PATTERN = re.compile(r"^\s*(\d+)\.\s+(.+)$", re.MULTILINE)


def entries():
    """(number, title) for each numbered sculpture in the prompt."""
    return [(int(n), t.strip()) for n, t in _ENTRY_PATTERN.findall(SYSTEM_PROMPT)]


def test_stated_count_matches_the_number_of_entries():
    listed = entries()
    expected = _NUMBER_WORDS[len(listed)]
    assert f"one of the {expected} specific sculptures" in SYSTEM_PROMPT, (
        f"prompt lists {len(listed)} sculptures but doesn't say '{expected}'")


def test_entries_are_numbered_consecutively():
    assert [n for n, _ in entries()] == list(range(1, len(entries()) + 1))


def test_every_entry_has_must_have_criteria():
    for _, title in entries():
        block = SYSTEM_PROMPT.split(title, 1)[1]
        assert block.lstrip().startswith("MUST HAVE:"), f"{title} has no MUST HAVE line"


@pytest.mark.parametrize("exhibit", [e for e in EXHIBITS if e["type"] == "sculpture"],
                         ids=lambda e: e["id"])
def test_material_claims_agree_with_the_knowledge_base(exhibit):
    """A work the knowledge base says isn't bronze must not be required to be bronze.

    This is the Miles Franklin bug: the criteria demanded "realistic bronze"
    for a statue in white artificial marble, so every clear photo of it
    returned "unknown" while the RAG answer described a bronze that isn't there.
    """
    listed = [title for _, title in entries() if exhibit["name"].lower() in title.lower()]
    if not listed:
        pytest.skip(f"{exhibit['name']} is not in the recogniser prompt")

    criteria = SYSTEM_PROMPT.split(listed[0], 1)[1].split("\n\n", 1)[0].lower()
    description = (exhibit.get("visual_description", "") + exhibit.get("key_facts", "")).lower()

    if "not bronze" in description or "rather than cast in bronze" in description:
        assert "not bronze" in criteria or "bronze" not in criteria, (
            f"{exhibit['name']}: the knowledge base says it is not bronze, "
            f"but the recogniser requires bronze")
