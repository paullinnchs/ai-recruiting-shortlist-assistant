"""JD readiness gate.

Decides whether a job description contains enough material hiring criteria to
evaluate candidates fairly. Candidate evaluation must not proceed until this
returns SUFFICIENT.

The check judges criteria quality, not length. A long job description made of
culture language and generic traits is insufficient. A short one that states its
material requirements clearly is sufficient.

The decision is deterministic: it never depends on an LLM response, so the same
job description always gets the same answer. A job description is SUFFICIENT
when it identifies the role and states at least one specific, verifiable
must-have criterion. Education, certifications, tools, domain, logistics, and
experience level are conditional: their absence never blocks on its own.
"""

from __future__ import annotations

import re

import run_log as run_log_module
from schemas import EvaluationPath, ReadinessResult, ReadinessStatus

# --- Thresholds. Deliberately low: the gate screens out job descriptions with
# --- no usable criteria, it does not grade good ones.
MIN_CONCRETE_MUST_HAVE = 1
MIN_CRITERIA_ITEMS = 3  # used only to recognize a role from a title plus duties

REQUIRED_MARKERS = (
    "requirement",
    "required",
    "must have",
    "must-have",
    "qualification",
    "you have",
    "you'll need",
    "you will need",
    "minimum",
    "essential",
    "responsibilities",
)

PREFERRED_MARKERS = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "bonus",
    "a plus",
    "plus:",
    "desired",
    "ideally",
)

PURPOSE_MARKERS = (
    "we are seeking",
    "we're seeking",
    "we are looking",
    "we're looking",
    "we are hiring",
    "you will",
    "you'll",
    "responsibilities",
    "in this role",
    "the role",
    "about the role",
    "reporting to",
)

RESPONSIBILITY_VERBS = (
    "manage",
    "lead",
    "own",
    "build",
    "develop",
    "design",
    "conduct",
    "drive",
    "support",
    "deliver",
    "coordinate",
    "analyze",
    "maintain",
    "partner",
    "collaborate",
    "oversee",
    "implement",
    "onboard",
)

# Phrases that describe a person rather than a verifiable qualification. Their
# presence is not disqualifying; a job description made mostly of them is.
VAGUE_PHRASES = (
    "team player",
    "self-starter",
    "self starter",
    "go-getter",
    "rock star",
    "rockstar",
    "ninja",
    "guru",
    "wear many hats",
    "wears many hats",
    "hit the ground running",
    "think outside the box",
    "fast-paced",
    "fast paced",
    "dynamic environment",
    "passionate",
    "passion for",
    "detail-oriented",
    "detail oriented",
    "hard-working",
    "hard working",
    "strong work ethic",
    "results-driven",
    "results driven",
    "excellent communication",
    "great communication",
    "strong communication",
    "excellent interpersonal",
    "positive attitude",
    "can-do attitude",
    "culture fit",
    "wants to grow",
    "eager to learn",
    "highly motivated",
    "proactive",
    "flexible",
    "adaptable",
    "problem solver",
    "problem-solver",
    "critical thinker",
    "works well with others",
    "multitask",
    "multi-task",
    "other duties as assigned",
    "and more",
    "etc.",
)

DEGREE_CERT_TERMS = (
    "bachelor",
    "master",
    "associate degree",
    "mba",
    "phd",
    "doctorate",
    "degree",
    "diploma",
    "ged",
    "certified",
    "certification",
    "certificate",
    "licensed",
    "license",
    "credential",
    "accredited",
)

"""Specific education levels. Kept apart from DEGREE_CERT_TERMS so that the word
"degree" cannot act as its own evidence of specificity."""
EDUCATION_LEVEL_TERMS = (
    "bachelor",
    "master",
    "associate degree",
    "mba",
    "phd",
    "doctorate",
    "diploma",
    "ged",
    "high school",
    "b.s.",
    "b.a.",
    "m.s.",
)

EXPERIENCE_LEVEL_TERMS = (
    "entry-level",
    "entry level",
    "junior",
    "mid-level",
    "mid level",
    "senior",
    "principal",
    "staff",
    "lead ",
    "director",
    "vp ",
    "vice president",
    "head of",
    "manager",
    "executive",
    "intern",
    "apprentice",
)

