"""Evidence-based candidate evaluation.

Assesses each candidate against each extracted :class:`Criterion` and turns the
assessments into a :class:`CandidateEvaluation`. Runs alongside the existing
fixed-rubric scorer in ``score_candidates.py``; nothing in the live CLI or web
path calls it yet.

Rules both paths follow:

* ``Verdict.UNKNOWN`` means the candidate information does not address the
  criterion. It is excluded from the normalized score rather than scored as a
  failure, and it is reported as unknown evidence, never as a gap.
* Any verdict other than UNKNOWN must be backed by an evidence quote found
  verbatim in the candidate information. An assessment whose evidence cannot be
  found is downgraded to UNKNOWN.
* Ranking is by decision status first and normalized score second
  (:meth:`CandidateEvaluation.sort_key`).
"""

from __future__ import annotations

import re

import llm
import run_log as run_log_module
from criteria_extraction import extract_criteria
from jd_readiness import check_readiness
from prompts import EVALUATION_SYSTEM_PROMPT, EVALUATION_USER_PROMPT
from schemas import (
    Assessment,
    CandidateEvaluation,
    Confidence,
    Criterion,
    CriterionKind,
    EvaluationPath,
    HiringCriteria,
    NextAction,
    RunResult,
    Verdict,
)

# --- Decision policy ---------------------------------------------------------

MUST_HAVE_POINTS = 10
PREFERRED_POINTS = 5
VERDICT_CREDIT = {
    Verdict.MEETS: 1.0,
    Verdict.PARTIALLY_MEETS: 0.5,
    Verdict.DOES_NOT_MEET: 0.0,
}
RECOMMEND_MIN_SCORE = 70
DO_NOT_RECOMMEND_MAX_SCORE = 50
HIGH_CONFIDENCE_COVERAGE = 80
MEDIUM_CONFIDENCE_COVERAGE = 50

NEXT_ACTION_TEXT = {
    NextAction.RECOMMEND: "Move the candidate forward to recruiter screening.",
    NextAction.REVIEW: "Recruiter review needed before deciding; see the review reasons.",
    NextAction.DO_NOT_RECOMMEND: (
        "Evidence shows misalignment with must-have criteria; confirm before declining."
    ),
    NextAction.CLARIFICATION_REQUIRED: (
        "Clarify the hiring criteria with the hiring manager before evaluating candidates."
    ),
}

# --- Fallback matching vocabulary ---------------------------------------------

STOPWORDS = {
    "a", "an", "and", "the", "of", "in", "on", "at", "to", "for", "with", "by", "as",
    "or", "from", "into", "across", "within", "via", "per", "is", "are", "be", "our",
    "your", "their", "such", "including", "etc", "e.g", "i.e",
    "experience", "experienced", "years", "year", "yrs", "strong", "advanced", "proven",
    "solid", "excellent", "demonstrated", "ability", "able", "skills", "skill",
    "knowledge", "understanding", "familiarity", "familiar", "background", "related",
    "relevant", "similar", "equivalent", "plus", "preferred", "required", "must", "have",
    "work", "working", "platforms", "platform", "systems", "system", "tools", "tool",
    "industry", "minimum", "least", "more", "other", "using", "use", "hands-on",
}
ALTERNATIVE_SPLIT = re.compile(r"\s+or\s+|\s+such as\s+|\s*,\s*|\s*/\s*|\(|\)", re.IGNORECASE)
LEADING_YEARS = re.compile(r"^\s*\d+\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?", re.IGNORECASE)
YEARS_PATTERN = re.compile(r"(\d+)\s*\+?\s*(?:years?|yrs?)", re.IGNORECASE)
NEGATION_CUES = re.compile(r"\b(?:no|not|without|never|lacks?|lacking)\b", re.IGNORECASE)
LIMITED_CUES = re.compile(r"\b(?:limited|minimal|little)\b", re.IGNORECASE)
CLAUSE_SPLIT = re.compile(r"\s+but\s+|;\s*|\s+however\s+", re.IGNORECASE)
FULL_MATCH = 0.75
PARTIAL_MATCH = 0.5


# --- Public entry points -------------------------------------------------------


