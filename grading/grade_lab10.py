#!/usr/bin/env python3
"""
Lab 10 autograder: fibonacci_timing.py

Designed for the CPSC 250L-style repo workflow.  It can grade either one lab
folder or a directory containing multiple student repositories.

Default expected file:
    labs/lab10_fibonacci_timing/fibonacci_timing.py

Examples:
    python grade_lab10.py --lab-path /path/to/student/repo/labs/lab10_fibonacci_timing
    python grade_lab10.py --submissions-root ./student_repos --lab-relative-path labs/lab10_fibonacci_timing
    python grade_lab10.py --submissions-root ./student_repos --output lab10_report.csv

Total: 24 points
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import csv
import importlib.util
import io
import math
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import types
from typing import Any, Callable

TOTAL_POINTS = 24
DEFAULT_LAB_RELATIVE_PATH = "labs/lab10_fibonacci_timing"
TARGET_FILENAME = "fibonacci_timing.py"


class TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):  # pragma: no cover
    raise TimeoutError("operation timed out")


@contextlib.contextmanager
def time_limit(seconds: int):
    """Unix-only alarm timeout, fine for the macOS/Linux grading environment."""
    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def find_submission_files(args: argparse.Namespace) -> list[tuple[str, Path]]:
    """Return (student_name, fibonacci_timing.py path) pairs."""
    if args.lab_path:
        lab_path = Path(args.lab_path).expanduser().resolve()
        target = lab_path / TARGET_FILENAME if lab_path.is_dir() else lab_path
        return [(lab_path.parent.name if lab_path.is_dir() else lab_path.stem, target)]

    root = Path(args.submissions_root).expanduser().resolve()
    pairs: list[tuple[str, Path]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        target = child / args.lab_relative_path / TARGET_FILENAME
        pairs.append((child.name, target))
    return pairs


def load_defs_only(path: Path) -> tuple[types.ModuleType | None, ast.Module | None, str | None]:
    """
    Parse a student file and execute only imports, assignments, class defs, and
    function defs. This avoids an unguarded main() call, which is especially
    important because a naive recursive fib(40) can take a long time.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except Exception as exc:
        return None, None, f"Could not read file: {exc}"

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return None, None, f"SyntaxError: line {exc.lineno}: {exc.msg}"
    except Exception as exc:
        return None, None, f"Could not parse file: {exc}"

    allowed = (
        ast.Import,
        ast.ImportFrom,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.Assign,
        ast.AnnAssign,
        ast.AugAssign,
    )
    safe_body = [node for node in tree.body if isinstance(node, allowed)]
    safe_tree = ast.Module(body=safe_body, type_ignores=[])
    ast.fix_missing_locations(safe_tree)

    module = types.ModuleType("student_fibonacci_timing")
    module.__dict__["__file__"] = str(path)
    module.__dict__["__name__"] = "student_fibonacci_timing"

    # Force a non-GUI backend before any student pyplot import is executed.
    os.environ.setdefault("MPLBACKEND", "Agg")

    try:
        with time_limit(4):
            exec(compile(safe_tree, str(path), "exec"), module.__dict__)
    except Exception as exc:
        return None, tree, f"Runtime error while loading definitions: {type(exc).__name__}: {exc}"

    return module, tree, None


