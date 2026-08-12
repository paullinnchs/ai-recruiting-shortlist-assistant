"""Shared test fixtures.

No test in this suite makes a network call. The LLM boundary is
``llm.complete_json``, and tests replace it directly.
"""

import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parents[1]


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


@pytest.fixture
def jd_strong() -> str:
    """Detailed job description with responsibilities and specific requirements."""
    return read_fixture("jd_strong.txt")


@pytest.fixture
def jd_concise() -> str:
    """Short job description that still states its material requirements."""
    return read_fixture("jd_concise.txt")


@pytest.fixture
def jd_long_vague() -> str:
    """Long job description made of culture language and generic traits."""
    return read_fixture("jd_long_vague.txt")


@pytest.fixture
def jd_generic() -> str:
    """Almost no content at all."""
    return read_fixture("jd_generic.txt")


@pytest.fixture
def jd_demo() -> str:
    """The committed demo job description, so the shipped demo stays covered."""
    return (REPO_ROOT / "demo" / "job_description.txt").read_text(encoding="utf-8")


@pytest.fixture
def demo_resume() -> dict:
    text = (REPO_ROOT / "demo" / "sample_resumes" / "candidate1.txt").read_text(encoding="utf-8")
    return {"file_name": "candidate1.txt", "candidate_name": "John Smith", "text": text}


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace the LLM boundary with a canned payload or an exception.

    Usage::

        fake_llm(payload={"status": "SUFFICIENT", ...})
        fake_llm(raises=llm.LLMUnavailable("no key"))
    """
    import llm

    calls = []

    def install(payload=None, raises=None):
        def fake_complete_json(system_prompt, user_prompt, **kwargs):
            calls.append({"system": system_prompt, "user": user_prompt, **kwargs})
            if raises is not None:
                raise raises
            return json.loads(json.dumps(payload))

        monkeypatch.setattr(llm, "complete_json", fake_complete_json)
        monkeypatch.setattr(llm, "is_available", lambda: True)
        return calls

    install.calls = calls
    return install


@pytest.fixture
def no_llm(monkeypatch):
    """Simulate an environment with no API key configured."""
    import llm

    monkeypatch.setattr(llm, "is_available", lambda: False)
