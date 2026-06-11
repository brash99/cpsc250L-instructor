#!/usr/bin/env python3
"""
grade_lab06.py

Automated Lab 6 checker for CPSC 250L student forks.

Lab 6: Collections of Objects
Default folder: labs/lab06_collections_of_objects

This version is intentionally flexible about implementation style. In particular,
it accepts:
  - StudentRecord.add_score(score) called one score at a time
  - StudentRecord.add_score([score1, score2, score3]) called with a list
  - find_highest_average_student() returning a StudentRecord object
  - find_highest_average_student() returning a (name, average) tuple

Run:

python grade_lab06.py \
  --students students.csv \
  --workdir student_repos \
  --report reports/lab06_report.csv \
  --exclude-test \
  --lab-path labs/lab06_collections_of_objects
"""

from __future__ import annotations

import argparse
import ast
import csv
import importlib.util
import math
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


EXPECTED_RECORDS = [
    {"student_id": "A001", "name": "Alice Johnson", "scores": [85, 90, 88], "average": 87.6666666667, "grade": "A"},
    {"student_id": "B002", "name": "Ben Carter", "scores": [72, 78, 80], "average": 76.6666666667, "grade": "C"},
    {"student_id": "C003", "name": "Carlos Rivera", "scores": [91, 95, 94], "average": 93.3333333333, "grade": "A"},
    {"student_id": "D004", "name": "Dana Lee", "scores": [88, None, 92], "average": 90.0, "grade": "A"},
    {"student_id": "E005", "name": "Eli Morgan", "scores": [70, None, 75], "average": 72.5, "grade": "C"},
    {"student_id": "F006", "name": "Fatima Ahmed", "scores": [84, 82, 86], "average": 84.0, "grade": "B"},
    {"student_id": "G007", "name": "Grace Kim", "scores": [None, 89, 91], "average": 90.0, "grade": "A"},
    {"student_id": "H008", "name": "Henry Smith", "scores": [65, 70, 60], "average": 65.0, "grade": "D"},
    {"student_id": "I009", "name": "Isabella Brown", "scores": [92, 88, 90], "average": 90.0, "grade": "A"},
    {"student_id": "J010", "name": "Jackson Davis", "scores": [55, None, None], "average": 55.0, "grade": "F"},
]

EXPECTED_CLASS_AVERAGE = sum(r["average"] for r in EXPECTED_RECORDS) / len(EXPECTED_RECORDS)
EXPECTED_HIGHEST_NAME = "Carlos Rivera"
EXPECTED_HIGHEST_AVERAGE = 93.3333333333
EXPECTED_LOWEST_NAME = "Jackson Davis"
EXPECTED_LOWEST_AVERAGE = 55.0

EXPECTED_STUDENT_RECORD_METHODS = [
    "__init__",
    "add_score",
    "calculate_average",
    "highest_score",
    "lowest_score",
    "letter_grade",
    "__str__",
]

# calculate_average() in class_report.py is allowed but not required.
EXPECTED_CLASS_REPORT_FUNCTIONS = [
    "clean_score",
    "read_student_records",
    "class_average",
    "find_highest_average_student",
    "find_lowest_average_student",
    "print_class_report",
    "main",
]

CSV_TEXT = """student_id,name,quiz1,quiz2,quiz3
A001,Alice Johnson,85,90,88
B002,Ben Carter,72,78,80
C003,Carlos Rivera,91,95,94
D004,Dana Lee,88,,92
E005,Eli Morgan,70,invalid,75
F006,Fatima Ahmed,84,82,86
G007,Grace Kim,absent,89,91
H008,Henry Smith,65,70,60
I009,Isabella Brown,92,88,90
J010,Jackson Davis,55,,invalid
"""


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

    filtered.sort(key=lambda p: ("lab06" not in str(p).lower() and "lab6" not in str(p).lower(), len(p.parts)))
    return filtered[0]


