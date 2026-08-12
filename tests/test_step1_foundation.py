"""Step 1 regression cover: the LLM wrapper, run log, and schema contracts.

These were verified by script when Step 1 landed. They are captured here so the
suite protects them from now on.
"""

import json

import llm
import pytest
import run_log
import schemas
import score_candidates


# --- llm.py -------------------------------------------------------------------


def test_scoring_routes_through_the_llm_wrapper(monkeypatch, demo_resume):
    captured = {}

    def fake_complete_json(system_prompt, user_prompt, **kwargs):
        captured.update(kwargs)
        captured["user"] = user_prompt
        return {
            "candidate_name": "John Smith",
            "scores": {
                "Required skills match": 28,
                "Relevant experience": 24,
                "Industry/domain fit": 14,
                "Tools/platforms match": 9,
                "Seniority alignment": 9,
                "Location/work authorization/availability fit": 8,
            },
            "strengths": ["7 years of SaaS customer success"],
            "gaps": [],
        }

    monkeypatch.setattr(llm, "complete_json", fake_complete_json)
    result = score_candidates.score_with_openai("Some JD", demo_resume)

    assert result["total_score"] == 92
    assert captured["purpose"] == "candidate_scoring"
    assert demo_resume["text"] in captured["user"]


def test_llm_failure_message_is_preserved_for_the_fallback_note(monkeypatch, demo_resume):
    monkeypatch.setattr(llm, "is_available", lambda: True)
    monkeypatch.setattr(
        llm,
        "complete_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(llm.LLMCallFailed("connection reset by peer")),
    )
    scored = score_candidates.score_all_candidates("Some JD", [demo_resume])
    assert scored[0]["notes"] == (
        "OpenAI scoring failed; used local heuristic. Error: connection reset by peer"
    )


def test_no_api_key_falls_back_with_the_original_note(monkeypatch, demo_resume):
    monkeypatch.setattr(llm, "is_available", lambda: False)
    scored = score_candidates.score_all_candidates("Some JD", [demo_resume])
    assert scored[0]["notes"] == "No OPENAI_API_KEY found; used local heuristic scoring."


def test_complete_json_requires_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(llm, "load_env_file", lambda path=".env": None)
    with pytest.raises(llm.LLMUnavailable):
        llm.complete_json("system", "user")


def test_scoring_rubric_is_unchanged():
    assert sum(score_candidates.SCORING_WEIGHTS.values()) == 100
    assert callable(score_candidates.load_env_file)


# --- run_log.py ---------------------------------------------------------------


def test_run_log_writes_jsonl(tmp_path):
    log = run_log.start_run(output_dir=str(tmp_path))
    log.event("jd_readiness_checked", status="SUFFICIENT")
    log.complete(candidates=3)

    records = log.records()
    assert [record["seq"] for record in records] == [1, 2, 3]
    assert records[0]["event"] == "run_started"
    assert records[-1]["event"] == "run_completed"
    assert all(json.dumps(record) for record in records)


def test_run_log_truncates_long_fields(tmp_path):
    log = run_log.start_run(output_dir=str(tmp_path))
    log.event("big", blob="x" * 900)
    assert "[truncated, 900 chars]" in log.records()[-1]["blob"]


def test_null_log_discards_everything():
    log = run_log.null_log()
    log.event("ignored", value=1)
    assert log.records() == []


# --- schemas.py ---------------------------------------------------------------


def test_unknown_is_not_a_confirmed_gap():
    assert schemas.Verdict.UNKNOWN is not schemas.Verdict.DOES_NOT_MEET


def test_decision_status_outranks_raw_score():
    thin = schemas.CandidateEvaluation(
        candidate_name="Thin evidence",
        recommendation=schemas.NextAction.REVIEW,
        normalized_score=95,
    )
    supported = schemas.CandidateEvaluation(
        candidate_name="Well supported",
        recommendation=schemas.NextAction.RECOMMEND,
        normalized_score=70,
    )
    ordered = sorted([thin, supported], key=lambda item: item.sort_key())
    assert [item.candidate_name for item in ordered] == ["Well supported", "Thin evidence"]


def test_evaluation_serializes_enums_to_strings():
    payload = schemas.CandidateEvaluation(
        candidate_name="X",
        assessments=[
            schemas.Assessment(
                criterion_id="c1",
                criterion_text="5+ years",
                required=True,
                verdict=schemas.Verdict.UNKNOWN,
            )
        ],
    ).to_dict()
    assert json.loads(json.dumps(payload))["assessments"][0]["verdict"] == "UNKNOWN"
