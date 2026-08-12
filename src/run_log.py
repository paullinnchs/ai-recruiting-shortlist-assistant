"""Append-only JSONL run log for the Candidate Evaluation Agent.

Every step the agent takes writes one JSON object per line so a completed run
can be reconstructed afterward. Long strings are truncated, and resume text and
full prompts are deliberately never passed here.

Logging is opt-in. Callers that have no log use ``null_log()``, which accepts
the same calls and does nothing, so no code path needs to branch on whether
logging is enabled. Nothing writes a log file until a caller explicitly calls
``start_run()``.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOGGER_NAME = "candidate_evaluation_agent"
MAX_FIELD_CHARS = 500


class RunLog:
    """Writes one JSON record per line to a run-scoped log file."""

    def __init__(self, run_id: str, path: Path | str | None = None) -> None:
        self.run_id = run_id
        self.path = Path(path) if path else None
        self._logger = logging.getLogger(LOGGER_NAME)
        self._sequence = 0

    def event(self, event: str, **fields) -> dict:
        """Record a single step. Returns the record that was written."""
        self._sequence += 1
        record = {
            "run_id": self.run_id,
            "seq": self._sequence,
            "timestamp": _timestamp(),
            "event": event,
        }
        for key in sorted(fields):
            record[key] = _clip(fields[key])

        self._write(record)
        self._logger.debug("%s %s", event, record)
        return record

    def error(self, event: str, exc: BaseException, **fields) -> dict:
        """Record a failure, keeping the exception type visible."""
        return self.event(
            event,
            error_type=type(exc).__name__,
            error_message=str(exc),
            **fields,
        )

    def complete(self, **fields) -> dict:
        return self.event("run_completed", **fields)

    def records(self) -> list[dict]:
        """Read the log back. Useful for verification and for tests."""
        if not self.path or not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def _write(self, record: dict) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, ensure_ascii=False) + "\n")


class NullRunLog(RunLog):
    """No-op log with the same interface, so callers never branch."""

    def __init__(self) -> None:
        super().__init__(run_id="", path=None)

    def event(self, event: str, **fields) -> dict:
        return {}

    def records(self) -> list[dict]:
        return []


def start_run(output_dir: str = "output", run_id: str | None = None) -> RunLog:
    """Open a new run log at ``<output_dir>/logs/run-<run_id>.jsonl``."""
    run_id = run_id or new_run_id()
    path = Path(output_dir) / "logs" / f"run-{run_id}.jsonl"
    log = RunLog(run_id=run_id, path=path)
    log.event("run_started")
    return log


def null_log() -> NullRunLog:
    """A log that discards everything. The default for optional parameters."""
    return NullRunLog()


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _clip(value):
    """Keep records readable and avoid dumping large text into the log."""
    if isinstance(value, str) and len(value) > MAX_FIELD_CHARS:
        return value[:MAX_FIELD_CHARS] + f"... [truncated, {len(value)} chars]"
    if isinstance(value, dict):
        return {key: _clip(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clip(item) for item in value]
    return value