def parse_python(py_path: Path) -> Tuple[Optional[ast.Module], str]:
    try:
        return ast.parse(py_path.read_text(encoding="utf-8")), "ok"
    except Exception as exc:
        return None, str(exc)


def get_function_names(tree: ast.Module) -> List[str]:
    return [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]


def get_class_method_names(tree: ast.Module, class_name: str) -> Tuple[bool, List[str]]:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return True, [item.name for item in node.body if isinstance(item, ast.FunctionDef)]
    return False, []


def import_student_record(record_path: Path) -> Tuple[Optional[Any], str]:
    try:
        module_name = f"student_record_{abs(hash(str(record_path)))}"
        spec = importlib.util.spec_from_file_location(module_name, record_path)
        if spec is None or spec.loader is None:
            return None, "Could not create import spec."
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, "ok"
    except Exception as exc:
        return None, f"Import student_record.py failed: {exc}"


def load_class_report_without_running_main(class_report_path: Path, record_path: Path) -> Tuple[Optional[Any], str]:
    tree, parse_note = parse_python(class_report_path)
    if tree is None:
        return None, f"Parse failed: {parse_note}"

    allowed_nodes = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
    safe_tree = ast.Module(body=allowed_nodes, type_ignores=[])
    ast.fix_missing_locations(safe_tree)

    module = types.ModuleType("student_class_report")
    module.__file__ = str(class_report_path)

    old_path = list(sys.path)
    old_student_record = sys.modules.get("student_record")

    try:
        sys.path.insert(0, str(class_report_path.parent))
        record_module, record_note = import_student_record(record_path)
        if record_module is None:
            return None, record_note
        sys.modules["student_record"] = record_module

        code = compile(safe_tree, filename=str(class_report_path), mode="exec")
        exec(code, module.__dict__)
        return module, "ok"
    except Exception as exc:
        return None, f"Function-only load failed: {exc}"
    finally:
        sys.path = old_path
        if old_student_record is not None:
            sys.modules["student_record"] = old_student_record
        elif "student_record" in sys.modules:
            del sys.modules["student_record"]


def make_test_csv() -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="lab06_grader_"))
    path = temp_dir / "student_scores.csv"
    path.write_text(CSV_TEXT, encoding="utf-8")
    return path


def close_enough(actual: float, expected: float, tol: float = 1e-6) -> bool:
    try:
        return math.isclose(float(actual), float(expected), rel_tol=tol, abs_tol=tol)
    except Exception:
        return False


def normalize_scores(scores: Any) -> List[Optional[int]]:
    normalized = []
    for score in scores:
        if score is None:
            normalized.append(None)
        else:
            normalized.append(int(score))
    return normalized


def get_student_id(record: Any) -> Any:
    if hasattr(record, "student_id"):
        return getattr(record, "student_id")
    if hasattr(record, "id"):
        return getattr(record, "id")
    return None


def construct_student_record(StudentRecord: Any, name: str, student_id: str, scores: Optional[List[Any]] = None) -> Tuple[Optional[Any], str]:
    """
    Construct a StudentRecord flexibly.

    The starter/solution used StudentRecord(name, student_id), but several
    reasonable student solutions use StudentRecord(name, student_id, scores)
    because read_student_records() builds the score list before constructing
    the object. Accept both forms.
    """
    if scores is None:
        scores = []

    attempts = [
        (name, student_id),
        (name, student_id, list(scores)),
    ]

    notes = []
    for args in attempts:
        try:
            return StudentRecord(*args), "ok"
        except Exception as exc:
            notes.append(f"StudentRecord{args!r} raised {exc}")

    return None, "; ".join(notes)


def average_from_record_or_report(student: Any, report_module: Optional[Any] = None) -> Optional[float]:
    """Return a student average, allowing class_report.calculate_average as fallback."""
    try:
        return float(student.calculate_average())
    except Exception:
        pass

    if report_module is not None and hasattr(report_module, "calculate_average"):
        try:
            return float(report_module.calculate_average(getattr(student, "scores", [])))
        except Exception:
            pass

    return None


