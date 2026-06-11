#!/usr/bin/env python3
"""
grade_lab07.py

Automated Lab 7 checker for CPSC 250L student forks.

Lab 7: Operator Overloading and Object Comparisons
Default folder: labs/lab07_operator_overloading_comparisons

This grader follows the same report-oriented style as the Lab 6 grader:
  - reads a students.csv roster
  - clones or updates each student repo
  - finds the expected Lab 7 files
  - checks TimeDuration structure and behavior
  - runs race_results.py from the terminal
  - checks lab-specific commit evidence and clean working tree status
  - writes a detailed CSV report

The main program race_results.py is assumed to be provided to students. Their main
job is to complete the TimeDuration class in time_duration.py.

Run:

python grade_lab07.py \
  --students students.csv \
  --workdir student_repos \
  --report reports/lab07_report.csv \
  --exclude-test \
  --lab-path labs/lab07_operator_overloading_comparisons
"""

from __future__ import annotations

import argparse
import ast
import csv
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


EXPECTED_TIME_DURATION_METHODS = [
    "__init__",
    "total_seconds",
    "__str__",
    "__eq__",
    "__lt__",
    "__add__",
]

EXPECTED_RACE_OUTPUT_CLUES = [
    "Original race times:",
    "0h 42m 15s",
    "0h 39m 58s",
    "0h 44m 03s",
    "0h 41m 20s",
    "Sorted race times:",
    "Fastest time: 0h 39m 58s",
    "Slowest time: 0h 44m 03s",
    "Equality test:",
    "0h 39m 58s == 0h 39m 58s ? True",
    "Addition test:",
    "Total time for all runners: 3h 27m 34s",
]


# -----------------------------------------------------------------------------
# Basic command / Git helpers
# -----------------------------------------------------------------------------


def run_command(command: List[str], cwd: Optional[Path] = None, timeout: int = 20) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(command, cwd=cwd, timeout=timeout, text=True, capture_output=True)
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

    filtered.sort(key=lambda p: ("lab07" not in str(p).lower() and "lab7" not in str(p).lower(), len(p.parts)))
    return filtered[0]




def find_lab7_file_pair(repo_dir: Path, lab_path: Optional[str] = None) -> Tuple[Optional[Path], Optional[Path], str]:
    """Find the TimeDuration/race_results pair to grade.

    Some student repos can contain more than one copy of time_duration.py, for
    example an old starter/template copy plus the real submitted copy.  The
    earlier grader selected files independently with rglob(), which could pair a
    stale template time_duration.py with the correct race_results.py and produce
    an artificially low score.

    Selection priority:
      1. directories under --lab-path containing both required files
      2. any directory whose path contains lab07/lab7 and contains both files
      3. any directory containing both files
      4. fallback to the old individual find_file behavior
    """
    excluded_parts = {".git", ".venv", "venv", "__pycache__"}

    def usable(path: Path) -> bool:
        return not any(part in excluded_parts for part in path.parts)

    time_files = [p for p in repo_dir.rglob("time_duration.py") if usable(p)]
    race_files = [p for p in repo_dir.rglob("race_results.py") if usable(p)]

    by_dir = {}
    for p in time_files:
        by_dir.setdefault(p.parent, {})["time"] = p
    for p in race_files:
        by_dir.setdefault(p.parent, {})["race"] = p

    paired_dirs = [d for d, files in by_dir.items() if "time" in files and "race" in files]

    def rel_str(path: Path) -> str:
        try:
            return str(path.relative_to(repo_dir))
        except ValueError:
            return str(path)

    def score_dir(path: Path) -> Tuple[int, int, str]:
        rel = rel_str(path).lower()
        supplied = lab_path.lower().rstrip("/") if lab_path else ""

        # Lower tuple is better.
        if supplied and (rel == supplied or rel.startswith(supplied + "/")):
            primary = 0
        elif "lab07" in rel or "lab7" in rel:
            primary = 1
        else:
            primary = 2

        # Avoid obvious template/starter/archive folders when another paired
        # folder exists, but do not make this an absolute exclusion because some
        # labs may legitimately call the working folder starter_code.
        penalty = 0
        for token in ["template", "templates", "starter", "starter_code", "old", "archive", "solution"]:
            if token in rel:
                penalty += 1

        return (primary, penalty, rel)

    if paired_dirs:
        paired_dirs.sort(key=score_dir)
        chosen = paired_dirs[0]
        return by_dir[chosen]["time"], by_dir[chosen]["race"], f"paired files selected from {rel_str(chosen)}"

    time_path = find_file(repo_dir, "time_duration.py")
    race_path = find_file(repo_dir, "race_results.py")
    return time_path, race_path, "fallback independent file search used"

