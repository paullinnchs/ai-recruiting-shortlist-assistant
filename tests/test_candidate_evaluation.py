"""Phase 1A: criteria extraction and criterion-by-criterion evaluation.

The new engine runs alongside the fixed-rubric scorer. These tests cover it
directly; the live CLI and web paths are unchanged.
"""

import json

import llm
import pytest
from candidate_evaluation import (
    assess_deterministic,
    decide,
    evaluate_all_candidates,
    evaluate_candidate,
    run_evaluation,
)
from criteria_extraction import extract_criteria, extract_criteria_deterministic
from schemas import (
    Assessment,
    Confidence,
    Criterion,
    CriterionKind,
    EvaluationPath,
    HiringCriteria,
    NextAction,
    Verdict,
)


def criterion(id, text, required=True, kind=CriterionKind.KSA):
    return Criterion(id=id, text=text, kind=kind, rubric_category="", required=required, source_excerpt=text)


def assessment(item, verdict, quote=""):
    return Assessment(
        criterion_id=item.id,
        criterion_text=item.text,
        required=item.required,
        verdict=verdict,
        evidence_quote=quote,
    )


def resume(text, name="Candidate"):
    return {"file_name": f"{name.lower()}.txt", "candidate_name": name, "text": text}


@pytest.fixture
def backend_criteria():
    return HiringCriteria(
        job_title="Senior Backend Engineer",
        must_have=[
            criterion("M1", "5+ years building production backend services in Python", kind=CriterionKind.EXPERIENCE),
            criterion("M2", "Experience deploying and operating services on AWS"),
        ],
        preferred=[criterion("P1", "Docker and Kubernetes", required=False)],
    )


# --- Criteria extraction --------------------------------------------------------


def test_ready_jd_is_extracted_into_hiring_criteria(jd_strong):
    criteria = extract_criteria_deterministic(jd_strong)

    assert isinstance(criteria, HiringCriteria)
    assert criteria.job_title == "Senior Revenue Operations Analyst"
    assert [item.id for item in criteria.must_have] == [f"M{n}" for n in range(1, 8)]
    for item in criteria.all_criteria():
        assert item.text and item.rubric_category
        assert isinstance(item.kind, CriterionKind)
        assert item.source_excerpt in jd_strong


def test_must_have_and_preferred_are_distinguished(jd_strong):
    criteria = extract_criteria_deterministic(jd_strong)

    assert all(item.required for item in criteria.must_have)
    assert not any(item.required for item in criteria.preferred)
    assert [item.text for item in criteria.preferred] == [
        "Healthcare or life sciences industry experience",
        "Experience with Snowflake",
        "Salesforce Administrator certification",
    ]
    assert "Strong SQL skills for querying warehouse data" in [item.text for item in criteria.must_have]


def test_responsibilities_are_not_turned_into_requirements(jd_strong):
    texts = [item.text for item in extract_criteria_deterministic(jd_strong).all_criteria()]
    assert not any("territory and quota planning" in text for text in texts)


def test_criteria_kinds_are_classified(jd_strong):
    kinds = {item.text: item.kind for item in extract_criteria_deterministic(jd_strong).all_criteria()}
    assert kinds["Salesforce Administrator certification"] is CriterionKind.CERTIFICATION
    assert kinds["Authorized to work in the United States without sponsorship"] is CriterionKind.LOGISTICS
    assert kinds["Healthcare or life sciences industry experience"] is CriterionKind.DOMAIN
    assert kinds["5+ years in Revenue Operations, Sales Operations, or Business Analytics"] is CriterionKind.EXPERIENCE


