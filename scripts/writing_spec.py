#!/usr/bin/env python3
"""Validate prose against a WritingSpec YAML contract."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.writing_spec import WritingSpecValidator, load_writing_spec


def _format_markdown(report) -> str:
    status = "PASS" if report.passed else "FAIL"
    lines = [
        f"WritingSpec: {report.spec_id}",
        f"Status: {status}",
        f"Score: {report.score:.1f} / threshold {report.threshold}",
        "",
        "Metrics:",
    ]
    for key, value in sorted(report.metrics.items()):
        lines.append(f"- {key}: {value:.4g}")

    if report.findings:
        lines.extend(["", "Findings:"])
        for finding in report.findings:
            evidence = f" | evidence: {', '.join(finding.evidence)}" if finding.evidence else ""
            lines.append(
                f"- [{finding.severity}] {finding.rule_id}: "
                f"{finding.message} (-{finding.deduction:.1f}){evidence}"
            )
    else:
        lines.extend(["", "Findings: none"])
    return "\n".join(lines)


def validate_cmd(args: argparse.Namespace) -> int:
    spec = load_writing_spec(args.spec)
    text = Path(args.input).read_text(encoding="utf-8")
    report = WritingSpecValidator(spec).validate(text)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(_format_markdown(report))
    return 0 if report.passed else 2


def main() -> None:
    parser = argparse.ArgumentParser(description="WritingSpec validation tool")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate a Markdown/TXT file")
    validate.add_argument("--spec", required=True, help="WritingSpec YAML path")
    validate.add_argument("--input", required=True, help="Candidate Markdown/TXT path")
    validate.add_argument("--json", action="store_true", help="Emit JSON report")
    validate.set_defaults(func=validate_cmd)

    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