# Conditional categories. Flagged as ambiguous only when the job description
# gestures at the category without naming anything specific.
CONDITIONAL_CATEGORIES = {
    "education": {
        "triggers": ("degree", "education", "educational", "academic", "graduate"),
        "anchors": EDUCATION_LEVEL_TERMS,
        "question": (
            "Education is referenced but not specified. What level of education is "
            "required, and is it required or preferred?"
        ),
        "label": "Education requirement is referenced without a specific level.",
    },
    "certification": {
        # No generic anchors: a named certification is recognized by the specific
        # signal on the same line ("Salesforce Administrator certification", "PMP").
        "triggers": ("certif", "licens", "credential", "accredit"),
        "anchors": (),
        "question": (
            "Certifications or licenses are referenced but not named. Which specific "
            "certifications or licenses are required, and which are preferred?"
        ),
        "label": "Certification or license requirement is referenced without naming one.",
    },
    "tools": {
        "triggers": ("tool", "platform", "software", "system", "technolog", "tech stack", "stack"),
        "anchors": (),
        "question": (
            "Tools or platforms are referenced generically. Which specific tools, "
            "platforms, or systems must a candidate have used?"
        ),
        "label": "Tools or platforms are referenced without naming any.",
    },
    "domain": {
        "triggers": ("industry", "domain", "vertical", "sector", "market"),
        "anchors": (),
        "question": (
            "Industry or domain experience is referenced generically. Which specific "
            "industry or domain experience matters for this role, and is it required "
            "or preferred?"
        ),
        "label": "Industry or domain requirement is referenced without naming one.",
    },
    "logistics": {
        "triggers": (
            "location",
            "remote",
            "hybrid",
            "onsite",
            "on-site",
            "relocat",
            "travel",
            "work authorization",
            "authorized to work",
            "visa",
            "sponsorship",
            "clearance",
            "availability",
            "shift",
        ),
        "anchors": (),
        "question": (
            "Location, work authorization, or availability is referenced without "
            "specifics. What are the exact location, work authorization, and "
            "availability requirements?"
        ),
        "label": "Location, work authorization, or availability is referenced without specifics.",
    },
}

CRITICAL_QUESTIONS = {
    "role_purpose": (
        "What is the purpose of this role, and what will the person be responsible "
        "for day to day?"
    ),
    "required_criteria": (
        "Which specific skills, knowledge, and abilities are required to do this "
        "job, and which are preferred?"
    ),
    "experience": (
        "What is the minimum relevant experience required, in years or in "
        "equivalent scope of work?"
    ),
}

CRITICAL_LABELS = {
    "role_purpose": "Role purpose and responsibilities are not described.",
    "required_criteria": (
        "No specific required qualifications are listed that a candidate could be "
        "evaluated against."
    ),
    "experience": "No minimum or expected experience level is stated.",
}

PROCEED_ACTION = "Proceed with candidate evaluation."
HOLD_ACTION = (
    "Send the clarification questions to the hiring manager. Candidate evaluation "
    "is on hold until the hiring criteria are confirmed."
)


def check_readiness(job_description: str, run_log=None, use_llm: bool | None = None) -> ReadinessResult:
    """Validate the hiring criteria before any candidate evaluation.

    Always deterministic, so the same job description always gets the same
    decision. ``use_llm`` is accepted for caller compatibility and ignored.
    """
    log = run_log or run_log_module.null_log()

    if not (job_description or "").strip():
        result = ReadinessResult(
            status=ReadinessStatus.INSUFFICIENT,
            missing_critical=[CRITICAL_LABELS[key] for key in CRITICAL_QUESTIONS],
            clarification_questions=list(CRITICAL_QUESTIONS.values()),
            recommended_next_action=HOLD_ACTION,
            path=EvaluationPath.FALLBACK,
            notes="The job description is empty, so there are no criteria to evaluate against.",
        )
        log.event(
            "jd_readiness_checked",
            status=result.status.value,
            path=result.path.value,
            reason="empty_job_description",
        )
        return result

    result = check_readiness_deterministic(job_description)
    result.notes = _join_notes("Checked by the deterministic readiness rules.", result.notes)

    log.event(
        "jd_readiness_checked",
        status=result.status.value,
        path=result.path.value,
        missing_critical=len(result.missing_critical),
        ambiguous=len(result.ambiguous),
        questions=len(result.clarification_questions),
    )
    return result