def grade_from_average(avg: Optional[float]) -> Optional[str]:
    if avg is None:
        return None
    if avg >= 87:
        return "A"
    if avg >= 77:
        return "B"
    if avg >= 67:
        return "C"
    if avg >= 57:
        return "D"
    return "F"


def populate_scores(student: Any, scores: List[Any]) -> bool:
    """
    Accept either add_score(list_of_scores) or repeated add_score(single_score).
    """
    try:
        student.add_score(scores)
        if normalize_scores(getattr(student, "scores", [])) == normalize_scores(scores):
            return True
    except Exception:
        pass

    try:
        if hasattr(student, "scores"):
            student.scores = []
        for score in scores:
            student.add_score(score)
        return normalize_scores(getattr(student, "scores", [])) == normalize_scores(scores)
    except Exception:
        return False


def unpack_student_or_tuple(value: Any, report_module: Optional[Any] = None) -> Tuple[Optional[str], Optional[float]]:
    """
    Accept either a StudentRecord-like object or a (name, average) tuple/list.
    For StudentRecord-like objects, allow class_report.calculate_average(scores)
    as a fallback when the StudentRecord method does not handle None values.
    """
    if value is None:
        return None, None

    if isinstance(value, (tuple, list)) and len(value) >= 2:
        try:
            return str(value[0]), float(value[1])
        except Exception:
            return str(value[0]), None

    name = getattr(value, "name", None)
    avg = average_from_record_or_report(value, report_module)
    return name, avg


def test_student_record_class(record_module: Any) -> Dict[str, str]:
    result = {
        "student_record_class_behavior_correct": "no",
        "constructor_correct": "no",
        "add_score_behavior_correct": "no",
        "student_average_correct": "no",
        "highest_lowest_correct": "no",
        "letter_grade_correct": "no",
        "student_str_readable": "no",
        "student_record_notes": "",
    }

    if not hasattr(record_module, "StudentRecord"):
        result["student_record_notes"] += "StudentRecord class not found. "
        return result

    StudentRecord = record_module.StudentRecord

    student, construct_note = construct_student_record(StudentRecord, "Alice Johnson", "A001")
    if student is None:
        result["student_record_notes"] += f"Constructor raised: {construct_note}. "
        return result

    if getattr(student, "name", None) == "Alice Johnson" and get_student_id(student) == "A001":
        result["constructor_correct"] = "yes"
    else:
        result["student_record_notes"] += "Constructor did not store expected name/student_id. "

    if populate_scores(student, [85, 90, 88]):
        result["add_score_behavior_correct"] = "yes"
    else:
        result["student_record_notes"] += f"Could not populate scores correctly; scores={getattr(student, 'scores', None)!r}. "

    try:
        if close_enough(student.calculate_average(), 87.6666666667):
            result["student_average_correct"] = "yes"
        else:
            result["student_record_notes"] += f"Student average expected 87.6667, got {student.calculate_average()!r}. "
    except Exception as exc:
        result["student_record_notes"] += f"calculate_average raised: {exc}. "

    try:
        if student.highest_score() == 90 and student.lowest_score() == 85:
            result["highest_lowest_correct"] = "yes"
        else:
            result["student_record_notes"] += (
                f"Highest/lowest expected 90/85, got {student.highest_score()!r}/{student.lowest_score()!r}. "
            )
    except Exception as exc:
        result["student_record_notes"] += f"highest_score/lowest_score raised: {exc}. "

    try:
        grade_cases = [
            ([87], "A"),
            ([86.99], "B"),
            ([77], "B"),
            ([76.99], "C"),
            ([67], "C"),
            ([66.99], "D"),
            ([57], "D"),
            ([56.99], "F"),
        ]
        grade_ok = True
        for scores, expected_grade in grade_cases:
            grade_student, construct_note = construct_student_record(StudentRecord, "Grade Tester", "G000")
            if grade_student is None:
                grade_ok = False
                result["student_record_notes"] += f"Could not construct grade tester: {construct_note}. "
                continue
            if not populate_scores(grade_student, scores):
                grade_ok = False
                result["student_record_notes"] += f"Could not populate grade test scores {scores}. "
                continue
            actual_grade = grade_student.letter_grade()
            if actual_grade != expected_grade:
                grade_ok = False
                result["student_record_notes"] += (
                    f"letter_grade for {scores[0]} expected {expected_grade}, got {actual_grade!r}. "
                )
        if grade_ok:
            result["letter_grade_correct"] = "yes"
    except Exception as exc:
        result["student_record_notes"] += f"letter_grade tests raised: {exc}. "

    try:
        text = str(student)
        lowered = text.lower()
        if "alice" in lowered and "a001" in lowered and "85" in text and "90" in text and "dummy string" not in lowered:
            result["student_str_readable"] = "yes"
        else:
            result["student_record_notes"] += f"__str__ output not sufficiently readable: {text!r}. "
    except Exception as exc:
        result["student_record_notes"] += f"__str__ raised: {exc}. "

    keys = [
        "constructor_correct",
        "add_score_behavior_correct",
        "student_average_correct",
        "highest_lowest_correct",
        "letter_grade_correct",
        "student_str_readable",
    ]
    if all(result[key] == "yes" for key in keys):
        result["student_record_class_behavior_correct"] = "yes"

    return result


