from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .models import (
    ExampleItem,
    ForbiddenRule,
    LLMJudgeRule,
    MetricRule,
    RequirementGroup,
    WritingSpec,
    WritingSpecFinding,
    WritingSpecReport,
)


_SENTENCE_SPLIT_RE = re.compile(r"[。！？!?；;]+")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(str(item) for item in value if str(item).strip())
    raise TypeError(f"Expected string or list, got {type(value).__name__}")


def _requirement_from_dict(data: dict[str, Any]) -> RequirementGroup:
    return RequirementGroup(
        id=str(data["id"]),
        description=str(data.get("description") or data["id"]),
        terms=_as_tuple(data.get("terms")),
        min_hits=int(data.get("min_hits", 1)),
        weight=int(data.get("weight", 10)),
    )


def _forbidden_from_dict(data: dict[str, Any]) -> ForbiddenRule:
    severity = str(data.get("severity", "error"))
    if severity not in {"error", "warning"}:
        raise ValueError(f"Invalid severity for forbidden rule {data.get('id')}: {severity}")
    return ForbiddenRule(
        id=str(data["id"]),
        description=str(data.get("description") or data["id"]),
        patterns=_as_tuple(data.get("patterns")),
        severity=severity,  # type: ignore[arg-type]
        weight=int(data.get("weight", 20)),
    )


def _metric_from_dict(data: dict[str, Any]) -> MetricRule:
    severity = str(data.get("severity", "warning"))
    if severity not in {"error", "warning"}:
        raise ValueError(f"Invalid severity for metric rule {data.get('id')}: {severity}")
    return MetricRule(
        id=str(data["id"]),
        description=str(data.get("description") or data["id"]),
        metric=str(data["metric"]),
        terms=_as_tuple(data.get("terms")),
        min_value=(float(data["min"]) if data.get("min") is not None else None),
        max_value=(float(data["max"]) if data.get("max") is not None else None),
        severity=severity,  # type: ignore[arg-type]
        weight=int(data.get("weight", 8)),
    )


def _example_from_dict(data: dict[str, Any], label: str, base_dir: Path) -> ExampleItem:
    severity = str(data.get("severity", "error"))
    if severity not in {"error", "warning"}:
        raise ValueError(f"Invalid severity for example {data.get('id')}: {severity}")
    raw_path = str(data.get("path") or "")
    resolved_path = ""
    if raw_path:
        path = Path(raw_path)
        resolved_path = str(path if path.is_absolute() else base_dir / path)
    if label not in {"positive", "negative"}:
        raise ValueError(f"Invalid example label: {label}")
    return ExampleItem(
        id=str(data["id"]),
        label=label,  # type: ignore[arg-type]
        description=str(data.get("description") or data["id"]),
        path=resolved_path,
        max_similarity=(float(data["max_similarity"]) if data.get("max_similarity") is not None else None),
        min_similarity=(float(data["min_similarity"]) if data.get("min_similarity") is not None else None),
        severity=severity,  # type: ignore[arg-type]
        weight=int(data.get("weight", 20)),
    )


def _examples_from_dict(data: dict[str, Any], base_dir: Path) -> tuple[ExampleItem, ...]:
    examples = data.get("examples") or {}
    if not isinstance(examples, dict):
        return ()
    out: list[ExampleItem] = []
    for label in ("positive", "negative"):
        for item in examples.get(label, []) or []:
            out.append(_example_from_dict(item, label, base_dir))
    return tuple(out)


def _bool_from_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", ""}
    return bool(value)


def _judge_from_dict(data: dict[str, Any]) -> LLMJudgeRule:
    severity = str(data.get("severity", "error"))
    if severity not in {"error", "warning"}:
        raise ValueError(f"Invalid severity for judge rule {data.get('id')}: {severity}")
    return LLMJudgeRule(
        id=str(data.get("id") or "llm-judge"),
        description=str(data.get("description") or data.get("id") or "LLM semantic judge"),
        checklist=_as_tuple(data.get("checklist")),
        min_score=float(data.get("min_score", 80)),
        severity=severity,  # type: ignore[arg-type]
        weight=int(data.get("weight", 25)),
    )


