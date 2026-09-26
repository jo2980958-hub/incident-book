"""The vocabulary California Labor Code 6401.9 uses, in the statute's own
words.

Every option list below was transcribed from the section text at
leginfo.legislature.ca.gov (lawCode=LAB, sectionNum=6401.9) rather than
paraphrased, because the whole argument for this product is that the record
it produces is the record Cal/OSHA asks for. A paraphrase is a different
document.

Three things the first build of this app got wrong, fixed here:

- (B) is "the workplace violence type **or types**", so it is a multi-select,
  and the four types have statutory numbers (Type 1 to Type 4) defined in
  subdivision (a)(6)(B)(iii). The numbers are what a Cal/OSHA inspector reads.
- (D) lists eight classifications, not five.
- (G) is "the type of incident, including ... whether it involved **any** of
  the following", so it is also a multi-select, and it includes animal attack.
- (H) has two named limbs: whether security or law enforcement was contacted
  and their response, and the actions taken to protect employees from a
  continuing threat.
- (I) is "name, job title, **and the date completed**".

Each entry is (value, short label, the statute's own wording). The UI shows
the short label and the statutory wording together, so the person filling the
form is choosing from the law rather than from someone's summary of it.
"""

from __future__ import annotations

STATUTE_NAME = "California Labor Code 6401.9"
STATUTE_URL = (
    "https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml"
    "?lawCode=LAB&sectionNum=6401.9"
)

# (B) Workplace violence type or types. Subdivision (a)(6)(B)(iii).
VIOLENCE_TYPES = (
    (
        "type_1",
        "Type 1: no legitimate business here",
        "Workplace violence committed by a person who has no legitimate business at "
        "the worksite, and includes violent acts by anyone who enters the workplace "
        "or approaches workers with the intent to commit a crime.",
    ),
    (
        "type_2",
        "Type 2: a customer, client or visitor",
        "Workplace violence directed at employees by customers, clients, patients, "
        "students, inmates, or visitors.",
    ),
    (
        "type_3",
        "Type 3: a present or former coworker",
        "Workplace violence against an employee by a present or former employee, "
        "supervisor, or manager.",
    ),
    (
        "type_4",
        "Type 4: someone with a personal relationship to an employee",
        "Workplace violence committed in the workplace by a person who does not work "
        "there, but has or is known to have had a personal relationship with an "
        "employee.",
    ),
)

# (D) Classification of who committed the violence. Subdivision (d)(2)(D).
PERPETRATOR_CLASSES = (
    ("client_or_customer", "Client or customer", "A client or customer."),
    (
        "family_or_friend_of_client",
        "Family or friend of a client or customer",
        "Family or friend of a client or customer.",
    ),
    (
        "stranger_with_criminal_intent",
        "Stranger with criminal intent",
        "A stranger with criminal intent.",
    ),
    ("coworker", "Coworker", "A coworker."),
    ("supervisor_or_manager", "Supervisor or manager", "A supervisor or manager."),
    ("partner_or_spouse", "Partner or spouse", "A partner or spouse."),
    ("parent_or_relative", "Parent or relative", "A parent or relative."),
    ("other", "Other", "Other perpetrator."),
    (
        "not_known",
        "Not known",
        "Not one of the statutory classifications: the person completing the log "
        "does not know who it was. Recorded as unknown rather than guessed.",
    ),
)

# (E) Classification of circumstances at the time. Subdivision (d)(2)(E).
CIRCUMSTANCE_OPTIONS = (
    ("usual_job_duties", "Completing usual job duties", "Completing usual job duties."),
    ("poorly_lit_area", "Working in a poorly lit area", "Working in poorly lit areas."),
    ("rushed", "Rushed", "Rushed."),
    (
        "low_staffing_level",
        "Working during a low staffing level",
        "Working during a low staffing level.",
    ),
    ("isolated_or_alone", "Isolated or alone", "Isolated or alone."),
    (
        "unable_to_get_help",
        "Unable to get help or assistance",
        "Unable to get help or assistance.",
    ),
    (
        "community_setting",
        "Working in a community setting",
        "Working in a community setting.",
    ),
    (
        "unfamiliar_location",
        "Working in an unfamiliar or new location",
        "Working in an unfamiliar or new location.",
    ),
    ("other", "Other", "The statutory list is not exhaustive: describe it in (C)."),
)

# (F) Classification of where the incident occurred. Subdivision (d)(2)(F).
LOCATION_CLASSES = (
    ("in_the_workplace", "In the workplace", "In the workplace."),
    (
        "outside_the_workplace",
        "Parking lot or other area outside the workplace",
        "Parking lot or other area outside the workplace.",
    ),
    ("other_area", "Other area", "Other area."),
)

# (G) Type of incident. Subdivision (d)(2)(G). Multi-select: "whether it
# involved any of the following".
INCIDENT_TYPES = (
    (
        "physical_attack_no_weapon",
        "Physical attack without a weapon",
        "Physical attack without a weapon, including, but not limited to, biting, "
        "choking, grabbing, hair pulling, kicking, punching, slapping, pushing, "
        "pulling, scratching, or spitting.",
    ),
    (
        "attack_with_weapon_or_object",
        "Attack with a weapon or object",
        "Attack with a weapon or object, including, but not limited to, a firearm, "
        "knife, or other object.",
    ),
    (
        "threat",
        "Threat of physical force or of a weapon",
        "Threat of physical force or threat of the use of a weapon or other object.",
    ),
    (
        "sexual_assault_or_threat",
        "Sexual assault or threat",
        "Sexual assault or threat, including, but not limited to, rape, attempted "
        "rape, physical display, or unwanted verbal or physical sexual contact.",
    ),
    ("animal_attack", "Animal attack", "Animal attack."),
    ("other", "Other", "Other."),
)


def _values(options) -> tuple[str, ...]:
    return tuple(value for value, _label, _text in options)


def label_for(options, value: str) -> str:
    for v, label, _text in options:
        if v == value:
            return label
    return value


def labels_for(options, values) -> list[str]:
    return [label_for(options, v) for v in values or []]


VIOLENCE_TYPE_VALUES = _values(VIOLENCE_TYPES)
PERPETRATOR_CLASS_VALUES = _values(PERPETRATOR_CLASSES)
CIRCUMSTANCE_VALUES = _values(CIRCUMSTANCE_OPTIONS)
LOCATION_CLASS_VALUES = _values(LOCATION_CLASSES)
INCIDENT_TYPE_VALUES = _values(INCIDENT_TYPES)

# Old option values from the first build, kept so a database written before
# the statute-exact vocabulary landed still opens. Nothing writes these.
LEGACY_VALUE_MAP = {
    "violence_types": {
        "client_or_customer": "type_2",
        "stranger_with_criminal_intent": "type_1",
        "worker_on_worker": "type_3",
        "personal_relationship": "type_4",
    },
    "perpetrator_class": {
        "stranger": "stranger_with_criminal_intent",
        "supervisor": "supervisor_or_manager",
        "unknown": "not_known",
    },
    "circumstances": {},
    "incident_types": {
        "physical_attack_with_weapon": "attack_with_weapon_or_object",
    },
}


def migrate_value(field: str, value: str) -> str:
    return LEGACY_VALUE_MAP.get(field, {}).get(value, value)