def test_llm_criteria_not_found_in_the_jd_are_dropped(jd_concise, fake_llm):
    fake_llm(
        payload={
            "job_title": "Senior Backend Engineer",
            "must_have": [
                {"text": "5+ years of Python backend work", "kind": "experience",
                 "source_excerpt": "5+ years building production backend services in Python"},
                {"text": "Go experience", "kind": "ksa", "source_excerpt": "Experience with Go"},
            ],
            "preferred": [{"text": "Docker and Kubernetes", "kind": "tool", "source_excerpt": "Docker and Kubernetes"}],
        }
    )
    criteria = extract_criteria(jd_concise)

    assert [item.text for item in criteria.must_have] == ["5+ years of Python backend work"]
    assert criteria.must_have[0].kind is CriterionKind.EXPERIENCE
    assert [(item.id, item.required) for item in criteria.preferred] == [("P1", False)]


def test_llm_extraction_failure_falls_back_to_deterministic(jd_concise, fake_llm):
    fake_llm(raises=llm.LLMCallFailed("timeout"))
    criteria = extract_criteria(jd_concise)
    assert criteria.to_dict() == extract_criteria_deterministic(jd_concise).to_dict()


# --- Candidate evaluation: evidence and UNKNOWN semantics -------------------------


def test_evidence_is_attached_to_assessments(backend_criteria):
    text = "Backend engineer with 8 years building production services in Python. Deployed services on AWS."
    by_id = {a.criterion_id: a for a in assess_deterministic(backend_criteria, text)}

    assert by_id["M1"].verdict is Verdict.MEETS
    assert by_id["M2"].verdict is Verdict.MEETS
    for item in (by_id["M1"], by_id["M2"]):
        assert item.evidence_quote and item.evidence_quote in text


def test_unmentioned_criterion_is_unknown_not_does_not_meet(backend_criteria):
    text = "Backend engineer with 8 years building production services in Python."
    by_id = {a.criterion_id: a for a in assess_deterministic(backend_criteria, text)}

    assert by_id["M2"].verdict is Verdict.UNKNOWN
    assert by_id["P1"].verdict is Verdict.UNKNOWN
    assert by_id["M2"].evidence_quote == ""


def test_stated_absence_is_a_confirmed_gap(backend_criteria):
    text = "Backend engineer with 8 years building production services in Python. No AWS experience."
    by_id = {a.criterion_id: a for a in assess_deterministic(backend_criteria, text)}

    assert by_id["M2"].verdict is Verdict.DOES_NOT_MEET
    assert by_id["M2"].evidence_quote == "No AWS experience."


def test_unknown_is_reported_as_unknown_evidence_not_a_gap(backend_criteria):
    text = "Backend engineer with 8 years building production services in Python."
    evaluation = evaluate_candidate(backend_criteria, resume(text), use_llm=False)

    assert backend_criteria.must_have[1].text in evaluation.unknown_evidence
    assert backend_criteria.must_have[1].text not in evaluation.gaps
    assert evaluation.human_review_required
    assert evaluation.recommendation is not NextAction.DO_NOT_RECOMMEND


# --- Decision layer -------------------------------------------------------------


def test_unknown_is_excluded_from_the_normalized_score(backend_criteria):
    m1, m2, p1 = backend_criteria.all_criteria()
    unknown = decide(backend_criteria, [assessment(m1, Verdict.MEETS), assessment(m2, Verdict.UNKNOWN),
                                        assessment(p1, Verdict.UNKNOWN)])
    failed = decide(backend_criteria, [assessment(m1, Verdict.MEETS), assessment(m2, Verdict.DOES_NOT_MEET),
                                       assessment(p1, Verdict.UNKNOWN)])

    assert (unknown.normalized_score, unknown.assessable_points, unknown.coverage_pct) == (100, 10, 40)
    assert (failed.normalized_score, failed.assessable_points, failed.coverage_pct) == (50, 20, 80)
    assert unknown.gaps == [] and failed.gaps == [m2.text]