def infer_lab_path_from_found_files(repo_dir: Path, *paths: Optional[Path]) -> Optional[str]:
    """Infer the lab folder from discovered Lab 7 files.

    This protects the Git-evidence check from a stale or accidentally copied
    --lab-path value. For example, if the files are found in

        labs/lab07_operator_overloading_comparisons/starter_code/time_duration.py

    then this returns

        labs/lab07_operator_overloading_comparisons

    rather than trusting an unrelated path such as labs/lab07_collections_of_objects.
    """
    for path in paths:
        if path is None:
            continue
        try:
            rel = path.relative_to(repo_dir)
        except ValueError:
            continue

        parts = rel.parts
        for i, part in enumerate(parts):
            lowered = part.lower()
            if lowered.startswith("lab07") or lowered.startswith("lab7"):
                return str(Path(*parts[: i + 1]))

        # Fallback for the normal labs/<lab-folder>/... layout.
        if len(parts) >= 2 and parts[0] == "labs":
            return str(Path(parts[0], parts[1]))

    return None


# -----------------------------------------------------------------------------
# Python parsing / import helpers
# -----------------------------------------------------------------------------


def parse_python(py_path: Path) -> Tuple[Optional[ast.Module], str]:
    try:
        return ast.parse(py_path.read_text(encoding="utf-8")), "ok"
    except Exception as exc:
        return None, str(exc)


def get_class_method_names(tree: ast.Module, class_name: str) -> Tuple[bool, List[str]]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return True, [item.name for item in node.body if isinstance(item, ast.FunctionDef)]
    return False, []


def import_time_duration(time_duration_path: Path) -> Tuple[Optional[Any], str]:
    try:
        module_name = f"student_time_duration_{abs(hash(str(time_duration_path)))}"
        spec = importlib.util.spec_from_file_location(module_name, time_duration_path)
        if spec is None or spec.loader is None:
            return None, "Could not create import spec."
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, "ok"
    except Exception as exc:
        return None, f"Import time_duration.py failed: {exc}"


# -----------------------------------------------------------------------------
# TimeDuration behavior tests
# -----------------------------------------------------------------------------


