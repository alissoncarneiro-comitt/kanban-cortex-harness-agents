#!/usr/bin/env python3
"""Gera review-report.md estruturado a partir de violações e failure modes."""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_FEATURE = "UNKNOWN"
DEFAULT_OUTPUT = "review-report.md"

BLOCKER_LINE_RE = re.compile(
    r"\[(?:BLOCKER|BLOCKING)\]"
    r"|(?:^|\s)(?:BLOCKER|BLOCKING)(?:\s|:|\]|—|$)",
    re.IGNORECASE,
)


def has_violations(content: str) -> bool:
    return bool(extract_violation_lines(content))


def extract_violation_lines(content: str) -> list[str]:
    if not content.strip():
        return []
    lines = []
    for line in content.splitlines():
        upper = line.upper()
        if upper.startswith("VIOLATION:") or upper.startswith("VIOLATION "):
            lines.append(line.strip())
    return lines


def find_blocking_failure_modes(content: str) -> list[str]:
    if not content.strip():
        return []
    blocking: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if stripped.startswith("#") and BLOCKER_LINE_RE.search(stripped):
                blocking.append(stripped)
            continue
        if BLOCKER_LINE_RE.search(stripped):
            blocking.append(stripped)
    return blocking


def determine_decision(has_violation: bool, blocking_modes: list[str]) -> str:
    if has_violation or blocking_modes:
        return "REQUEST_CHANGES"
    return "APPROVE"


def generate_report(
    feature: str,
    violation_lines: list[str],
    failure_modes_body: str,
    blocking_modes: list[str],
    decision: str,
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Review Report — {feature}",
        "",
        f"> Gerado: {timestamp}",
        f"> **Decision: {decision}**",
        "",
        "## Boundary Violations",
        "",
    ]
    if violation_lines:
        lines.extend(f"- {item}" for item in violation_lines)
    else:
        lines.append("- Nenhuma violação de boundary detectada.")
    lines.extend(["", "## Failure Modes", ""])
    if failure_modes_body.strip():
        lines.append(failure_modes_body.rstrip())
    else:
        lines.append("_Sem notas de failure modes fornecidas._")
    if blocking_modes:
        lines.extend(["", "### Itens bloqueantes", ""])
        lines.extend(f"- {item}" for item in blocking_modes)
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"**{decision}**",
            "",
        ]
    )
    if decision == "APPROVE":
        lines.append(
            "Revisor pode confirmar manualmente antes de `/a-test`. "
            "Nenhuma violação de boundary nem failure mode bloqueante."
        )
    else:
        lines.append(
            "Corrigir violações e/ou failure modes bloqueantes antes de avançar. "
            "Re-invoke `/a-build` após correções."
        )
    lines.append("")
    return "\n".join(lines)


def build_report_from_inputs(
    feature: str, violations_content: str, failure_modes_content: str
) -> tuple[str, str]:
    violation_lines = extract_violation_lines(violations_content)
    blocking_modes = find_blocking_failure_modes(failure_modes_content)
    decision = determine_decision(has_violations(violations_content), blocking_modes)
    report = generate_report(
        feature=feature,
        violation_lines=violation_lines,
        failure_modes_body=failure_modes_content,
        blocking_modes=blocking_modes,
        decision=decision,
    )
    return report, decision


def read_optional_file(path: Path | None) -> str:
    if path is None:
        return ""
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gera review-report.md a partir de violações e failure modes"
    )
    parser.add_argument(
        "--feature",
        default=DEFAULT_FEATURE,
        help=f"ID da feature (default: {DEFAULT_FEATURE})",
    )
    parser.add_argument(
        "--violations",
        dest="violations_file",
        help="Arquivo de saída do boundary-checker (txt)",
    )
    parser.add_argument(
        "--failure-modes",
        dest="failure_modes_file",
        help="Arquivo markdown com failure modes do revisor",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Caminho do review-report.md (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args(argv)

    violations_path = Path(args.violations_file) if args.violations_file else None
    failure_path = Path(args.failure_modes_file) if args.failure_modes_file else None
    output_path = Path(args.output)

    try:
        violations_content = read_optional_file(violations_path)
        failure_modes_content = read_optional_file(failure_path)
        report, decision = build_report_from_inputs(
            args.feature, violations_content, failure_modes_content
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
    except FileNotFoundError as exc:
        print(f"ERROR: file not found: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Report written to {output_path}")
    print(f"Decision: {decision}")
    return 1 if decision == "REQUEST_CHANGES" else 0


if __name__ == "__main__":
    sys.exit(main())
