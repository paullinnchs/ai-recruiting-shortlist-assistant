"""JD readiness gate — Design spec sections 8 (Step 1), 13, 14, and 16 (Tests 1-2)."""

import llm
import pytest
from jd_readiness import check_readiness, check_readiness_deterministic, format_readiness_report
from schemas import EvaluationPath, ReadinessStatus


# --- Test Category 1: strong job description -> SUFFICIENT --------------------


def test_strong_jd_is_sufficient(jd_strong):
    result = check_readiness_deterministic(jd_strong)
    assert result.status is ReadinessStatus.SUFFICIENT
    assert result.missing_critical == []
    assert result.clarification_questions == []
    assert result.recommended_next_action


def test_committed_demo_jd_is_sufficient(jd_demo):
    """The shipped demo must still reach candidate evaluation."""
    result = check_readiness_deterministic(jd_demo)
    assert result.status is ReadinessStatus.SUFFICIENT, result.missing_critical


# --- Test Category 2: concise but clear -> SUFFICIENT -------------------------


def test_concise_but_clear_jd_is_sufficient(jd_concise):
    """Word count is not the measure. A short, specific JD passes."""
    result = check_readiness_deterministic(jd_concise)
    assert result.status is ReadinessStatus.SUFFICIENT, result.missing_critical


def test_concise_jd_passes_while_longer_vague_jd_fails(jd_concise, jd_long_vague):
    """The gate must not reward length."""
    assert len(jd_long_vague) > len(jd_concise) * 4
    assert check_readiness_deterministic(jd_concise).status is ReadinessStatus.SUFFICIENT
    assert check_readiness_deterministic(jd_long_vague).status is ReadinessStatus.INSUFFICIENT


# --- Test Category 3: long but vague -> INSUFFICIENT --------------------------


def test_long_vague_jd_is_insufficient(jd_long_vague):
    result = check_readiness_deterministic(jd_long_vague)
    assert result.status is ReadinessStatus.INSUFFICIENT
    assert result.missing_critical
    assert result.clarification_questions


def test_long_vague_jd_flags_generic_criteria_as_ambiguous(jd_long_vague):
    result = check_readiness_deterministic(jd_long_vague)
    assert any("general" in item.lower() for item in result.ambiguous), result.ambiguous


def test_long_vague_jd_names_the_boilerplate_it_found(jd_long_vague):
    """Telling the recruiter which phrases are the problem makes the ask concrete."""
    result = check_readiness_deterministic(jd_long_vague)
    joined = " ".join(result.ambiguous).lower()
    assert "generic candidate language" in joined
    assert "team player" in joined


def test_specific_jd_is_not_accused_of_boilerplate(jd_strong):
    result = check_readiness_deterministic(jd_strong)
    assert not any("generic candidate language" in item.lower() for item in result.ambiguous)


def test_long_vague_jd_missing_experience_expectation(jd_long_vague):
    result = check_readiness_deterministic(jd_long_vague)
    assert any("experience" in item.lower() for item in result.missing_critical)


# --- Test Category 4: very weak / generic -> INSUFFICIENT ---------------------


def test_generic_jd_is_insufficient(jd_generic):
    result = check_readiness_deterministic(jd_generic)
    assert result.status is ReadinessStatus.INSUFFICIENT
    assert len(result.missing_critical) >= 2


def test_empty_jd_is_insufficient_without_calling_the_llm(fake_llm):
    calls = fake_llm(payload={"status": "SUFFICIENT"})
    result = check_readiness("   \n  ")
    assert result.status is ReadinessStatus.INSUFFICIENT
    assert result.clarification_questions
    assert calls == [], "an empty JD must not cost an LLM call"


# --- Test Category 5: clarification questions --------------------------------