def run_evaluation(job_description: str, resumes: list[dict], run_log=None, use_llm: bool | None = None) -> RunResult:
    """Readiness gate, then criteria extraction, then evaluation of every candidate.

    The existing readiness gate stays authoritative: when it returns
    INSUFFICIENT, no criteria are extracted and no candidate is evaluated.
    """
    log = run_log or run_log_module.null_log()
    readiness = check_readiness(job_description, run_log=log, use_llm=use_llm)
    result = RunResult(run_id=log.run_id, readiness=readiness)

    if not readiness.is_sufficient:
        result.stopped = True
        result.stop_reason = "jd_criteria_insufficient"
        return result

    result.criteria = extract_criteria(job_description, run_log=log, use_llm=use_llm)
    result.evaluations = evaluate_all_candidates(result.criteria, resumes, run_log=log, use_llm=use_llm)
    return result


def evaluate_all_candidates(
    criteria: HiringCriteria, resumes: list[dict], run_log=None, use_llm: bool | None = None
) -> list[CandidateEvaluation]:
    """Evaluate every candidate and rank them: decision status first, then score."""
    evaluations = [evaluate_candidate(criteria, resume, run_log=run_log, use_llm=use_llm) for resume in resumes]
    return sorted(evaluations, key=lambda evaluation: evaluation.sort_key())


def evaluate_candidate(
    criteria: HiringCriteria, resume: dict, run_log=None, use_llm: bool | None = None
) -> CandidateEvaluation:
    """Assess one candidate against every criterion and decide the next action."""
    log = run_log or run_log_module.null_log()
    resume_text = resume.get("text", "")
    should_use_llm = llm.is_available() if use_llm is None else use_llm
    path = EvaluationPath.FALLBACK
    notes = ""

    if not criteria.all_criteria():
        assessments = []
    elif should_use_llm:
        try:
            assessments = _assess_with_llm(criteria, resume_text, log)
            path = EvaluationPath.LLM
        except Exception as exc:
            log.error("candidate_evaluation_llm_failed", exc, file_name=resume.get("file_name", ""))
            assessments = assess_deterministic(criteria, resume_text)
            notes = f"LLM evaluation failed; used the deterministic evaluation instead. Error: {exc}"
    else:
        assessments = assess_deterministic(criteria, resume_text)
        notes = "No LLM was available; used the deterministic evaluation."

    evaluation = decide(
        criteria,
        assessments,
        candidate_name=resume.get("candidate_name", ""),
        file_name=resume.get("file_name", ""),
        path=path,
        notes=notes,
    )
    log.event(
        "candidate_evaluated",
        file_name=evaluation.file_name,
        path=evaluation.path.value,
        recommendation=evaluation.recommendation.value,
        confidence=evaluation.confidence.value,
        normalized_score=evaluation.normalized_score,
        coverage_pct=evaluation.coverage_pct,
    )
    return evaluation


# --- Decision layer ------------------------------------------------------------


