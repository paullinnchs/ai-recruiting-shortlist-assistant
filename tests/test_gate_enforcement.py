"""The gate must actually stop the workflow — Design spec sections 8, 12, and 14.

Tests 7 and 8 from the Step 2 request: candidate scoring must not execute when
readiness is INSUFFICIENT, and must still execute when it is SUFFICIENT.
"""

import main
import pytest
from schemas import EvaluationPath, ReadinessResult, ReadinessStatus


@pytest.fixture
def workspace(tmp_path, monkeypatch, jd_demo):
    """A throwaway working directory laid out like the real project."""
    (tmp_path / "input" / "resumes").mkdir(parents=True)
    (tmp_path / "input" / "job_description.txt").write_text(jd_demo, encoding="utf-8")
    (tmp_path / "input" / "resumes" / "candidate1.txt").write_text(
        "John Smith\n\nEnterprise Customer Success Manager with 7 years of SaaS "
        "experience. Conducted QBRs. Used Salesforce and HubSpot.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def scoring_spy(monkeypatch):
    """Records whether candidate scoring was invoked."""
    calls = []

    def spy(job_description, resumes, run_log=None):
        calls.append({"resumes": len(resumes)})
        return [
            {
                "candidate_name": "John Smith",
                "file_name": "candidate1.txt",
                "scores": {},
                "total_score": 88,
                "strengths": ["7 years of SaaS customer success"],
                "gaps": [],
                "recommendation": "Strong Match",
                "outreach_message": "Hi John, ...",
            }
        ]

    monkeypatch.setattr(main, "score_all_candidates", spy)
    return calls


def stub_readiness(monkeypatch, status):
    result = ReadinessResult(
        status=status,
        missing_critical=(
            [] if status is ReadinessStatus.SUFFICIENT else ["No minimum experience is stated."]
        ),
        clarification_questions=(
            [] if status is ReadinessStatus.SUFFICIENT else ["What is the minimum experience?"]
        ),
        recommended_next_action="Proceed." if status is ReadinessStatus.SUFFICIENT else "Ask.",
        path=EvaluationPath.FALLBACK,
    )
    monkeypatch.setattr(main, "check_readiness", lambda *args, **kwargs: result)
    return result


# --- Test 7: INSUFFICIENT stops candidate evaluation --------------------------


def test_insufficient_readiness_blocks_scoring(workspace, scoring_spy, monkeypatch, capsys):
    stub_readiness(monkeypatch, ReadinessStatus.INSUFFICIENT)
    main.main()
    assert scoring_spy == [], "candidate scoring ran despite insufficient hiring criteria"
    output = capsys.readouterr().out
    assert "INSUFFICIENT" in output
    assert "What is the minimum experience?" in output


def test_insufficient_readiness_writes_no_candidate_outputs(workspace, scoring_spy, monkeypatch):
    stub_readiness(monkeypatch, ReadinessStatus.INSUFFICIENT)
    main.main()
    for name in ("ranked_shortlist.csv", "candidate_report.md", "outreach_messages.md"):
        assert not (workspace / "output" / name).exists(), f"{name} was written after a stop"


def test_insufficient_readiness_does_not_overwrite_earlier_outputs(
    workspace, scoring_spy, monkeypatch
):
    """A stop must not silently replace a previous run's results."""
    output_dir = workspace / "output"
    output_dir.mkdir(exist_ok=True)
    earlier = output_dir / "ranked_shortlist.csv"
    earlier.write_text("Rank,Candidate Name\n1,Earlier Run\n", encoding="utf-8")

    stub_readiness(monkeypatch, ReadinessStatus.INSUFFICIENT)
    main.main()
    assert "Earlier Run" in earlier.read_text(encoding="utf-8")


def test_stop_is_recorded_in_the_run_log(workspace, scoring_spy, monkeypatch):
    stub_readiness(monkeypatch, ReadinessStatus.INSUFFICIENT)
    main.main()
    log_files = list((workspace / "output" / "logs").glob("run-*.jsonl"))
    assert len(log_files) == 1
    body = log_files[0].read_text(encoding="utf-8")
    assert "jd_criteria_insufficient" in body


def test_stop_tells_the_recruiter_nothing_was_written(workspace, scoring_spy, monkeypatch, capsys):
    stub_readiness(monkeypatch, ReadinessStatus.INSUFFICIENT)
    main.main()
    assert "no candidate outputs were written" in capsys.readouterr().out


# --- Test 8: SUFFICIENT lets the existing workflow run unchanged --------------


def test_sufficient_readiness_allows_scoring(workspace, scoring_spy, monkeypatch):
    stub_readiness(monkeypatch, ReadinessStatus.SUFFICIENT)
    main.main()
    assert scoring_spy == [{"resumes": 1}], "candidate scoring did not run on a sufficient JD"


def test_sufficient_readiness_writes_all_three_outputs(workspace, scoring_spy, monkeypatch):
    stub_readiness(monkeypatch, ReadinessStatus.SUFFICIENT)
    main.main()
    for name in ("ranked_shortlist.csv", "candidate_report.md", "outreach_messages.md"):
        assert (workspace / "output" / name).exists(), f"{name} missing"
    assert "John Smith" in (workspace / "output" / "ranked_shortlist.csv").read_text(encoding="utf-8")


def test_demo_jd_passes_the_real_gate_end_to_end(workspace, no_llm):
    """No stubs: the committed demo JD must clear the gate and produce outputs."""
    main.main()
    shortlist = (workspace / "output" / "ranked_shortlist.csv").read_text(encoding="utf-8")
    assert "John Smith" in shortlist
    assert "/100" in shortlist


def test_weak_jd_stops_the_real_workflow_end_to_end(workspace, no_llm, jd_generic, capsys):
    """No stubs: a generic JD must stop before scoring."""
    (workspace / "input" / "job_description.txt").write_text(jd_generic, encoding="utf-8")
    main.main()
    assert not (workspace / "output" / "ranked_shortlist.csv").exists()
    assert "INSUFFICIENT" in capsys.readouterr().out
