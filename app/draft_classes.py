"""The hazardous classes themselves, and nothing else.

Split from `draft_language.py` following this package's sibling convention --
Doorstep Receipt splits `guard.py` / `guard_rules.py` / `guard_findings.py` the
same way, and its reasoning applies here word for word: one module owns the
data, another owns the behaviour, so the list a reviewer has to read to audit
the promise is a page of words with nothing else on it.

That matters more here than it does there. These lists are the difference
between a model characterising a violent crime and a model writing down what a
worker said, in a record kept five years under Labor Code 6401.9(f)(3). Somebody
should be able to read them without reading a stemmer.

A word in one of these is not banned. It may only reach the draft by way of the
worker's own words -- see `draft_language.findings`. Ethnicity is the exception
and is handled apart from `CLASSES` for that reason.
"""

from __future__ import annotations

# --- the hazardous classes -----------------------------------------------
#
# Each is a class of meaning, not a list of sentences somebody imagined. A word
# in one of these may still reach the draft; it may only do so by way of the
# worker's own words.

CRIME = "a criminal characterisation"
DESCRIPTION = "a physical description of a person"
INTENT = "an assertion about somebody's intent"
ETHNICITY = "a person's race or ethnicity"
FIGURE = "a figure nobody stated"

CRIME_WORDS = frozenset("""
rob robbed robbing robbery robber
steal stole stolen stealing theft thief shoplift shoplifting shoplifter
burgle burglary burglar loot looting
mug mugged mugging
assault assaulted assaulting battery
attack attacked attacking attacker
kill killed killing murder murdered homicide manslaughter
stab stabbed stabbing shoot shot shooting
threaten threatened threatening threat threats intimidate intimidated
rape raped sexual
abduct abducted kidnap kidnapped hostage
extort extortion blackmail
arson vandalise vandalised vandalism
armed weapon weapons knife gun firearm pistol machete
trespass trespassing
""".split())

# Features that belong to a person and to nobody else. A "red jacket" is only a
# description when somebody is wearing it, and the grounding rule below is what
# distinguishes a jacket the worker mentioned from one the model invented.
DESCRIPTION_WORDS = frozenset("""
hair haired blonde blond brunette ginger greying balding bald
beard bearded moustache mustache goatee stubble sideburns cleanshaven
tattoo tattoos tattooed piercing piercings scar scars freckles birthmark
dreadlocks cornrows braids ponytail
complexion skinned build height weight physique
tall short slim slender skinny stocky heavyset chubby overweight muscular
teens twenties thirties forties fifties sixties seventies eighties
teenage teenager middleaged elderly youngish
jacket coat hoodie hooded jumper sweater shirt tshirt blouse
trousers jeans shorts skirt tracksuit uniform overalls
cap hat beanie balaclava mask hood scarf gloves
trainers sneakers shoes boots sandals
glasses spectacles sunglasses
accent lisp
""".split())

ETHNICITY_WORDS = frozenset("""
white black brown asian african caribbean hispanic latino latina latinx
caucasian oriental arab arabic middleeastern indian pakistani chinese japanese
korean vietnamese filipino mexican somali nigerian ethnic ethnicity race racial
""".split())

INTENT_WORDS = frozenset("""
intent intention intentions intentional intentionally intended intending
deliberate deliberately purposely wilfully willfully knowingly
premeditated planned plotting motive motivated
trying tried attempt attempted attempting
""".split())

# The three classes the grounding rule applies to. Ethnicity is handled apart
# from them because it is the one unconditional refusal.
CLASSES: tuple[tuple[str, frozenset[str]], ...] = (
    (CRIME, CRIME_WORDS),
    (DESCRIPTION, DESCRIPTION_WORDS),
    (INTENT, INTENT_WORDS),
)