def decide(
    criteria: HiringCriteria,
    assessments: list[Assessment],
    candidate_name: str = "",
    file_name: str = "",
    path: EvaluationPath = EvaluationPath.FALLBACK,
    notes: str = "",
) -> CandidateEvaluation:
    """Turn per-criterion assessments into a scored, confidence-rated next action.

    UNKNOWN criteria contribute nothing to earned or assessable points, so the
    normalized score reflects only what the evidence actually shows.
    """
    total_points = sum(_points(criterion.required) for criterion in criteria.all_criteria())
    earned = 0.0
    assessable = 0
    for assessment in assessments:
        if assessment.verdict is Verdict.UNKNOWN:
            continue
        points = _points(assessment.required)
        assessable += points
        earned += points * VERDICT_CREDIT[assessment.verdict]

    normalized = round(100 * earned / assessable) if assessable else 0
    coverage = round(100 * assessable / total_points) if total_points else 0

    must = [assessment for assessment in assessments if assessment.required]
    must_failed = [assessment for assessment in must if assessment.verdict is Verdict.DOES_NOT_MEET]
    must_unknown = [assessment for assessment in must if assessment.verdict is Verdict.UNKNOWN]
    must_coverage = round(100 * (len(must) - len(must_unknown)) / len(must)) if must else 0
    ungrounded = [assessment for assessment in assessments if not assessment.grounded]

    if not criteria.must_have:
        confidence = Confidence.LOW
    elif not must_unknown and coverage >= HIGH_CONFIDENCE_COVERAGE:
        confidence = Confidence.HIGH
    elif must_coverage >= MEDIUM_CONFIDENCE_COVERAGE and coverage >= MEDIUM_CONFIDENCE_COVERAGE:
        confidence = Confidence.MEDIUM
    else:
        confidence = Confidence.LOW

    if not criteria.must_have:
        action = NextAction.CLARIFICATION_REQUIRED
    elif must_failed and normalized < DO_NOT_RECOMMEND_MAX_SCORE:
        action = NextAction.DO_NOT_RECOMMEND
    elif not must_failed and not must_unknown and normalized >= RECOMMEND_MIN_SCORE:
        action = NextAction.RECOMMEND
    else:
        action = NextAction.REVIEW

    reasons: list[str] = []
    if action is NextAction.CLARIFICATION_REQUIRED:
        reasons.append("No must-have criteria were extracted from the job description.")
    if must_unknown:
        reasons.append(
            f"{len(must_unknown)} must-have criteria have no evidence either way: "
            + "; ".join(assessment.criterion_id for assessment in must_unknown)
            + "."
        )
    if must_failed and action is not NextAction.DO_NOT_RECOMMEND:
        reasons.append(
            "Must-have criteria are not met despite otherwise supporting evidence: "
            + "; ".join(assessment.criterion_id for assessment in must_failed)
            + "."
        )
    if confidence is Confidence.LOW and action is not NextAction.CLARIFICATION_REQUIRED:
        reasons.append(f"Low confidence: only {coverage}% of weighted criteria could be assessed.")
    if ungrounded:
        reasons.append(
            f"{len(ungrounded)} verdicts were downgraded to UNKNOWN because their evidence "
            "could not be found in the candidate information."
        )
    if path is EvaluationPath.FALLBACK and criteria.all_criteria():
        reasons.append("Evaluated by the deterministic fallback, not the LLM.")

    human_review = action in (NextAction.REVIEW, NextAction.CLARIFICATION_REQUIRED) or bool(
        must_unknown or ungrounded or confidence is Confidence.LOW or path is EvaluationPath.FALLBACK
    )

    return CandidateEvaluation(
        candidate_name=candidate_name,
        file_name=file_name,
        earned_points=round(earned),
        assessable_points=assessable,
        normalized_score=normalized,
        coverage_pct=coverage,
        recommendation=action,
        confidence=confidence,
        assessments=assessments,
        strengths=[a.criterion_text for a in assessments if a.verdict is Verdict.MEETS],
        gaps=[a.criterion_text for a in assessments if a.verdict is Verdict.DOES_NOT_MEET]
        + [f"Partially meets: {a.criterion_text}" for a in assessments if a.verdict is Verdict.PARTIALLY_MEETS],
        unknown_evidence=[a.criterion_text for a in assessments if a.verdict is Verdict.UNKNOWN],
        human_review_required=human_review,
        review_reasons=reasons,
        recommended_next_action=NEXT_ACTION_TEXT[action],
        path=path,
        notes=notes,
    )


def _points(required: bool) -> int:
    return MUST_HAVE_POINTS if required else PREFERRED_POINTS


# --- LLM path ------------------------------------------------------------------