def test_unknown_must_have_blocks_recommend_and_lowers_confidence(backend_criteria):
    m1, m2, p1 = backend_criteria.all_criteria()
    full = decide(backend_criteria, [assessment(m1, Verdict.MEETS), assessment(m2, Verdict.MEETS),
                                     assessment(p1, Verdict.MEETS)], path=EvaluationPath.LLM)
    thin = decide(backend_criteria, [assessment(m1, Verdict.MEETS), assessment(m2, Verdict.UNKNOWN),
                                     assessment(p1, Verdict.MEETS)], path=EvaluationPath.LLM)

    assert (full.recommendation, full.confidence, full.human_review_required) == (
        NextAction.RECOMMEND, Confidence.HIGH, False)
    assert thin.recommendation is NextAction.REVIEW
    assert thin.confidence is not Confidence.HIGH
    assert thin.human_review_required and thin.review_reasons


def test_confirmed_must_have_failures_lead_to_do_not_recommend(backend_criteria):
    m1, m2, p1 = backend_criteria.all_criteria()
    evaluation = decide(backend_criteria, [assessment(m1, Verdict.DOES_NOT_MEET), assessment(m2, Verdict.DOES_NOT_MEET),
                                           assessment(p1, Verdict.UNKNOWN)])
    assert evaluation.recommendation is NextAction.DO_NOT_RECOMMEND


def test_no_must_have_criteria_requires_clarification():
    evaluation = evaluate_candidate(HiringCriteria(), resume("Anything"), use_llm=False)
    assert evaluation.recommendation is NextAction.CLARIFICATION_REQUIRED
    assert evaluation.human_review_required


def test_decision_status_outranks_raw_score(backend_criteria):
    # Meets every checked criterion (score 100) but AWS is unknown -> REVIEW.
    thin = resume("8 years building production backend services in Python. Docker and Kubernetes.", "Thin")
    # Meets both must-haves, preferred only partially -> RECOMMEND at a lower score.
    supported = resume(
        "8 years building production backend services in Python. Deployed services on AWS. "
        "Limited Docker and Kubernetes exposure.",
        "Supported",
    )
    ranked = evaluate_all_candidates(backend_criteria, [thin, supported], use_llm=False)

    assert [e.candidate_name for e in ranked] == ["Supported", "Thin"]
    assert [e.recommendation for e in ranked] == [NextAction.RECOMMEND, NextAction.REVIEW]
    assert ranked[0].normalized_score < ranked[1].normalized_score


# --- LLM path and fallback ------------------------------------------------------


def test_llm_verdicts_without_resume_evidence_are_downgraded_to_unknown(backend_criteria, fake_llm):
    text = "Backend engineer with 8 years building production services in Python."
    fake_llm(
        payload={
            "assessments": [
                {"criterion_id": "M1", "verdict": "MEETS", "evidence_quote": "8 years building production services in Python",
                 "rationale": "Stated."},
                {"criterion_id": "M2", "verdict": "DOES_NOT_MEET", "evidence_quote": "", "rationale": "No AWS mentioned."},
                {"criterion_id": "P1", "verdict": "MEETS", "evidence_quote": "Kubernetes at scale", "rationale": "Invented."},
            ]
        }
    )
    evaluation = evaluate_candidate(backend_criteria, resume(text))
    by_id = {a.criterion_id: a for a in evaluation.assessments}

    assert evaluation.path is EvaluationPath.LLM
    assert by_id["M1"].verdict is Verdict.MEETS and by_id["M1"].evidence_quote in text
    assert by_id["M2"].verdict is Verdict.UNKNOWN and not by_id["M2"].grounded
    assert by_id["P1"].verdict is Verdict.UNKNOWN and not by_id["P1"].grounded
    assert evaluation.gaps == []
    assert evaluation.human_review_required


RETAIL_RESUME = (
    "Retail Store Manager with 12 years of experience leading teams and improving customer satisfaction. "
    "No SaaS, CRM, or B2B customer success experience."
)