def test_time_duration_class(time_module: Any) -> Dict[str, str]:
    result = {
        "time_duration_class_behavior_correct": "no",
        "constructor_stores_attributes": "no",
        "total_seconds_correct": "no",
        "str_format_correct": "no",
        "equality_correct": "no",
        "less_than_correct": "no",
        "sorting_works": "no",
        "add_returns_time_duration": "no",
        "add_normalizes_correctly": "no",
        "add_chain_sum_correct": "no",
        "comparisons_use_total_duration": "no",
        "original_objects_unchanged_by_add": "no",
        "time_duration_notes": "",
    }

    if not hasattr(time_module, "TimeDuration"):
        result["time_duration_notes"] += "TimeDuration class not found. "
        return result

    TimeDuration = time_module.TimeDuration

    try:
        duration = TimeDuration(1, 5, 9)
    except Exception as exc:
        result["time_duration_notes"] += f"Constructor raised: {exc}. "
        return result

    try:
        if (
            getattr(duration, "hours", None) == 1
            and getattr(duration, "minutes", None) == 5
            and getattr(duration, "seconds", None) == 9
        ):
            result["constructor_stores_attributes"] = "yes"
        else:
            result["time_duration_notes"] += (
                "Constructor did not store hours/minutes/seconds as expected; "
                f"got {getattr(duration, 'hours', None)!r}/"
                f"{getattr(duration, 'minutes', None)!r}/"
                f"{getattr(duration, 'seconds', None)!r}. "
            )
    except Exception as exc:
        result["time_duration_notes"] += f"Could not inspect constructor attributes: {exc}. "

    try:
        cases = [
            (TimeDuration(0, 0, 0), 0),
            (TimeDuration(0, 1, 1), 61),
            (TimeDuration(1, 2, 3), 3723),
            (TimeDuration(2, 0, 15), 7215),
        ]
        total_ok = all(obj.total_seconds() == expected for obj, expected in cases)
        if total_ok:
            result["total_seconds_correct"] = "yes"
        else:
            details = [(obj.hours, obj.minutes, obj.seconds, obj.total_seconds(), expected) for obj, expected in cases]
            result["time_duration_notes"] += f"total_seconds incorrect for one or more cases: {details}. "
    except Exception as exc:
        result["time_duration_notes"] += f"total_seconds tests raised: {exc}. "

    try:
        str_cases = [
            (TimeDuration(1, 5, 9), "1h 05m 09s"),
            (TimeDuration(0, 39, 58), "0h 39m 58s"),
            (TimeDuration(3, 0, 4), "3h 00m 04s"),
        ]
        str_ok = True
        for obj, expected in str_cases:
            actual = str(obj)
            if actual != expected:
                str_ok = False
                result["time_duration_notes"] += f"str({obj.hours},{obj.minutes},{obj.seconds}) expected {expected!r}, got {actual!r}. "
        if str_ok:
            result["str_format_correct"] = "yes"
    except Exception as exc:
        result["time_duration_notes"] += f"__str__ tests raised: {exc}. "

    try:
        equality_cases = [
            (TimeDuration(0, 39, 58), TimeDuration(0, 39, 58), True),
            (TimeDuration(1, 0, 0), TimeDuration(0, 60, 0), True),
            (TimeDuration(0, 59, 59), TimeDuration(1, 0, 0), False),
        ]
        equality_ok = True
        for left, right, expected in equality_cases:
            actual = (left == right)
            if actual != expected:
                equality_ok = False
                result["time_duration_notes"] += f"Equality expected {expected} for {left!s} and {right!s}, got {actual}. "
        if equality_ok:
            result["equality_correct"] = "yes"
    except Exception as exc:
        result["time_duration_notes"] += f"__eq__ tests raised: {exc}. "

    try:
        less_cases = [
            (TimeDuration(0, 39, 58), TimeDuration(0, 41, 20), True),
            (TimeDuration(0, 41, 20), TimeDuration(0, 39, 58), False),
            (TimeDuration(1, 0, 0), TimeDuration(0, 60, 0), False),
        ]
        less_ok = True
        for left, right, expected in less_cases:
            actual = (left < right)
            if actual != expected:
                less_ok = False
                result["time_duration_notes"] += f"Less-than expected {expected} for {left!s} < {right!s}, got {actual}. "
        if less_ok:
            result["less_than_correct"] = "yes"
    except Exception as exc:
        result["time_duration_notes"] += f"__lt__ tests raised: {exc}. "

    try:
        times = [
            TimeDuration(0, 42, 15),
            TimeDuration(0, 39, 58),
            TimeDuration(0, 44, 3),
            TimeDuration(0, 41, 20),
            TimeDuration(0, 39, 58),
        ]
        sorted_times = sorted(times)
        actual_seconds = [obj.total_seconds() for obj in sorted_times]
        expected_seconds = [2398, 2398, 2480, 2535, 2643]
        if actual_seconds == expected_seconds:
            result["sorting_works"] = "yes"
        else:
            result["time_duration_notes"] += f"Sorting expected seconds {expected_seconds}, got {actual_seconds}. "
    except Exception as exc:
        result["time_duration_notes"] += f"Sorting test raised: {exc}. "

    try:
        a = TimeDuration(1, 20, 50)
        b = TimeDuration(0, 45, 30)
        summed = a + b
        if isinstance(summed, TimeDuration):
            result["add_returns_time_duration"] = "yes"
        else:
            result["time_duration_notes"] += f"__add__ returned {type(summed).__name__}, not TimeDuration. "

        if (
            getattr(summed, "hours", None) == 2
            and getattr(summed, "minutes", None) == 6
            and getattr(summed, "seconds", None) == 20
            and summed.total_seconds() == 7580
        ):
            result["add_normalizes_correctly"] = "yes"
        else:
            result["time_duration_notes"] += (
                "__add__ did not normalize 1h20m50s + 0h45m30s correctly; "
                f"got {summed!s} with attributes "
                f"{getattr(summed, 'hours', None)!r}/"
                f"{getattr(summed, 'minutes', None)!r}/"
                f"{getattr(summed, 'seconds', None)!r}. "
            )

        if (
            getattr(a, "hours", None) == 1
            and getattr(a, "minutes", None) == 20
            and getattr(a, "seconds", None) == 50
            and getattr(b, "hours", None) == 0
            and getattr(b, "minutes", None) == 45
            and getattr(b, "seconds", None) == 30
        ):
            result["original_objects_unchanged_by_add"] = "yes"
        else:
            result["time_duration_notes"] += "__add__ appears to mutate one of the original objects. "
    except Exception as exc:
        result["time_duration_notes"] += f"__add__ normalization tests raised: {exc}. "

    try:
        total_time = TimeDuration(0, 0, 0)
        for time in [
            TimeDuration(0, 42, 15),
            TimeDuration(0, 39, 58),
            TimeDuration(0, 44, 3),
            TimeDuration(0, 41, 20),
            TimeDuration(0, 39, 58),
        ]:
            total_time = total_time + time
        if str(total_time) == "3h 27m 34s" and total_time.total_seconds() == 12454:
            result["add_chain_sum_correct"] = "yes"
        else:
            result["time_duration_notes"] += f"Chained addition expected 3h 27m 34s, got {total_time!s}. "
    except Exception as exc:
        result["time_duration_notes"] += f"Chained addition test raised: {exc}. "

    try:
        weird = TimeDuration(0, 61, 61)
        normal = TimeDuration(1, 2, 1)
        shorter = TimeDuration(1, 2, 0)
        longer = TimeDuration(1, 2, 2)
        if weird == normal and shorter < weird and weird < longer:
            result["comparisons_use_total_duration"] = "yes"
        else:
            result["time_duration_notes"] += "Comparisons do not appear to use total duration in seconds. "
    except Exception as exc:
        result["time_duration_notes"] += f"Total-duration comparison test raised: {exc}. "

    keys = [
        "constructor_stores_attributes",
        "total_seconds_correct",
        "str_format_correct",
        "equality_correct",
        "less_than_correct",
        "sorting_works",
        "add_returns_time_duration",
        "add_normalizes_correctly",
        "add_chain_sum_correct",
        "comparisons_use_total_duration",
        "original_objects_unchanged_by_add",
    ]
    if all(result[key] == "yes" for key in keys):
        result["time_duration_class_behavior_correct"] = "yes"

    return result