def test_class_report_functions(report_module: Any) -> Dict[str, str]:
    result = {
        "clean_score_correct": "no",
        "read_student_records_correct": "no",
        "header_skipped": "no",
        "student_objects_created": "no",
        "ids_names_stored_correctly": "no",
        "scores_cleaned_correctly": "no",
        "student_averages_correct": "no",
        "student_letter_grades_correct": "no",
        "class_average_correct": "no",
        "highest_average_student_correct": "no",
        "lowest_average_student_correct": "no",
        "class_report_notes": "",
    }

    try:
        clean_cases = {
            "85": 85,
            " 92 ": 92,
            "": None,
            "   ": None,
            "invalid": None,
            "absent": None,
        }
        clean_ok = True
        for raw, expected in clean_cases.items():
            actual = report_module.clean_score(raw)
            if actual != expected:
                clean_ok = False
                result["class_report_notes"] += f"clean_score({raw!r}) expected {expected}, got {actual}. "
        if clean_ok:
            result["clean_score_correct"] = "yes"
    except Exception as exc:
        result["class_report_notes"] += f"clean_score tests raised: {exc}. "

    csv_path = make_test_csv()

    try:
        students = report_module.read_student_records(csv_path)
    except Exception as exc:
        result["class_report_notes"] += f"read_student_records raised: {exc}. "
        return result

    if not isinstance(students, list):
        result["class_report_notes"] += f"read_student_records returned {type(students).__name__}, not list. "
        return result

    if len(students) == len(EXPECTED_RECORDS):
        result["header_skipped"] = "yes"
    else:
        result["class_report_notes"] += f"Expected {len(EXPECTED_RECORDS)} students, got {len(students)}. "

    if all(hasattr(student, "calculate_average") for student in students):
        result["student_objects_created"] = "yes"
    else:
        result["class_report_notes"] += "List does not appear to contain StudentRecord-like objects. "

    try:
        ids_names = [(get_student_id(student), getattr(student, "name", None)) for student in students]
        expected_ids_names = [(record["student_id"], record["name"]) for record in EXPECTED_RECORDS]
        if ids_names == expected_ids_names:
            result["ids_names_stored_correctly"] = "yes"
        else:
            result["class_report_notes"] += f"IDs/names incorrect: {ids_names}. "
    except Exception as exc:
        result["class_report_notes"] += f"Could not inspect IDs/names: {exc}. "

    try:
        scores_ok = True
        averages_ok = True
        grades_ok = True

        for student, expected in zip(students, EXPECTED_RECORDS):
            scores = normalize_scores(getattr(student, "scores", []))
            if scores != expected["scores"]:
                scores_ok = False
                result["class_report_notes"] += f"{expected['name']} scores expected {expected['scores']}, got {scores}. "

            actual_average = average_from_record_or_report(student, report_module)
            if actual_average is None or not close_enough(actual_average, expected["average"]):
                averages_ok = False
                result["class_report_notes"] += f"{expected['name']} average expected {expected['average']:.6f}, got {actual_average}. "

            try:
                actual_grade = student.letter_grade()
            except Exception:
                actual_grade = grade_from_average(actual_average)
            if actual_grade != expected["grade"]:
                grades_ok = False
                result["class_report_notes"] += f"{expected['name']} grade expected {expected['grade']}, got {actual_grade!r}. "

        if scores_ok:
            result["scores_cleaned_correctly"] = "yes"
        if averages_ok:
            result["student_averages_correct"] = "yes"
        if grades_ok:
            result["student_letter_grades_correct"] = "yes"
    except Exception as exc:
        result["class_report_notes"] += f"Could not inspect student records: {exc}. "

    if (
        result["header_skipped"] == "yes"
        and result["student_objects_created"] == "yes"
        and result["ids_names_stored_correctly"] == "yes"
        and result["scores_cleaned_correctly"] == "yes"
        and result["student_averages_correct"] == "yes"
    ):
        result["read_student_records_correct"] = "yes"

    try:
        class_avg = report_module.class_average(students)
        if close_enough(class_avg, EXPECTED_CLASS_AVERAGE):
            result["class_average_correct"] = "yes"
        else:
            result["class_report_notes"] += f"Class average expected {EXPECTED_CLASS_AVERAGE:.6f}, got {class_avg}. "
    except Exception as exc:
        result["class_report_notes"] += f"class_average raised: {exc}. "

    try:
        highest = report_module.find_highest_average_student(students)
        highest_name, highest_avg = unpack_student_or_tuple(highest, report_module)
        if highest_name == EXPECTED_HIGHEST_NAME and close_enough(highest_avg, EXPECTED_HIGHEST_AVERAGE):
            result["highest_average_student_correct"] = "yes"
        else:
            result["class_report_notes"] += f"Highest expected {EXPECTED_HIGHEST_NAME}/{EXPECTED_HIGHEST_AVERAGE:.2f}, got {highest_name!r}/{highest_avg!r}. "
    except Exception as exc:
        result["class_report_notes"] += f"find_highest_average_student raised: {exc}. "

    try:
        lowest = report_module.find_lowest_average_student(students)
        lowest_name, lowest_avg = unpack_student_or_tuple(lowest, report_module)
        if lowest_name == EXPECTED_LOWEST_NAME and close_enough(lowest_avg, EXPECTED_LOWEST_AVERAGE):
            result["lowest_average_student_correct"] = "yes"
        else:
            result["class_report_notes"] += f"Lowest expected {EXPECTED_LOWEST_NAME}/{EXPECTED_LOWEST_AVERAGE:.2f}, got {lowest_name!r}/{lowest_avg!r}. "
    except Exception as exc:
        result["class_report_notes"] += f"find_lowest_average_student raised: {exc}. "

    return result


