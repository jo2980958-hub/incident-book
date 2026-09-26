"""The statutory-field guard, tested against sentences it was not written from.

`tests/test_drafting.py` feeds the model's draft five of the thirteen phrases in
``incident_language.BANNED_ACCUSATIONS`` and asserts they are refused. That
proves the list contains the words in the list.

The sentence that made this file necessary contains none of them:

    "The individual attempted to rob the register and threatened to kill the
    clerk. A man in his forties in a red jacket with a neck tattoo came over
    the counter."

It passed, into statute field (C) of a record kept for five years and copied
unredacted into the pack that goes to the police. Every case below was written
before the guard it tests, from that reproduction, from the shared adversarial
corpus, and from paraphrasing each hazard until the sentence no longer looked
like anything anybody had listed.
"""

from __future__ import annotations

import pytest
from factories import blank_incident

from app import draft_language
from app.bedrock import StubRunner
from app.drafting import draft_narrative

WORDS = "a man came over the counter shouting about the till, I called 911"
RECORDED = "Counter camera. The device classified the event 'human'. Clip attached."


def _vocabulary(words: str = WORDS, recorded: str = RECORDED):
    return (
        draft_language.source_vocabulary(words, recorded),
        draft_language.source_numbers(words, recorded),
    )


def _findings(text: str, words: str = WORDS):
    vocabulary, numbers = _vocabulary(words)
    return draft_language.findings(text, vocabulary, numbers)


def _draft(text: str, words: str = WORDS):
    return draft_narrative(
        StubRunner([{"tool_input": {"description": text}, "usage": {}}]),
        blank_incident(),
        words,
    )


# --- the reproduction, sentence by sentence ------------------------------

REPRODUCTION = (
    "The individual attempted to rob the register and threatened to kill the "
    "clerk. A man in his forties in a red jacket with a neck tattoo came over "
    "the counter."
)


def test_the_reproduction_no_longer_reaches_the_statutory_field():
    draft = _draft(REPRODUCTION)
    assert draft.status == "rejected"
    assert draft.description == WORDS, "the worker's own words are what survive"


@pytest.mark.parametrize(
    ("sentence", "rule"),
    [
        ("The individual attempted to rob the register.", draft_language.CRIME),
        ("The individual threatened to kill the clerk.", draft_language.CRIME),
        ("A man in his forties came over the counter.", draft_language.DESCRIPTION),
        ("A person in a red jacket came over the counter.", draft_language.DESCRIPTION),
        ("A person with a neck tattoo came over the counter.", draft_language.DESCRIPTION),
        (
            "A person came in with the intention of taking the till.",
            draft_language.INTENT,
        ),
    ],
)
def test_each_half_of_the_reproduction_is_caught_on_its_own(sentence, rule):
    """Split up, because a guard that catches a long sentence for one reason
    tells you nothing about the other four hazards inside it."""
    assert rule in {f.rule for f in _findings(sentence)}


@pytest.mark.parametrize(
    "sentence",
    [
        # Paraphrases. None of these contains a word from the thirteen phrases,
        # and none was written by looking at the class lists either.
        "A person came in with the intention of taking the till and made threats to the staff.",
        "The customer became aggressive and assaulted the worker before leaving.",
        "The person was tall, bald, and wearing a blue hooded top.",
        "A woman, roughly twenty-five, with long dark hair, left through the side door.",
        "The person deliberately swept the display onto the floor.",
        "An attempted burglary took place at the rear of the premises.",
        "The individual was armed and demanded the contents of the register.",
        "A young man of about thirty in a grey tracksuit was involved.",
    ],
)
def test_a_paraphrase_of_the_hazard_is_refused_too(sentence):
    assert _findings(sentence), "no finding: the class was matched as a token, not as a class"


# --- the paired false positives ------------------------------------------
#
# Every rule needs one, or the rule is "reject anything that looks a bit like
# this" and nobody can tell the difference.

@pytest.mark.parametrize(
    "sentence",
    [
        "A person came over the counter and shouted about the till.",
        "The worker called 911 and stayed behind the counter.",
        "A person came over the counter. The worker moved to the back of the shop.",
        "The device classified the event as human and a clip was attached.",
    ],
)
def test_an_ordinary_rewrite_of_the_workers_words_is_allowed(sentence):
    """The gate has to be able to pass something. A guard that refuses every
    draft is not a guard, it is the drafting feature switched off, and then
    nobody ever exercises the path the product is for."""
    assert _findings(sentence) == []
    assert _draft(sentence).status == "proposed"


