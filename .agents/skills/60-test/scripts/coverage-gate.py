#!/usr/bin/env python3
"""Gate de cobertura — lê coverage.json ou executa pytest --cov."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DEFAULT_COVERAGE = "coverage.json"
DEFAULT_MIN = 60.0


class CoverageError(Exception):
    """Erro ao ler ou gerar cobertura."""


def read_coverage_percent(coverage_path: Path) -> float:
    if not coverage_path.is_file():
        raise CoverageError(f"coverage file not found: {coverage_path}")
    try:
        data = json.loads(coverage_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageError(str(exc)) from exc
    try:
        return float(data["totals"]["percent_covered"])
    except (KeyError, TypeError, ValueError) as exc:
        raise CoverageError("invalid coverage.json: missing totals.percent_covered") from exc


def run_pytest_coverage(coverage_path: Path, cov_source: str = "src") -> Path:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        f"--cov={cov_source}",
        "--cov-report=json",
        "-q",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise CoverageError(f"failed to run pytest: {exc}") from exc
    if proc.returncode not in (0, 1, 2, 5):
        raise CoverageError(
            f"pytest failed (exit {proc.returncode}): {proc.stderr or proc.stdout}"
        )
    if not coverage_path.is_file():
        default_path = Path("coverage.json")
        if default_path.is_file():
            return default_path
        raise CoverageError("pytest did not produce coverage.json")
    return coverage_path


def ensure_coverage(coverage_path: Path, cov_source: str) -> float:
    if coverage_path.is_file():
        return read_coverage_percent(coverage_path)
    run_pytest_coverage(coverage_path, cov_source=cov_source)
    return read_coverage_percent(coverage_path)


def evaluate_gate(coverage_pct: float, minimum: float) -> tuple[bool, str]:
    rounded = round(coverage_pct, 1)
    min_rounded = round(minimum, 1)
    if coverage_pct < minimum:
        return False, f"GATE FAILED: {rounded}% < {min_rounded}%"
    return True, f"GATE PASSED: {rounded}%"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica cobertura mínima de testes")
    parser.add_argument(
        "--coverage",
        default=DEFAULT_COVERAGE,
        help=f"Arquivo coverage.json (default: {DEFAULT_COVERAGE})",
    )
    parser.add_argument(
        "--min",
        type=float,
        default=DEFAULT_MIN,
        dest="minimum",
        help=f"Cobertura mínima em %% (default: {DEFAULT_MIN})",
    )
    parser.add_argument(
        "--cov-source",
        default="src",
        help="Pacote/diretório para --cov (default: src)",
    )
    args = parser.parse_args(argv)

    coverage_path = Path(args.coverage)

    try:
        pct = ensure_coverage(coverage_path, cov_source=args.cov_source)
    except CoverageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    passed, message = evaluate_gate(pct, args.minimum)
    print(message)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
