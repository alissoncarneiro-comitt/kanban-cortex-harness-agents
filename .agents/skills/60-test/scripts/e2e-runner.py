#!/usr/bin/env python3
"""Executa ACs de requirements.md como testes pytest parametrizados."""
from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUTPUT = "qa-report.md"
AC_SECTION_RE = re.compile(
    r"- \*\*Acceptance Criteria\*\*:\s*\n((?:\s*\d+\.\s+.+\n?)+)",
    re.MULTILINE,
)
AC_ITEM_RE = re.compile(r"^\s*(\d+)\.\s+(.+)$", re.MULTILINE)
ENTAO_ASSERT_RE = re.compile(r"(?:Então|Then)\s+`([^`]+)`", re.IGNORECASE)
BACKTICK_ASSERT_RE = re.compile(r"`([^`]+)`")
CLI_PLACEHOLDER_RE = re.compile(r"<\w+>")
NON_PYTHON_TOKEN_RE = re.compile(r"\b(GATE\s+FAILED|REQUEST_CHANGES|APPROVE|REJECT)\b")


def is_assertable(expr: str) -> bool:
    """Return True if expr is safe to embed as a Python assert."""
    if not expr or not expr.strip():
        return False
    stripped = expr.strip()
    if CLI_PLACEHOLDER_RE.search(stripped):
        return False
    if NON_PYTHON_TOKEN_RE.search(stripped):
        return False
    if stripped.startswith(("--", "-")):
        return False
    if stripped.startswith("assert "):
        stripped = stripped[7:].strip()
    try:
        ast.parse(stripped, mode="eval")
    except SyntaxError:
        return False
    return True


@dataclass
class AcceptanceCriterion:
    number: int
    text: str
    section_index: int

    @property
    def ac_id(self) -> str:
        return f"AC-{self.section_index + 1}-{self.number}"


@dataclass
class AcResult:
    ac_id: str
    text: str
    passed: bool
    evidence: str


def parse_acceptance_criteria(content: str) -> list[AcceptanceCriterion]:
    acs: list[AcceptanceCriterion] = []
    for section_index, match in enumerate(AC_SECTION_RE.finditer(content)):
        block = match.group(1)
        for item in AC_ITEM_RE.finditer(block):
            acs.append(
                AcceptanceCriterion(
                    number=int(item.group(1)),
                    text=item.group(2).strip(),
                    section_index=section_index,
                )
            )
    return acs


def extract_assertion(ac_text: str) -> str | None:
    then_match = ENTAO_ASSERT_RE.search(ac_text)
    if then_match:
        expr = then_match.group(1).strip()
        return expr if is_assertable(expr) else None
    for match in BACKTICK_ASSERT_RE.finditer(ac_text):
        expr = match.group(1).strip()
        if any(op in expr for op in ("==", "!=", "<=", ">=", "<", ">")):
            if is_assertable(expr):
                return expr
    return None


def safe_eval_assertion(expr: str) -> bool:
    if expr.startswith("assert "):
        expr = expr[7:].strip()
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.Expression,
                ast.Compare,
                ast.BoolOp,
                ast.UnaryOp,
                ast.BinOp,
                ast.Constant,
                ast.Eq,
                ast.NotEq,
                ast.Lt,
                ast.LtE,
                ast.Gt,
                ast.GtE,
                ast.Add,
                ast.Sub,
                ast.Mult,
                ast.Div,
                ast.Mod,
                ast.And,
                ast.Or,
                ast.Not,
                ast.Load,
            ),
        ):
            raise ValueError(f"unsupported expression: {expr}")
    return bool(eval(compile(tree, "<ac>", "eval"), {"__builtins__": {}}, {}))