def _judges_from_dict(data: dict[str, Any]) -> tuple[LLMJudgeRule, ...]:
    raw_judges = data.get("judges")
    if isinstance(raw_judges, list):
        return tuple(_judge_from_dict(item) for item in raw_judges if isinstance(item, dict))

    raw_judge = data.get("judge")
    if not isinstance(raw_judge, dict) or not _bool_from_value(raw_judge.get("enabled"), default=False):
        return ()
    return (_judge_from_dict(raw_judge),)


def load_writing_spec(path: str | Path) -> WritingSpec:
    spec_path = Path(path)
    data = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("WritingSpec YAML root must be a mapping")

    meaning_data = data.get("meaning") or {}
    if not isinstance(meaning_data, dict):
        meaning_data = {}
    style_data = data.get("style") or {}
    if not isinstance(style_data, dict):
        style_data = {}
    reader_data = data.get("reader") or {}
    if not isinstance(reader_data, dict):
        reader_data = {}
    metrics_data = [*(data.get("metrics", []) or ()), *(style_data.get("metrics", []) or ())]
    reader_metrics_data = reader_data.get("metrics", []) or ()

    return WritingSpec(
        id=str(data["id"]),
        title=str(data.get("title") or data["id"]),
        version=str(data.get("version", "1")),
        description=str(data.get("description", "")),
        core_question=str(data.get("core_question", "")),
        meaning_contract=str(data.get("meaning_contract", "")),
        threshold=int(data.get("threshold", 80)),
        required=tuple(_requirement_from_dict(item) for item in data.get("required", [])),
        meaning=tuple(_requirement_from_dict(item) for item in meaning_data.get("argument_steps", [])),
        reader=tuple(_requirement_from_dict(item) for item in reader_data.get("requirements", [])),
        forbidden=tuple(_forbidden_from_dict(item) for item in data.get("forbidden", [])),
        metrics=tuple(_metric_from_dict(item) for item in metrics_data),
        reader_metrics=tuple(_metric_from_dict(item) for item in reader_metrics_data),
        examples=_examples_from_dict(data, spec_path.parent),
        judges=_judges_from_dict(data),
        notes=_as_tuple(data.get("notes")),
    )


def load_writing_spec_by_id(spec_id: str, specs_dir: str | Path | None = None) -> WritingSpec:
    """Load a WritingSpec by id without allowing arbitrary path input."""

    normalized_id = spec_id.strip()
    if not normalized_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", normalized_id):
        raise ValueError(f"Invalid writing_spec_id: {spec_id!r}")

    root = Path(__file__).resolve().parents[2]
    directory = Path(specs_dir) if specs_dir else root / "writing_specs"
    if not directory.is_dir():
        raise FileNotFoundError(f"WritingSpec directory not found: {directory}")

    normalized_stem = normalized_id.replace("_", "-")
    candidates = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))
    for candidate in candidates:
        spec = load_writing_spec(candidate)
        if spec.id == normalized_id:
            return spec
        if candidate.stem.replace("_", "-") == normalized_stem:
            return spec
    raise FileNotFoundError(f"WritingSpec not found: {normalized_id}")


def _find_patterns(text: str, patterns: tuple[str, ...]) -> tuple[str, ...]:
    matches: list[str] = []
    for pattern in patterns:
        if pattern.startswith("regex:"):
            expr = pattern.removeprefix("regex:")
            found = re.findall(expr, text, flags=re.MULTILINE)
            matches.extend(str(item if not isinstance(item, tuple) else item[0]) for item in found)
            continue
        if pattern in text:
            matches.append(pattern)
    return tuple(dict.fromkeys(item for item in matches if item))


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(text) if part.strip()]


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


