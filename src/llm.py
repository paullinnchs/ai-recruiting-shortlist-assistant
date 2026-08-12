"""Single entry point for LLM calls.

Every LLM request in the project goes through :func:`complete_json`. Centralizing
it gives one place to classify failures, one place to log them, and one seam to
substitute in tests without network access.

Failures raise an :class:`LLMError`. Callers decide what to do about them; this
module never silently degrades to another engine on its own.
"""

from __future__ import annotations

import json
import os

import run_log as run_log_module

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.2


class LLMError(Exception):
    """Base class for every LLM failure."""


class LLMUnavailable(LLMError):
    """No API key, or the client library could not be loaded."""


class LLMCallFailed(LLMError):
    """The request reached the client but did not return a usable response."""


class LLMInvalidResponse(LLMError):
    """A response came back but was not a JSON object."""


def load_env_file(path: str = ".env") -> None:
    """Load ``KEY=value`` pairs from a local .env file without overriding os.environ."""
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def is_available() -> bool:
    """True when an API key is present, after loading the local .env file."""
    load_env_file()
    return bool(os.getenv("OPENAI_API_KEY"))


def model_name() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def complete_json(
    system_prompt: str,
    user_prompt: str,
    *,
    purpose: str = "",
    model: str | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
    run_log=None,
) -> dict:
    """Send one chat completion and return the parsed JSON object.

    ``purpose`` is a short label recorded in the run log so a completed run
    shows which step made which call. Prompts themselves are not logged.
    """
    log = run_log or run_log_module.null_log()

    if not is_available():
        raise LLMUnavailable("No OPENAI_API_KEY found.")

    model = model or model_name()
    log.event("llm_call_started", purpose=purpose, model=model, temperature=temperature)

    try:
        from openai import OpenAI
    except Exception as exc:
        log.error("llm_unavailable", exc, purpose=purpose)
        raise LLMUnavailable(str(exc)) from exc

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
        )
    except Exception as exc:
        log.error("llm_call_failed", exc, purpose=purpose, model=model)
        raise LLMCallFailed(str(exc)) from exc

    try:
        content = response.choices[0].message.content
        data = json.loads(content)
    except Exception as exc:
        log.error("llm_invalid_response", exc, purpose=purpose, model=model)
        raise LLMInvalidResponse(str(exc)) from exc

    if not isinstance(data, dict):
        exc = LLMInvalidResponse(f"Expected a JSON object, received {type(data).__name__}.")
        log.error("llm_invalid_response", exc, purpose=purpose, model=model)
        raise exc

    log.event("llm_call_succeeded", purpose=purpose, model=model, keys=sorted(data))
    return data
