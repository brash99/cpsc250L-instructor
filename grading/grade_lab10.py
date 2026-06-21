#!/usr/bin/env python3
"""
grade_lab10.py

Automated Lab 10 checker for CPSC 250L student forks.

Lab 10: Recursion and Timing
Default folder: labs/lab10_recursion_and_timing
Expected file: fibonacci_timing.py

Recommended use:

python grade_lab10.py \
  --students students.csv \
  --workdir student_repos \
  --report reports/lab10_report.csv \
  --lab-path labs/lab10_recursion_and_timing
"""

from __future__ import annotations

import argparse
import ast
import csv
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


EXPECTED_FILE = "fibonacci_timing.py"
EXPECTED_FUNCTIONS = ["fib_recursive", "fib_iterative", "time_function", "main"]
TOTAL_POINTS = 24
SHOW_PLOTS = False
PLOT_PAUSE_SECONDS = 1.5


def run_command(
    command: List[str],
    cwd: Optional[Path] = None,
    timeout: int = 20,
) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            timeout=timeout,
            text=True,
            capture_output=True,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout} seconds: {' '.join(command)}"
    except Exception as exc:
        return 1, "", f"Command failed: {exc}"


def clone_or_update_repo(repo_url: str, repo_dir: Path) -> Tuple[bool, str]:
    if not repo_dir.exists():
        code, out, err = run_command(["git", "clone", repo_url, str(repo_dir)], timeout=60)
        if code != 0:
            return False, err or out
        return True, "cloned"

    if not (repo_dir / ".git").exists():
        return False, f"{repo_dir} exists but is not a git repository"

    run_command(["git", "fetch", "--all"], cwd=repo_dir, timeout=60)

    code, out, err = run_command(["git", "checkout", "main"], cwd=repo_dir)
    if code != 0:
        run_command(["git", "checkout", "master"], cwd=repo_dir)

    code, out, err = run_command(["git", "pull"], cwd=repo_dir, timeout=60)
    if code != 0:
        return False, err or out

    return True, "updated"


def find_file(repo_dir: Path, filename: str) -> Optional[Path]:
    candidates = list(repo_dir.rglob(filename))
    filtered = [
        p for p in candidates
        if ".git" not in p.parts
        and ".venv" not in p.parts
        and "venv" not in p.parts
        and "__pycache__" not in p.parts
    ]

    if not filtered:
        return None

    filtered.sort(
        key=lambda p: (
            "lab10" not in str(p).lower() and "lab_10" not in str(p).lower(),
            len(p.parts),
        )
    )
    return filtered[0]


def parse_python(py_path: Path) -> Tuple[Optional[ast.Module], str]:
    try:
        return ast.parse(py_path.read_text(encoding="utf-8")), "ok"
    except Exception as exc:
        return None, str(exc)


def function_names(tree: ast.Module) -> List[str]:
    return [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]


def get_function_node(tree: ast.Module, name: str) -> Optional[ast.FunctionDef]:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def contains_call_to(node: ast.AST, name: str) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name) and func.id == name:
                return True
            if isinstance(func, ast.Attribute) and func.attr == name:
                return True
    return False


def contains_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(child, ast.Name) and child.id == name for child in ast.walk(node))


def contains_attribute(node: ast.AST, attr: str) -> bool:
    return any(isinstance(child, ast.Attribute) and child.attr == attr for child in ast.walk(node))


def contains_numeric_constant(node: ast.AST, value: int) -> bool:
    return any(isinstance(child, ast.Constant) and child.value == value for child in ast.walk(node))


def is_placeholder_function(node: ast.FunctionDef) -> bool:
    meaningful = [stmt for stmt in node.body if not isinstance(stmt, ast.Expr) or not isinstance(getattr(stmt, "value", None), ast.Constant) or not isinstance(stmt.value.value, str)]
    if not meaningful:
        return True
    if len(meaningful) == 1:
        stmt = meaningful[0]
        if isinstance(stmt, ast.Pass):
            return True
        if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant) and stmt.value.value in (None, 0):
            return True
    return False