def test_insufficient_result_always_carries_questions(jd_generic, jd_long_vague):
    for job_description in (jd_generic, jd_long_vague):
        result = check_readiness_deterministic(job_description)
        assert result.status is ReadinessStatus.INSUFFICIENT
        assert result.clarification_questions, "stopping without questions leaves the recruiter stuck"
        assert all(question.strip().endswith("?") for question in result.clarification_questions)


def test_questions_target_the_missing_experience_requirement(jd_long_vague):
    result = check_readiness_deterministic(jd_long_vague)
    joined = " ".join(result.clarification_questions).lower()
    assert "experience" in joined
    assert "years" in joined


def test_questions_are_deduplicated(jd_generic):
    result = check_readiness_deterministic(jd_generic)
    assert len(result.clarification_questions) == len(set(result.clarification_questions))


def test_gate_does_not_manufacture_missing_requirements(jd_generic):
    """The gate asks for criteria. It never supplies them."""
    result = check_readiness_deterministic(jd_generic)
    invented = ("5+ years", "bachelor", "salesforce", "python")
    haystack = " ".join(
        [*result.missing_critical, *result.ambiguous, *result.clarification_questions, result.notes]
    ).lower()
    for token in invented:
        assert token not in haystack, f"gate invented a requirement: {token}"


def test_sufficient_jd_reports_unaddressed_areas_without_blocking(jd_concise):
    """A category the JD never mentions is a coverage note, not a blocker."""
    result = check_readiness_deterministic(jd_concise)
    assert result.status is ReadinessStatus.SUFFICIENT
    assert "work authorization" in result.notes.lower()


def test_ambiguous_conditional_category_is_flagged(jd_concise):
    """Gesturing at certifications without naming one is ambiguous, not missing."""
    vague_cert = jd_concise + "\n- Relevant certifications required\n"
    result = check_readiness_deterministic(vague_cert)
    assert any("certification" in item.lower() for item in result.ambiguous), result.ambiguous
    assert result.status is ReadinessStatus.SUFFICIENT, "an ambiguous extra must not block on its own"


# --- Test Category 6: LLM unavailable -> deterministic fallback ---------------


def test_no_api_key_uses_deterministic_path(jd_strong, no_llm):
    result = check_readiness(jd_strong)
    assert result.path is EvaluationPath.FALLBACK
    assert result.status is ReadinessStatus.SUFFICIENT
    assert "deterministic" in result.notes.lower()


def test_llm_failure_falls_back_and_still_gates(jd_long_vague, fake_llm):
    fake_llm(raises=llm.LLMCallFailed("connection reset by peer"))
    result = check_readiness(jd_long_vague)
    assert result.path is EvaluationPath.FALLBACK
    assert result.status is ReadinessStatus.INSUFFICIENT
    assert result.clarification_questions
    assert "connection reset by peer" in result.notes


def test_llm_failure_does_not_wave_a_weak_jd_through(jd_generic, fake_llm):
    """A broken LLM must never become a permissive gate."""
    fake_llm(raises=llm.LLMUnavailable("no key"))
    result = check_readiness(jd_generic)
    assert result.status is ReadinessStatus.INSUFFICIENT


def test_llm_failure_is_logged(jd_generic, fake_llm, tmp_path):
    import run_log

    fake_llm(raises=llm.LLMCallFailed("boom"))
    log = run_log.start_run(output_dir=str(tmp_path))
    check_readiness(jd_generic, run_log=log)
    events = [record["event"] for record in log.records()]
    assert "jd_readiness_llm_failed" in events
    assert "jd_readiness_checked" in events


# --- LLM path: parsing and guardrails ----------------------------------------


def test_llm_sufficient_result_is_used(jd_strong, fake_llm):
    fake_llm(
        payload={
            "status": "SUFFICIENT",
            "missing_critical": [],
            "ambiguous": [],
            "clarification_questions": [],
            "recommended_next_action": "Proceed.",
            "notes": "Criteria are specific.",
        }
    )
    result = check_readiness(jd_strong)
    assert result.status is ReadinessStatus.SUFFICIENT
    assert result.path is EvaluationPath.LLM
    assert result.recommended_next_action == "Proceed."