def test_a_crime_word_the_worker_typed_is_the_workers_to_keep():
    """Provenance, not vocabulary. A worker who says they were robbed is
    entitled to have their account written up in that word; a model that
    reaches for it unprompted has invented the most serious sentence in the
    document."""
    words = "he tried to rob the till and threatened to kill me, I called 911"
    drafted = "A person tried to rob the till and threatened to kill the worker."
    assert _findings(drafted, words) == []
    # The same sentence, for the worker who never said any of it.
    assert _findings(drafted)


def test_characterising_the_workers_words_is_not_the_same_as_repeating_them():
    """"said he would kill me" is an account. "threatened to kill" is a legal
    characterisation of that account, and the characterisation is the model's,
    not the worker's. The draft is refused and the worker's own sentence is
    what gets filed."""
    words = "he said he would kill me, I called 911"
    assert draft_language.CRIME in {
        f.rule for f in _findings("A person threatened to kill the worker.", words)
    }


def test_a_garment_the_worker_mentioned_is_not_an_invented_description():
    words = "someone took a jacket off the rail and walked out"
    assert draft_language.DESCRIPTION not in {
        f.rule for f in _findings("A person took a jacket from the rail and left.", words)
    }


def test_an_inflection_of_a_word_the_worker_typed_is_allowed():
    """"shouting" has to reach "shouted", or the guard refuses the rewriting it
    exists to permit."""
    assert _findings("A person shouted about the till.") == []


# --- race and ethnicity, the one unconditional rule ----------------------

@pytest.mark.parametrize(
    "sentence",
    [
        "A white man came over the counter.",
        "The person appeared to be of Asian origin.",
        "A Hispanic customer became aggressive.",
    ],
)
def test_race_is_refused_whether_or_not_the_worker_said_it(sentence):
    words = WORDS + " he was white and asian and hispanic"
    assert draft_language.ETHNICITY in {f.rule for f in _findings(sentence, words)}


# --- figures ------------------------------------------------------------

@pytest.mark.parametrize(
    "sentence",
    [
        "A person took about 200 dollars from the till.",
        "Two people came over the counter.",
        "The worker called 999.",
        "The incident lasted around five minutes.",
    ],
)
def test_a_figure_nobody_stated_discards_the_draft(sentence):
    assert draft_language.FIGURE in {f.rule for f in _findings(sentence)}


def test_a_figure_the_worker_stated_survives_in_any_spelling():
    assert _findings("The worker called 911.") == []
    assert _findings("A person came over the counter once.", WORDS + " it happened one time") == []


# --- §2, the spelling of it all ------------------------------------------

MUTATIONS = [
    ("plain", lambda s: s),
    ("curly", lambda s: s.replace("'", "’")),
    ("zero-width", lambda s: s.replace(" ", "​ ", 1)),
    ("lookalike", lambda s: s.replace("o", "о", 1)),
    ("full-width", lambda s: s.replace("a", "ａ")),
    ("upper", lambda s: s.upper()),
    ("double-space", lambda s: s.replace(" ", "  ")),
]


@pytest.mark.parametrize("name,mutate", MUTATIONS, ids=[m[0] for m in MUTATIONS])
@pytest.mark.parametrize(
    "sentence",
    [
        "The individual attempted to rob the register.",
        "A person with a neck tattoo came over the counter.",
    ],
)
def test_the_guard_sees_through_the_spelling(sentence, name, mutate):
    assert _findings(mutate(sentence)), f"{name} walked past the guard"


def test_a_letter_outside_the_alphabet_is_a_refusal_in_itself():
    """A fold table is a denylist wearing different clothes: `rоb` with a
    Cyrillic o is caught by the map, `rоb` with the next lookalike is not. The
    allowlist -- anything outside a-z after folding -- needs no extending."""
    assert _findings("The individual tried tо rоb the regıster.")


# --- what a refusal is allowed to say ------------------------------------

def test_the_refusal_names_the_class_and_reprints_nothing():
    """A rejection is model output with a frame around it, not metadata. The
    completer is told which class fired and in which statutory field; the
    sentence itself goes to the log, where a developer is and they are not."""
    draft = _draft(REPRODUCTION)
    lowered = draft.note.lower()
    for word in ("rob", "kill", "forties", "tattoo", "jacket", "clerk", "register"):
        assert word not in lowered
    assert "(c)" in lowered
    assert "physical description" in lowered or "criminal characterisation" in lowered


def test_the_worker_is_not_told_the_draft_was_fine_when_it_was_not():
    """Non-vacuity for the test above: the note has to say something, or an
    empty string would satisfy every assertion in it."""
    assert len(_draft(REPRODUCTION).note) > 80
