#!/usr/bin/env python3
"""
grade_lab11.py

Automated Lab 11 checker for CPSC 250L student forks.

Lab 11: Search and Roots
Default folder: labs/lab11_search_and_roots
Expected file: search_and_roots.py

Recommended use:

python grade_lab11.py \
  --students students.csv \
  --workdir student_repos \
  --report reports/lab11_report.csv \
  --lab-path labs/lab11_search_and_roots
"""

from __future__ import annotations

import argparse
import ast
import csv
import math
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


EXPECTED_FILE = "search_and_roots.py"
EXPECTED_FUNCTIONS = ["linear_search", "binary_search", "f", "bisection_root", "main"]
TOTAL_POINTS = 24


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
            "lab11" not in str(p).lower() and "lab_11" not in str(p).lower(),
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


def contains_operator(node: ast.AST, op_type: type[ast.AST]) -> bool:
    return any(isinstance(child, op_type) for child in ast.walk(node))


def contains_comparison_operator(node: ast.AST, op_type: type[ast.cmpop]) -> bool:
    return any(isinstance(child, ast.Compare) and any(isinstance(op, op_type) for op in child.ops) for child in ast.walk(node))


def contains_numeric_constant(node: ast.AST, value: int | float) -> bool:
    return any(isinstance(child, ast.Constant) and child.value == value for child in ast.walk(node))


def is_placeholder_function(node: ast.FunctionDef) -> bool:
    meaningful = [
        stmt for stmt in node.body
        if not (
            isinstance(stmt, ast.Expr)
            and isinstance(getattr(stmt, "value", None), ast.Constant)
            and isinstance(stmt.value.value, str)
        )
    ]
    if not meaningful:
        return True
    if len(meaningful) == 1:
        stmt = meaningful[0]
        if isinstance(stmt, ast.Pass):
            return True
        if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant) and stmt.value.value in (None, 0, False):
            return True
    return False