def safe_load_functions(py_path: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    """Execute only imports, assignments, and function definitions; skip top-level main() calls."""
    try:
        source = py_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        safe_body: List[ast.stmt] = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign, ast.AnnAssign)):
                safe_body.append(node)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                # Skip top-level calls such as main().
                continue
            elif isinstance(node, ast.If):
                # Skip if __name__ == "__main__" blocks while loading functions.
                continue

        module = ast.Module(body=safe_body, type_ignores=[])
        ast.fix_missing_locations(module)

        namespace: Dict[str, Any] = {"__name__": "lab10_grader_import"}
        exec(compile(module, str(py_path), "exec"), namespace)
        return namespace, "ok"
    except Exception as exc:
        return None, f"Could not load functions safely: {exc}"


def call_with_timeout(function: Callable[..., Any], args: Tuple[Any, ...], timeout_seconds: float = 2.0) -> Tuple[bool, Any, str]:
    # For these small Fibonacci cases, direct calls are sufficient and avoid multiprocessing/import complications.
    start = time.perf_counter()
    try:
        value = function(*args)
        elapsed = time.perf_counter() - start
        if elapsed > timeout_seconds:
            return False, value, f"Call exceeded {timeout_seconds:.1f} seconds"
        return True, value, "ok"
    except RecursionError as exc:
        return False, None, f"RecursionError: {exc}"
    except Exception as exc:
        return False, None, f"Exception: {exc}"


def expected_fib(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def test_function_behavior(namespace: Dict[str, Any]) -> Dict[str, str]:
    result = {
        "fib_recursive_base_cases_correct": "no",
        "fib_recursive_values_correct": "no",
        "fib_iterative_base_cases_correct": "no",
        "fib_iterative_values_correct": "no",
        "time_function_returns_number": "no",
        "time_function_calls_argument_function": "no",
        "time_function_measures_elapsed_time": "no",
        "behavior_notes": "",
    }

    fib_recursive = namespace.get("fib_recursive")
    fib_iterative = namespace.get("fib_iterative")
    time_function = namespace.get("time_function")

    if callable(fib_recursive):
        try:
            base_ok = all(fib_recursive(n) == expected_fib(n) for n in [0, 1, 2])
            result["fib_recursive_base_cases_correct"] = "yes" if base_ok else "no"
            if not base_ok:
                result["behavior_notes"] += "fib_recursive base cases are incorrect. "
        except Exception as exc:
            result["behavior_notes"] += f"fib_recursive base case test raised: {exc}. "

        try:
            values_ok = True
            for n in [3, 5, 7, 10, 12]:
                ok, value, note = call_with_timeout(fib_recursive, (n,), timeout_seconds=2.0)
                if not ok or value != expected_fib(n):
                    values_ok = False
                    result["behavior_notes"] += f"fib_recursive({n}) returned {value!r}; expected {expected_fib(n)} ({note}). "
                    break
            result["fib_recursive_values_correct"] = "yes" if values_ok else "no"
        except Exception as exc:
            result["behavior_notes"] += f"fib_recursive value test raised: {exc}. "
    else:
        result["behavior_notes"] += "fib_recursive is not callable. "

    if callable(fib_iterative):
        try:
            base_ok = all(fib_iterative(n) == expected_fib(n) for n in [0, 1, 2])
            result["fib_iterative_base_cases_correct"] = "yes" if base_ok else "no"
            if not base_ok:
                result["behavior_notes"] += "fib_iterative base cases are incorrect. "
        except Exception as exc:
            result["behavior_notes"] += f"fib_iterative base case test raised: {exc}. "

        try:
            values_ok = True
            for n in [3, 5, 10, 20, 30]:
                ok, value, note = call_with_timeout(fib_iterative, (n,), timeout_seconds=1.0)
                if not ok or value != expected_fib(n):
                    values_ok = False
                    result["behavior_notes"] += f"fib_iterative({n}) returned {value!r}; expected {expected_fib(n)} ({note}). "
                    break
            result["fib_iterative_values_correct"] = "yes" if values_ok else "no"
        except Exception as exc:
            result["behavior_notes"] += f"fib_iterative value test raised: {exc}. "
    else:
        result["behavior_notes"] += "fib_iterative is not callable. "

    if callable(time_function):
        calls = {"count": 0}

        def sample_function(n: int) -> int:
            calls["count"] += 1
            time.sleep(0.002)
            return n * 2

        try:
            elapsed = time_function(sample_function, 21)
            if isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool) and math.isfinite(float(elapsed)) and float(elapsed) >= 0:
                result["time_function_returns_number"] = "yes"
            else:
                result["behavior_notes"] += f"time_function returned non-numeric or invalid elapsed value: {elapsed!r}. "

            if calls["count"] >= 1:
                result["time_function_calls_argument_function"] = "yes"
            else:
                result["behavior_notes"] += "time_function did not call the function argument. "

            if isinstance(elapsed, (int, float)) and float(elapsed) > 0:
                result["time_function_measures_elapsed_time"] = "yes"
            else:
                result["behavior_notes"] += "time_function did not appear to measure positive elapsed time. "
        except Exception as exc:
            result["behavior_notes"] += f"time_function test raised: {exc}. "
    else:
        result["behavior_notes"] += "time_function is not callable. "

    return result