def test_llm_broad_negative_cannot_fail_unrelated_criteria(fake_llm):
    criteria = HiringCriteria(
        must_have=[
            criterion("M1", "Experience with SaaS platforms"),
            criterion("M2", "Experience conducting QBRs"),
            criterion("M3", "Experience with onboarding and implementation"),
        ]
    )
    blanket = "No SaaS, CRM, or B2B customer success experience."
    fake_llm(
        payload={
            "assessments": [
                {"criterion_id": cid, "verdict": "DOES_NOT_MEET", "evidence_quote": blanket, "rationale": ""}
                for cid in ("M1", "M2", "M3")
            ]
        }
    )
    evaluation = evaluate_candidate(criteria, resume(RETAIL_RESUME))
    by_id = {a.criterion_id: a for a in evaluation.assessments}

    assert by_id["M1"].verdict is Verdict.DOES_NOT_MEET
    assert by_id["M2"].verdict is Verdict.UNKNOWN and not by_id["M2"].grounded
    assert by_id["M3"].verdict is Verdict.UNKNOWN and not by_id["M3"].grounded
    assert evaluation.gaps == ["Experience with SaaS platforms"]


def test_llm_adjacent_experience_cannot_meet_a_named_experience_type(fake_llm):
    criteria = HiringCriteria(
        must_have=[
            criterion("M1", "5+ years in Customer Success or Account Management", kind=CriterionKind.EXPERIENCE)
        ]
    )
    retail = "Retail Store Manager with 12 years of experience leading teams and improving customer satisfaction."
    fake_llm(payload={"assessments": [{"criterion_id": "M1", "verdict": "MEETS", "evidence_quote": retail}]})
    adjacent = evaluate_candidate(criteria, resume(RETAIL_RESUME)).assessments[0]

    matching = "Enterprise Customer Success Manager with 7 years of SaaS experience."
    fake_llm(payload={"assessments": [{"criterion_id": "M1", "verdict": "MEETS", "evidence_quote": matching}]})
    named = evaluate_candidate(criteria, resume(matching)).assessments[0]

    assert adjacent.verdict is Verdict.PARTIALLY_MEETS
    assert named.verdict is Verdict.MEETS


def test_llm_omitted_criteria_are_unknown(backend_criteria, fake_llm):
    fake_llm(payload={"assessments": []})
    evaluation = evaluate_candidate(backend_criteria, resume("Python developer."))
    assert {a.verdict for a in evaluation.assessments} == {Verdict.UNKNOWN}
    assert evaluation.normalized_score == 0 and evaluation.assessable_points == 0


def test_llm_failure_falls_back_with_the_same_verdict_semantics(backend_criteria, fake_llm):
    text = "Backend engineer with 8 years building production services in Python."
    fake_llm(raises=llm.LLMCallFailed("connection reset"))
    evaluation = evaluate_candidate(backend_criteria, resume(text))
    by_id = {a.criterion_id: a for a in evaluation.assessments}

    assert evaluation.path is EvaluationPath.FALLBACK
    assert "connection reset" in evaluation.notes
    assert by_id["M1"].verdict is Verdict.MEETS
    assert by_id["M2"].verdict is Verdict.UNKNOWN


def test_no_api_key_uses_the_fallback(backend_criteria, no_llm):
    evaluation = evaluate_candidate(backend_criteria, resume("Python developer."))
    assert evaluation.path is EvaluationPath.FALLBACK
    assert evaluation.human_review_required


# --- End to end -----------------------------------------------------------------


def test_run_evaluation_on_the_demo(jd_demo, no_llm):
    from parse_resumes import read_txt_resumes
    from conftest import REPO_ROOT

    result = run_evaluation(jd_demo, read_txt_resumes(str(REPO_ROOT / "demo" / "sample_resumes")))

    assert not result.stopped
    assert result.criteria.must_have and result.criteria.preferred
    names = [e.candidate_name for e in result.evaluations]
    assert names[-1] == "Michael Brown"
    assert result.evaluations[-1].recommendation is NextAction.DO_NOT_RECOMMEND
    assert json.dumps(result.to_dict())


def test_run_evaluation_stops_when_the_jd_is_not_ready(jd_generic, no_llm):
    result = run_evaluation(jd_generic, [resume("Python developer.")])

    assert result.stopped and result.stop_reason == "jd_criteria_insufficient"
    assert result.criteria is None and result.evaluations == []
