#!/usr/bin/env python3
"""
grade_lab13.py

Automated Lab 13 checker for CPSC 250L student forks.

Lab 13: Weather Analysis
Default folder: labs/lab13_weather_analysis
Expected files: weather_analysis.py, weather_june.csv/data/weather_june.csv

Recommended use:

python grade_lab13.py \
  --students students.csv \
  --workdir student_repos \
  --report reports/lab13_report.csv \
  --lab-path labs/lab13_weather_analysis
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


EXPECTED_FILE = "weather_analysis.py"
EXPECTED_DATA_FILE = "weather_june.csv"
EXPECTED_FUNCTIONS = [
    "load_weather_data",
    "print_summary",
    "add_celsius",
    "clean_temperature_range",
    "plot_temperatures",
    "main",
]
TOTAL_POINTS = 24
SHOW_PLOTS = False
PLOT_PAUSE_SECONDS = 1.5
DEFAULT_LAB_PATH = "labs/lab13_weather_analysis"

SAMPLE_CSV = """day,high,low,precipitation
1,82,68,0.00
2,85,70,0.00
3,79,66,0.15
4,88,72,0.00
5,91,75,0.00
6,84,69,0.30
7,80,65,0.05
8,86,71,0.00
9,90,74,0.00
10,87,73,0.20
"""


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
            "lab13" not in str(p).lower() and "lab_13" not in str(p).lower(),
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
        namespace: Dict[str, Any] = {"__name__": "lab13_grader_import", "__file__": str(py_path)}
        exec(compile(module, str(py_path), "exec"), namespace)
        return namespace, tree, "ok"
    except Exception as exc:
        return None, None, f"Could not load functions safely: {exc}"


def call_function(function: Callable[..., Any], args: Tuple[Any, ...]) -> Tuple[bool, Any, str]:
    try:
        return True, function(*args), "ok"
    except Exception as exc:
        return False, None, f"Exception: {type(exc).__name__}: {exc}"


def values_close(actual: Any, expected: Any, tolerance: float = 1e-6) -> bool:
    try:
        import numpy as np
        return bool(np.allclose(actual, expected, rtol=tolerance, atol=tolerance, equal_nan=True))
    except Exception:
        try:
            return abs(actual - expected) <= tolerance
        except Exception:
            return False


def make_sample_csv(tempdir: Path) -> Path:
    csv_path = tempdir / EXPECTED_DATA_FILE
    csv_path.write_text(SAMPLE_CSV, encoding="utf-8")
    data_dir = tempdir / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / EXPECTED_DATA_FILE).write_text(SAMPLE_CSV, encoding="utf-8")
    return csv_path


def find_celsius_columns(df: Any) -> Tuple[Optional[str], Optional[str], str]:
    """Return likely high/low Celsius columns, accepting several reasonable names."""
    try:
        import numpy as np
        cols = list(df.columns)
        high_f = df["high"].astype(float)
        low_f = df["low"].astype(float)
        high_c_expected = (high_f - 32) * 5 / 9
        low_c_expected = (low_f - 32) * 5 / 9

        high_candidates: List[str] = []
        low_candidates: List[str] = []

        for col in cols:
            if col in {"day", "high", "low", "precipitation"}:
                continue
            try:
                series = df[col].astype(float)
            except Exception:
                continue
            if np.allclose(series, high_c_expected, rtol=1e-5, atol=1e-5):
                high_candidates.append(col)
            if np.allclose(series, low_c_expected, rtol=1e-5, atol=1e-5):
                low_candidates.append(col)

        high_col = high_candidates[0] if high_candidates else None
        low_col = low_candidates[0] if low_candidates else None
        note = ""
        if high_col is None:
            note += "No added column matching high temperature converted to Celsius. "
        if low_col is None:
            note += "No added column matching low temperature converted to Celsius. "
        return high_col, low_col, note
    except Exception as exc:
        return None, None, f"Could not inspect Celsius columns: {exc}. "


def test_function_behavior(namespace: Dict[str, Any], py_path: Path) -> Dict[str, str]:
    result = {
        "load_weather_data_returns_dataframe": "no",
        "load_weather_data_correct_shape_columns": "no",
        "add_celsius_returns_dataframe": "no",
        "add_celsius_adds_high_celsius": "no",
        "add_celsius_adds_low_celsius": "no",
        "clean_temperature_range_returns_dataframe": "no",
        "clean_temperature_range_correct_rows": "no",
        "print_summary_runs": "no",
        "print_summary_mentions_mean": "no",
        "print_summary_prints_numeric_mean": "no",
        "behavior_notes": "",
    }

    load_weather_data = namespace.get("load_weather_data")
    add_celsius = namespace.get("add_celsius")
    clean_temperature_range = namespace.get("clean_temperature_range")
    print_summary = namespace.get("print_summary")

    try:
        import pandas as pd
        with tempfile.TemporaryDirectory(prefix="lab13_func_") as tmp:
            tempdir = Path(tmp)
            csv_path = make_sample_csv(tempdir)

            df_loaded = None
            if callable(load_weather_data):
                ok, value, note = call_function(load_weather_data, (str(csv_path),))
                if ok:
                    df_loaded = value
                    if isinstance(value, pd.DataFrame):
                        result["load_weather_data_returns_dataframe"] = "yes"
                        expected_cols = {"day", "high", "low", "precipitation"}
                        if expected_cols.issubset(set(value.columns)) and len(value) == 10:
                            result["load_weather_data_correct_shape_columns"] = "yes"
                        else:
                            result["behavior_notes"] += f"load_weather_data columns/rows unexpected: columns={list(value.columns)!r}, rows={len(value)}. "
                    else:
                        result["behavior_notes"] += f"load_weather_data returned {type(value).__name__}, not DataFrame. "
                else:
                    result["behavior_notes"] += f"load_weather_data failed: {note}. "
            else:
                result["behavior_notes"] += "load_weather_data is not callable. "

            if df_loaded is None:
                df_loaded = pd.read_csv(csv_path)

            df_c = None
            high_c_col = low_c_col = None
            if callable(add_celsius):
                ok, value, note = call_function(add_celsius, (df_loaded.copy(),))
                if ok:
                    df_c = value
                    if isinstance(value, pd.DataFrame):
                        result["add_celsius_returns_dataframe"] = "yes"
                        high_c_col, low_c_col, col_note = find_celsius_columns(value)
                        result["behavior_notes"] += col_note
                        if high_c_col is not None:
                            result["add_celsius_adds_high_celsius"] = "yes"
                        if low_c_col is not None:
                            result["add_celsius_adds_low_celsius"] = "yes"
                    else:
                        result["behavior_notes"] += f"add_celsius returned {type(value).__name__}, not DataFrame. "
                else:
                    result["behavior_notes"] += f"add_celsius failed: {note}. "
            else:
                result["behavior_notes"] += "add_celsius is not callable. "

            if df_c is None:
                df_c = df_loaded.copy()
                df_c["high_celsius"] = (df_c["high"] - 32) * 5 / 9
                df_c["low_celsius"] = (df_c["low"] - 32) * 5 / 9
                high_c_col = "high_celsius"
                low_c_col = "low_celsius"

            if callable(clean_temperature_range):
                ok, value, note = call_function(clean_temperature_range, (df_c.copy(), 19.0, 31.0))
                if ok:
                    if isinstance(value, pd.DataFrame):
                        result["clean_temperature_range_returns_dataframe"] = "yes"
                        days = list(value["day"].astype(int)) if "day" in value.columns else []
                        expected_days = [1, 2, 6, 8, 10]
                        if days == expected_days:
                            result["clean_temperature_range_correct_rows"] = "yes"
                        else:
                            result["behavior_notes"] += f"clean_temperature_range kept days {days!r}; expected {expected_days!r}. "
                    else:
                        result["behavior_notes"] += f"clean_temperature_range returned {type(value).__name__}, not DataFrame. "
                else:
                    result["behavior_notes"] += f"clean_temperature_range failed: {note}. "
            else:
                result["behavior_notes"] += "clean_temperature_range is not callable. "

            if callable(print_summary):
                stdout = io.StringIO()
                stderr = io.StringIO()
                try:
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        out_value = print_summary(df_c.copy())
                    result["print_summary_runs"] = "yes"
                    printed = stdout.getvalue().lower()
                    if "mean" in printed or "average" in printed or "describe" in printed:
                        result["print_summary_mentions_mean"] = "yes"
                    # A mean high temperature in the sample is 85.2 F; mean low is 70.3 F.
                    # Celsius versions are about 29.6 and 21.3.  Accept any sensible printed mean.
                    numeric_targets = [85.2, 70.3, 29.5556, 21.2778]
                    if any(f"{target:.1f}" in printed or f"{target:.2f}" in printed for target in numeric_targets):
                        result["print_summary_prints_numeric_mean"] = "yes"
                    else:
                        # Also accept Pandas describe/table output if it includes decimal numeric stats.
                        import re
                        numbers = [float(x) for x in re.findall(r"[-+]?\d+\.\d+", printed)]
                        if any(any(abs(num - target) < 0.15 for target in numeric_targets) for num in numbers):
                            result["print_summary_prints_numeric_mean"] = "yes"
                        else:
                            result["behavior_notes"] += "print_summary did not clearly print a relevant numeric mean. "
                except Exception as exc:
                    result["behavior_notes"] += f"print_summary raised {type(exc).__name__}: {exc}. "
            else:
                result["behavior_notes"] += "print_summary is not callable. "
    except Exception as exc:
        result["behavior_notes"] += f"Function behavior tests failed unexpectedly: {type(exc).__name__}: {exc}. "

    return result


def run_plot_function(namespace: Dict[str, Any], py_path: Path, student_slug: str) -> Dict[str, str]:
    result = {
        "plot_temperatures_runs": "no",
        "plot_creates_matplotlib_figure": "no",
        "plot_has_high_series": "no",
        "plot_has_low_series": "no",
        "plot_has_axis_labels": "no",
        "plot_has_title_or_legend": "no",
        "plot_saves_or_shows": "no",
        "plot_notes": "",
    }

    plot_fn = namespace.get("plot_temperatures")
    if not callable(plot_fn):
        result["plot_notes"] = "plot_temperatures is not callable."
        return result

    try:
        import pandas as pd
        import matplotlib
        if not SHOW_PLOTS:
            matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        plt.close("all")
        show_called = {"value": False}
        original_show = plt.show
        def fake_show(*args: Any, **kwargs: Any) -> None:
            show_called["value"] = True
        plt.show = fake_show

        with tempfile.TemporaryDirectory(prefix=f"lab13_plot_{student_slug}_") as tmp:
            tempdir = Path(tmp)
            csv_path = make_sample_csv(tempdir)
            df = pd.read_csv(csv_path)
            df["high_celsius"] = (df["high"] - 32) * 5 / 9
            df["low_celsius"] = (df["low"] - 32) * 5 / 9

            old_cwd = Path.cwd()
            os.chdir(tempdir)
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    plot_fn(df)
                result["plot_temperatures_runs"] = "yes"
            finally:
                os.chdir(old_cwd)

            figs = [plt.figure(num) for num in plt.get_fignums()]
            axes = [ax for fig in figs for ax in fig.axes]
            saved = [p.name for p in tempdir.iterdir() if p.suffix.lower() in {".png", ".pdf", ".jpg", ".jpeg", ".svg"}]
            if show_called["value"] or saved:
                result["plot_saves_or_shows"] = "yes"

            if axes:
                result["plot_creates_matplotlib_figure"] = "yes"
                line_count = sum(len(ax.lines) for ax in axes)
                all_label_text = " ".join(
                    [ax.get_xlabel().lower() + " " + ax.get_ylabel().lower() + " " + ax.get_title().lower() for ax in axes]
                    + [
                        text.get_text().lower()
                        for ax in axes
                        if ax.get_legend() is not None
                        for text in ax.get_legend().get_texts()
                    ]
                )
                if line_count >= 2 or "high" in all_label_text:
                    result["plot_has_high_series"] = "yes"
                if line_count >= 2 or "low" in all_label_text:
                    result["plot_has_low_series"] = "yes"
                if any(ax.get_xlabel().strip() for ax in axes) and any(ax.get_ylabel().strip() for ax in axes):
                    result["plot_has_axis_labels"] = "yes"
                if any(ax.get_title().strip() for ax in axes) or any(ax.get_legend() is not None for ax in axes):
                    result["plot_has_title_or_legend"] = "yes"
            else:
                result["plot_notes"] += "plot_temperatures did not leave an inspectable matplotlib figure. "

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
        result["plot_notes"] += f"plot_temperatures test raised: {type(exc).__name__}: {exc}. "

    return result


def run_main_and_check(namespace: Dict[str, Any], py_path: Path, student_slug: str) -> Dict[str, str]:
    result = {
        "main_runs_safely": "no",
        "main_loads_data": "no",
        "main_adds_celsius": "no",
        "main_cleans_data": "no",
        "main_prints_summary": "no",
        "main_creates_matplotlib_figure": "no",
        "main_notes": "",
    }

    main_fn = namespace.get("main")
    if not callable(main_fn):
        result["main_notes"] = "main is not callable."
        return result

    old_cwd = Path.cwd()
    tempdir = Path(tempfile.mkdtemp(prefix=f"lab13_main_{student_slug}_"))

    try:
        import matplotlib
        if not SHOW_PLOTS:
            matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        plt.close("all")
        original_show = plt.show
        plt.show = lambda *a, **k: None

        # Support either ../data/weather_june.csv from a scripts folder or data/weather_june.csv.
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

        out = stdout.getvalue().lower()
        if "mean" in out or "average" in out or "describe" in out:
            result["main_prints_summary"] = "yes"
        figs = [plt.figure(num) for num in plt.get_fignums()]
        axes = [ax for fig in figs for ax in fig.axes]
        if axes:
            result["main_creates_matplotlib_figure"] = "yes"

        # Static evidence from the main body is more reliable than monkeypatching student globals.
        tree, _ = parse_python(py_path)
        main_node = get_function_node(tree, "main") if tree is not None else None
        if main_node is not None:
            if contains_call_to(main_node, "load_weather_data"):
                result["main_loads_data"] = "yes"
            if contains_call_to(main_node, "add_celsius"):
                result["main_adds_celsius"] = "yes"
            if contains_call_to(main_node, "clean_temperature_range"):
                result["main_cleans_data"] = "yes"

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
        result["main_notes"] += f"main test raised: {type(exc).__name__}: {exc}. "
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(tempdir, ignore_errors=True)

    return result


def run_program(py_path: Path) -> Tuple[bool, str]:
    env = dict(os.environ)
    env["MPLBACKEND"] = "Agg"
    with tempfile.TemporaryDirectory(prefix="lab13_run_") as tmp:
        tempdir = Path(tmp)
        temp_path = tempdir / EXPECTED_FILE
        shutil.copy2(py_path, temp_path)
        make_sample_csv(tempdir)
        parent_data = tempdir.parent / "data"
        parent_data.mkdir(exist_ok=True)
        (parent_data / EXPECTED_DATA_FILE).write_text(SAMPLE_CSV, encoding="utf-8")
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
        "weather_analysis_exists": "no",
        "weather_analysis_path": "",
        "weather_june_csv_found": "no",
        "weather_june_csv_path": "",
        "parses": "no",
        "imports_pandas": "no",
        "imports_matplotlib_pyplot": "no",
        "load_weather_data_exists": "no",
        "print_summary_exists": "no",
        "add_celsius_exists": "no",
        "clean_temperature_range_exists": "no",
        "plot_temperatures_exists": "no",
        "main_exists": "no",
        "load_weather_data_not_placeholder": "no",
        "print_summary_not_placeholder": "no",
        "add_celsius_not_placeholder": "no",
        "clean_temperature_range_not_placeholder": "no",
        "plot_temperatures_not_placeholder": "no",
        "main_not_placeholder": "no",
        "load_weather_data_uses_read_csv": "no",
        "add_celsius_formula_structure_detected": "no",
        "clean_temperature_range_filter_structure_detected": "no",
        "plot_temperatures_uses_plot": "no",
        "load_weather_data_returns_dataframe": "no",
        "load_weather_data_correct_shape_columns": "no",
        "add_celsius_returns_dataframe": "no",
        "add_celsius_adds_high_celsius": "no",
        "add_celsius_adds_low_celsius": "no",
        "clean_temperature_range_returns_dataframe": "no",
        "clean_temperature_range_correct_rows": "no",
        "print_summary_runs": "no",
        "print_summary_mentions_mean": "no",
        "print_summary_prints_numeric_mean": "no",
        "plot_temperatures_runs": "no",
        "plot_creates_matplotlib_figure": "no",
        "plot_has_high_series": "no",
        "plot_has_low_series": "no",
        "plot_has_axis_labels": "no",
        "plot_has_title_or_legend": "no",
        "plot_saves_or_shows": "no",
        "main_runs_safely": "no",
        "main_loads_data": "no",
        "main_adds_celsius": "no",
        "main_cleans_data": "no",
        "main_prints_summary": "no",
        "main_creates_matplotlib_figure": "no",
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
        result["weather_june_csv_found"] = "yes"
        result["weather_june_csv_path"] = str(data_path.relative_to(repo_dir))
        score += 1
    else:
        result["notes"] += "weather_june.csv not found in repo; grader used built-in sample data for runtime tests. "

    if not py_path:
        result["notes"] += "weather_analysis.py not found; awarded zero for Lab 13 file/function/plot work. "
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

    result["weather_analysis_exists"] = "yes"
    result["weather_analysis_path"] = str(py_path.relative_to(repo_dir))
    score += 1

    tree, parse_note = parse_python(py_path)
    namespace: Optional[Dict[str, Any]] = None

    if tree is None:
        result["notes"] += f"Could not parse weather_analysis.py: {parse_note}. "
    else:
        result["parses"] = "yes"
        score += 1

        source = py_path.read_text(encoding="utf-8", errors="replace")
        if "pandas" in source or "pd." in source:
            result["imports_pandas"] = "yes"
            score += 1
        else:
            result["notes"] += "pandas import/use not detected. "
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

        load_node = get_function_node(tree, "load_weather_data")
        if load_node is not None:
            if contains_call_to(load_node, "read_csv"):
                result["load_weather_data_uses_read_csv"] = "yes"
                score += 1
            else:
                result["notes"] += "load_weather_data does not clearly call pandas read_csv. "

        add_node = get_function_node(tree, "add_celsius")
        if add_node is not None:
            formula_evidence = (
                (contains_name(add_node, "df") or contains_name(add_node, "dataframe"))
                and contains_operator(add_node, ast.Sub)
                and contains_operator(add_node, ast.Mult)
                and contains_operator(add_node, ast.Div)
                and contains_numeric_constant(add_node, 32)
                and contains_numeric_constant(add_node, 5)
                and contains_numeric_constant(add_node, 9)
            )
            if formula_evidence:
                result["add_celsius_formula_structure_detected"] = "yes"
                score += 1
            else:
                result["notes"] += "Celsius conversion formula structure was not clearly detected. "

        clean_node = get_function_node(tree, "clean_temperature_range")
        if clean_node is not None:
            filter_evidence = (
                (contains_name(clean_node, "t_low_cut") or contains_name(clean_node, "T_low_cut"))
                and (contains_name(clean_node, "t_high_cut") or contains_name(clean_node, "T_high_cut"))
                and (contains_operator(clean_node, ast.GtE) or contains_operator(clean_node, ast.Gt))
                and (contains_operator(clean_node, ast.LtE) or contains_operator(clean_node, ast.Lt))
            )
            if filter_evidence:
                result["clean_temperature_range_filter_structure_detected"] = "yes"
                score += 1
            else:
                result["notes"] += "Temperature range filtering structure was not clearly detected. "

        plot_node = get_function_node(tree, "plot_temperatures")
        if plot_node is not None:
            if contains_call_to(plot_node, "plot") or contains_call_to(plot_node, "subplots"):
                result["plot_temperatures_uses_plot"] = "yes"
                score += 1
            else:
                result["notes"] += "plot_temperatures does not clearly make a matplotlib plot. "

        namespace, loaded_tree, load_note = safe_load_functions(py_path)
        if namespace is not None:
            behavior = test_function_behavior(namespace, py_path)
            for key, value in behavior.items():
                if key in result:
                    result[key] = value
            result["notes"] += behavior.get("behavior_notes", "")

            for key in [
                "load_weather_data_returns_dataframe",
                "load_weather_data_correct_shape_columns",
                "add_celsius_returns_dataframe",
                "add_celsius_adds_high_celsius",
                "add_celsius_adds_low_celsius",
                "clean_temperature_range_returns_dataframe",
                "clean_temperature_range_correct_rows",
                "print_summary_runs",
                "print_summary_mentions_mean",
                "print_summary_prints_numeric_mean",
            ]:
                if result[key] == "yes":
                    score += 1

            plot_result = run_plot_function(namespace, py_path, username)
            for key, value in plot_result.items():
                if key in result:
                    result[key] = value
            result["notes"] += plot_result.get("plot_notes", "")
            for key in [
                "plot_temperatures_runs",
                "plot_creates_matplotlib_figure",
                "plot_has_high_series",
                "plot_has_low_series",
                "plot_has_axis_labels",
                "plot_has_title_or_legend",
                "plot_saves_or_shows",
            ]:
                if result[key] == "yes":
                    score += 1

            main_result = run_main_and_check(namespace, py_path, username)
            for key, value in main_result.items():
                if key in result:
                    result[key] = value
            result["notes"] += main_result.get("main_notes", "")
            for key in [
                "main_runs_safely",
                "main_loads_data",
                "main_adds_celsius",
                "main_cleans_data",
                "main_prints_summary",
                "main_creates_matplotlib_figure",
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
        result["notes"] += "weather_analysis.py did not run successfully from terminal. "

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
    fieldnames = list(empty_result({"name": "", "github_username": "", "repo_url": "", "type": "student"}, DEFAULT_LAB_PATH).keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade CPSC 250L Lab 13 student forks.")
    parser.add_argument("--students", required=True, help="Path to students.csv")
    parser.add_argument("--workdir", default="student_repos", help="Folder where repos are cloned")
    parser.add_argument("--report", default="reports/lab13_report.csv", help="Output CSV report path")
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
        if result.get("program_output"):
            preview = result["program_output"].replace("\n", " | ")[:160]
            print(f"  output preview: {preview}")
        results.append(result)

    write_report(report_path, results)
    print(f"\nWrote report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