def test_llm_insufficient_result_is_used(jd_long_vague, fake_llm):
    fake_llm(
        payload={
            "status": "INSUFFICIENT",
            "missing_critical": ["No required skills stated."],
            "ambiguous": ["Traits rather than qualifications."],
            "clarification_questions": ["Which skills are required?"],
            "recommended_next_action": "Ask the hiring manager.",
            "notes": "",
        }
    )
    result = check_readiness(jd_long_vague)
    assert result.status is ReadinessStatus.INSUFFICIENT
    assert result.missing_critical == ["No required skills stated."]
    assert result.clarification_questions == ["Which skills are required?"]


def test_contradictory_llm_result_is_downgraded(jd_long_vague, fake_llm):
    """SUFFICIENT while also naming missing critical criteria resolves to a human."""
    fake_llm(
        payload={
            "status": "SUFFICIENT",
            "missing_critical": ["Minimum experience is not stated."],
            "clarification_questions": [],
        }
    )
    result = check_readiness(jd_long_vague)
    assert result.status is ReadinessStatus.INSUFFICIENT
    assert result.clarification_questions
    assert "downgraded" in result.notes.lower()


def test_insufficient_without_questions_gets_questions(jd_long_vague, fake_llm):
    fake_llm(payload={"status": "INSUFFICIENT", "missing_critical": ["Experience unclear."]})
    result = check_readiness(jd_long_vague)
    assert result.clarification_questions


def test_unrecognized_status_is_treated_as_insufficient(jd_strong, fake_llm):
    fake_llm(payload={"status": "probably fine", "clarification_questions": ["What is required?"]})
    result = check_readiness(jd_strong)
    assert result.status is ReadinessStatus.INSUFFICIENT


def test_malformed_llm_lists_are_coerced(jd_strong, fake_llm):
    fake_llm(
        payload={
            "status": "INSUFFICIENT",
            "missing_critical": "Experience is not stated.",
            "ambiguous": None,
            "clarification_questions": "How many years?",
        }
    )
    result = check_readiness(jd_strong)
    assert result.missing_critical == ["Experience is not stated."]
    assert result.ambiguous == []
    assert result.clarification_questions == ["How many years?"]


def test_llm_receives_the_job_description(jd_strong, fake_llm):
    calls = fake_llm(payload={"status": "SUFFICIENT"})
    check_readiness(jd_strong)
    assert "Senior Revenue Operations Analyst" in calls[0]["user"]
    assert calls[0]["purpose"] == "jd_readiness"


def test_sufficient_result_carries_no_questions(jd_strong, fake_llm):
    fake_llm(payload={"status": "SUFFICIENT", "clarification_questions": ["Stray question?"]})
    result = check_readiness(jd_strong)
    assert result.clarification_questions == []


# --- Report formatting -------------------------------------------------------


def test_report_shows_status_questions_and_next_action(jd_long_vague):
    result = check_readiness_deterministic(jd_long_vague)
    report = format_readiness_report(result)
    assert "INSUFFICIENT" in report
    assert "Clarification questions" in report
    assert result.clarification_questions[0] in report
    assert result.recommended_next_action in report


def test_report_names_the_path_used(jd_strong, no_llm):
    report = format_readiness_report(check_readiness(jd_strong))
    assert "deterministic" in report.lower()


@pytest.mark.parametrize(
    "fixture_name", ["jd_strong", "jd_concise", "jd_long_vague", "jd_generic"]
)
def test_result_is_always_serializable(fixture_name, request):
    result = check_readiness_deterministic(request.getfixturevalue(fixture_name))
    payload = result.to_dict()
    assert payload["status"] in {"SUFFICIENT", "INSUFFICIENT"}
    assert isinstance(payload["clarification_questions"], list)