def _assess_with_llm(criteria: HiringCriteria, resume_text: str, log) -> list[Assessment]:
    listing = "\n".join(
        f"- {criterion.id} ({'must-have' if criterion.required else 'preferred'}): {criterion.text}"
        for criterion in criteria.all_criteria()
    )
    data = llm.complete_json(
        EVALUATION_SYSTEM_PROMPT,
        EVALUATION_USER_PROMPT.format(criteria=listing, resume_text=resume_text),
        purpose="candidate_evaluation",
        run_log=log,
    )

    returned = {}
    for item in data.get("assessments") or []:
        if isinstance(item, dict) and item.get("criterion_id") is not None:
            returned.setdefault(str(item["criterion_id"]).strip(), item)

    normalized_resume = _normalize(resume_text)
    assessments = []
    for criterion in criteria.all_criteria():
        item = returned.get(criterion.id)
        if item is None:
            assessments.append(
                _unknown(criterion, "The evaluation returned no verdict for this criterion.")
            )
            continue

        verdict = _parse_verdict(item.get("verdict"))
        quote = str(item.get("evidence_quote") or "").strip()
        rationale = str(item.get("rationale") or "").strip()

        # Guardrail: a finding either way must rest on words the candidate wrote.
        if verdict is not Verdict.UNKNOWN and not (quote and _normalize(quote) in normalized_resume):
            assessments.append(
                Assessment(
                    criterion_id=criterion.id,
                    criterion_text=criterion.text,
                    required=criterion.required,
                    verdict=Verdict.UNKNOWN,
                    evidence_quote="",
                    rationale=(
                        f"Downgraded from {verdict.value}: the cited evidence was not found in "
                        "the candidate information."
                    ),
                    grounded=False,
                )
            )
            continue

        if verdict is not Verdict.UNKNOWN:
            relevance = _relevance(criterion, quote)
            # Guardrail: the evidence must be about this criterion, so one broad
            # statement cannot settle unrelated criteria.
            if relevance == 0:
                assessments.append(
                    Assessment(
                        criterion_id=criterion.id,
                        criterion_text=criterion.text,
                        required=criterion.required,
                        verdict=Verdict.UNKNOWN,
                        evidence_quote="",
                        rationale=(
                            f"Downgraded from {verdict.value}: the cited evidence does not "
                            "address this criterion."
                        ),
                        grounded=False,
                    )
                )
                continue
            # Guardrail: tenure in a named field is met only by evidence of that
            # field, not by adjacent experience that shares a word with it.
            if verdict is Verdict.MEETS and YEARS_PATTERN.search(criterion.text) and relevance < FULL_MATCH:
                verdict = Verdict.PARTIALLY_MEETS
                rationale = _join(
                    "Downgraded from MEETS: the evidence does not show the named type of experience.",
                    rationale,
                )

        assessments.append(
            Assessment(
                criterion_id=criterion.id,
                criterion_text=criterion.text,
                required=criterion.required,
                verdict=verdict,
                evidence_quote=quote if verdict is not Verdict.UNKNOWN else "",
                rationale=rationale,
            )
        )
    return assessments


def _relevance(criterion: Criterion, quote: str) -> float:
    """How fully the quote covers the criterion's best-matching alternative (0 to 1)."""
    alternatives = _alternatives(criterion)
    if not alternatives:
        return 1.0  # Nothing specific to check against; rely on the quote grounding.
    return max(_coverage(terms, quote) for terms, _ in alternatives)


def _join(*parts: str) -> str:
    return " ".join(part for part in parts if part)


def _parse_verdict(value) -> Verdict:
    text = re.sub(r"[\s\-]+", "_", str(value or "").strip().upper())
    try:
        return Verdict(text)
    except ValueError:
        return Verdict.UNKNOWN


# --- Deterministic fallback ----------------------------------------------------


def assess_deterministic(criteria: HiringCriteria, resume_text: str) -> list[Assessment]:
    """Mechanical per-criterion assessment. No LLM, no network, fully repeatable.

    A criterion the resume never mentions is UNKNOWN. DOES_NOT_MEET is only
    returned when the resume itself states the absence ("No SaaS experience").
    """
    clauses = _clauses(resume_text)
    return [_assess_one(criterion, clauses) for criterion in criteria.all_criteria()]


