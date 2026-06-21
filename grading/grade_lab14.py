#!/usr/bin/env python3
"""
grade_lab14.py

Automated Lab 14 checker for CPSC 250L student forks.

Lab 14: Regression Analysis
Default folder: labs/lab14_regression_analysis
Expected files: regression_analysis.py, study_scores.csv/data/study_scores.csv

Recommended use:

python grade_lab14.py \
  --students students.csv \
  --workdir student_repos \
  --report reports/lab14_report.csv \
  --lab-path labs/lab14_regression_analysis
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

EXPECTED_FILE = "regression_analysis.py"
EXPECTED_DATA_FILE = "study_scores.csv"
EXPECTED_FUNCTIONS = ["load_data", "fit_line", "predict", "main"]
TOTAL_POINTS = 24
DEFAULT_LAB_PATH = "labs/lab14_regression_analysis"

SAMPLE_CSV = """hours,score
1.0,58
1.5,62
2.0,65
2.5,68
3.0,72
3.5,74
4.0,78
4.5,81
5.0,84
5.5,86
6.0,90
"""
EXPECTED_SLOPE = 6.272727272727274
EXPECTED_INTERCEPT = 52.40909090909091


def run_command(command: List[str], cwd: Optional[Path] = None, timeout: int = 20, env: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(command, cwd=cwd, timeout=timeout, text=True, capture_output=True, env=env)
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
        if ".git" not in p.parts and ".venv" not in p.parts and "venv" not in p.parts and "__pycache__" not in p.parts
    ]
    if not filtered:
        return None
    filtered.sort(key=lambda p: ("lab14" not in str(p).lower() and "lab_14" not in str(p).lower(), len(p.parts)))
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


def is_placeholder_function(node: ast.FunctionDef) -> bool:
    meaningful = [
        stmt for stmt in node.body
        if not (isinstance(stmt, ast.Expr) and isinstance(getattr(stmt, "value", None), ast.Constant) and isinstance(stmt.value.value, str))
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
        namespace: Dict[str, Any] = {"__name__": "lab14_grader_import", "__file__": str(py_path)}
        exec(compile(module, str(py_path), "exec"), namespace)
        return namespace, tree, "ok"
    except Exception as exc:
        return None, None, f"Could not load functions safely: {exc}"


def call_function(function: Callable[..., Any], args: Tuple[Any, ...]) -> Tuple[bool, Any, str]:
    try:
        return True, function(*args), "ok"
    except Exception as exc:
        return False, None, f"Exception: {type(exc).__name__}: {exc}"


def make_sample_csv(tempdir: Path) -> Path:
    csv_path = tempdir / EXPECTED_DATA_FILE
    csv_path.write_text(SAMPLE_CSV, encoding="utf-8")
    data_dir = tempdir / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / EXPECTED_DATA_FILE).write_text(SAMPLE_CSV, encoding="utf-8")
    return csv_path


def coerce_slope_intercept(value: Any) -> Tuple[Optional[float], Optional[float], str]:
    """Accept (slope, intercept), numpy arrays/lists, or a small mapping."""
    try:
        if isinstance(value, dict):
            slope_keys = ["slope", "m", "coefficient", "coef"]
            intercept_keys = ["intercept", "b"]
            slope = next((value[k] for k in slope_keys if k in value), None)
            intercept = next((value[k] for k in intercept_keys if k in value), None)
            if slope is not None and intercept is not None:
                return float(slope), float(intercept), "ok"
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return float(value[0]), float(value[1]), "ok"
        try:
            import numpy as np
            arr = np.asarray(value, dtype=float).ravel()
            if arr.size >= 2:
                return float(arr[0]), float(arr[1]), "ok"
        except Exception:
            pass
        return None, None, f"Could not interpret fit_line return value {value!r} as slope/intercept."
    except Exception as exc:
        return None, None, f"Could not interpret fit_line return value: {exc}"


def numeric_close(a: Any, b: float, tol: float = 1e-6) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False


def array_close(actual: Any, expected: Any, tol: float = 1e-6) -> bool:
    try:
        import numpy as np
        return bool(np.allclose(actual, expected, rtol=tol, atol=tol))
    except Exception:
        return False


def test_function_behavior(namespace: Dict[str, Any], py_path: Path) -> Dict[str, str]:
    result = {
        "load_data_returns_dataframe": "no",
        "load_data_correct_shape_columns": "no",
        "fit_line_returns_pair": "no",
        "fit_line_correct_slope": "no",
        "fit_line_correct_intercept": "no",
        "predict_scalar_correct": "no",
        "predict_array_correct": "no",
        "behavior_notes": "",
    }
    load_data = namespace.get("load_data")
    fit_line = namespace.get("fit_line")
    predict = namespace.get("predict")

    try:
        import pandas as pd
        import numpy as np
        with tempfile.TemporaryDirectory(prefix="lab14_func_") as tmp:
            tempdir = Path(tmp)
            csv_path = make_sample_csv(tempdir)
            df_loaded = None
            if callable(load_data):
                ok, value, note = call_function(load_data, (str(csv_path),))
                if ok:
                    df_loaded = value
                    if isinstance(value, pd.DataFrame):
                        result["load_data_returns_dataframe"] = "yes"
                        if {"hours", "score"}.issubset(set(value.columns)) and len(value) == 11:
                            result["load_data_correct_shape_columns"] = "yes"
                        else:
                            result["behavior_notes"] += f"load_data columns/rows unexpected: columns={list(value.columns)!r}, rows={len(value)}. "
                    else:
                        result["behavior_notes"] += f"load_data returned {type(value).__name__}, not DataFrame. "
                else:
                    result["behavior_notes"] += f"load_data failed: {note}. "
            else:
                result["behavior_notes"] += "load_data is not callable. "
            if df_loaded is None:
                df_loaded = pd.read_csv(csv_path)
            x = df_loaded["hours"].to_numpy(dtype=float)
            y = df_loaded["score"].to_numpy(dtype=float)
            slope = intercept = None
            if callable(fit_line):
                ok, value, note = call_function(fit_line, (x, y))
                if ok:
                    slope, intercept, fit_note = coerce_slope_intercept(value)
                    if slope is not None and intercept is not None:
                        result["fit_line_returns_pair"] = "yes"
                        if numeric_close(slope, EXPECTED_SLOPE, 1e-5):
                            result["fit_line_correct_slope"] = "yes"
                        else:
                            result["behavior_notes"] += f"fit_line slope {slope!r}; expected about {EXPECTED_SLOPE:.6f}. "
                        if numeric_close(intercept, EXPECTED_INTERCEPT, 1e-5):
                            result["fit_line_correct_intercept"] = "yes"
                        else:
                            result["behavior_notes"] += f"fit_line intercept {intercept!r}; expected about {EXPECTED_INTERCEPT:.6f}. "
                    else:
                        result["behavior_notes"] += fit_note + " "
                else:
                    result["behavior_notes"] += f"fit_line failed: {note}. "
            else:
                result["behavior_notes"] += "fit_line is not callable. "
            if slope is None or intercept is None:
                slope, intercept = EXPECTED_SLOPE, EXPECTED_INTERCEPT
            if callable(predict):
                ok, value, note = call_function(predict, (4.0, slope, intercept))
                if ok:
                    expected = slope * 4.0 + intercept
                    if numeric_close(value, expected, 1e-5):
                        result["predict_scalar_correct"] = "yes"
                    else:
                        result["behavior_notes"] += f"predict scalar returned {value!r}; expected {expected:.6f}. "
                else:
                    result["behavior_notes"] += f"predict scalar failed: {note}. "
                test_x = np.array([1.0, 2.5, 6.0])
                ok, value, note = call_function(predict, (test_x, slope, intercept))
                if ok:
                    expected = slope * test_x + intercept
                    if array_close(value, expected, 1e-5):
                        result["predict_array_correct"] = "yes"
                    else:
                        result["behavior_notes"] += f"predict array returned {value!r}; expected values near {expected!r}. "
                else:
                    result["behavior_notes"] += f"predict array failed: {note}. "
            else:
                result["behavior_notes"] += "predict is not callable. "
    except Exception as exc:
        result["behavior_notes"] += f"Function behavior tests failed unexpectedly: {type(exc).__name__}: {exc}. "
    return result


def run_main_and_check(namespace: Dict[str, Any], py_path: Path, student_slug: str) -> Dict[str, str]:
    result = {
        "main_runs_safely": "no",
        "main_loads_data": "no",
        "main_fits_line": "no",
        "main_predicts_values": "no",
        "main_creates_matplotlib_figure": "no",
        "main_has_scatter_points": "no",
        "main_has_fit_line": "no",
        "main_has_axis_labels": "no",
        "main_has_title_or_legend": "no",
        "main_saves_or_shows_plot": "no",
        "main_notes": "",
    }
    main_fn = namespace.get("main")
    if not callable(main_fn):
        result["main_notes"] = "main is not callable."
        return result
    old_cwd = Path.cwd()
    tempdir = Path(tempfile.mkdtemp(prefix=f"lab14_main_{student_slug}_"))
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        plt.close("all")
        show_called = {"value": False}
        original_show = plt.show
        def fake_show(*args: Any, **kwargs: Any) -> None:
            show_called["value"] = True
        plt.show = fake_show

        make_sample_csv(tempdir)
        parent_data = tempdir.parent / "data"
        parent_data.mkdir(exist_ok=True)
        (parent_data / EXPECTED_DATA_FILE).write_text(SAMPLE_CSV, encoding="utf-8")

        os.chdir(tempdir)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            main_fn()
        result["main_runs_safely"] = "yes"

        tree, _ = parse_python(py_path)
        main_node = get_function_node(tree, "main") if tree is not None else None
        if main_node is not None:
            if contains_call_to(main_node, "load_data") or contains_call_to(main_node, "read_csv"):
                result["main_loads_data"] = "yes"
            if contains_call_to(main_node, "fit_line") or contains_call_to(main_node, "polyfit"):
                result["main_fits_line"] = "yes"
            if contains_call_to(main_node, "predict"):
                result["main_predicts_values"] = "yes"

        figs = [plt.figure(num) for num in plt.get_fignums()]
        axes = [ax for fig in figs for ax in fig.axes]
        saved = [p.name for p in tempdir.iterdir() if p.suffix.lower() in {".png", ".pdf", ".jpg", ".jpeg", ".svg"}]
        if axes:
            result["main_creates_matplotlib_figure"] = "yes"
            if any(len(ax.collections) >= 1 for ax in axes):
                result["main_has_scatter_points"] = "yes"
            # Accept a plotted regression line either as a line object or as second plotted series.
            if any(len(ax.lines) >= 1 for ax in axes):
                result["main_has_fit_line"] = "yes"
            labels = " ".join(
                [ax.get_xlabel().lower() + " " + ax.get_ylabel().lower() + " " + ax.get_title().lower() for ax in axes]
                + [text.get_text().lower() for ax in axes if ax.get_legend() for text in ax.get_legend().get_texts()]
            )
            if any(ax.get_xlabel().strip() for ax in axes) and any(ax.get_ylabel().strip() for ax in axes):
                result["main_has_axis_labels"] = "yes"
            if any(ax.get_title().strip() for ax in axes) or any(ax.get_legend() is not None for ax in axes):
                result["main_has_title_or_legend"] = "yes"
        else:
            result["main_notes"] += "main did not leave an inspectable matplotlib figure. "
        if show_called["value"] or saved:
            result["main_saves_or_shows_plot"] = "yes"

        # Display the plot briefly for instructor visual inspection when running interactively.
        if axes:
            print(f"  plot generated for {student_slug}: {len(axes)} axes, {sum(len(ax.lines) for ax in axes)} line(s), {sum(len(ax.collections) for ax in axes)} scatter collection(s)")

        plt.show = original_show
        plt.close("all")
    except Exception as exc:
        result["main_notes"] += f"main test raised: {type(exc).__name__}: {exc}. "
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tempdir, ignore_errors=True)
    return result


def run_program(py_path: Path) -> Tuple[bool, str]:
    env = dict(os.environ)
    env["MPLBACKEND"] = "Agg"
    with tempfile.TemporaryDirectory(prefix="lab14_run_") as tmp:
        tempdir = Path(tmp)
        temp_path = tempdir / EXPECTED_FILE
        shutil.copy2(py_path, temp_path)
        make_sample_csv(tempdir)
        parent_data = tempdir.parent / "data"
        parent_data.mkdir(exist_ok=True)
        (parent_data / EXPECTED_DATA_FILE).write_text(SAMPLE_CSV, encoding="utf-8")
        code, out, err = run_command([sys.executable, str(temp_path.name)], cwd=temp_path.parent, timeout=10, env=env)
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
    code, out, err = run_command(["git", "rev-list", "--count", "HEAD", "--", lab_path], cwd=repo_dir)
    if code != 0:
        return None, err or out
    try:
        return int(out), "ok"
    except ValueError:
        return None, f"could not parse commit count: {out}"


def get_recent_lab_commits(repo_dir: Path, lab_path: Optional[str], n: int = 8) -> str:
    if not lab_path:
        return ""
    code, out, err = run_command(["git", "log", "--oneline", f"-{n}", "--", lab_path], cwd=repo_dir)
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
        "regression_analysis_exists": "no",
        "regression_analysis_path": "",
        "study_scores_csv_found": "no",
        "study_scores_csv_path": "",
        "parses": "no",
        "imports_pandas": "no",
        "imports_numpy": "no",
        "imports_matplotlib_pyplot": "no",
        "load_data_exists": "no",
        "fit_line_exists": "no",
        "predict_exists": "no",
        "main_exists": "no",
        "load_data_not_placeholder": "no",
        "fit_line_not_placeholder": "no",
        "predict_not_placeholder": "no",
        "main_not_placeholder": "no",
        "load_data_uses_read_csv": "no",
        "fit_line_uses_polyfit_or_linear_algebra": "no",
        "predict_formula_structure_detected": "no",
        "main_uses_scatter_or_plot": "no",
        "load_data_returns_dataframe": "no",
        "load_data_correct_shape_columns": "no",
        "fit_line_returns_pair": "no",
        "fit_line_correct_slope": "no",
        "fit_line_correct_intercept": "no",
        "predict_scalar_correct": "no",
        "predict_array_correct": "no",
        "main_runs_safely": "no",
        "main_loads_data": "no",
        "main_fits_line": "no",
        "main_predicts_values": "no",
        "main_creates_matplotlib_figure": "no",
        "main_has_scatter_points": "no",
        "main_has_fit_line": "no",
        "main_has_axis_labels": "no",
        "main_has_title_or_legend": "no",
        "main_saves_or_shows_plot": "no",
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
    data_path = find_file(repo_dir, EXPECTED_DATA_FILE)
    if data_path is not None:
        result["study_scores_csv_found"] = "yes"
        result["study_scores_csv_path"] = str(data_path.relative_to(repo_dir))
        score += 1
    else:
        result["notes"] += "study_scores.csv not found in repo; grader used built-in sample data for runtime tests. "

    if not py_path:
        result["notes"] += "regression_analysis.py not found; awarded zero for Lab 14 file/function/plot work. "
        clean, clean_note = is_working_tree_clean(repo_dir)
        result["working_tree_clean"] = "yes" if clean else "no"
        result["recent_commits"] = get_recent_commits(repo_dir).replace("\n", " | ")[:900]
        result["branch_info"] = get_branch_info(repo_dir).replace("\n", " | ")[:900]
        return result

    result["regression_analysis_exists"] = "yes"
    result["regression_analysis_path"] = str(py_path.relative_to(repo_dir))
    score += 1

    tree, parse_note = parse_python(py_path)
    namespace: Optional[Dict[str, Any]] = None
    if tree is None:
        result["notes"] += f"Could not parse regression_analysis.py: {parse_note}. "
    else:
        result["parses"] = "yes"
        score += 1
        source = py_path.read_text(encoding="utf-8", errors="replace")
        if "pandas" in source or "pd." in source:
            result["imports_pandas"] = "yes"; score += 1
        else:
            result["notes"] += "pandas import/use not detected. "
        if "numpy" in source or "np." in source:
            result["imports_numpy"] = "yes"; score += 1
        else:
            result["notes"] += "numpy import/use not detected. "
        if "matplotlib" in source or "plt." in source:
            result["imports_matplotlib_pyplot"] = "yes"; score += 1
        else:
            result["notes"] += "matplotlib/pyplot import/use not detected. "

        names = function_names(tree)
        for fn_name in EXPECTED_FUNCTIONS:
            if fn_name in names:
                result[f"{fn_name}_exists"] = "yes"; score += 1
            else:
                result["notes"] += f"{fn_name} function not found. "
        for fn_name in EXPECTED_FUNCTIONS:
            fn_node = get_function_node(tree, fn_name)
            if fn_node is not None and not is_placeholder_function(fn_node):
                result[f"{fn_name}_not_placeholder"] = "yes"; score += 1
            elif fn_node is not None:
                result["notes"] += f"{fn_name} still looks like placeholder code. "

        load_node = get_function_node(tree, "load_data")
        if load_node is not None:
            if contains_call_to(load_node, "read_csv"):
                result["load_data_uses_read_csv"] = "yes"; score += 1
            else:
                result["notes"] += "load_data does not clearly call pandas read_csv. "
        fit_node = get_function_node(tree, "fit_line")
        if fit_node is not None:
            if contains_call_to(fit_node, "polyfit") or contains_call_to(fit_node, "lstsq") or contains_call_to(fit_node, "LinearRegression"):
                result["fit_line_uses_polyfit_or_linear_algebra"] = "yes"; score += 1
            else:
                result["notes"] += "fit_line does not clearly use polyfit, lstsq, or a linear regression helper. "
        predict_node = get_function_node(tree, "predict")
        if predict_node is not None:
            if contains_operator(predict_node, ast.Mult) and contains_operator(predict_node, ast.Add):
                result["predict_formula_structure_detected"] = "yes"; score += 1
            else:
                result["notes"] += "predict does not clearly compute slope*x + intercept. "
        main_node = get_function_node(tree, "main")
        if main_node is not None:
            if contains_call_to(main_node, "scatter") or contains_call_to(main_node, "plot"):
                result["main_uses_scatter_or_plot"] = "yes"; score += 1
            else:
                result["notes"] += "main does not clearly call scatter or plot. "

        namespace, loaded_tree, load_note = safe_load_functions(py_path)
        if namespace is not None:
            behavior = test_function_behavior(namespace, py_path)
            for key, value in behavior.items():
                if key in result:
                    result[key] = value
            result["notes"] += behavior.get("behavior_notes", "")
            for key in [
                "load_data_returns_dataframe", "load_data_correct_shape_columns",
                "fit_line_returns_pair", "fit_line_correct_slope", "fit_line_correct_intercept",
                "predict_scalar_correct", "predict_array_correct",
            ]:
                if result[key] == "yes":
                    score += 1
            main_result = run_main_and_check(namespace, py_path, username)
            for key, value in main_result.items():
                if key in result:
                    result[key] = value
            result["notes"] += main_result.get("main_notes", "")
            for key in [
                "main_runs_safely", "main_loads_data", "main_fits_line", "main_predicts_values",
                "main_creates_matplotlib_figure", "main_has_scatter_points", "main_has_fit_line",
                "main_has_axis_labels", "main_has_title_or_legend", "main_saves_or_shows_plot",
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
        result["notes"] += "regression_analysis.py did not run successfully from terminal. "

    if lab_path:
        commits, commit_note = count_commits_touching_path(repo_dir, lab_path)
        result["commits_touching_lab"] = "" if commits is None else str(commits)
        result["recent_lab_commits"] = get_recent_lab_commits(repo_dir, lab_path).replace("\n", " | ")[:900]
        if commits is not None:
            if commits >= 2:
                result["meaningful_lab_commit_evidence"] = "yes"; score += 1
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
    fieldnames = list(empty_result({"name": "", "github_username": "", "repo_url": "", "type": "student"}, DEFAULT_LAB_PATH).keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade CPSC 250L Lab 14 student forks.")
    parser.add_argument("--students", required=True, help="Path to students.csv")
    parser.add_argument("--workdir", default="student_repos", help="Folder where repos are cloned")
    parser.add_argument("--report", default="reports/lab14_report.csv", help="Output CSV report path")
    parser.add_argument("--lab-path", default=DEFAULT_LAB_PATH, help="Repo-relative path used for lab-specific Git commit checks")
    args = parser.parse_args()

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
        if result.get("program_output"):
            preview = result["program_output"].replace("\n", " | ")[:160]
            print(f"  output preview: {preview}")
        results.append(result)

    write_report(report_path, results)
    print(f"\nWrote report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