def run_program(py_path: Path) -> Tuple[bool, str]:
    code, out, err = run_command(
        [sys.executable, str(py_path.name)],
        cwd=py_path.parent,
        timeout=25,
    )
    if code == 0:
        return True, out
    return False, err or out


def display_program_plot(py_path: Path, student_slug: str) -> None:
    """Optionally rerun the student's script without output capture so matplotlib windows can appear."""
    if not SHOW_PLOTS:
        return
    print(f"  displaying Lab 10 plot for {student_slug}; close the window to continue if it blocks")
    env = dict(os.environ) if "os" in globals() else None
    if env is not None:
        env.pop("MPLBACKEND", None)
    try:
        subprocess.run(
            [sys.executable, str(py_path.name)],
            cwd=py_path.parent,
            timeout=90,
            env=env,
        )
    except subprocess.TimeoutExpired:
        print(f"  plot display timed out for {student_slug}; continuing")
    except Exception as exc:
        print(f"  plot display failed for {student_slug}: {exc}")


def output_has_expected_content(output: str) -> Tuple[bool, str]:
    notes = []
    lowered = output.lower()

    if "fibonacci timing" not in lowered:
        notes.append("Missing title 'Fibonacci Timing'")
    if "recursive" not in lowered:
        notes.append("Missing recursive timing label")
    if "iterative" not in lowered:
        notes.append("Missing iterative timing label")
    if "seconds" not in lowered:
        notes.append("Missing seconds in timing output")
    for n in [5, 10, 20, 25, 30, 35, 40]:
        if str(n) not in output:
            notes.append(f"Missing n value: {n}")
    if "none" in lowered or "todo" in lowered or "pass" in lowered:
        notes.append("Output contains placeholder-like text")

    return len(notes) == 0, "; ".join(notes)


def count_commits_touching_path(repo_dir: Path, lab_path: Optional[str]) -> Tuple[Optional[int], str]:
    if not lab_path:
        return None, "lab path not provided"

    code, out, err = run_command(
        ["git", "rev-list", "--count", "HEAD", "--", lab_path],
        cwd=repo_dir,
    )

    if code != 0:
        return None, err or out

    try:
        return int(out), "ok"
    except ValueError:
        return None, f"could not parse commit count: {out}"


def get_recent_lab_commits(repo_dir: Path, lab_path: Optional[str], n: int = 8) -> str:
    if not lab_path:
        return ""

    code, out, err = run_command(
        ["git", "log", "--oneline", f"-{n}", "--", lab_path],
        cwd=repo_dir,
    )

    return out if code == 0 else err


def get_recent_commits(repo_dir: Path, n: int = 10) -> str:
    code, out, err = run_command(["git", "log", "--oneline", f"-{n}"], cwd=repo_dir)
    return out if code == 0 else err


def get_branch_info(repo_dir: Path) -> str:
    code, out, err = run_command(["git", "branch", "-a"], cwd=repo_dir)
    return out if code == 0 else err