def function_names_called(fn_node: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn_node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


def get_function_node(tree: ast.Module | None, name: str) -> ast.FunctionDef | None:
    if tree is None:
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def safe_call(func: Callable[..., Any], *args: Any, seconds: int = 2) -> tuple[bool, Any, str]:
    try:
        with time_limit(seconds):
            result = func(*args)
        return True, result, ""
    except Exception as exc:
        return False, None, f"{type(exc).__name__}: {exc}"


def check_fib_function(func: Callable[[int], int], test_values: list[tuple[int, int]], seconds: int) -> tuple[int, list[str]]:
    passed = 0
    messages: list[str] = []
    for n, expected in test_values:
        ok, result, err = safe_call(func, n, seconds=seconds)
        if ok and result == expected:
            passed += 1
        else:
            messages.append(f"n={n}: expected {expected}, got {result!r}{' (' + err + ')' if err else ''}")
    return passed, messages


def grade_one(student: str, path: Path) -> dict[str, Any]:
    row: dict[str, Any] = {
        "student": student,
        "file": str(path),
        "score": 0,
        "max_score": TOTAL_POINTS,
        "file_load_points": 0,
        "fib_recursive_points": 0,
        "fib_iterative_points": 0,
        "time_function_points": 0,
        "output_points": 0,
        "plot_points": 0,
        "notes": "",
    }
    notes: list[str] = []

    if not path.exists():
        row["notes"] = "Missing fibonacci_timing.py"
        return row

    module, tree, load_error = load_defs_only(path)
    if load_error:
        notes.append(load_error)
        row["notes"] = "; ".join(notes)
        return row

    assert module is not None
    row["file_load_points"] = 2

    # --- fib_recursive: 5 pts ---
    fib_rec = getattr(module, "fib_recursive", None)
    rec_node = get_function_node(tree, "fib_recursive")
    if callable(fib_rec):
        base_tests = [(0, 0), (1, 1)]
        value_tests = [(2, 1), (5, 5), (10, 55)]
        base_passed, base_msgs = check_fib_function(fib_rec, base_tests, seconds=1)
        value_passed, value_msgs = check_fib_function(fib_rec, value_tests, seconds=2)
        row["fib_recursive_points"] += base_passed  # 2 pts
        row["fib_recursive_points"] += min(2, math.floor(value_passed * 2 / len(value_tests)))  # 0-2 pts
        if rec_node and "fib_recursive" in function_names_called(rec_node):
            row["fib_recursive_points"] += 1
        else:
            notes.append("fib_recursive does not appear to call itself")
        if base_msgs or value_msgs:
            notes.append("fib_recursive issues: " + ", ".join(base_msgs + value_msgs[:2]))
    else:
        notes.append("fib_recursive missing or not callable")

    # --- fib_iterative: 5 pts ---
    fib_it = getattr(module, "fib_iterative", None)
    if callable(fib_it):
        base_tests = [(0, 0), (1, 1)]
        value_tests = [(2, 1), (5, 5), (10, 55), (20, 6765), (40, 102334155)]
        base_passed, base_msgs = check_fib_function(fib_it, base_tests, seconds=1)
        value_passed, value_msgs = check_fib_function(fib_it, value_tests, seconds=1)
        row["fib_iterative_points"] += base_passed  # 2 pts
        row["fib_iterative_points"] += min(2, math.floor(value_passed * 2 / len(value_tests)))  # 0-2 pts
        start = time.perf_counter()
        ok, result, err = safe_call(fib_it, 500, seconds=1)
        elapsed = time.perf_counter() - start
        if ok and isinstance(result, int) and elapsed < 0.25:
            row["fib_iterative_points"] += 1
        else:
            notes.append("fib_iterative is not efficient for n=500")
        if base_msgs or value_msgs:
            notes.append("fib_iterative issues: " + ", ".join(base_msgs + value_msgs[:2]))
    else:
        notes.append("fib_iterative missing or not callable")

    # --- time_function: 4 pts ---
    time_function = getattr(module, "time_function", None)
    if callable(time_function):
        calls: list[int] = []

        def dummy(n: int) -> int:
            calls.append(n)
            time.sleep(0.01)
            return 12345

        ok, elapsed, err = safe_call(time_function, dummy, 7, seconds=2)
        if ok and calls == [7]:
            row["time_function_points"] += 1
        else:
            notes.append("time_function did not call the supplied function exactly once with n")
        if ok and isinstance(elapsed, (int, float)):
            row["time_function_points"] += 1
            if elapsed > 0:
                row["time_function_points"] += 1
            if 0.005 <= elapsed <= 0.5:
                row["time_function_points"] += 1
        else:
            notes.append(f"time_function did not return a numeric elapsed time{': ' + err if err else ''}")
    else:
        notes.append("time_function missing or not callable")

    # --- main output: 2 pts ---
    main_fn = getattr(module, "main", None)
    if callable(main_fn):
        # Monkeypatch expensive pieces so main can be tested safely.
        time_calls: list[tuple[str, int]] = []

        def fake_time_function(function: Callable[[int], int], n: int) -> float:
            time_calls.append((getattr(function, "__name__", "unknown"), n))
            return 0.001 * max(1, n)

        original_time_function = module.__dict__.get("time_function")
        module.__dict__["time_function"] = fake_time_function
        try:
            import matplotlib
            matplotlib.use("Agg", force=True)
            import matplotlib.pyplot as plt
            plt.close("all")
            original_show = plt.show
            plt.show = lambda *a, **k: None
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                ok, _, err = safe_call(main_fn, seconds=3)
            output = buf.getvalue()
            values_seen = sorted({n for _, n in time_calls})
            if "Fibonacci" in output and "recursive" in output.lower() and "iterative" in output.lower():
                row["output_points"] += 1
            else:
                notes.append("main output is missing expected heading/columns")
            if values_seen == [5, 10, 20, 25, 30, 35, 40]:
                row["output_points"] += 1
            else:
                notes.append(f"main did not time the expected n values; saw {values_seen}")

            # --- plot: 6 pts ---
            figs = [plt.figure(num) for num in plt.get_fignums()]
            axes = [ax for fig in figs for ax in fig.axes]
            if axes:
                ax = axes[0]
                if len(ax.lines) >= 2:
                    row["plot_points"] += 1
                else:
                    notes.append("plot has fewer than two data series")
                if ax.get_xlabel().strip():
                    row["plot_points"] += 1
                else:
                    notes.append("plot missing x-axis label")
                if ax.get_ylabel().strip():
                    row["plot_points"] += 1
                else:
                    notes.append("plot missing y-axis label")
                if ax.get_title().strip():
                    row["plot_points"] += 1
                else:
                    notes.append("plot missing title")
                has_legend = ax.get_legend() is not None
                is_log = ax.get_yscale() == "log"
                if has_legend:
                    row["plot_points"] += 1
                else:
                    notes.append("plot missing legend")
                if is_log:
                    row["plot_points"] += 1
                else:
                    notes.append("plot y-axis is not logarithmic")
            else:
                notes.append("main did not create a matplotlib plot")
            plt.show = original_show
        except Exception as exc:
            notes.append(f"main/plot test failed: {type(exc).__name__}: {exc}")
        finally:
            if original_time_function is not None:
                module.__dict__["time_function"] = original_time_function
    else:
        notes.append("main missing or not callable")

    categories = [
        "file_load_points",
        "fib_recursive_points",
        "fib_iterative_points",
        "time_function_points",
        "output_points",
        "plot_points",
    ]
    row["score"] = sum(int(row[key]) for key in categories)
    row["notes"] = "; ".join(notes)
    return row


def write_report(rows: list[dict[str, Any]], output_path: Path) -> None:
    fieldnames = [
        "student",
        "score",
        "max_score",
        "file_load_points",
        "fib_recursive_points",
        "fib_iterative_points",
        "time_function_points",
        "output_points",
        "plot_points",
        "file",
        "notes",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade CPSC 250L Lab 10 Fibonacci Timing submissions.")
    parser.add_argument("--lab-path", help="Path to one lab folder or directly to fibonacci_timing.py")
    parser.add_argument("--submissions-root", default=".", help="Directory containing student repositories")
    parser.add_argument("--lab-relative-path", default=DEFAULT_LAB_RELATIVE_PATH,
                        help=f"Path from each student repo to the lab folder; default {DEFAULT_LAB_RELATIVE_PATH}")
    parser.add_argument("--output", default="lab10_report.csv", help="CSV report path")
    args = parser.parse_args()

    pairs = find_submission_files(args)
    rows = [grade_one(student, path) for student, path in pairs]
    output_path = Path(args.output).expanduser().resolve()
    write_report(rows, output_path)

    for row in rows:
        print(f"{row['student']}: {row['score']}/{row['max_score']}")
    print(f"\nWrote report to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