def run_class_report_from_terminal(class_report_path: Path) -> Tuple[bool, str]:
    code, out, err = run_command([sys.executable, str(class_report_path.name)], cwd=class_report_path.parent, timeout=10)
    if code == 0:
        return True, out
    return False, err or out


def output_has_expected_content(output: str) -> Tuple[bool, str]:
    notes = []
    lowered = output.lower()

    for name in ["alice johnson", "carlos rivera", "jackson davis"]:
        if name not in lowered:
            notes.append(f"Missing student name: {name}")

    for clue in ["Class average: 80.42", "Highest average: Carlos Rivera with 93.33", "Lowest average: Jackson Davis with 55.00"]:
        if clue not in output:
            notes.append(f"Missing expected output clue: {clue}")

    if "dummy string" in lowered:
        notes.append("Output still contains dummy string")

    return len(notes) == 0, "; ".join(notes)


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
        "class_report_exists": "no",
        "class_report_path": "",
        "student_record_exists": "no",
        "student_record_path": "",
        "student_scores_csv_exists": "no",
        "student_scores_csv_path": "",
        "student_record_class_exists": "no",
        "student_record_methods_present": "no",
        "missing_student_record_methods": "",
        "class_report_functions_present": "no",
        "missing_class_report_functions": "",
        "constructor_correct": "no",
        "add_score_behavior_correct": "no",
        "student_average_correct": "no",
        "highest_lowest_correct": "no",
        "letter_grade_correct": "no",
        "student_str_readable": "no",
        "clean_score_correct": "no",
        "read_student_records_correct": "no",
        "header_skipped": "no",
        "student_objects_created": "no",
        "ids_names_stored_correctly": "no",
        "scores_cleaned_correctly": "no",
        "student_averages_correct": "no",
        "student_letter_grades_correct": "no",
        "class_average_correct": "no",
        "highest_average_student_correct": "no",
        "lowest_average_student_correct": "no",
        "class_report_runs_from_terminal": "no",
        "class_report_output_readable": "no",
        "class_report_output": "",
        "lab_path_checked": lab_path or "",
        "commits_touching_lab": "",
        "meaningful_lab_commit_evidence": "no",
        "recent_lab_commits": "",
        "working_tree_clean": "no",
        "recent_commits": "",
        "branch_info": "",
        "auto_score_out_of_29": "0",
        "manual_review_out_of_0": "",
        "total_score_out_of_29": "",
        "notes": "",
    }

    ok, message = clone_or_update_repo(repo_url, repo_dir)
    result["clone_or_update"] = "yes" if ok else "no"
    if not ok:
        result["notes"] = message
        return result

    class_report_path = find_file(repo_dir, "class_report.py")
    record_path = find_file(repo_dir, "student_record.py")
    csv_path = find_file(repo_dir, "student_scores.csv")

    if not class_report_path and not record_path:
        result["notes"] += "No Lab 6 files found; awarded zero for Lab 6. "
        clean, _ = is_working_tree_clean(repo_dir)
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

    score = 1

    if class_report_path:
        result["class_report_exists"] = "yes"
        result["class_report_path"] = str(class_report_path.relative_to(repo_dir))
        score += 1
    else:
        result["notes"] += "class_report.py not found. "

    if record_path:
        result["student_record_exists"] = "yes"
        result["student_record_path"] = str(record_path.relative_to(repo_dir))
        score += 1
    else:
        result["notes"] += "student_record.py not found. "

    if csv_path:
        result["student_scores_csv_exists"] = "yes"
        result["student_scores_csv_path"] = str(csv_path.relative_to(repo_dir))
        score += 1
    else:
        result["notes"] += "student_scores.csv not found. "

    if record_path:
        record_tree, parse_note = parse_python(record_path)
        if record_tree is not None:
            class_exists, methods = get_class_method_names(record_tree, "StudentRecord")
            result["student_record_class_exists"] = "yes" if class_exists else "no"
            if class_exists:
                score += 1

            missing_methods = [m for m in EXPECTED_STUDENT_RECORD_METHODS if m not in methods]
            result["missing_student_record_methods"] = ", ".join(missing_methods)
            if not missing_methods:
                result["student_record_methods_present"] = "yes"
                score += 1
        else:
            result["notes"] += f"Could not parse student_record.py: {parse_note}. "

        record_module, record_note = import_student_record(record_path)
        if record_module is not None:
            record_results = test_student_record_class(record_module)
            for key, value in record_results.items():
                if key in result:
                    result[key] = value
            result["notes"] += record_results.get("student_record_notes", "")

            for key in [
                "constructor_correct",
                "add_score_behavior_correct",
                "student_average_correct",
                "highest_lowest_correct",
                "letter_grade_correct",
                "student_str_readable",
            ]:
                if result[key] == "yes":
                    score += 1
        else:
            result["notes"] += record_note + " "

    if class_report_path:
        report_tree, parse_note = parse_python(class_report_path)
        if report_tree is not None:
            functions = get_function_names(report_tree)
            missing_functions = [fn for fn in EXPECTED_CLASS_REPORT_FUNCTIONS if fn not in functions]
            result["missing_class_report_functions"] = ", ".join(missing_functions)
            if not missing_functions:
                result["class_report_functions_present"] = "yes"
                score += 1
        else:
            result["notes"] += f"Could not parse class_report.py: {parse_note}. "

    if class_report_path and record_path:
        report_module, report_note = load_class_report_without_running_main(class_report_path, record_path)
        if report_module is not None:
            report_results = test_class_report_functions(report_module)
            for key, value in report_results.items():
                if key in result:
                    result[key] = value
            result["notes"] += report_results.get("class_report_notes", "")

            for key in [
                "clean_score_correct",
                "read_student_records_correct",
                "header_skipped",
                "student_objects_created",
                "ids_names_stored_correctly",
                "scores_cleaned_correctly",
                "student_averages_correct",
                "student_letter_grades_correct",
                "class_average_correct",
                "highest_average_student_correct",
                "lowest_average_student_correct",
            ]:
                if result[key] == "yes":
                    score += 1
        else:
            result["notes"] += report_note + " "

    if class_report_path:
        run_ok, output = run_class_report_from_terminal(class_report_path)
        result["class_report_runs_from_terminal"] = "yes" if run_ok else "no"
        result["class_report_output"] = output[:1200]
        if run_ok:
            score += 1
            readable, output_note = output_has_expected_content(output)
            if readable:
                result["class_report_output_readable"] = "yes"
                score += 1
            else:
                result["notes"] += f"Output check: {output_note}. "
        else:
            result["notes"] += "class_report.py did not run successfully from terminal. "

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
    result["auto_score_out_of_29"] = str(score)
    return result


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
        "class_report_exists",
        "class_report_path",
        "student_record_exists",
        "student_record_path",
        "student_scores_csv_exists",
        "student_scores_csv_path",
        "student_record_class_exists",
        "student_record_methods_present",
        "missing_student_record_methods",
        "class_report_functions_present",
        "missing_class_report_functions",
        "constructor_correct",
        "add_score_behavior_correct",
        "student_average_correct",
        "highest_lowest_correct",
        "letter_grade_correct",
        "student_str_readable",
        "clean_score_correct",
        "read_student_records_correct",
        "header_skipped",
        "student_objects_created",
        "ids_names_stored_correctly",
        "scores_cleaned_correctly",
        "student_averages_correct",
        "student_letter_grades_correct",
        "class_average_correct",
        "highest_average_student_correct",
        "lowest_average_student_correct",
        "class_report_runs_from_terminal",
        "class_report_output_readable",
        "class_report_output",
        "lab_path_checked",
        "commits_touching_lab",
        "meaningful_lab_commit_evidence",
        "recent_lab_commits",
        "working_tree_clean",
        "recent_commits",
        "branch_info",
        "auto_score_out_of_29",
        "manual_review_out_of_0",
        "total_score_out_of_29",
        "notes",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade CPSC 250L Lab 6 student forks.")
    parser.add_argument("--students", required=True, help="Path to students.csv")
    parser.add_argument("--workdir", default="student_repos", help="Folder where repos are cloned")
    parser.add_argument("--report", default="reports/lab06_report.csv", help="Output CSV report path")
    parser.add_argument(
        "--lab-path",
        default="labs/lab06_collections_of_objects",
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
