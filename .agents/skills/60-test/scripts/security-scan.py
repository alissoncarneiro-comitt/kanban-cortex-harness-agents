#!/usr/bin/env python3
"""OWASP static analysis — bandit se disponível, fallback regex."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_OUTPUT = "security-report.md"
CONFIDENCE_BANDIT = 8
CONFIDENCE_REGEX = 5

REGEX_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "A01",
        "Hardcoded secret",
        re.compile(r'password\s*=\s*[\'"][^\'"]{8,}[\'"]', re.IGNORECASE),
    ),
    (
        "A03",
        "SQL f-string injection",
        re.compile(r'f"SELECT.*\{', re.IGNORECASE),
    ),
    (
        "A03",
        "SQL plus concatenation",
        re.compile(r'"SELECT"\s*\+\s*', re.IGNORECASE),
    ),
    (
        "A02",
        "Weak hash (md5/sha1)",
        re.compile(r"hashlib\.(md5|sha1)\s*\("),
    ),
    (
        "A05",
        "Overly permissive chmod",
        re.compile(r"os\.chmod\([^)]*0o?777|chmod\s+777", re.IGNORECASE),
    ),
]

A02_SAFE_RE = re.compile(r"usedforsecurity\s*=\s*False", re.IGNORECASE)

BANDIT_OWASP_MAP: dict[str, tuple[str, str]] = {
    "B105": ("A01", "Hardcoded password"),
    "B106": ("A01", "Hardcoded password"),
    "B107": ("A01", "Hardcoded password"),
    "B608": ("A03", "SQL injection"),
    "B609": ("A03", "SQL injection"),
    "B324": ("A02", "Weak hash function"),
    "B303": ("A02", "Weak hash function"),
    "B103": ("A05", "Insecure permissions"),
}


@dataclass
class Finding:
    owasp: str
    title: str
    severity: str
    file_path: str
    line: int
    source: str
    detail: str = ""


def bandit_available() -> bool:
    return shutil.which("bandit") is not None


def _is_pattern_definition_line(line: str) -> bool:
    """Skip regex definition lines to avoid self-referential false positives."""
    stripped = line.strip()
    return "re.compile(" in stripped or stripped.startswith("REGEX_PATTERNS")


def collect_python_files(target: Path) -> list[Path]:
    if target.is_file() and target.suffix == ".py":
        return [target]
    if target.is_dir():
        return sorted(p for p in target.rglob("*.py") if p.is_file())
    return []


def scan_with_regex(target: Path, files: list[Path] | None = None) -> list[Finding]:
    py_files = files if files is not None else collect_python_files(target)
    findings: list[Finding] = []
    base = target if target.is_dir() else target.parent

    for py_file in py_files:
        if not py_file.is_file():
            continue
        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel_path = _relative_path(py_file, base)
        for line_num, line in enumerate(content.splitlines(), 1):
            if _is_pattern_definition_line(line):
                continue
            for owasp, title, pattern in REGEX_PATTERNS:
                if not pattern.search(line):
                    continue
                if owasp == "A02" and A02_SAFE_RE.search(line):
                    continue
                findings.append(
                    Finding(
                        owasp=owasp,
                        title=title,
                        severity="high",
                        file_path=rel_path,
                        line=line_num,
                        source="regex",
                        detail=line.strip(),
                    )
                )
    return findings


def map_bandit_finding(test_id: str, issue_text: str) -> tuple[str, str]:
    if test_id in BANDIT_OWASP_MAP:
        return BANDIT_OWASP_MAP[test_id]
    return ("A??", issue_text or f"Bandit {test_id}")


def _bandit_severity(raw: str) -> str:
    normalized = raw.strip().lower()
    if normalized in {"high", "medium", "low"}:
        return normalized
    return "medium"


def scan_with_bandit(target: Path) -> tuple[list[Finding], str | None]:
    cmd = ["bandit", "-r", str(target), "-f", "json", "-q"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], str(exc)

    if result.returncode not in (0, 1) and not result.stdout.strip():
        return [], result.stderr.strip() or f"bandit exit {result.returncode}"

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        return [], str(exc)

    findings: list[Finding] = []
    for item in payload.get("results", []):
        test_id = str(item.get("test_id", ""))
        owasp, title = map_bandit_finding(test_id, str(item.get("issue_text", "")))
        file_path = str(item.get("filename", ""))
        try:
            rel = str(Path(file_path).resolve().relative_to(target.resolve()))
        except ValueError:
            rel = file_path
        findings.append(
            Finding(
                owasp=owasp,
                title=title,
                severity=_bandit_severity(str(item.get("issue_severity", "medium"))),
                file_path=rel,
                line=int(item.get("line_number", 0) or 0),
                source="bandit",
                detail=str(item.get("issue_text", "")).strip(),
            )
        )
    return findings, None


def has_high_severity(findings: list[Finding]) -> bool:
    return any(f.severity.lower() == "high" for f in findings)


def generate_report(
    findings: list[Finding], confidence_score: int, used_bandit: bool
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    engine = "bandit" if used_bandit else "regex fallback"
    lines = [
        "# Security Scan Report",
        "",
        f"> Gerado: {timestamp}",
        f"> Engine: {engine}",
        f"> Confiança (**confidence_score**): **{confidence_score}**",
        "",
        "## Findings",
        "",
        "| OWASP | Title | Severity | File | Line | Source |",
        "|-------|-------|----------|------|------|--------|",
    ]
    if findings:
        for finding in findings:
            lines.append(
                f"| {finding.owasp} | {finding.title} | {finding.severity} | "
                f"`{finding.file_path}` | {finding.line} | {finding.source} |"
            )
    else:
        lines.append("| — | Nenhum finding | — | — | — | — |")
    lines.extend(["", "## Summary", ""])
    if findings:
        high_count = sum(1 for f in findings if f.severity.lower() == "high")
        lines.append(
            f"- Total findings: **{len(findings)}** "
            f"(high severity: **{high_count}**)"
        )
        if high_count:
            lines.append("- **Resultado: FAIL** — corrigir findings de alta severidade.")
        else:
            lines.append("- **Resultado: PASS** — nenhum finding de alta severidade.")
    else:
        lines.append("- **Resultado: PASS** — nenhuma vulnerabilidade detectada.")
    lines.append("")
    return "\n".join(lines)


def run_scan(target: Path) -> tuple[list[Finding], int, bool]:
    if bandit_available():
        findings, error = scan_with_bandit(target)
        if error:
            print(f"WARNING: bandit failed ({error}); using regex fallback", file=sys.stderr)
            findings = scan_with_regex(target)
            return findings, CONFIDENCE_REGEX, False
        return findings, CONFIDENCE_BANDIT, True
    print("WARNING: bandit not found in PATH; using regex fallback", file=sys.stderr)
    return scan_with_regex(target), CONFIDENCE_REGEX, False


def _relative_path(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="OWASP static analysis em arquivos Python"
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Arquivo ou diretório Python para analisar",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Caminho do security-report.md (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args(argv)

    target = Path(args.target)
    output_path = Path(args.output)

    if not target.exists():
        print(f"ERROR: target not found: {target}", file=sys.stderr)
        return 2

    py_files = collect_python_files(target)
    if not py_files:
        print(f"WARNING: no Python files under {target}", file=sys.stderr)

    findings, confidence_score, used_bandit = run_scan(target)
    report = generate_report(findings, confidence_score, used_bandit)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Report written to {output_path}")
    print(f"confidence_score: {confidence_score}")
    print(f"Findings: {len(findings)}")
    if has_high_severity(findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