def is_working_tree_clean(repo_dir: Path) -> Tuple[bool, str]:
    code, out, err = run_command(["git", "status", "--porcelain"], cwd=repo_dir)

    if code != 0:
        return False, err or out

    if out.strip() == "":
        return True, "clean"

    return False, out.replace("\n", " | ")


def empty_result(row: Dict[str, str], lab_path: Optional[str]) -> Dict[str, str]:
    return {
        "name": row["name"].strip(),
        "github_username": row["github_username"].strip(),
        "repo_url": row["repo_url"].strip(),
        "type": row.get("type", "student").strip() or "student",
        "clone_or_update": "no",
        "fibonacci_timing_exists": "no",
        "fibonacci_timing_path": "",
        "parses": "no",
        "fib_recursive_exists": "no",
        "fib_iterative_exists": "no",
        "time_function_exists": "no",
        "main_exists": "no",
        "fib_recursive_not_placeholder": "no",
        "fib_iterative_not_placeholder": "no",
        "time_function_not_placeholder": "no",
        "fib_recursive_base_cases_correct": "no",
        "fib_recursive_values_correct": "no",
        "fib_iterative_base_cases_correct": "no",
        "fib_iterative_values_correct": "no",
        "time_function_returns_number": "no",
        "time_function_calls_argument_function": "no",
        "time_function_measures_elapsed_time": "no",
        "main_uses_required_values": "no",
        "main_calls_time_function": "no",
        "plot_code_present": "no",
        "plot_labels_present": "no",
        "log_y_axis_present": "no",
        "program_runs_from_terminal": "no",
        "program_output_readable": "no",
        "program_output": "",
        "lab_path_checked": lab_path or "",
        "commits_touching_lab": "",
        "meaningful_lab_commit_evidence": "no",
        "recent_lab_commits": "",
        "working_tree_clean": "no",
        "recent_commits": "",
        "branch_info": "",
        f"auto_score_out_of_{TOTAL_POINTS}": "0",
        "manual_review_out_of_0": "",
        f"total_score_out_of_{TOTAL_POINTS}": "",
        "notes": "",
    }