def generate_pytest_module(acs: list[AcceptanceCriterion], output_path: Path) -> Path:
    lines = [
        '"""Generated AC tests — do not edit manually."""',
        "import pytest",
        "",
    ]
    for ac in acs:
        func_name = f"test_ac_{ac.section_index + 1}_{ac.number}"
        assertion = extract_assertion(ac.text)
        lines.append(f"def {func_name}():")
        lines.append(f'    """{ac.text.replace(chr(34), chr(39))}"""')
        if assertion and is_assertable(assertion):
            lines.append(f"    assert ({assertion})")
        else:
            lines.append("    pass  # informational AC")
        lines.append("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


TEST_RESULT_RE = re.compile(r"::(test_ac_(\d+)_(\d+))\s+(PASSED|FAILED)")


def run_pytest(test_file: Path) -> tuple[list[AcResult], str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", str(test_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = proc.stdout + proc.stderr
    results: list[AcResult] = []
    for line in stdout.splitlines():
        match = TEST_RESULT_RE.search(line.strip())
        if not match:
            continue
        section_idx = int(match.group(2)) - 1
        number = int(match.group(3))
        status = match.group(4)
        ac_id = f"AC-{section_idx + 1}-{number}"
        results.append(
            AcResult(
                ac_id=ac_id,
                text=match.group(1),
                passed=status == "PASSED",
                evidence=line.strip(),
            )
        )
    if not results:
        passed = proc.returncode == 0
        results.append(
            AcResult(
                ac_id="AC-0-0",
                text="pytest run",
                passed=passed,
                evidence=stdout.strip() or f"exit code {proc.returncode}",
            )
        )
    return results, stdout


def generate_qa_report(results: list[AcResult], playwright_note: bool) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# QA Report — E2E / AC Runner",
        "",
        f"Generated: {now}",
        "",
    ]
    if playwright_note:
        lines.extend(
            [
                "> **Nota**: `PLAYWRIGHT_AVAILABLE=true` — integração Playwright é task futura; "
                "execução atual via pytest.",
                "",
            ]
        )
    lines.extend(
        [
            "## Acceptance Criteria Results",
            "",
            "| AC | Resultado | Evidência |",
            "|----|-----------|-----------|",
        ]
    )
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        evidence = result.evidence.replace("|", "\\|")
        lines.append(f"| {result.ac_id} | {status} | {evidence} |")
    lines.append("")
    failed = sum(1 for r in results if not r.passed)
    passed = sum(1 for r in results if r.passed)
    lines.append(f"- Total: **{len(results)}** | PASS: **{passed}** | FAIL: **{failed}**")
    if failed:
        lines.append("- **Resultado: FAIL** — um ou mais ACs falharam.")
    else:
        lines.append("- **Resultado: PASS** — todos os ACs passaram.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Executa ACs Given-When-Then de requirements.md via pytest"
    )
    parser.add_argument(
        "--requirements",
        required=True,
        help="Caminho para requirements.md com Acceptance Criteria",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Caminho do qa-report.md (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--workdir",
        default=None,
        help="Diretório para testes gerados (default: temp ao lado do output)",
    )
    args = parser.parse_args(argv)

    req_path = Path(args.requirements)
    output_path = Path(args.output)

    if not req_path.is_file():
        print(f"ERROR: requirements not found: {req_path}", file=sys.stderr)
        return 2

    try:
        content = req_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    acs = parse_acceptance_criteria(content)
    if not acs:
        print("WARNING: no acceptance criteria found", file=sys.stderr)

    workdir = Path(args.workdir) if args.workdir else output_path.parent
    test_file = workdir / "_generated_ac_tests.py"
    generate_pytest_module(acs, test_file)

    results, _stdout = run_pytest(test_file)
    ac_text_map = {ac.ac_id: ac.text for ac in acs}
    for result in results:
        if result.ac_id in ac_text_map:
            result.text = ac_text_map[result.ac_id]

    playwright_note = os.environ.get("PLAYWRIGHT_AVAILABLE", "").lower() == "true"
    report = generate_qa_report(results, playwright_note)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Report written to {output_path}")
    print(f"ACs: {len(results)} | PASS: {sum(1 for r in results if r.passed)}")
    if any(not r.passed for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