class WritingSpecValidator:
    def __init__(self, spec: WritingSpec):
        self.spec = spec

    def validate(self, text: str) -> WritingSpecReport:
        normalized = (text or "").strip()
        findings: list[WritingSpecFinding] = []
        score = 100.0

        for group in self.spec.required:
            finding = self._validate_requirement(normalized, group, "缺少必要写作锚点")
            if finding is not None:
                findings.append(finding)
                score -= finding.deduction

        for group in self.spec.meaning:
            finding = self._validate_requirement(normalized, group, "MeaningSpec 论证骨架缺失")
            if finding is not None:
                findings.append(finding)
                score -= finding.deduction

        for group in self.spec.reader:
            finding = self._validate_requirement(normalized, group, "ReaderSpec 外行阅读台阶缺失")
            if finding is not None:
                findings.append(finding)
                score -= finding.deduction

        for rule in self.spec.forbidden:
            hits = _find_patterns(normalized, rule.patterns)
            if not hits:
                continue
            deduction = rule.weight if rule.severity == "error" else rule.weight * 0.5
            findings.append(
                WritingSpecFinding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=f"触发反规格：{rule.description}",
                    evidence=hits[:8],
                    deduction=deduction,
                )
            )
            score -= deduction

        metrics = self._compute_metrics(normalized)
        for rule in self.spec.metrics:
            score = self._validate_metric_rule(normalized, metrics, findings, score, rule, "文法指标不满足")

        for rule in self.spec.reader_metrics:
            score = self._validate_metric_rule(normalized, metrics, findings, score, rule, "ReaderSpec 可读性指标不满足")

        for example in self.spec.examples:
            finding = self._validate_example(normalized, example)
            if finding is not None:
                findings.append(finding)
                score -= finding.deduction

        has_error = any(finding.severity == "error" for finding in findings)
        score = max(0.0, min(100.0, score))
        passed = score >= self.spec.threshold and not has_error
        return WritingSpecReport(
            spec_id=self.spec.id,
            passed=passed,
            score=score,
            threshold=self.spec.threshold,
            findings=tuple(findings),
            metrics=metrics,
        )

    def _validate_metric_rule(
        self,
        text: str,
        metrics: dict[str, float],
        findings: list[WritingSpecFinding],
        score: float,
        rule: MetricRule,
        prefix: str,
    ) -> float:
        value = self._metric_value(rule, metrics, text)
        if value is None:
            findings.append(
                WritingSpecFinding(
                    rule_id=rule.id,
                    severity="warning",
                    message=f"未知 metric：{rule.metric}",
                )
            )
            return score
        failed_min = rule.min_value is not None and value < rule.min_value
        failed_max = rule.max_value is not None and value > rule.max_value
        if failed_min or failed_max:
            deduction = rule.weight if rule.severity == "error" else rule.weight * 0.5
            expected = []
            if rule.min_value is not None:
                expected.append(f">= {rule.min_value:g}")
            if rule.max_value is not None:
                expected.append(f"<= {rule.max_value:g}")
            findings.append(
                WritingSpecFinding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    message=(
                        f"{prefix}：{rule.description}; "
                        f"{rule.metric}={value:.2f}, expected {' and '.join(expected)}"
                    ),
                    deduction=deduction,
                )
            )
            score -= deduction
        metrics[f"rule.{rule.id}"] = value
        return score

    @staticmethod
    def _validate_requirement(
        text: str,
        group: RequirementGroup,
        prefix: str,
    ) -> WritingSpecFinding | None:
        hits = _find_patterns(text, group.terms)
        if len(hits) >= group.min_hits:
            return None
        missing_ratio = (group.min_hits - len(hits)) / max(group.min_hits, 1)
        deduction = group.weight * missing_ratio
        return WritingSpecFinding(
            rule_id=group.id,
            severity="error",
            message=f"{prefix}：{group.description} ({len(hits)}/{group.min_hits})",
            evidence=hits,
            deduction=deduction,
        )

    @staticmethod
    def _metric_value(rule: MetricRule, metrics: dict[str, float], text: str) -> float | None:
        if rule.metric == "term_density_per_1000":
            if not rule.terms:
                return None
            count = sum(text.count(term) for term in rule.terms)
            return float(count / max(len(text), 1) * 1000)
        return metrics.get(rule.metric)

    def _validate_example(self, text: str, example: ExampleItem) -> WritingSpecFinding | None:
        if not example.path:
            return None
        path = Path(example.path)
        if not path.exists():
            return WritingSpecFinding(
                rule_id=example.id,
                severity="warning",
                message=f"ExampleBank 样本不存在：{path}",
            )
        sample = path.read_text(encoding="utf-8").strip()
        if not sample:
            return None
        similarity = _text_similarity(text, sample)
        failed = False
        message = ""
        if example.label == "negative" and example.max_similarity is not None:
            failed = similarity >= example.max_similarity
            message = (
                f"ExampleBank 反例相似度过高：{example.description}; "
                f"similarity={similarity:.2f}, max < {example.max_similarity:g}"
            )
        elif example.label == "positive" and example.min_similarity is not None:
            failed = similarity < example.min_similarity
            message = (
                f"ExampleBank 正例相似度不足：{example.description}; "
                f"similarity={similarity:.2f}, min >= {example.min_similarity:g}"
            )
        if not failed:
            return None
        deduction = example.weight if example.severity == "error" else example.weight * 0.5
        return WritingSpecFinding(
            rule_id=example.id,
            severity=example.severity,
            message=message,
            evidence=(f"similarity={similarity:.4f}",),
            deduction=deduction,
        )

    def _compute_metrics(self, text: str) -> dict[str, float]:
        sentences = _sentences(text)
        paragraphs = _paragraphs(text)
        sentence_lengths = [len(sentence) for sentence in sentences]
        paragraph_lengths = [len(paragraph) for paragraph in paragraphs]
        short_sentences = [length for length in sentence_lengths if length <= 12]
        short_paragraphs = [length for length in paragraph_lengths if length <= 16]
        return {
            "char_count": float(len(text)),
            "paragraph_count": float(len(paragraphs)),
            "heading_count": float(len(_HEADING_RE.findall(text))),
            "sentence_count": float(len(sentences)),
            "avg_sentence_chars": (
                float(sum(sentence_lengths) / len(sentence_lengths)) if sentence_lengths else 0.0
            ),
            "avg_paragraph_chars": (
                float(sum(paragraph_lengths) / len(paragraph_lengths)) if paragraph_lengths else 0.0
            ),
            "short_sentence_ratio": (
                float(len(short_sentences) / len(sentence_lengths)) if sentence_lengths else 0.0
            ),
            "short_paragraph_ratio": (
                float(len(short_paragraphs) / len(paragraph_lengths)) if paragraph_lengths else 0.0
            ),
            "max_consecutive_short_paragraphs": float(_max_consecutive_short_paragraphs(paragraph_lengths)),
            "tiny_paragraph_count": float(len([length for length in paragraph_lengths if length <= 8])),
        }


def _max_consecutive_short_paragraphs(lengths: list[int]) -> int:
    max_run = 0
    run = 0
    for length in lengths:
        if length <= 16:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    return max_run


def _text_similarity(left: str, right: str, n: int = 5) -> float:
    left_grams = _char_ngrams(left, n)
    right_grams = _char_ngrams(right, n)
    if not left_grams or not right_grams:
        return 0.0
    return len(left_grams & right_grams) / len(left_grams | right_grams)


def _char_ngrams(text: str, n: int) -> set[str]:
    compact = re.sub(r"\s+", "", text or "")
    if len(compact) < n:
        return {compact} if compact else set()
    return {compact[index:index + n] for index in range(0, len(compact) - n + 1)}
