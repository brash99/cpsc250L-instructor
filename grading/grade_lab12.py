#!/usr/bin/env python3
"""
grade_lab12.py

Automated Lab 12 checker for CPSC 250L student forks.

Lab 12: Motion Plot
Default folder: labs/lab12_motion_plot
Expected file: motion_plot.py

Recommended use:

python grade_lab12.py \
  --students students.csv \
  --workdir student_repos \
  --report reports/lab12_report.csv \
  --lab-path labs/lab12_motion_plot
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import csv
import io
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


EXPECTED_FILE = "motion_plot.py"
EXPECTED_FUNCTIONS = ["position", "velocity", "main"]
TOTAL_POINTS = 24
SHOW_PLOTS = False
PLOT_PAUSE_SECONDS = 1.5
DEFAULT_LAB_PATH = "labs/lab12_motion_plot"


def run_command(
    command: List[str],
    cwd: Optional[Path] = None,
    timeout: int = 20,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            timeout=timeout,
            text=True,
            capture_output=True,
            env=env,
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
            "lab12" not in str(p).lower() and "lab_12" not in str(p).lower(),
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


def contains_operator(node: ast.AST, op_type: type[ast.AST]) -> bool:
    return any(isinstance(child, op_type) for child in ast.walk(node))


def contains_numeric_constant(node: ast.AST, target: float, tolerance: float = 1e-12) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, (int, float)):
            if abs(float(child.value) - target) <= tolerance:
                return True
    return False


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


def safe_load_functions(py_path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[ast.Module], str]:
    """Execute imports, assignments, and function definitions; skip top-level main() calls."""
    try:
        source = py_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        safe_body: List[ast.stmt] = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign, ast.AnnAssign)):
                safe_body.append(node)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                continue
            elif isinstance(node, ast.If):
                continue

        module = ast.Module(body=safe_body, type_ignores=[])
        ast.fix_missing_locations(module)

        os.environ.setdefault("MPLBACKEND", "Agg")
        namespace: Dict[str, Any] = {"__name__": "lab12_grader_import", "__file__": str(py_path)}
        exec(compile(module, str(py_path), "exec"), namespace)
        return namespace, tree, "ok"
    except Exception as exc:
        return None, None, f"Could not load functions safely: {exc}"


def call_function(function: Callable[..., Any], args: Tuple[Any, ...]) -> Tuple[bool, Any, str]:
    try:
        return True, function(*args), "ok"
    except Exception as exc:
        return False, None, f"Exception: {exc}"


def values_close(actual: Any, expected: Any, tolerance: float = 1e-9) -> bool:
    try:
        import numpy as np
        return bool(np.allclose(actual, expected, rtol=tolerance, atol=tolerance))
    except Exception:
        try:
            return abs(actual - expected) <= tolerance
        except Exception:
            return False


def test_function_behavior(namespace: Dict[str, Any]) -> Dict[str, str]:
    result = {
        "position_scalar_cases_correct": "no",
        "position_array_case_correct": "no",
        "velocity_scalar_cases_correct": "no",
        "velocity_array_case_correct": "no",
        "behavior_notes": "",
    }

    position = namespace.get("position")
    velocity = namespace.get("velocity")

    if callable(position):
        scalar_cases = [
            ((0, 10, 3, -9.8), 10),
            ((2, 10, 3, -9.8), 10 + 3 * 2 + 0.5 * -9.8 * 2 ** 2),
            ((4.5, -2, 7, 1.25), -2 + 7 * 4.5 + 0.5 * 1.25 * 4.5 ** 2),
        ]
        ok_count = 0
        for args, expected in scalar_cases:
            ok, value, note = call_function(position, args)
            if ok and values_close(value, expected):
                ok_count += 1
            else:
                result["behavior_notes"] += f"position{args} returned {value!r}; expected {expected!r} ({note}). "
                break
        if ok_count == len(scalar_cases):
            result["position_scalar_cases_correct"] = "yes"

        try:
            import numpy as np
            t = np.array([0.0, 1.0, 2.0, 3.0])
            expected = 5 + 2 * t + 0.5 * (-1.5) * t ** 2
            ok, value, note = call_function(position, (t, 5, 2, -1.5))
            if ok and values_close(value, expected):
                result["position_array_case_correct"] = "yes"
            else:
                result["behavior_notes"] += f"position array case returned {value!r}; expected numpy-compatible vector result ({note}). "
        except Exception as exc:
            result["behavior_notes"] += f"position array test raised: {exc}. "
    else:
        result["behavior_notes"] += "position is not callable. "

    if callable(velocity):
        scalar_cases = [
            ((0, 3, -9.8), 3),
            ((2, 3, -9.8), 3 + -9.8 * 2),
            ((4.5, 7, 1.25), 7 + 1.25 * 4.5),
        ]
        ok_count = 0
        for args, expected in scalar_cases:
            ok, value, note = call_function(velocity, args)
            if ok and values_close(value, expected):
                ok_count += 1
            else:
                result["behavior_notes"] += f"velocity{args} returned {value!r}; expected {expected!r} ({note}). "
                break
        if ok_count == len(scalar_cases):
            result["velocity_scalar_cases_correct"] = "yes"

        try:
            import numpy as np
            t = np.array([0.0, 1.0, 2.0, 3.0])
            expected = 2 + -1.5 * t
            ok, value, note = call_function(velocity, (t, 2, -1.5))
            if ok and values_close(value, expected):
                result["velocity_array_case_correct"] = "yes"
            else:
                result["behavior_notes"] += f"velocity array case returned {value!r}; expected numpy-compatible vector result ({note}). "
        except Exception as exc:
            result["behavior_notes"] += f"velocity array test raised: {exc}. "
    else:
        result["behavior_notes"] += "velocity is not callable. "

    return result


def run_main_and_check_plot(namespace: Dict[str, Any], py_path: Path, student_slug: str) -> Dict[str, str]:
    result = {
        "main_runs_safely": "no",
        "main_creates_matplotlib_figure": "no",
        "plot_has_position_series": "no",
        "plot_has_velocity_series": "no",
        "plot_has_axis_labels": "no",
        "plot_has_title_or_legend": "no",
        "main_saves_plot_file": "no",
        "saved_plot_files": "",
        "main_notes": "",
    }

    main_fn = namespace.get("main")
    if not callable(main_fn):
        result["main_notes"] = "main is not callable."
        return result

    old_cwd = Path.cwd()
    tempdir = Path(tempfile.mkdtemp(prefix=f"lab12_plot_{student_slug}_"))

    try:
        import matplotlib
        if not SHOW_PLOTS:
            matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        plt.close("all")
        original_show = plt.show
        plt.show = lambda *a, **k: None

        os.chdir(tempdir)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            main_fn()
        result["main_runs_safely"] = "yes"

        figs = [plt.figure(num) for num in plt.get_fignums()]
        axes = [ax for fig in figs for ax in fig.axes]
        saved = sorted([p.name for p in tempdir.iterdir() if p.suffix.lower() in {".png", ".pdf", ".jpg", ".jpeg", ".svg"}])
        result["saved_plot_files"] = " | ".join(saved)
        if saved:
            result["main_saves_plot_file"] = "yes"

        if axes:
            result["main_creates_matplotlib_figure"] = "yes"
            line_count = sum(len(ax.lines) for ax in axes)
            ylabel_text = " ".join(ax.get_ylabel().lower() for ax in axes)
            title_text = " ".join(ax.get_title().lower() for ax in axes)
            legend_text = " ".join(
                text.get_text().lower()
                for ax in axes
                if ax.get_legend() is not None
                for text in ax.get_legend().get_texts()
            )
            all_label_text = f"{ylabel_text} {title_text} {legend_text}"

            if line_count >= 1 and ("position" in all_label_text or len(axes) >= 2 or line_count >= 2):
                result["plot_has_position_series"] = "yes"
            if line_count >= 1 and ("velocity" in all_label_text or len(axes) >= 2 or line_count >= 2):
                result["plot_has_velocity_series"] = "yes"
            if any(ax.get_xlabel().strip() for ax in axes) and any(ax.get_ylabel().strip() for ax in axes):
                result["plot_has_axis_labels"] = "yes"
            if any(ax.get_title().strip() for ax in axes) or any(ax.get_legend() is not None for ax in axes):
                result["plot_has_title_or_legend"] = "yes"
        else:
            result["main_notes"] += "main did not leave an inspectable matplotlib figure. "

        if not saved:
            result["main_notes"] += "No saved plot file was found in the working directory after main() ran. "

        plt.show = original_show
        if SHOW_PLOTS and plt.get_fignums():
            try:
                for fig_num in plt.get_fignums():
                    fig = plt.figure(fig_num)
                    fig.suptitle(f"{student_slug} — generated plot", fontsize=10)
                print(f"  displaying plot for {student_slug} ({len(plt.get_fignums())} figure(s)); close or wait to continue")
                plt.show(block=False)
                plt.pause(PLOT_PAUSE_SECONDS)
            except Exception as exc:
                print(f"  could not display plot for {student_slug}: {exc}")
        plt.close("all")
    except Exception as exc:
        result["main_notes"] += f"main/plot test raised: {type(exc).__name__}: {exc}. "
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tempdir, ignore_errors=True)

    return result


def run_program(py_path: Path) -> Tuple[bool, str]:
    env = dict(os.environ)
    env["MPLBACKEND"] = "Agg"
    with tempfile.TemporaryDirectory(prefix="lab12_run_") as tmp:
        temp_path = Path(tmp) / EXPECTED_FILE
        shutil.copy2(py_path, temp_path)
        code, out, err = run_command(
            [sys.executable, str(temp_path.name)],
            cwd=temp_path.parent,
            timeout=10,
            env=env,
        )
        generated = sorted([p.name for p in temp_path.parent.iterdir() if p.suffix.lower() in {".png", ".pdf", ".jpg", ".jpeg", ".svg"}])
        message = (out or err or "").strip()
        if generated:
            message = (message + "\n" if message else "") + "generated_files: " + " | ".join(generated)
        if code == 0:
            return True, message
        return False, message


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
        "motion_plot_exists": "no",
        "motion_plot_path": "",
        "parses": "no",
        "imports_numpy": "no",
        "imports_matplotlib_pyplot": "no",
        "position_exists": "no",
        "velocity_exists": "no",
        "main_exists": "no",
        "position_not_placeholder": "no",
        "velocity_not_placeholder": "no",
        "main_not_placeholder": "no",
        "position_formula_structure_detected": "no",
        "velocity_formula_structure_detected": "no",
        "main_uses_linspace": "no",
        "main_calls_position": "no",
        "main_calls_velocity": "no",
        "main_uses_plot": "no",
        "main_uses_savefig": "no",
        "position_scalar_cases_correct": "no",
        "position_array_case_correct": "no",
        "velocity_scalar_cases_correct": "no",
        "velocity_array_case_correct": "no",
        "main_runs_safely": "no",
        "main_creates_matplotlib_figure": "no",
        "plot_has_position_series": "no",
        "plot_has_velocity_series": "no",
        "plot_has_axis_labels": "no",
        "plot_has_title_or_legend": "no",
        "main_saves_plot_file": "no",
        "saved_plot_files": "",
        "program_runs_from_terminal": "no",
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
    score = 0

    ok, message = clone_or_update_repo(repo_url, repo_dir)
    result["clone_or_update"] = "yes" if ok else "no"
    if not ok:
        result["notes"] = message
        return result
    score += 1

    py_path = find_file(repo_dir, EXPECTED_FILE)

    if not py_path:
        result["notes"] += "motion_plot.py not found; awarded zero for Lab 12 file/function/plot work. "
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

    result["motion_plot_exists"] = "yes"
    result["motion_plot_path"] = str(py_path.relative_to(repo_dir))
    score += 1

    tree, parse_note = parse_python(py_path)
    namespace: Optional[Dict[str, Any]] = None

    if tree is None:
        result["notes"] += f"Could not parse motion_plot.py: {parse_note}. "
    else:
        result["parses"] = "yes"
        score += 1

        source = py_path.read_text(encoding="utf-8", errors="replace")
        if "numpy" in source or "np." in source:
            result["imports_numpy"] = "yes"
            score += 1
        else:
            result["notes"] += "numpy import/use not detected. "
        if "matplotlib" in source or "plt." in source:
            result["imports_matplotlib_pyplot"] = "yes"
            score += 1
        else:
            result["notes"] += "matplotlib/pyplot import/use not detected. "

        names = function_names(tree)
        for fn_name in EXPECTED_FUNCTIONS:
            col = f"{fn_name}_exists" if fn_name != "main" else "main_exists"
            if fn_name in names:
                result[col] = "yes"
                score += 1
            else:
                result["notes"] += f"{fn_name} function not found. "

        for fn_name in EXPECTED_FUNCTIONS:
            fn_node = get_function_node(tree, fn_name)
            col = f"{fn_name}_not_placeholder" if fn_name != "main" else "main_not_placeholder"
            if fn_node is not None and not is_placeholder_function(fn_node):
                result[col] = "yes"
            elif fn_node is not None:
                result["notes"] += f"{fn_name} still looks like placeholder code. "

        position_node = get_function_node(tree, "position")
        if position_node is not None:
            formula_evidence = (
                all(contains_name(position_node, name) for name in ["t", "x0", "v0", "a"])
                and contains_operator(position_node, ast.Add)
                and contains_operator(position_node, ast.Mult)
                and (contains_operator(position_node, ast.Pow) or contains_numeric_constant(position_node, 2))
                and (contains_numeric_constant(position_node, 0.5) or contains_numeric_constant(position_node, 1/2))
            )
            if formula_evidence:
                result["position_formula_structure_detected"] = "yes"
                score += 1
            else:
                result["notes"] += "position formula structure was not clearly detected. "

        velocity_node = get_function_node(tree, "velocity")
        if velocity_node is not None:
            formula_evidence = (
                all(contains_name(velocity_node, name) for name in ["t", "v0", "a"])
                and contains_operator(velocity_node, ast.Add)
                and contains_operator(velocity_node, ast.Mult)
            )
            if formula_evidence:
                result["velocity_formula_structure_detected"] = "yes"
                score += 1
            else:
                result["notes"] += "velocity formula structure was not clearly detected. "

        main_node = get_function_node(tree, "main")
        if main_node is not None:
            if contains_call_to(main_node, "linspace"):
                result["main_uses_linspace"] = "yes"
                score += 1
            else:
                result["notes"] += "main does not clearly call np.linspace. "
            if contains_call_to(main_node, "position"):
                result["main_calls_position"] = "yes"
                score += 1
            else:
                result["notes"] += "main does not appear to call position(). "
            if contains_call_to(main_node, "velocity"):
                result["main_calls_velocity"] = "yes"
                score += 1
            else:
                result["notes"] += "main does not appear to call velocity(). "
            if contains_call_to(main_node, "plot") or contains_call_to(main_node, "subplots"):
                result["main_uses_plot"] = "yes"
                score += 1
            else:
                result["notes"] += "main does not clearly make a matplotlib plot. "
            if contains_call_to(main_node, "savefig"):
                result["main_uses_savefig"] = "yes"
                score += 1
            else:
                result["notes"] += "main does not clearly save a plot file with savefig(). "

        namespace, loaded_tree, load_note = safe_load_functions(py_path)
        if namespace is not None:
            behavior = test_function_behavior(namespace)
            for key, value in behavior.items():
                if key in result:
                    result[key] = value
            result["notes"] += behavior.get("behavior_notes", "")

            for key in [
                "position_scalar_cases_correct",
                "position_array_case_correct",
                "velocity_scalar_cases_correct",
                "velocity_array_case_correct",
            ]:
                if result[key] == "yes":
                    score += 1

            main_result = run_main_and_check_plot(namespace, py_path, username)
            for key, value in main_result.items():
                if key in result:
                    result[key] = value
            result["notes"] += main_result.get("main_notes", "")

            for key in [
                "main_runs_safely",
                "main_creates_matplotlib_figure",
                "plot_has_position_series",
                "plot_has_velocity_series",
                "plot_has_axis_labels",
                "plot_has_title_or_legend",
                "main_saves_plot_file",
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
    else:
        result["notes"] += "motion_plot.py did not run successfully from terminal. "

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
        "motion_plot_exists",
        "motion_plot_path",
        "parses",
        "imports_numpy",
        "imports_matplotlib_pyplot",
        "position_exists",
        "velocity_exists",
        "main_exists",
        "position_not_placeholder",
        "velocity_not_placeholder",
        "main_not_placeholder",
        "position_formula_structure_detected",
        "velocity_formula_structure_detected",
        "main_uses_linspace",
        "main_calls_position",
        "main_calls_velocity",
        "main_uses_plot",
        "main_uses_savefig",
        "position_scalar_cases_correct",
        "position_array_case_correct",
        "velocity_scalar_cases_correct",
        "velocity_array_case_correct",
        "main_runs_safely",
        "main_creates_matplotlib_figure",
        "plot_has_position_series",
        "plot_has_velocity_series",
        "plot_has_axis_labels",
        "plot_has_title_or_legend",
        "main_saves_plot_file",
        "saved_plot_files",
        "program_runs_from_terminal",
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
    parser = argparse.ArgumentParser(description="Grade CPSC 250L Lab 12 student forks.")

    parser.add_argument("--students", required=True, help="Path to students.csv")
    parser.add_argument("--workdir", default="student_repos", help="Folder where repos are cloned")
    parser.add_argument("--report", default="reports/lab12_report.csv", help="Output CSV report path")
    parser.add_argument(
        "--lab-path",
        default=DEFAULT_LAB_PATH,
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
        result = grade_student(student, workdir, args.lab_path)
        print(f"  score: {result[f'auto_score_out_of_{TOTAL_POINTS}']}/{TOTAL_POINTS}")
        if result.get("saved_plot_files"):
            print(f"  saved plot files seen during main(): {result['saved_plot_files']}")
        results.append(result)

    write_report(report_path, results)
    print(f"\nWrote report: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