def grade_student(row: Dict[str, str], workdir: Path, lab_path: Optional[str]) -> Dict[str, str]:
    username = row["github_username"].strip()
    repo_url = row["repo_url"].strip()
    repo_dir = workdir / username
    result = empty_result(row, lab_path)

    ok, message = clone_or_update_repo(repo_url, repo_dir)
    result["clone_or_update"] = "yes" if ok else "no"
    if not ok:
        result["notes"] = message
        return result

    fib_path = find_file(repo_dir, EXPECTED_FILE)

    if not fib_path:
        result["notes"] += "fibonacci_timing.py not found; awarded zero for Lab 10. "
        clean, clean_note = is_working_tree_clean(repo_dir)
        result["working_tree_clean"] = "yes" if clean else "no"
        result["recent_commits"] = get_recent_commits(repo_dir).replace("\n", " | ")[:900]
        result["branch_info"] = get_branch_info(repo_dir).replace("\n", " | ")[:900]
        if lab_path:
            commits, commit_note = count_commits_touching_path(repo_dir, lab_path)
            result["commits_touching_lab"] = "" if commits is None else str(commits)
            result["recent_lab_commits"] = get_recent_lab_commits(repo_dir, lab_path).replace("\n", " | ")[:900]
            if commits is None:
                result["notes"] += f"Lab commit check failed: {commit_note}. "
        return result

    score = 1  # clone/update

    result["fibonacci_timing_exists"] = "yes"
    result["fibonacci_timing_path"] = str(fib_path.relative_to(repo_dir))
    score += 1

    tree, parse_note = parse_python(fib_path)
    if tree is None:
        result["notes"] += f"Could not parse fibonacci_timing.py: {parse_note}. "
    else:
        result["parses"] = "yes"
        score += 1

        names = function_names(tree)
        for fn_name in EXPECTED_FUNCTIONS:
            col = f"{fn_name}_exists" if fn_name != "main" else "main_exists"
            if fn_name in names:
                result[col] = "yes"
                score += 1
            else:
                result["notes"] += f"{fn_name} function not found. "

        for fn_name in ["fib_recursive", "fib_iterative", "time_function"]:
            fn_node = get_function_node(tree, fn_name)
            if fn_node is not None and not is_placeholder_function(fn_node):
                result[f"{fn_name}_not_placeholder"] = "yes"
            elif fn_node is not None:
                result["notes"] += f"{fn_name} still looks like placeholder code. "

        fib_recursive_node = get_function_node(tree, "fib_recursive")
        if fib_recursive_node is not None and contains_call_to(fib_recursive_node, "fib_recursive"):
            result["fib_recursive_uses_recursion"] = "yes"
            score += 1
        elif fib_recursive_node is not None:
            result["notes"] += "fib_recursive does not appear to call itself recursively. "

        fib_iterative_node = get_function_node(tree, "fib_iterative")
        if fib_iterative_node is not None and any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(fib_iterative_node)):
            result["fib_iterative_uses_loop"] = "yes"
            score += 1
        elif fib_iterative_node is not None:
            result["notes"] += "fib_iterative does not appear to use a loop. "

        main_node = get_function_node(tree, "main")
        if main_node is not None:
            required_values = [5, 10, 20, 25, 30, 35, 40]
            if all(contains_numeric_constant(main_node, n) for n in required_values):
                result["main_uses_required_values"] = "yes"
                score += 1
            else:
                result["notes"] += "main does not appear to use the required n values. "

            if contains_call_to(main_node, "time_function"):
                result["main_calls_time_function"] = "yes"
                score += 1
            else:
                result["notes"] += "main does not appear to call time_function. "

            if any(contains_attribute(main_node, attr) or contains_call_to(main_node, attr) for attr in ["plot", "semilogy", "scatter"]):
                result["plot_code_present"] = "yes"
            else:
                result["notes"] += "Plotting code not found in main. "

            labels_ok = any(contains_attribute(main_node, attr) or contains_call_to(main_node, attr) for attr in ["xlabel", "ylabel", "title", "legend"])
            # Require at least evidence of labeling/legend; detailed plot aesthetics are manually reviewable if needed.
            label_count = sum(1 for attr in ["xlabel", "ylabel", "title", "legend"] if contains_attribute(main_node, attr) or contains_call_to(main_node, attr))
            if labels_ok and label_count >= 3:
                result["plot_labels_present"] = "yes"
                score += 1
            else:
                result["notes"] += "Plot labels/title/legend are incomplete or missing. "

            if contains_attribute(main_node, "yscale") or contains_call_to(main_node, "semilogy"):
                result["log_y_axis_present"] = "yes"
                score += 1
            else:
                result["notes"] += "Logarithmic y-axis code not found. "

        namespace, load_note = safe_load_functions(fib_path)
        if namespace is not None:
            behavior = test_function_behavior(namespace)
            for key, value in behavior.items():
                if key in result:
                    result[key] = value
            result["notes"] += behavior.get("behavior_notes", "")

            for key in [
                "fib_recursive_base_cases_correct",
                "fib_recursive_values_correct",
                "fib_iterative_base_cases_correct",
                "fib_iterative_values_correct",
                "time_function_returns_number",
                "time_function_calls_argument_function",
                "time_function_measures_elapsed_time",
            ]:
                if result[key] == "yes":
                    score += 1
        else:
            result["notes"] += load_note + " "

    run_ok, output = run_program(fib_path)
    result["program_runs_from_terminal"] = "yes" if run_ok else "no"
    result["program_output"] = output[:1200]
    if SHOW_PLOTS:
        display_program_plot(fib_path, username)
    if run_ok:
        score += 1
        readable, output_note = output_has_expected_content(output)
        if readable:
            result["program_output_readable"] = "yes"
            score += 1
        else:
            result["notes"] += f"Output check: {output_note}. "
    else:
        result["notes"] += "fibonacci_timing.py did not run successfully from terminal. "

    if lab_path:
        commits, commit_note = count_commits_touching_path(repo_dir, lab_path)
        result["commits_touching_lab"] = "" if commits is None else str(commits)
        result["recent_lab_commits"] = get_recent_lab_commits(repo_dir, lab_path).replace("\n", " | ")[:900]
        if commits is not None:
            if commits >= 2:
                result["meaningful_lab_commit_evidence"] = "yes"
                score += 1
            else:
                result["notes"] += f"Expected at least 2 commits touching {lab_path}, got {commits}. "
        else:
            result["notes"] += f"Lab commit check failed: {commit_note}. "
    else:
        result["notes"] += "No --lab-path supplied; lab-specific commit credit not awarded. "

    clean, clean_note = is_working_tree_clean(repo_dir)
    result["working_tree_clean"] = "yes" if clean else "no"
    if clean:
        score += 1
    else:
        result["notes"] += f"Working tree: {clean_note}. "

    result["recent_commits"] = get_recent_commits(repo_dir).replace("\n", " | ")[:900]
    result["branch_info"] = get_branch_info(repo_dir).replace("\n", " | ")[:900]
    result[f"auto_score_out_of_{TOTAL_POINTS}"] = str(score)
    return result


