"""Hiring criteria extraction.

Converts a job description that has passed the readiness gate into
:class:`HiringCriteria`: normalized MUST-HAVE and PREFERRED criteria, each tied
back to the words in the job description that state it.

This module does not decide readiness. Callers run
:func:`jd_readiness.check_readiness` first and only extract criteria from a job
description it returned SUFFICIENT for.

Two paths produce the same :class:`HiringCriteria`:

* the LLM path, used when an API key is configured, and
* a deterministic path that reads the job description's own structure.

Both paths only keep criteria they can trace to the job description text, so
neither can introduce a requirement the job description does not state.
"""

from __future__ import annotations

import re

import llm
import run_log as run_log_module
from jd_readiness import _criteria_items, _looks_like_bullet, _names_something_specific
from prompts import CRITERIA_SYSTEM_PROMPT, CRITERIA_USER_PROMPT
from schemas import Criterion, CriterionKind, EvaluationPath, HiringCriteria

# Existing fixed-rubric categories, kept on each criterion so the new engine can
# be compared against the old scorer during validation.
RUBRIC_CATEGORIES = {
    CriterionKind.EXPERIENCE: "Relevant experience",
    CriterionKind.KSA: "Required skills match",
    CriterionKind.EDUCATION: "Required skills match",
    CriterionKind.CERTIFICATION: "Required skills match",
    CriterionKind.DOMAIN: "Industry/domain fit",
    CriterionKind.TOOL: "Tools/platforms match",
    CriterionKind.LOGISTICS: "Location/work authorization/availability fit",
}

PREFERRED_MARKERS = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "bonus",
    "a plus",
    "desired",
    "ideally",
)

REQUIRED_HEADER_MARKERS = (
    "requirement",
    "required",
    "must have",
    "must-have",
    "qualification",
    "you have",
    "you'll need",
    "you will need",
    "you bring",
    "minimum",
    "essential",
)

# Sections whose bullets describe the job or the company, not the candidate.
NON_CRITERIA_HEADER_MARKERS = (
    "responsibilit",
    "what you'll do",
    "what you will do",
    "you will",
    "you'll",
    "duties",
    "day to day",
    "day-to-day",
    "about",
    "benefit",
    "perk",
    "compensation",
    "salary",
    "why join",
    "what we offer",
    "who we are",
    "our company",
    "mission",
)

KIND_RULES = (
    (CriterionKind.CERTIFICATION, ("certif", "licens", "credential")),
    (
        CriterionKind.EDUCATION,
        ("degree", "bachelor", "master's", "masters", "mba", "phd", "doctorate", "diploma", "high school", "ged"),
    ),
    (
        CriterionKind.LOGISTICS,
        (
            "authorized to work",
            "work authorization",
            "sponsorship",
            "visa",
            "remote",
            "hybrid",
            "onsite",
            "on-site",
            "relocat",
            "travel",
            "clearance",
            "schedule",
            "shift",
            "located",
            "location",
            "availability",
        ),
    ),
    (CriterionKind.DOMAIN, ("industry", "domain", "sector", "vertical")),
)

TOOL_TRIGGERS = ("tool", "platform", "software", "system", "stack")
TOOL_PHRASES = re.compile(r"\b(?:experience with|proficien\w* (?:in|with)|using|knowledge of|hands-on with)\b")
EXPERIENCE_PATTERN = re.compile(r"\d+\s*\+?\s*(?:years?|yrs?)|\b(?:minimum|at least)\b.*\b(?:years?|yrs?)\b")


def extract_criteria(job_description: str, run_log=None, use_llm: bool | None = None) -> HiringCriteria:
    """Convert a ready job description into must-have and preferred criteria.

    Uses the LLM when one is configured and falls back to the deterministic
    extraction when it is not, when the call fails, or when it returns nothing
    that can be traced to the job description.
    """
    log = run_log or run_log_module.null_log()
    should_use_llm = llm.is_available() if use_llm is None else use_llm
    path = EvaluationPath.FALLBACK

    if should_use_llm:
        try:
            criteria = _extract_with_llm(job_description, log)
        except Exception as exc:
            log.error("criteria_extraction_llm_failed", exc)
            criteria = extract_criteria_deterministic(job_description)
        else:
            if criteria.all_criteria():
                path = EvaluationPath.LLM
            else:
                log.event("criteria_extraction_llm_empty")
                criteria = extract_criteria_deterministic(job_description)
    else:
        criteria = extract_criteria_deterministic(job_description)

    log.event(
        "criteria_extracted",
        path=path.value,
        must_have=len(criteria.must_have),
        preferred=len(criteria.preferred),
    )
    return criteria