def check_readiness_deterministic(job_description: str) -> ReadinessResult:
    """Mechanical readiness check. No LLM, no network, fully repeatable.

    SUFFICIENT requires an identifiable role and at least one specific,
    verifiable must-have criterion. Every other category is conditional: it
    blocks only when the job description says it is required without saying
    what it is.
    """
    # Imported here: criteria_extraction imports helpers from this module.
    from criteria_extraction import extract_criteria_deterministic

    text = job_description or ""
    lowered = text.lower()
    items = _criteria_items(text)
    concrete = [item for item in items if _is_concrete(item)]
    vague = [item for item in items if not _is_concrete(item)]
    concrete_must_have = [
        criterion
        for criterion in extract_criteria_deterministic(text).must_have
        if _is_concrete(criterion.text)
    ]

    missing: list[str] = []
    ambiguous: list[str] = []
    questions: list[str] = []
    notes: list[str] = []

    # --- Critical: identifiable role --------------------------------------------
    # A title counts as identifying the role once it comes with specific criteria.
    if not (_has_role_purpose(text, lowered, items) or (_has_title(text) and concrete_must_have)):
        missing.append(CRITICAL_LABELS["role_purpose"])
        questions.append(CRITICAL_QUESTIONS["role_purpose"])

    # --- Critical: at least one specific must-have criterion --------------------
    enough_concrete = len(concrete_must_have) >= MIN_CONCRETE_MUST_HAVE

    if not enough_concrete:
        missing.append(CRITICAL_LABELS["required_criteria"])
        questions.append(CRITICAL_QUESTIONS["required_criteria"])
        if items:
            ambiguous.append(
                f"{len(vague)} of {len(items)} stated requirements describe general "
                "traits rather than verifiable qualifications."
            )
            questions.append(
                "The following are stated in general terms. What specific, observable "
                "evidence would show a candidate meets them: "
                + "; ".join(vague[:5])
                + "?"
            )
    elif vague and len(vague) > len(concrete):
        ambiguous.append(
            f"{len(vague)} of {len(items)} stated requirements describe general traits "
            "rather than verifiable qualifications."
        )

    boilerplate = _boilerplate_phrases(lowered)
    if boilerplate and len(vague) > len(concrete):
        ambiguous.append(
            "Requirements lean on generic candidate language: " + "; ".join(boilerplate[:6]) + "."
        )

    # --- Conditional: experience expectation (flagged, never blocking) ---------
    if not _has_experience_expectation(text, lowered):
        ambiguous.append(CRITICAL_LABELS["experience"])
        questions.append(CRITICAL_QUESTIONS["experience"])

    # --- Required vs preferred --------------------------------------------------
    has_required_marker = any(marker in lowered for marker in REQUIRED_MARKERS)
    has_preferred_marker = any(marker in lowered for marker in PREFERRED_MARKERS)
    if items and not has_required_marker and not has_preferred_marker:
        ambiguous.append(
            "Required and preferred qualifications cannot be told apart; the listed "
            "items are not labeled either way."
        )
        questions.append("Which of the listed qualifications are required, and which are preferred?")
    elif has_preferred_marker and not has_required_marker:
        ambiguous.append(
            "Preferred qualifications are labeled, but required qualifications are not."
        )
        questions.append("Which qualifications are strictly required for this role?")

    # --- Conditional categories: only when the role gestures at them ------------
    for _, config in CONDITIONAL_CATEGORIES.items():
        if not any(trigger in lowered for trigger in config["triggers"]):
            continue
        if _category_is_anchored(text, lowered, config):
            continue
        # Blocking only when the JD itself says the unnamed category is required.
        if _category_marked_required(text, config):
            missing.append(config["label"])
        else:
            ambiguous.append(config["label"])
        questions.append(config["question"])

    # --- Non-blocking observations ---------------------------------------------
    if not any(trigger in lowered for trigger in CONDITIONAL_CATEGORIES["logistics"]["triggers"]):
        notes.append(
            "The job description does not address location, work authorization, or "
            "availability, so there is nothing to evaluate candidates against in that area."
        )

    status = ReadinessStatus.INSUFFICIENT if missing else ReadinessStatus.SUFFICIENT

    if status is ReadinessStatus.SUFFICIENT:
        questions = []
    else:
        notes.insert(
            0,
            f"Reviewed {len(items)} stated requirement(s); "
            f"{len(concrete)} contained specific, verifiable detail.",
        )

    return ReadinessResult(
        status=status,
        missing_critical=missing,
        ambiguous=ambiguous,
        clarification_questions=_dedupe(questions),
        recommended_next_action=PROCEED_ACTION if status is ReadinessStatus.SUFFICIENT else HOLD_ACTION,
        path=EvaluationPath.FALLBACK,
        notes=" ".join(notes).strip(),
    )


def format_readiness_report(result: ReadinessResult) -> str:
    """Recruiter-readable summary of the gate decision."""
    lines = [
        "Job Criteria Readiness",
        "----------------------",
        f"Status: {result.status.value}",
        f"Checked by: {'LLM review' if result.path is EvaluationPath.LLM else 'deterministic check'}",
    ]

    if result.missing_critical:
        lines.extend(["", "Missing critical criteria:"])
        lines.extend(f"  - {item}" for item in result.missing_critical)

    if result.ambiguous:
        lines.extend(["", "Ambiguous criteria:"])
        lines.extend(f"  - {item}" for item in result.ambiguous)

    if result.clarification_questions:
        lines.extend(["", "Clarification questions for the hiring manager:"])
        lines.extend(
            f"  {index}. {question}"
            for index, question in enumerate(result.clarification_questions, start=1)
        )

    if result.notes:
        lines.extend(["", f"Notes: {result.notes}"])

    lines.extend(["", f"Recommended next action: {result.recommended_next_action}"])
    return "\n".join(lines)