def read_students(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"name", "github_username", "repo_url"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"students.csv is missing required columns: {', '.join(sorted(missing))}")
        return list(reader)


def write_report(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "name",
        "github_username",
        "repo_url",
        "type",
        "clone_or_update",
        "fibonacci_timing_exists",
        "fibonacci_timing_path",
        "parses",
        "fib_recursive_exists",
        "fib_iterative_exists",
        "time_function_exists",
        "main_exists",
        "fib_recursive_not_placeholder",
        "fib_iterative_not_placeholder",
        "time_function_not_placeholder",
        "fib_recursive_base_cases_correct",
        "fib_recursive_values_correct",
        "fib_recursive_uses_recursion",
        "fib_iterative_base_cases_correct",
        "fib_iterative_values_correct",
        "fib_iterative_uses_loop",
        "time_function_returns_number",
        "time_function_calls_argument_function",
        "time_function_measures_elapsed_time",
        "main_uses_required_values",
        "main_calls_time_function",
        "plot_code_present",
        "plot_labels_present",
        "log_y_axis_present",
        "program_runs_from_terminal",
        "program_output_readable",
        "program_output",
        "lab_path_checked",
        "commits_touching_lab",
        "meaningful_lab_commit_evidence",
        "recent_lab_commits",
        "working_tree_clean",
        "recent_commits",
        "branch_info",
        f"auto_score_out_of_{TOTAL_POINTS}",
        "manual_review_out_of_0",
        f"total_score_out_of_{TOTAL_POINTS}",
        "notes",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade CPSC 250L Lab 10 student forks.")

    parser.add_argument("--students", required=True, help="Path to students.csv")
    parser.add_argument("--workdir", default="student_repos", help="Folder where repos are cloned")
    parser.add_argument("--report", default="reports/lab10_report.csv", help="Output CSV report path")
    parser.add_argument(
        "--lab-path",
        default="labs/lab10_recursion_and_timing",
        help="Repo-relative path used for lab-specific Git commit checks",
    )

    parser.add_argument(
        "--show-plots",
        action="store_true",
        help="Display each student's generated plot during grading for visual inspection",
    )
    parser.add_argument(
        "--plot-pause",
        type=float,
        default=1.5,
        help="Seconds to pause for each displayed plot when --show-plots is used",
    )

    args = parser.parse_args()

    global SHOW_PLOTS, PLOT_PAUSE_SECONDS
    SHOW_PLOTS = bool(args.show_plots)
    PLOT_PAUSE_SECONDS = float(args.plot_pause)


    students_path = Path(args.students)
    workdir = Path(args.workdir)
    report_path = Path(args.report)

    workdir.mkdir(parents=True, exist_ok=True)

    students = read_students(students_path)
    results = []

    for student in students:
        print(f"Grading {student['name']}...")
        results.append(grade_student(student, workdir, args.lab_path))

    write_report(report_path, results)
    print(f"\nWrote report: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