# -----------------------------------------------------------------------------
# Terminal output tests
# -----------------------------------------------------------------------------


def run_race_results_from_terminal(race_results_path: Path) -> Tuple[bool, str]:
    code, out, err = run_command([sys.executable, str(race_results_path.name)], cwd=race_results_path.parent, timeout=10)
    if code == 0:
        return True, out
    return False, err or out


def output_has_expected_content(output: str) -> Tuple[bool, str]:
    notes = []

    for clue in EXPECTED_RACE_OUTPUT_CLUES:
        if clue not in output:
            notes.append(f"Missing expected output clue: {clue}")

    lowered = output.lower()
    for bad in ["dummy string", "pass", "none"]:
        if bad in lowered:
            notes.append(f"Output appears to contain placeholder text: {bad}")

    return len(notes) == 0, "; ".join(notes)


# -----------------------------------------------------------------------------
# Git metadata helpers
# -----------------------------------------------------------------------------


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


# -----------------------------------------------------------------------------
# Student grading
# -----------------------------------------------------------------------------


def grade_student(row: Dict[str, str], workdir: Path, lab_path: Optional[str]) -> Dict[str, str]:
    name = row["name"].strip()
    username = row["github_username"].strip()
    repo_url = row["repo_url"].strip()
    repo_dir = workdir / username

    result: Dict[str, str] = {
        "name": name,
        "github_username": username,
        "repo_url": repo_url,
        "type": row.get("type", "student").strip() or "student",
        "clone_or_update": "no",
        "time_duration_exists": "no",
        "time_duration_path": "",
        "race_results_exists": "no",
        "race_results_path": "",
        "time_duration_class_exists": "no",
        "time_duration_methods_present": "no",
        "missing_time_duration_methods": "",
        "constructor_stores_attributes": "no",
        "total_seconds_correct": "no",
        "str_format_correct": "no",
        "equality_correct": "no",
        "less_than_correct": "no",
        "sorting_works": "no",
        "add_returns_time_duration": "no",
        "add_normalizes_correctly": "no",
        "add_chain_sum_correct": "no",
        "comparisons_use_total_duration": "no",
        "original_objects_unchanged_by_add": "no",
        "race_results_runs_from_terminal": "no",
        "race_results_output_readable": "no",
        "race_results_output": "",
        "lab_path_checked": "",
        "commits_touching_lab": "",
        "meaningful_lab_commit_evidence": "no",
        "recent_lab_commits": "",
        "working_tree_clean": "no",
        "recent_commits": "",
        "branch_info": "",
        "auto_score_out_of_20": "0",
        "manual_review_out_of_0": "",
        "total_score_out_of_20": "",
        "notes": "",
    }

    ok, message = clone_or_update_repo(repo_url, repo_dir)
    result["clone_or_update"] = "yes" if ok else "no"
    if not ok:
        result["notes"] = message
        return result

    time_duration_path, race_results_path, file_selection_note = find_lab7_file_pair(repo_dir, lab_path)

    effective_lab_path = infer_lab_path_from_found_files(repo_dir, time_duration_path, race_results_path) or lab_path
    result["notes"] += file_selection_note + ". "
    result["lab_path_checked"] = effective_lab_path or ""

    if lab_path and effective_lab_path and lab_path != effective_lab_path:
        result["notes"] += (
            f"Using inferred lab path {effective_lab_path} for Git evidence "
            f"instead of supplied --lab-path {lab_path}. "
        )

    if not time_duration_path and not race_results_path:
        result["notes"] += "No Lab 7 files found; awarded zero for Lab 7. "
        clean, _ = is_working_tree_clean(repo_dir)
        result["working_tree_clean"] = "yes" if clean else "no"
        result["recent_commits"] = get_recent_commits(repo_dir).replace("\n", " | ")[:900]
        result["branch_info"] = get_branch_info(repo_dir).replace("\n", " | ")[:900]
        if effective_lab_path:
            commits, commit_note = count_commits_touching_path(repo_dir, effective_lab_path)
            result["commits_touching_lab"] = "" if commits is None else str(commits)
            result["recent_lab_commits"] = get_recent_lab_commits(repo_dir, effective_lab_path).replace("\n", " | ")[:900]
            if commits is None:
                result["notes"] += f"Lab commit check failed: {commit_note}. "
        return result

    # One point for having a repo that could be cloned/updated and contains some Lab 7 evidence.
    score = 1

    if time_duration_path:
        result["time_duration_exists"] = "yes"
        result["time_duration_path"] = str(time_duration_path.relative_to(repo_dir))
        score += 1
    else:
        result["notes"] += "time_duration.py not found. "

    if race_results_path:
        result["race_results_exists"] = "yes"
        result["race_results_path"] = str(race_results_path.relative_to(repo_dir))
        score += 1
    else:
        result["notes"] += "race_results.py not found. "

    if time_duration_path:
        time_tree, parse_note = parse_python(time_duration_path)
        if time_tree is not None:
            class_exists, methods = get_class_method_names(time_tree, "TimeDuration")
            result["time_duration_class_exists"] = "yes" if class_exists else "no"
            if class_exists:
                score += 1

            missing_methods = [m for m in EXPECTED_TIME_DURATION_METHODS if m not in methods]
            result["missing_time_duration_methods"] = ", ".join(missing_methods)
            if not missing_methods:
                result["time_duration_methods_present"] = "yes"
                score += 1
        else:
            result["notes"] += f"Could not parse time_duration.py: {parse_note}. "

        time_module, time_note = import_time_duration(time_duration_path)
        if time_module is not None:
            time_results = test_time_duration_class(time_module)
            for key, value in time_results.items():
                if key in result:
                    result[key] = value
            result["notes"] += time_results.get("time_duration_notes", "")

            for key in [
                "constructor_stores_attributes",
                "total_seconds_correct",
                "str_format_correct",
                "equality_correct",
                "less_than_correct",
                "sorting_works",
                "add_returns_time_duration",
                "add_normalizes_correctly",
                "add_chain_sum_correct",
                "comparisons_use_total_duration",
                "original_objects_unchanged_by_add",
            ]:
                if result[key] == "yes":
                    score += 1
        else:
            result["notes"] += time_note + " "

    if race_results_path:
        run_ok, output = run_race_results_from_terminal(race_results_path)
        result["race_results_runs_from_terminal"] = "yes" if run_ok else "no"
        result["race_results_output"] = output[:1200]
        if run_ok:
            score += 1
            readable, output_note = output_has_expected_content(output)
            if readable:
                result["race_results_output_readable"] = "yes"
                score += 1
            else:
                result["notes"] += f"Output check: {output_note}. "
        else:
            result["notes"] += "race_results.py did not run successfully from terminal. "

    if effective_lab_path:
        commits, commit_note = count_commits_touching_path(repo_dir, effective_lab_path)
        result["commits_touching_lab"] = "" if commits is None else str(commits)
        result["recent_lab_commits"] = get_recent_lab_commits(repo_dir, effective_lab_path).replace("\n", " | ")[:900]
        if commits is not None:
            if commits >= 2:
                result["meaningful_lab_commit_evidence"] = "yes"
                score += 1
            else:
                result["notes"] += f"Expected at least 2 commits touching {effective_lab_path}, got {commits}. "
        else:
            result["notes"] += f"Lab commit check failed: {commit_note}. "
    else:
        result["notes"] += "No lab path could be determined; lab-specific commit credit not awarded. "

    clean, clean_note = is_working_tree_clean(repo_dir)
    result["working_tree_clean"] = "yes" if clean else "no"
    if clean:
        score += 1
    else:
        result["notes"] += f"Working tree: {clean_note}. "

    result["recent_commits"] = get_recent_commits(repo_dir).replace("\n", " | ")[:900]
    result["branch_info"] = get_branch_info(repo_dir).replace("\n", " | ")[:900]
    result["auto_score_out_of_20"] = str(score)
    return result