# --- Text inspection helpers --------------------------------------------------


def _criteria_items(text: str) -> list[str]:
    """Pull out the individually stated requirement lines.

    Bulleted or numbered lines are treated as requirement items. When a job
    description uses no bullets, sentences inside a requirements-style paragraph
    are used instead, so prose job descriptions are not unfairly failed.
    """
    items: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        stripped = re.sub(r"^[\-\*•·●–—>]+\s*", "", line)
        stripped = re.sub(r"^\(?\d{1,2}[\.\)]\s+", "", stripped)
        if stripped == line and not _looks_like_bullet(raw_line):
            continue
        if len(stripped.split()) >= 2:
            items.append(stripped)

    if items:
        return items

    for sentence in re.split(r"(?<=[.;!?])\s+", text):
        candidate = sentence.strip()
        if len(candidate.split()) >= 4 and _mentions_requirement(candidate.lower()):
            items.append(candidate)
    return items


def _looks_like_bullet(raw_line: str) -> bool:
    return bool(re.match(r"^\s*(?:[\-\*•·●–—>]|\(?\d{1,2}[\.\)])\s+", raw_line))


def _mentions_requirement(lowered_sentence: str) -> bool:
    return any(
        marker in lowered_sentence
        for marker in (*REQUIRED_MARKERS, "experience", "skill", "ability", "proficien", "knowledge")
    )


def _names_something_specific(fragment: str) -> bool:
    """True when the text names a verifiable thing rather than a quality.

    Numbers, acronyms, and mid-sentence proper nouns are the cheap, reliable
    signals: "5+ years", "CRM", "Salesforce", "Kubernetes".
    """
    if re.search(r"\d", fragment):
        return True
    if re.search(r"\b[A-Z]{2,}s?\b", fragment):  # CRM, SQL, QBRs, AWS
        return True

    tokens = re.findall(r"[A-Za-z][A-Za-z+#.\-]*", fragment)
    for token in tokens[1:]:
        if len(token) > 2 and token[0].isupper() and any(char.islower() for char in token[1:]):
            return True
    return False


def _boilerplate_phrases(lowered_text: str) -> list[str]:
    """Generic candidate language found in the job description, in order."""
    return [phrase for phrase in VAGUE_PHRASES if phrase in lowered_text]


def _is_concrete(item: str) -> bool:
    """True when a requirement contains something verifiable in a resume."""
    if any(term in item.lower() for term in DEGREE_CERT_TERMS):
        return True
    return _names_something_specific(item)


def _has_role_purpose(text: str, lowered: str, items: list[str]) -> bool:
    """A title plus some statement of what the role does or owns."""
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    has_title = 1 <= len(first_line.split()) <= 12 and not _looks_like_bullet(first_line)

    if any(marker in lowered for marker in PURPOSE_MARKERS):
        return True

    verb_hits = sum(1 for verb in RESPONSIBILITY_VERBS if verb in lowered)
    if has_title and verb_hits >= 2:
        return True

    return has_title and len(items) >= MIN_CRITERIA_ITEMS and verb_hits >= 1


def _has_title(text: str) -> bool:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return 1 <= len(first_line.split()) <= 12 and not _looks_like_bullet(first_line)


def _category_marked_required(text: str, config: dict) -> bool:
    """True when a line that mentions the category also says it is required."""
    for line in text.splitlines():
        line_lower = line.lower()
        if any(trigger in line_lower for trigger in config["triggers"]) and re.search(
            r"\b(?:required|must|mandatory)\b", line_lower
        ):
            return True
    return False


def _has_experience_expectation(text: str, lowered: str) -> bool:
    if re.search(r"\d+\s*\+?\s*(?:years?|yrs?)", lowered):
        return True
    if re.search(r"(?:minimum|at least|no less than)\s+\w+\s+(?:years?|yrs?)", lowered):
        return True
    return any(term in lowered for term in EXPERIENCE_LEVEL_TERMS)


def _category_is_anchored(text: str, lowered: str, config: dict) -> bool:
    """True when the category is named specifically rather than gestured at.

    Scoped to the line holding the trigger word, so a proper noun elsewhere in
    the job description cannot vouch for a vague requirement. One specific
    mention anywhere is enough to consider the category named.
    """
    for line in text.splitlines():
        line_lower = line.lower()
        if not any(trigger in line_lower for trigger in config["triggers"]):
            continue
        if any(anchor in line_lower for anchor in config["anchors"]):
            return True
        if _names_something_specific(line):
            return True
    return False


# --- Small utilities ---------------------------------------------------------


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _join_notes(*parts: str) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())