def _extract_with_llm(job_description: str, log) -> HiringCriteria:
    data = llm.complete_json(
        CRITERIA_SYSTEM_PROMPT,
        CRITERIA_USER_PROMPT.format(job_description=job_description),
        purpose="criteria_extraction",
        run_log=log,
    )

    normalized_jd = _normalize(job_description)
    seen: set[str] = set()
    dropped = 0
    groups: dict[bool, list[Criterion]] = {True: [], False: []}

    for key, required in (("must_have", True), ("preferred", False)):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                dropped += 1
                continue
            text = str(item.get("text") or "").strip()
            excerpt = str(item.get("source_excerpt") or "").strip()
            # Guardrail: a criterion must be traceable to the job description.
            if excerpt and _normalize(excerpt) in normalized_jd:
                source = excerpt
            elif text and _normalize(text) in normalized_jd:
                source = text
            else:
                dropped += 1
                continue
            text = text or source
            if _normalize(text) in seen:
                continue
            seen.add(_normalize(text))
            groups[required].append(
                _make_criterion(text, required, source, kind=_parse_kind(item.get("kind"), text))
            )

    if dropped:
        log.event("criteria_extraction_ungrounded_dropped", count=dropped)

    return _number(
        HiringCriteria(
            job_title=str(data.get("job_title") or "").strip() or _job_title(job_description),
            must_have=groups[True],
            preferred=groups[False],
        )
    )


def extract_criteria_deterministic(job_description: str) -> HiringCriteria:
    """Mechanical extraction from the job description's own sections and labels.

    Bullets under a preferred-style header, or that label themselves preferred,
    become PREFERRED. Bullets under a requirements-style header, or under no
    header at all, become MUST-HAVE. Bullets under responsibilities, benefits,
    and company sections are not candidate criteria and are skipped.
    """
    text = job_description or ""
    lines = [line for line in text.splitlines() if line.strip()]
    must_have: list[Criterion] = []
    preferred: list[Criterion] = []
    seen: set[str] = set()
    section: str | None = None
    found_bullets = False

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not _looks_like_bullet(raw_line):
            if index > 0 and _is_header(line):
                section = _section_for(line)
            continue

        found_bullets = True
        if section == "skip":
            continue
        item = re.sub(r"^\s*(?:[\-\*•·●–—>]|\(?\d{1,2}[\.\)])\s+", "", raw_line).strip()
        if len(item.split()) < 2 or _normalize(item) in seen:
            continue
        seen.add(_normalize(item))

        required = section != "preferred" and not _labels_itself_preferred(item)
        (must_have if required else preferred).append(_make_criterion(item, required, item))

    if not found_bullets:
        # Prose job description: reuse the readiness gate's requirement sentences.
        for sentence in _criteria_items(text):
            if _normalize(sentence) in seen:
                continue
            seen.add(_normalize(sentence))
            required = not _labels_itself_preferred(sentence)
            (must_have if required else preferred).append(_make_criterion(sentence, required, sentence))

    return _number(HiringCriteria(job_title=_job_title(text), must_have=must_have, preferred=preferred))


def classify_kind(text: str) -> CriterionKind:
    """Best-effort category for a criterion, from its own wording."""
    lowered = text.lower()
    for kind, triggers in KIND_RULES:
        if any(trigger in lowered for trigger in triggers):
            return kind
    if EXPERIENCE_PATTERN.search(lowered):
        return CriterionKind.EXPERIENCE
    if any(trigger in lowered for trigger in TOOL_TRIGGERS):
        return CriterionKind.TOOL
    if TOOL_PHRASES.search(lowered) and _names_something_specific(text):
        return CriterionKind.TOOL
    return CriterionKind.KSA


# --- Helpers -----------------------------------------------------------------


def _make_criterion(text: str, required: bool, source: str, kind: CriterionKind | None = None) -> Criterion:
    kind = kind or classify_kind(text)
    return Criterion(
        id="",
        text=text,
        kind=kind,
        rubric_category=RUBRIC_CATEGORIES[kind],
        required=required,
        source_excerpt=source,
    )


def _number(criteria: HiringCriteria) -> HiringCriteria:
    """Stable, readable ids: M1, M2, ... for must-have and P1, P2, ... for preferred."""
    for index, criterion in enumerate(criteria.must_have, start=1):
        criterion.id = f"M{index}"
    for index, criterion in enumerate(criteria.preferred, start=1):
        criterion.id = f"P{index}"
    return criteria


def _is_header(line: str) -> bool:
    return line.endswith(":") or len(line.split()) <= 6


def _section_for(header: str) -> str | None:
    lowered = header.lower()
    if any(marker in lowered for marker in PREFERRED_MARKERS):
        return "preferred"
    if any(marker in lowered for marker in REQUIRED_HEADER_MARKERS):
        return "must"
    if any(marker in lowered for marker in NON_CRITERIA_HEADER_MARKERS):
        return "skip"
    return None


def _labels_itself_preferred(item: str) -> bool:
    lowered = item.lower()
    return any(marker in lowered for marker in PREFERRED_MARKERS)


def _job_title(text: str) -> str:
    first_line = next((line.strip() for line in (text or "").splitlines() if line.strip()), "")
    if first_line and len(first_line.split()) <= 12 and not _looks_like_bullet(first_line):
        return first_line
    return ""


def _parse_kind(value, text: str) -> CriterionKind:
    try:
        return CriterionKind(str(value or "").strip().lower())
    except ValueError:
        return classify_kind(text)


def _normalize(value: str) -> str:
    """Case- and whitespace-insensitive form used to trace text back to its source."""
    value = re.sub(r"^\s*(?:[\-\*•·●–—>]|\(?\d{1,2}[\.\)])\s+", "", value or "")
    return re.sub(r"\s+", " ", value).strip().strip(".;,").lower()
