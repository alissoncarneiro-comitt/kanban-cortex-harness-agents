#!/usr/bin/env python3
"""Performance benchmark — P50/P95/P99 vs baseline local."""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OUTPUT = "perf-report.json"
DEFAULT_BASELINE = "perf-baseline.json"
DEFAULT_REPETITIONS = 5
DEFAULT_TIMEOUT = 60
REGRESSION_THRESHOLD = 1.20


class BenchmarkError(Exception):
    """Erro durante execução do benchmark."""


@dataclass
class RunResult:
    execution_time_ms: float
    exit_code: int


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return sorted_data[0]
    k = (n - 1) * (p / 100.0)
    floor_k = int(k)
    ceil_k = min(floor_k + 1, n - 1)
    if floor_k == ceil_k:
        return sorted_data[floor_k]
    fraction = k - floor_k
    return sorted_data[floor_k] + fraction * (sorted_data[ceil_k] - sorted_data[floor_k])


def run_benchmark(
    target: str,
    repetitions: int = DEFAULT_REPETITIONS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[RunResult]:
    cmd = shlex.split(target)
    runs: list[RunResult] = []
    for _ in range(repetitions):
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            raise BenchmarkError(f"target timed out after {timeout}s: {target}") from exc
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        runs.append(RunResult(execution_time_ms=elapsed_ms, exit_code=exit_code))
    return runs


def regression_pct(current_p95: float, baseline_p95: float) -> float | None:
    if baseline_p95 <= 0:
        return None
    return ((current_p95 - baseline_p95) / baseline_p95) * 100.0


def is_regression(current_p95: float, baseline_p95: float, threshold: float = REGRESSION_THRESHOLD) -> bool:
    if baseline_p95 <= 0:
        return False
    return current_p95 > baseline_p95 * threshold


def build_report(
    runs: list[RunResult],
    baseline_p95: float | None = None,
) -> dict:
    times = [r.execution_time_ms for r in runs]
    p50 = percentile(times, 50)
    p95 = percentile(times, 95)
    p99 = percentile(times, 99)
    reg_pct = regression_pct(p95, baseline_p95) if baseline_p95 is not None else None
    return {
        "p50": round(p50, 3),
        "p95": round(p95, 3),
        "p99": round(p99, 3),
        "baseline_p95": baseline_p95,
        "regression_pct": round(reg_pct, 3) if reg_pct is not None else None,
        "runs": [
            {"execution_time_ms": round(r.execution_time_ms, 3), "exit_code": r.exit_code}
            for r in runs
        ],
    }


def load_baseline(path: Path) -> float | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if "p95" in data:
        return float(data["p95"])
    return None


def save_baseline(path: Path, p95: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"p95": round(p95, 3)}, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mede P50/P95/P99 de um comando e compara com baseline"
    )
    parser.add_argument("--target", required=True, help="Comando a executar (shell-quoted)")
    parser.add_argument(
        "--baseline",
        default=DEFAULT_BASELINE,
        help=f"Arquivo JSON baseline (default: {DEFAULT_BASELINE})",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Arquivo perf-report.json (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=DEFAULT_REPETITIONS,
        help=f"Número de repetições (default: {DEFAULT_REPETITIONS})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout por run em segundos (default: {DEFAULT_TIMEOUT})",
    )
    args = parser.parse_args(argv)

    if not args.target.strip():
        print("ERROR: --target is required", file=sys.stderr)
        return 2

    baseline_path = Path(args.baseline)
    output_path = Path(args.output)

    try:
        runs = run_benchmark(args.target, repetitions=args.repetitions, timeout=args.timeout)
    except BenchmarkError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    baseline_p95 = load_baseline(baseline_path)
    report = build_report(runs, baseline_p95=baseline_p95)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Report written to {output_path}")
    print(f"P50={report['p50']}ms P95={report['p95']}ms P99={report['p99']}ms")

    if baseline_p95 is None:
        save_baseline(baseline_path, report["p95"])
        print(f"Baseline created at {baseline_path} (p95={report['p95']}ms)")
        return 0

    if is_regression(report["p95"], baseline_p95):
        pct = report["regression_pct"] or 0.0
        print(
            f"REGRESSION: P95 increased by {pct:.1f}% "
            f"({report['p95']}ms > {baseline_p95 * REGRESSION_THRESHOLD:.3f}ms threshold)",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