def _assess_one(criterion: Criterion, clauses: list[tuple[str, str]]) -> Assessment:
    alternatives = _alternatives(criterion)
    if not alternatives:
        return _unknown(criterion, "The criterion has no specific terms that can be checked mechanically.")

    best_positive = (0.0, "")
    negative = limited = ""
    for terms, named in alternatives:
        for clause, tone in clauses:
            coverage = _coverage(terms, clause)
            if tone == "positive":
                if coverage > best_positive[0]:
                    best_positive = (coverage, clause)
                continue
            # A stated absence counts when it names the criterion's specific
            # subject ("No AWS experience"), even without the surrounding verbs.
            if coverage < FULL_MATCH and not (named and _coverage(named, clause) == 1.0):
                continue
            if tone == "negative" and not negative:
                negative = clause
            elif tone == "limited" and not limited:
                limited = clause

    coverage, positive_clause = best_positive
    if coverage >= FULL_MATCH:
        verdict, quote, rationale = Verdict.MEETS, positive_clause, "The candidate information states this directly."
        if criterion.kind is CriterionKind.EXPERIENCE:
            verdict, rationale = _check_tenure(criterion.text, positive_clause)
    elif negative:
        verdict, quote, rationale = Verdict.DOES_NOT_MEET, negative, "The candidate information states this is absent."
    elif limited:
        verdict, quote, rationale = Verdict.PARTIALLY_MEETS, limited, "The candidate information describes this as limited."
    elif coverage >= PARTIAL_MATCH:
        verdict, quote, rationale = (
            Verdict.PARTIALLY_MEETS,
            positive_clause,
            "The candidate information addresses part of this criterion.",
        )
    else:
        return _unknown(criterion, "The candidate information does not address this criterion.")

    return Assessment(
        criterion_id=criterion.id,
        criterion_text=criterion.text,
        required=criterion.required,
        verdict=verdict,
        evidence_quote=quote,
        rationale=rationale,
    )


def _check_tenure(criterion_text: str, clause: str) -> tuple[Verdict, str]:
    required = YEARS_PATTERN.search(criterion_text)
    if not required:
        return Verdict.MEETS, "The candidate information states this directly."
    stated = [int(value) for value in YEARS_PATTERN.findall(clause)]
    if not stated:
        return Verdict.PARTIALLY_MEETS, "Relevant experience is stated, but its length is not."
    if max(stated) >= int(required.group(1)):
        return Verdict.MEETS, f"{max(stated)} years stated; {required.group(1)}+ required."
    return Verdict.PARTIALLY_MEETS, f"{max(stated)} years stated; {required.group(1)}+ required."


def _alternatives(criterion: Criterion) -> list[tuple[list[str], list[str]]]:
    """Term groups, any one of which satisfies the criterion.

    "CRM systems such as Salesforce or HubSpot" yields [crm], [salesforce],
    [hubspot]. Education and certification wording is kept whole, because a
    field of study listed on its own is not the credential. Each group also
    carries its named terms (capitalized or acronyms, such as "AWS").
    """
    text = LEADING_YEARS.sub("", criterion.text)
    if criterion.kind in (CriterionKind.EDUCATION, CriterionKind.CERTIFICATION):
        parts = [text]
    else:
        parts = ALTERNATIVE_SPLIT.split(text)
    groups = []
    for part in parts:
        terms = _terms(part)
        if terms:
            named = [term for term in _terms(" ".join(re.findall(r"\b[A-Z][\w+#.\-']*", part))) if term in terms]
            groups.append((terms, named))
    return groups


def _terms(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9+#.\-']*", text.lower())
    cleaned = [token.strip(".'-").removesuffix("'s") for token in tokens]
    return [token for token in cleaned if len(token) >= 2 and token not in STOPWORDS]


def _coverage(terms: list[str], clause: str) -> float:
    words = _terms(clause)
    hits = sum(1 for term in terms if any(_same_word(term, word) for word in words))
    return hits / len(terms)


def _same_word(term: str, word: str) -> bool:
    """Exact match for short terms (AI, HR, SQL); shared stem for longer ones."""
    if len(term) <= 3 or len(word) <= 3:
        return term == word
    stem = term[:5]
    return word.startswith(stem) or term.startswith(word[:5])


def _clauses(resume_text: str) -> list[tuple[str, str]]:
    """Split the resume into clauses, each tagged positive, negative, or limited."""
    clauses = []
    for line in (resume_text or "").splitlines():
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            for clause in CLAUSE_SPLIT.split(sentence):
                clause = clause.strip()
                if not clause:
                    continue
                if NEGATION_CUES.search(clause):
                    tone = "negative"
                elif LIMITED_CUES.search(clause):
                    tone = "limited"
                else:
                    tone = "positive"
                clauses.append((clause, tone))
    return clauses


def _unknown(criterion: Criterion, rationale: str) -> Assessment:
    return Assessment(
        criterion_id=criterion.id,
        criterion_text=criterion.text,
        required=criterion.required,
        verdict=Verdict.UNKNOWN,
        rationale=rationale,
    )


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().strip(".;,").lower()
