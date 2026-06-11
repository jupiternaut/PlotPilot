from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Severity = Literal["error", "warning"]
ExampleLabel = Literal["positive", "negative"]


@dataclass(frozen=True)
class RequirementGroup:
    """A semantic or stylistic anchor that must appear in the draft."""

    id: str
    description: str
    terms: tuple[str, ...]
    min_hits: int = 1
    weight: int = 10


@dataclass(frozen=True)
class ForbiddenRule:
    """A drift marker that should not appear in the draft."""

    id: str
    description: str
    patterns: tuple[str, ...]
    severity: Severity = "error"
    weight: int = 20


@dataclass(frozen=True)
class MetricRule:
    """A numeric style rule computed from the candidate text."""

    id: str
    description: str
    metric: str
    terms: tuple[str, ...] = field(default_factory=tuple)
    min_value: float | None = None
    max_value: float | None = None
    severity: Severity = "warning"
    weight: int = 8


@dataclass(frozen=True)
class ExampleItem:
    """A positive or negative example used by the verifier."""

    id: str
    label: ExampleLabel
    description: str = ""
    path: str = ""
    max_similarity: float | None = None
    min_similarity: float | None = None
    severity: Severity = "error"
    weight: int = 20


@dataclass(frozen=True)
class LLMJudgeRule:
    """A model-judged semantic check applied after deterministic checks pass."""

    id: str
    description: str
    checklist: tuple[str, ...] = field(default_factory=tuple)
    min_score: float = 80.0
    severity: Severity = "error"
    weight: int = 25


@dataclass(frozen=True)
class WritingSpec:
    id: str
    title: str
    version: str = "1"
    description: str = ""
    core_question: str = ""
    meaning_contract: str = ""
    threshold: int = 80
    required: tuple[RequirementGroup, ...] = field(default_factory=tuple)
    meaning: tuple[RequirementGroup, ...] = field(default_factory=tuple)
    reader: tuple[RequirementGroup, ...] = field(default_factory=tuple)
    forbidden: tuple[ForbiddenRule, ...] = field(default_factory=tuple)
    metrics: tuple[MetricRule, ...] = field(default_factory=tuple)
    reader_metrics: tuple[MetricRule, ...] = field(default_factory=tuple)
    examples: tuple[ExampleItem, ...] = field(default_factory=tuple)
    judges: tuple[LLMJudgeRule, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class WritingSpecFinding:
    rule_id: str
    severity: Severity
    message: str
    evidence: tuple[str, ...] = field(default_factory=tuple)
    deduction: float = 0.0


@dataclass(frozen=True)
class WritingSpecReport:
    spec_id: str
    passed: bool
    score: float
    threshold: int
    findings: tuple[WritingSpecFinding, ...]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "passed": self.passed,
            "score": round(self.score, 2),
            "threshold": self.threshold,
            "metrics": {k: round(v, 4) for k, v in self.metrics.items()},
            "findings": [
                {
                    "rule_id": finding.rule_id,
                    "severity": finding.severity,
                    "message": finding.message,
                    "evidence": list(finding.evidence),
                    "deduction": round(finding.deduction, 2),
                }
                for finding in self.findings
            ],
        }
