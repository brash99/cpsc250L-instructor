#!/usr/bin/env python3
"""
grade_lab09.py

Automated Lab 9 checker for CPSC 250L student forks.

Lab 9: Inheritance and Polymorphism
Default folder: labs/lab09_garden_inventory

This grader checks the automatable parts of the garden inventory lab:

  - repository can be cloned/updated
  - plant.py exists
  - garden_inventory.py exists
  - Plant, Flower, and Vegetable classes exist
  - Flower and Vegetable inherit from Plant
  - required methods exist
  - constructors store expected attributes
  - care_instructions() behaves polymorphically
  - __str__() returns readable object summaries
  - a mixed list of Plant/Flower/Vegetable objects can be processed polymorphically
  - garden_inventory.py runs from the terminal
  - output looks readable and includes the expected plants
  - Git commits touching --lab-path are counted
  - working tree is clean

Expected students.csv format:

name,github_username,repo_url,type
Edward Test,edwardbrash,https://github.com/edwardbrash/cpsc250L.git,test
Alice Smith,asmith,https://github.com/asmith/cpsc250L.git,student

Recommended use:

python grade_lab09.py \
  --students students.csv \
  --workdir student_repos \
  --report reports/lab09_report.csv \
  --lab-path labs/lab09_garden_inventory

Adjust --lab-path if the actual folder name differs.
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


EXPECTED_CLASSES = ["Plant", "Flower", "Vegetable"]
EXPECTED_METHODS = ["__init__", "care_instructions", "__str__"]


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
            "lab09" not in str(p).lower() and "lab9" not in str(p).lower(),
            len(p.parts),
        )
    )
    return filtered[0]


def parse_python(py_path: Path) -> Tuple[Optional[ast.Module], str]:
    try:
        return ast.parse(py_path.read_text(encoding="utf-8")), "ok"
    except Exception as exc:
        return None, str(exc)


def class_info(tree: ast.Module) -> Dict[str, Dict[str, Any]]:
    info: Dict[str, Dict[str, Any]] = {}

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(base.id)
                elif isinstance(base, ast.Attribute):
                    bases.append(base.attr)

            methods = [
                item.name for item in node.body
                if isinstance(item, ast.FunctionDef)
            ]

            info[node.name] = {
                "bases": bases,
                "methods": methods,
            }

    return info


def import_plant_module(plant_path: Path) -> Tuple[Optional[Any], str]:
    try:
        module_name = f"plant_{abs(hash(str(plant_path)))}"
        spec = importlib.util.spec_from_file_location(module_name, plant_path)
        if spec is None or spec.loader is None:
            return None, "Could not create import spec."

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module, "ok"
    except Exception as exc:
        return None, f"Import plant.py failed: {exc}"


def get_attr(obj: Any, *names: str) -> Any:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def text_contains_all(text: str, required: List[str]) -> bool:
    lowered = text.lower()
    return all(item.lower() in lowered for item in required)


def text_contains_any(text: str, options: List[str]) -> bool:
    lowered = text.lower()
    return any(item.lower() in lowered for item in options)


def test_plant_classes(module: Any) -> Dict[str, str]:
    result = {
        "constructors_store_attributes": "no",
        "flower_inherits_plant": "no",
        "vegetable_inherits_plant": "no",
        "plant_care_instructions_readable": "no",
        "flower_care_instructions_readable": "no",
        "vegetable_care_instructions_readable": "no",
        "plant_str_readable": "no",
        "flower_str_readable": "no",
        "vegetable_str_readable": "no",
        "polymorphic_list_behavior": "no",
        "class_behavior_notes": "",
    }

    try:
        Plant = module.Plant
        Flower = module.Flower
        Vegetable = module.Vegetable
    except Exception as exc:
        result["class_behavior_notes"] += f"Could not access Plant/Flower/Vegetable: {exc}. "
        return result

    try:
        if issubclass(Flower, Plant):
            result["flower_inherits_plant"] = "yes"
        else:
            result["class_behavior_notes"] += "Flower does not inherit from Plant. "
    except Exception as exc:
        result["class_behavior_notes"] += f"Could not test Flower inheritance: {exc}. "

    try:
        if issubclass(Vegetable, Plant):
            result["vegetable_inherits_plant"] = "yes"
        else:
            result["class_behavior_notes"] += "Vegetable does not inherit from Plant. "
    except Exception as exc:
        result["class_behavior_notes"] += f"Could not test Vegetable inheritance: {exc}. "

    try:
        fern = Plant("Fern", 35)
        rose = Flower("Rose", 45, "red")
        tomato = Vegetable("Tomato", 80, 70)
    except Exception as exc:
        result["class_behavior_notes"] += f"Constructor test raised: {exc}. "
        return result

    try:
        attr_checks = [
            get_attr(fern, "name") == "Fern",
            get_attr(fern, "height_cm", "height") == 35,
            get_attr(rose, "name") == "Rose",
            get_attr(rose, "height_cm", "height") == 45,
            get_attr(rose, "color", "flower_color") == "red",
            get_attr(tomato, "name") == "Tomato",
            get_attr(tomato, "height_cm", "height") == 80,
            get_attr(tomato, "harvest_days", "days_to_harvest") == 70,
        ]

        if all(attr_checks):
            result["constructors_store_attributes"] = "yes"
        else:
            result["class_behavior_notes"] += (
                "One or more constructors did not store expected attributes. "
            )
    except Exception as exc:
        result["class_behavior_notes"] += f"Attribute check raised: {exc}. "

    try:
        plant_care = str(fern.care_instructions())
        if (
            plant_care.strip()
            and "pass" not in plant_care.lower()
            and "none" not in plant_care.lower()
            and text_contains_any(plant_care, ["water", "sun", "light", "soil", "care"])
        ):
            result["plant_care_instructions_readable"] = "yes"
        else:
            result["class_behavior_notes"] += f"Plant care instructions look weak: {plant_care!r}. "
    except Exception as exc:
        result["class_behavior_notes"] += f"Plant care_instructions raised: {exc}. "

    try:
        flower_care = str(rose.care_instructions())
        if (
            flower_care.strip()
            and "pass" not in flower_care.lower()
            and "none" not in flower_care.lower()
            and text_contains_any(flower_care, ["flower", "bloom", "color", "red", "sun", "water"])
        ):
            result["flower_care_instructions_readable"] = "yes"
        else:
            result["class_behavior_notes"] += f"Flower care instructions look weak: {flower_care!r}. "
    except Exception as exc:
        result["class_behavior_notes"] += f"Flower care_instructions raised: {exc}. "

    try:
        vegetable_care = str(tomato.care_instructions())
        if (
            vegetable_care.strip()
            and "pass" not in vegetable_care.lower()
            and "none" not in vegetable_care.lower()
            and text_contains_any(vegetable_care, ["harvest", "vegetable", "tomato", "70", "water", "days"])
        ):
            result["vegetable_care_instructions_readable"] = "yes"
        else:
            result["class_behavior_notes"] += f"Vegetable care instructions look weak: {vegetable_care!r}. "
    except Exception as exc:
        result["class_behavior_notes"] += f"Vegetable care_instructions raised: {exc}. "

    try:
        plant_text = str(fern)
        if (
            text_contains_all(plant_text, ["Fern"])
            and "35" in plant_text
            and "dummy string" not in plant_text.lower()
            and "pass" not in plant_text.lower()
        ):
            result["plant_str_readable"] = "yes"
        else:
            result["class_behavior_notes"] += f"Plant __str__ output not readable enough: {plant_text!r}. "
    except Exception as exc:
        result["class_behavior_notes"] += f"Plant __str__ raised: {exc}. "

    try:
        flower_text = str(rose)
        if (
            text_contains_all(flower_text, ["Rose", "red"])
            and "45" in flower_text
            and "dummy string" not in flower_text.lower()
            and "pass" not in flower_text.lower()
        ):
            result["flower_str_readable"] = "yes"
        else:
            result["class_behavior_notes"] += f"Flower __str__ output not readable enough: {flower_text!r}. "
    except Exception as exc:
        result["class_behavior_notes"] += f"Flower __str__ raised: {exc}. "

    try:
        vegetable_text = str(tomato)
        if (
            text_contains_all(vegetable_text, ["Tomato"])
            and "80" in vegetable_text
            and "70" in vegetable_text
            and "dummy string" not in vegetable_text.lower()
            and "pass" not in vegetable_text.lower()
        ):
            result["vegetable_str_readable"] = "yes"
        else:
            result["class_behavior_notes"] += f"Vegetable __str__ output not readable enough: {vegetable_text!r}. "
    except Exception as exc:
        result["class_behavior_notes"] += f"Vegetable __str__ raised: {exc}. "

    try:
        plants = [
            Plant("Fern", 35),
            Flower("Rose", 45, "red"),
            Flower("Marigold", 25, "orange"),
            Vegetable("Tomato", 80, 70),
            Vegetable("Lettuce", 20, 45),
        ]

        summaries = [str(plant) for plant in plants]
        cares = [str(plant.care_instructions()) for plant in plants]

        names_ok = all(
            any(name in summary for summary in summaries)
            for name in ["Fern", "Rose", "Marigold", "Tomato", "Lettuce"]
        )

        distinct_care_ok = len(set(cares)) >= 3

        if names_ok and distinct_care_ok:
            result["polymorphic_list_behavior"] = "yes"
        else:
            result["class_behavior_notes"] += (
                "Mixed plant list did not produce expected names or distinct polymorphic care outputs. "
            )
    except Exception as exc:
        result["class_behavior_notes"] += f"Polymorphic list test raised: {exc}. "

    return result


def run_garden_inventory(garden_path: Path) -> Tuple[bool, str]:
    code, out, err = run_command(
        [sys.executable, str(garden_path.name)],
        cwd=garden_path.parent,
        timeout=10,
    )

    if code == 0:
        return True, out

    return False, err or out


def output_has_expected_content(output: str) -> Tuple[bool, str]:
    notes = []
    lowered = output.lower()

    if "garden inventory" not in lowered:
        notes.append("Missing title 'Garden Inventory'")

    for name in ["fern", "rose", "marigold", "tomato", "lettuce"]:
        if name not in lowered:
            notes.append(f"Missing plant name: {name}")

    if lowered.count("care") < 5:
        notes.append("Expected at least five care instruction lines")

    for clue in ["red", "orange", "70", "45"]:
        if clue not in lowered:
            notes.append(f"Missing detail clue: {clue}")

    if "none" in lowered or "dummy string" in lowered:
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
        "plant_exists": "no",
        "plant_path": "",
        "garden_inventory_exists": "no",
        "garden_inventory_path": "",
        "plant_class_exists": "no",
        "flower_class_exists": "no",
        "vegetable_class_exists": "no",
        "plant_methods_present": "no",
        "flower_methods_present": "no",
        "vegetable_methods_present": "no",
        "missing_plant_methods": "",
        "missing_flower_methods": "",
        "missing_vegetable_methods": "",
        "flower_inherits_plant": "no",
        "vegetable_inherits_plant": "no",
        "constructors_store_attributes": "no",
        "plant_care_instructions_readable": "no",
        "flower_care_instructions_readable": "no",
        "vegetable_care_instructions_readable": "no",
        "plant_str_readable": "no",
        "flower_str_readable": "no",
        "vegetable_str_readable": "no",
        "polymorphic_list_behavior": "no",
        "garden_inventory_runs_from_terminal": "no",
        "garden_inventory_output_readable": "no",
        "garden_inventory_output": "",
        "lab_path_checked": lab_path or "",
        "commits_touching_lab": "",
        "meaningful_lab_commit_evidence": "no",
        "recent_lab_commits": "",
        "working_tree_clean": "no",
        "recent_commits": "",
        "branch_info": "",
        "auto_score_out_of_23": "0",
        "manual_review_out_of_0": "",
        "total_score_out_of_23": "",
        "notes": "",
    }

    ok, message = clone_or_update_repo(repo_url, repo_dir)
    result["clone_or_update"] = "yes" if ok else "no"

    if not ok:
        result["notes"] = message
        return result

    plant_path = find_file(repo_dir, "plant.py")
    garden_path = find_file(repo_dir, "garden_inventory.py")

    if not plant_path and not garden_path:
        result["notes"] += "No Lab 9 files found; awarded zero for Lab 9. "
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

    score = 1  # clone/update

    if plant_path:
        result["plant_exists"] = "yes"
        result["plant_path"] = str(plant_path.relative_to(repo_dir))
        score += 1
    else:
        result["notes"] += "plant.py not found. "

    if garden_path:
        result["garden_inventory_exists"] = "yes"
        result["garden_inventory_path"] = str(garden_path.relative_to(repo_dir))
        score += 1
    else:
        result["notes"] += "garden_inventory.py not found. "

    if plant_path:
        tree, parse_note = parse_python(plant_path)

        if tree is None:
            result["notes"] += f"Could not parse plant.py: {parse_note}. "
        else:
            info = class_info(tree)

            for class_name in EXPECTED_CLASSES:
                class_exists_col = f"{class_name.lower()}_class_exists"
                if class_name in info:
                    result[class_exists_col] = "yes"
                    score += 1
                else:
                    result["notes"] += f"{class_name} class not found. "

            for class_name in EXPECTED_CLASSES:
                if class_name in info:
                    missing = [
                        method for method in EXPECTED_METHODS
                        if method not in info[class_name]["methods"]
                    ]

                    missing_col = f"missing_{class_name.lower()}_methods"
                    present_col = f"{class_name.lower()}_methods_present"

                    result[missing_col] = ", ".join(missing)

                    if not missing:
                        result[present_col] = "yes"
                        score += 1

        module, import_note = import_plant_module(plant_path)
        if module is not None:
            behavior_results = test_plant_classes(module)

            for key, value in behavior_results.items():
                if key in result:
                    result[key] = value

            result["notes"] += behavior_results.get("class_behavior_notes", "")

            for key in [
                "flower_inherits_plant",
                "vegetable_inherits_plant",
                "constructors_store_attributes",
                "plant_care_instructions_readable",
                "flower_care_instructions_readable",
                "vegetable_care_instructions_readable",
                "plant_str_readable",
                "flower_str_readable",
                "vegetable_str_readable",
                "polymorphic_list_behavior",
            ]:
                if result[key] == "yes":
                    score += 1
        else:
            result["notes"] += import_note + " "

    if garden_path:
        run_ok, output = run_garden_inventory(garden_path)
        result["garden_inventory_runs_from_terminal"] = "yes" if run_ok else "no"
        result["garden_inventory_output"] = output[:1200]

        if run_ok:
            score += 1
            readable, output_note = output_has_expected_content(output)
            if readable:
                result["garden_inventory_output_readable"] = "yes"
                score += 1
            else:
                result["notes"] += f"Output check: {output_note}. "
        else:
            result["notes"] += "garden_inventory.py did not run successfully from terminal. "

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
    result["auto_score_out_of_23"] = str(score)

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
        "plant_exists",
        "plant_path",
        "garden_inventory_exists",
        "garden_inventory_path",
        "plant_class_exists",
        "flower_class_exists",
        "vegetable_class_exists",
        "plant_methods_present",
        "flower_methods_present",
        "vegetable_methods_present",
        "missing_plant_methods",
        "missing_flower_methods",
        "missing_vegetable_methods",
        "flower_inherits_plant",
        "vegetable_inherits_plant",
        "constructors_store_attributes",
        "plant_care_instructions_readable",
        "flower_care_instructions_readable",
        "vegetable_care_instructions_readable",
        "plant_str_readable",
        "flower_str_readable",
        "vegetable_str_readable",
        "polymorphic_list_behavior",
        "garden_inventory_runs_from_terminal",
        "garden_inventory_output_readable",
        "garden_inventory_output",
        "lab_path_checked",
        "commits_touching_lab",
        "meaningful_lab_commit_evidence",
        "recent_lab_commits",
        "working_tree_clean",
        "recent_commits",
        "branch_info",
        "auto_score_out_of_23",
        "manual_review_out_of_0",
        "total_score_out_of_23",
        "notes",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade CPSC 250L Lab 9 student forks.")

    parser.add_argument("--students", required=True, help="Path to students.csv")
    parser.add_argument("--workdir", default="student_repos", help="Folder where repos are cloned")
    parser.add_argument("--report", default="reports/lab09_report.csv", help="Output CSV report path")

    parser.add_argument(
        "--lab-path",
        default="labs/lab09_garden_inventory",
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
