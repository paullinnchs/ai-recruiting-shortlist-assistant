"""Shared data types for the Candidate Evaluation Agent.

Foundation module. Nothing in the current scoring or output path depends on
these types yet. They define the contract that the JD readiness check, the
Candidate Evaluation Skill, confidence handling, and the structured outputs
will populate in later implementation steps.

Two design rules are encoded here on purpose:

1. ``Verdict.UNKNOWN`` is a first-class outcome, distinct from
   ``Verdict.DOES_NOT_MEET``. Absence of evidence is not evidence of absence,
   so a requirement the candidate information does not speak to must never be
   recorded as a confirmed gap.
2. Ranking is grouped by decision status first (see
   ``NextAction.ranking_group``) and only then by normalized score, so a
   high-scoring candidate with thin evidence cannot outrank a well-supported
   recommendation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class ReadinessStatus(str, Enum):
    """Outcome of the JD readiness check."""

    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"


class CriterionKind(str, Enum):
    """Category of a normalized hiring criterion."""

    EXPERIENCE = "experience"
    KSA = "ksa"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    DOMAIN = "domain"
    TOOL = "tool"
    LOGISTICS = "logistics"


class Verdict(str, Enum):
    """How candidate evidence relates to a single criterion.

    UNKNOWN means the available candidate information does not address the
    criterion. It is not a negative finding and must not be scored as one.
    """

    MEETS = "MEETS"
    PARTIALLY_MEETS = "PARTIALLY_MEETS"
    DOES_NOT_MEET = "DOES_NOT_MEET"
    UNKNOWN = "UNKNOWN"


class Confidence(str, Enum):
    """Confidence in a candidate recommendation."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class NextAction(str, Enum):
    """The agent's recommended next action. Never a final hiring decision."""

    RECOMMEND = "RECOMMEND"
    REVIEW = "REVIEW"
    DO_NOT_RECOMMEND = "DO_NOT_RECOMMEND"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"

    @property
    def ranking_group(self) -> int:
        """Primary shortlist sort key. Lower sorts first.

        Decision status outranks numeric score, so every RECOMMEND appears
        ahead of every REVIEW regardless of points.
        """
        return _RANKING_GROUPS[self]


_RANKING_GROUPS = {
    NextAction.RECOMMEND: 0,
    NextAction.REVIEW: 1,
    NextAction.DO_NOT_RECOMMEND: 2,
    NextAction.CLARIFICATION_REQUIRED: 3,
}


class EvaluationPath(str, Enum):
    """Which engine produced a result, so fallback use stays visible."""

    LLM = "llm"
    FALLBACK = "fallback"


@dataclass
class Criterion:
    """One normalized hiring requirement drawn from the job description."""

    id: str
    text: str
    kind: CriterionKind
    rubric_category: str
    required: bool
    source_excerpt: str = ""

    def to_dict(self) -> dict:
        return to_jsonable(asdict(self))


@dataclass
class HiringCriteria:
    """Normalized criteria for a role, split into must-have and preferred."""

    job_title: str = ""
    must_have: list[Criterion] = field(default_factory=list)
    preferred: list[Criterion] = field(default_factory=list)

    def all_criteria(self) -> list[Criterion]:
        return [*self.must_have, *self.preferred]

    def to_dict(self) -> dict:
        return to_jsonable(asdict(self))


@dataclass
class ReadinessResult:
    """Result of validating the hiring criteria before any candidate scoring."""

    status: ReadinessStatus
    missing_critical: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    clarification_questions: list[str] = field(default_factory=list)
    recommended_next_action: str = ""
    path: EvaluationPath = EvaluationPath.LLM
    notes: str = ""

    @property
    def is_sufficient(self) -> bool:
        return self.status is ReadinessStatus.SUFFICIENT

    def to_dict(self) -> dict:
        return to_jsonable(asdict(self))


@dataclass
class Assessment:
    """Evidence assessment for one criterion against one candidate."""

    criterion_id: str
    criterion_text: str
    required: bool
    verdict: Verdict
    evidence_quote: str = ""
    rationale: str = ""
    grounded: bool = True

    def to_dict(self) -> dict:
        return to_jsonable(asdict(self))


@dataclass
class CandidateEvaluation:
    """Everything the agent concluded about one candidate."""

    candidate_name: str
    file_name: str = ""
    scores: dict[str, int] = field(default_factory=dict)
    earned_points: int = 0
    assessable_points: int = 0
    normalized_score: int = 0
    coverage_pct: int = 0
    recommendation: NextAction = NextAction.REVIEW
    match_tier: str = ""
    confidence: Confidence = Confidence.LOW
    assessments: list[Assessment] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    unknown_evidence: list[str] = field(default_factory=list)
    human_review_required: bool = True
    review_reasons: list[str] = field(default_factory=list)
    recommended_next_action: str = ""
    path: EvaluationPath = EvaluationPath.LLM
    notes: str = ""
    outreach_message: str = ""

    def sort_key(self) -> tuple[int, int]:
        """Decision group first, then normalized score descending."""
        return (self.recommendation.ranking_group, -self.normalized_score)

    def to_dict(self) -> dict:
        return to_jsonable(asdict(self))


@dataclass
class RunResult:
    """One end-to-end agent run, reviewable after the fact."""

    run_id: str
    readiness: ReadinessResult | None = None
    criteria: HiringCriteria | None = None
    evaluations: list[CandidateEvaluation] = field(default_factory=list)
    stopped: bool = False
    stop_reason: str = ""

    def to_dict(self) -> dict:
        return to_jsonable(asdict(self))


def to_jsonable(value):
    """Convert dataclass output into plain JSON-serializable values."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value