# -----------------------------------------------------------------------------
# Roster / report
# -----------------------------------------------------------------------------


def read_students(path: Path, exclude_test: bool = False) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"name", "github_username", "repo_url"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"students.csv is missing required columns: {', '.join(sorted(missing))}")
        rows = list(reader)

    if exclude_test:
        rows = [row for row in rows if row.get("type", "student").strip().lower() != "test"]

    return rows


def write_report(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "name",
        "github_username",
        "repo_url",
        "type",
        "clone_or_update",
        "time_duration_exists",
        "time_duration_path",
        "race_results_exists",
        "race_results_path",
        "time_duration_class_exists",
        "time_duration_methods_present",
        "missing_time_duration_methods",
        "constructor_stores_attributes",
        "total_seconds_correct",
        "str_format_correct",
        "equality_correct",
        "less_than_correct",
        "sorting_works",
        "add_returns_time_duration",
        "add_normalizes_correctly",
        "add_chain_sum_correct",
        "comparisons_use_total_duration",
        "original_objects_unchanged_by_add",
        "race_results_runs_from_terminal",
        "race_results_output_readable",
        "race_results_output",
        "lab_path_checked",
        "commits_touching_lab",
        "meaningful_lab_commit_evidence",
        "recent_lab_commits",
        "working_tree_clean",
        "recent_commits",
        "branch_info",
        "auto_score_out_of_20",
        "manual_review_out_of_0",
        "total_score_out_of_20",
        "notes",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade CPSC 250L Lab 7 student forks.")
    parser.add_argument("--students", required=True, help="Path to students.csv")
    parser.add_argument("--workdir", default="student_repos", help="Folder where repos are cloned")
    parser.add_argument("--report", default="reports/lab07_report.csv", help="Output CSV report path")
    parser.add_argument(
        "--lab-path",
        default="labs/lab07_operator_overloading_comparisons",
        help="Repo-relative path used for lab-specific Git commit checks",
    )
    parser.add_argument("--exclude-test", action="store_true", help="Skip rows in students.csv where type is test")
    args = parser.parse_args()

    students_path = Path(args.students)
    workdir = Path(args.workdir)
    report_path = Path(args.report)

    workdir.mkdir(parents=True, exist_ok=True)

    students = read_students(students_path, exclude_test=args.exclude_test)
    results = []

    for student in students:
        print(f"Grading {student['name']}...")
        results.append(grade_student(student, workdir, args.lab_path))

    write_report(report_path, results)
    print(f"\nWrote report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