def safe_load_functions(py_path: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    """Execute imports, assignments, and function definitions; skip top-level main() calls."""
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

        namespace: Dict[str, Any] = {"__name__": "lab11_grader_import"}
        exec(compile(module, str(py_path), "exec"), namespace)
        return namespace, "ok"
    except Exception as exc:
        return None, f"Could not load functions safely: {exc}"


def normalize_search_result(value: Any) -> Tuple[Any, Any]:
    """Return (index, comparisons) when a search function returns a tuple/list; otherwise (value, None)."""
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        return value[0], value[1]
    return value, None


def call_function(function: Callable[..., Any], args: Tuple[Any, ...]) -> Tuple[bool, Any, str]:
    try:
        return True, function(*args), "ok"
    except Exception as exc:
        return False, None, f"Exception: {exc}"


def index_is_not_found(index: Any) -> bool:
    return index in (-1, None, False)


def test_function_behavior(namespace: Dict[str, Any]) -> Dict[str, str]:
    result = {
        "linear_search_found_cases_correct": "no",
        "linear_search_not_found_case_correct": "no",
        "linear_search_comparison_count_reasonable": "no",
        "binary_search_found_cases_correct": "no",
        "binary_search_not_found_case_correct": "no",
        "binary_search_comparison_count_reasonable": "no",
        "binary_search_more_efficient_than_linear": "no",
        "f_function_correct": "no",
        "bisection_root_sqrt2_correct": "no",
        "bisection_root_handles_other_function": "no",
        "bisection_root_respects_tolerance": "no",
        "behavior_notes": "",
    }

    linear_search = namespace.get("linear_search")
    binary_search = namespace.get("binary_search")
    f = namespace.get("f")
    bisection_root = namespace.get("bisection_root")

    sorted_values = [1, 3, 5, 7, 9, 11, 13, 15]
    large_values = list(range(0, 1000, 2))

    if callable(linear_search):
        try:
            found_ok = True
            for target, expected_index in [(1, 0), (7, 3), (15, 7)]:
                ok, value, note = call_function(linear_search, (sorted_values, target))
                index, comps = normalize_search_result(value)
                if not ok or index != expected_index:
                    found_ok = False
                    result["behavior_notes"] += f"linear_search({target}) returned {value!r}; expected index {expected_index} ({note}). "
                    break
            result["linear_search_found_cases_correct"] = "yes" if found_ok else "no"
        except Exception as exc:
            result["behavior_notes"] += f"linear_search found-case test raised: {exc}. "

        try:
            ok, value, note = call_function(linear_search, (sorted_values, 8))
            index, comps = normalize_search_result(value)
            if ok and index_is_not_found(index):
                result["linear_search_not_found_case_correct"] = "yes"
            else:
                result["behavior_notes"] += f"linear_search not-found case returned {value!r}; expected -1 or None ({note}). "
        except Exception as exc:
            result["behavior_notes"] += f"linear_search not-found test raised: {exc}. "

        try:
            ok, value, note = call_function(linear_search, (large_values, large_values[-1]))
            index, comps = normalize_search_result(value)
            if ok and index == len(large_values) - 1 and isinstance(comps, int) and len(large_values) - 2 <= comps <= len(large_values) + 1:
                result["linear_search_comparison_count_reasonable"] = "yes"
            else:
                result["behavior_notes"] += f"linear_search comparison count looked wrong: returned {value!r}. "
        except Exception as exc:
            result["behavior_notes"] += f"linear_search comparison-count test raised: {exc}. "
    else:
        result["behavior_notes"] += "linear_search is not callable. "

    if callable(binary_search):
        try:
            found_ok = True
            for target, expected_index in [(1, 0), (7, 3), (15, 7)]:
                ok, value, note = call_function(binary_search, (sorted_values, target))
                index, comps = normalize_search_result(value)
                if not ok or index != expected_index:
                    found_ok = False
                    result["behavior_notes"] += f"binary_search({target}) returned {value!r}; expected index {expected_index} ({note}). "
                    break
            result["binary_search_found_cases_correct"] = "yes" if found_ok else "no"
        except Exception as exc:
            result["behavior_notes"] += f"binary_search found-case test raised: {exc}. "

        try:
            ok, value, note = call_function(binary_search, (sorted_values, 8))
            index, comps = normalize_search_result(value)
            if ok and index_is_not_found(index):
                result["binary_search_not_found_case_correct"] = "yes"
            else:
                result["behavior_notes"] += f"binary_search not-found case returned {value!r}; expected -1 or None ({note}). "
        except Exception as exc:
            result["behavior_notes"] += f"binary_search not-found test raised: {exc}. "

        try:
            target = large_values[-1]
            ok, value, note = call_function(binary_search, (large_values, target))
            index, comps = normalize_search_result(value)
            if ok and index == len(large_values) - 1 and isinstance(comps, int) and 1 <= comps <= 12:
                result["binary_search_comparison_count_reasonable"] = "yes"
            else:
                result["behavior_notes"] += f"binary_search comparison count looked wrong: returned {value!r}. "
        except Exception as exc:
            result["behavior_notes"] += f"binary_search comparison-count test raised: {exc}. "
    else:
        result["behavior_notes"] += "binary_search is not callable. "

    if callable(linear_search) and callable(binary_search):
        try:
            target = large_values[-1]
            lin_ok, lin_value, _ = call_function(linear_search, (large_values, target))
            bin_ok, bin_value, _ = call_function(binary_search, (large_values, target))
            _, lin_comps = normalize_search_result(lin_value)
            _, bin_comps = normalize_search_result(bin_value)
            if lin_ok and bin_ok and isinstance(lin_comps, int) and isinstance(bin_comps, int) and bin_comps < lin_comps / 10:
                result["binary_search_more_efficient_than_linear"] = "yes"
            else:
                result["behavior_notes"] += f"Efficiency comparison failed or missing counts: linear={lin_value!r}, binary={bin_value!r}. "
        except Exception as exc:
            result["behavior_notes"] += f"Efficiency comparison test raised: {exc}. "

    if callable(f):
        try:
            values_ok = (
                abs(f(0) + 2) < 1e-12
                and abs(f(1) + 1) < 1e-12
                and abs(f(2) - 2) < 1e-12
                and abs(f(math.sqrt(2))) < 1e-10
            )
            result["f_function_correct"] = "yes" if values_ok else "no"
            if not values_ok:
                result["behavior_notes"] += "f(x) does not appear to return x*x - 2. "
        except Exception as exc:
            result["behavior_notes"] += f"f function test raised: {exc}. "
    else:
        result["behavior_notes"] += "f is not callable. "

    if callable(bisection_root):
        try:
            root = bisection_root(lambda x: x * x - 2, 1, 2, 0.0001)
            if isinstance(root, (int, float)) and abs(root - math.sqrt(2)) <= 0.001:
                result["bisection_root_sqrt2_correct"] = "yes"
            else:
                result["behavior_notes"] += f"bisection_root sqrt(2) test returned {root!r}. "
        except Exception as exc:
            result["behavior_notes"] += f"bisection_root sqrt(2) test raised: {exc}. "

        try:
            root = bisection_root(lambda x: x ** 3 - 27, 2, 4, 0.0001)
            if isinstance(root, (int, float)) and abs(root - 3) <= 0.001:
                result["bisection_root_handles_other_function"] = "yes"
            else:
                result["behavior_notes"] += f"bisection_root cubic test returned {root!r}. "
        except Exception as exc:
            result["behavior_notes"] += f"bisection_root cubic test raised: {exc}. "

        try:
            coarse = bisection_root(lambda x: x * x - 2, 1, 2, 0.1)
            fine = bisection_root(lambda x: x * x - 2, 1, 2, 1e-6)
            if (
                isinstance(coarse, (int, float))
                and isinstance(fine, (int, float))
                and abs(fine - math.sqrt(2)) <= 1e-4
                and abs(fine - math.sqrt(2)) <= abs(coarse - math.sqrt(2)) + 1e-12
            ):
                result["bisection_root_respects_tolerance"] = "yes"
            else:
                result["behavior_notes"] += f"bisection tolerance test looked wrong: coarse={coarse!r}, fine={fine!r}. "
        except Exception as exc:
            result["behavior_notes"] += f"bisection tolerance test raised: {exc}. "
    else:
        result["behavior_notes"] += "bisection_root is not callable. "

    return result


def run_program(py_path: Path) -> Tuple[bool, str]:
    code, out, err = run_command(
        [sys.executable, str(py_path.name)],
        cwd=py_path.parent,
        timeout=10,
    )
    if code == 0:
        return True, out
    return False, err or out


def output_has_expected_content(output: str) -> Tuple[bool, str]:
    notes = []
    lowered = output.lower()

    for phrase in ["search tests", "linear", "binary", "root finding", "approximate root"]:
        if phrase not in lowered:
            notes.append(f"Missing expected output phrase: {phrase}")

    if "1.414" not in output and "1.41" not in output:
        notes.append("Output does not appear to show a sqrt(2) root near 1.414")

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
        "search_and_roots_exists": "no",
        "search_and_roots_path": "",
        "parses": "no",
        "linear_search_exists": "no",
        "binary_search_exists": "no",
        "f_exists": "no",
        "bisection_root_exists": "no",
        "main_exists": "no",
        "linear_search_not_placeholder": "no",
        "binary_search_not_placeholder": "no",
        "bisection_root_not_placeholder": "no",
        "linear_search_uses_loop": "no",
        "binary_search_uses_loop": "no",
        "binary_search_uses_midpoint_logic": "no",
        "bisection_root_uses_loop": "no",
        "bisection_root_calls_function_argument": "no",
        "main_uses_random_sample_and_sort": "no",
        "main_calls_search_functions": "no",
        "main_calls_bisection_root": "no",
        "linear_search_found_cases_correct": "no",
        "linear_search_not_found_case_correct": "no",
        "linear_search_comparison_count_reasonable": "no",
        "binary_search_found_cases_correct": "no",
        "binary_search_not_found_case_correct": "no",
        "binary_search_comparison_count_reasonable": "no",
        "binary_search_more_efficient_than_linear": "no",
        "f_function_correct": "no",
        "bisection_root_sqrt2_correct": "no",
        "bisection_root_handles_other_function": "no",
        "bisection_root_respects_tolerance": "no",
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

    py_path = find_file(repo_dir, EXPECTED_FILE)

    if not py_path:
        result["notes"] += "search_and_roots.py not found; awarded zero for Lab 11. "
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

    result["search_and_roots_exists"] = "yes"
    result["search_and_roots_path"] = str(py_path.relative_to(repo_dir))
    score += 1

    tree, parse_note = parse_python(py_path)
    if tree is None:
        result["notes"] += f"Could not parse search_and_roots.py: {parse_note}. "
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

        for fn_name in ["linear_search", "binary_search", "bisection_root"]:
            fn_node = get_function_node(tree, fn_name)
            if fn_node is not None and not is_placeholder_function(fn_node):
                result[f"{fn_name}_not_placeholder"] = "yes"
            elif fn_node is not None:
                result["notes"] += f"{fn_name} still looks like placeholder code. "

        linear_node = get_function_node(tree, "linear_search")
        if linear_node is not None and any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(linear_node)):
            result["linear_search_uses_loop"] = "yes"
            score += 1
        elif linear_node is not None:
            result["notes"] += "linear_search does not appear to use a loop. "

        binary_node = get_function_node(tree, "binary_search")
        if binary_node is not None:
            if any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(binary_node)):
                result["binary_search_uses_loop"] = "yes"
                score += 1
            else:
                result["notes"] += "binary_search does not appear to use a loop. "

            midpoint_evidence = (
                contains_operator(binary_node, ast.FloorDiv)
                or contains_operator(binary_node, ast.RShift)
                or contains_name(binary_node, "mid")
                or contains_name(binary_node, "middle")
            )
            boundary_evidence = (
                contains_name(binary_node, "left")
                or contains_name(binary_node, "right")
                or contains_name(binary_node, "low")
                or contains_name(binary_node, "high")
            )
            if midpoint_evidence and boundary_evidence:
                result["binary_search_uses_midpoint_logic"] = "yes"
                score += 1
            else:
                result["notes"] += "binary_search midpoint/boundary logic was not clearly detected. "

        bisect_node = get_function_node(tree, "bisection_root")
        if bisect_node is not None:
            if any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(bisect_node)):
                result["bisection_root_uses_loop"] = "yes"
                score += 1
            else:
                result["notes"] += "bisection_root does not appear to use a loop. "

            if contains_call_to(bisect_node, "function") or contains_name(bisect_node, "function"):
                result["bisection_root_calls_function_argument"] = "yes"
                score += 1
            else:
                result["notes"] += "bisection_root does not appear to use the function argument. "

        main_node = get_function_node(tree, "main")
        if main_node is not None:
            if contains_call_to(main_node, "sample") and contains_call_to(main_node, "sort"):
                result["main_uses_random_sample_and_sort"] = "yes"
            else:
                result["notes"] += "main does not clearly use random.sample and sort. "

            if contains_call_to(main_node, "linear_search") and contains_call_to(main_node, "binary_search"):
                result["main_calls_search_functions"] = "yes"
                score += 1
            else:
                result["notes"] += "main does not appear to call both search functions. "

            if contains_call_to(main_node, "bisection_root"):
                result["main_calls_bisection_root"] = "yes"
                score += 1
            else:
                result["notes"] += "main does not appear to call bisection_root. "

        namespace, load_note = safe_load_functions(py_path)
        if namespace is not None:
            behavior = test_function_behavior(namespace)
            for key, value in behavior.items():
                if key in result:
                    result[key] = value
            result["notes"] += behavior.get("behavior_notes", "")

            for key in [
                "linear_search_found_cases_correct",
                "linear_search_not_found_case_correct",
                "linear_search_comparison_count_reasonable",
                "binary_search_found_cases_correct",
                "binary_search_not_found_case_correct",
                "binary_search_comparison_count_reasonable",
                "binary_search_more_efficient_than_linear",
                "f_function_correct",
                "bisection_root_sqrt2_correct",
                "bisection_root_handles_other_function",
                "bisection_root_respects_tolerance",
            ]:
                if result[key] == "yes":
                    score += 1
        else:
            result["notes"] += load_note + " "

    run_ok, output = run_program(py_path)
    result["program_runs_from_terminal"] = "yes" if run_ok else "no"
    result["program_output"] = output[:1200]
    if run_ok:
        score += 1
        readable, output_note = output_has_expected_content(output)
        if readable:
            result["program_output_readable"] = "yes"
            score += 1
        else:
            result["notes"] += f"Output check: {output_note}. "
    else:
        result["notes"] += "search_and_roots.py did not run successfully from terminal. "

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
    result[f"auto_score_out_of_{TOTAL_POINTS}"] = str(min(score, TOTAL_POINTS))
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
        "search_and_roots_exists",
        "search_and_roots_path",
        "parses",
        "linear_search_exists",
        "binary_search_exists",
        "f_exists",
        "bisection_root_exists",
        "main_exists",
        "linear_search_not_placeholder",
        "binary_search_not_placeholder",
        "bisection_root_not_placeholder",
        "linear_search_uses_loop",
        "binary_search_uses_loop",
        "binary_search_uses_midpoint_logic",
        "bisection_root_uses_loop",
        "bisection_root_calls_function_argument",
        "main_uses_random_sample_and_sort",
        "main_calls_search_functions",
        "main_calls_bisection_root",
        "linear_search_found_cases_correct",
        "linear_search_not_found_case_correct",
        "linear_search_comparison_count_reasonable",
        "binary_search_found_cases_correct",
        "binary_search_not_found_case_correct",
        "binary_search_comparison_count_reasonable",
        "binary_search_more_efficient_than_linear",
        "f_function_correct",
        "bisection_root_sqrt2_correct",
        "bisection_root_handles_other_function",
        "bisection_root_respects_tolerance",
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
    parser = argparse.ArgumentParser(description="Grade CPSC 250L Lab 11 student forks.")

    parser.add_argument("--students", required=True, help="Path to students.csv")
    parser.add_argument("--workdir", default="student_repos", help="Folder where repos are cloned")
    parser.add_argument("--report", default="reports/lab11_report.csv", help="Output CSV report path")
    parser.add_argument(
        "--lab-path",
        default="labs/lab11_search_and_roots",
        help="Repo-relative path used for lab-specific Git commit checks",
    )

    args = parser.parse_args()

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
