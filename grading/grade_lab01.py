#!/usr/bin/env python3
"""
grade_lab01_v2.py

Automated Lab 1 checker for CPSC 250L student forks.

Version 2 changes:
  - If --starter-commit is supplied, commit scoring uses commits after that hash.
  - If --starter-commit is not supplied, the script uses a practical fallback:
      any successful git log with at least one recent commit counts as commit evidence.
    This is appropriate for Lab 1 when you have already verified that students pushed.
  - The report now separates automated evidence from manual/live checkoff.

Suggested use:

python grade_lab01_v2.py \
  --students students.csv \
  --workdir student_repos \
  --report reports/lab01_report.csv \
  --starter-commit 02462a8

If you do not know the starter commit:

python grade_lab01_v2.py \
  --students students.csv \
  --workdir student_repos \
  --report reports/lab01_report.csv
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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


def find_helloworld(repo_dir: Path) -> Optional[Path]:
    candidates = list(repo_dir.rglob("helloworld.py"))
    filtered = [
        p for p in candidates
        if ".git" not in p.parts
        and ".venv" not in p.parts
        and "venv" not in p.parts
        and "__pycache__" not in p.parts
    ]

    if not filtered:
        return None

    filtered.sort(key=lambda p: ("lab1" not in str(p).lower(), len(p.parts)))
    return filtered[0]


def count_commits_since_starter(repo_dir: Path, starter_commit: Optional[str]) -> Tuple[Optional[int], str]:
    if not starter_commit:
        return None, "starter commit not provided"

    code, out, err = run_command(
        ["git", "rev-list", "--count", f"{starter_commit}..HEAD"],
        cwd=repo_dir,
    )

    if code != 0:
        return None, err or out

    try:
        return int(out), "ok"
    except ValueError:
        return None, f"could not parse commit count: {out}"


def get_recent_commits(repo_dir: Path, n: int = 5) -> Tuple[bool, str]:
    code, out, err = run_command(
        ["git", "log", "--oneline", f"-{n}"],
        cwd=repo_dir,
    )
    if code != 0:
        return False, err or out
    return True, out


def is_working_tree_clean(repo_dir: Path) -> Tuple[bool, str]:
    code, out, err = run_command(["git", "status", "--porcelain"], cwd=repo_dir)
    if code != 0:
        return False, err or out

    if out.strip() == "":
        return True, "clean"

    return False, out.replace("\n", " | ")


def run_helloworld(helloworld_path: Path) -> Tuple[bool, str]:
    code, out, err = run_command(
        [sys.executable, str(helloworld_path.name)],
        cwd=helloworld_path.parent,
        timeout=10,
    )

    if code == 0:
        return True, out

    return False, err or out


def grade_student(row: Dict[str, str], workdir: Path, starter_commit: Optional[str]) -> Dict[str, str]:
    name = row["name"].strip()
    username = row["github_username"].strip()
    repo_url = row["repo_url"].strip()

    repo_dir = workdir / username

    result: Dict[str, str] = {
        "name": name,
        "github_username": username,
        "repo_url": repo_url,
        "clone_or_update": "no",
        "helloworld_exists": "no",
        "helloworld_path": "",
        "helloworld_runs": "no",
        "helloworld_output": "",
        "commits_since_starter": "",
        "has_commit_evidence": "no",
        "commit_check_method": "",
        "working_tree_clean": "no",
        "recent_commits": "",
        "auto_score_out_of_8": "0",
        "manual_live_question_out_of_2": "",
        "total_score_out_of_10": "",
        "notes": "",
    }

    ok, message = clone_or_update_repo(repo_url, repo_dir)
    result["clone_or_update"] = "yes" if ok else "no"
    if not ok:
        result["notes"] = message
        return result

    score = 1

    helloworld = find_helloworld(repo_dir)
    if helloworld is not None:
        result["helloworld_exists"] = "yes"
        result["helloworld_path"] = str(helloworld.relative_to(repo_dir))
        score += 2

        runs, output = run_helloworld(helloworld)
        result["helloworld_runs"] = "yes" if runs else "no"
        result["helloworld_output"] = output[:500]
        if runs:
            score += 2

    commits_since, commit_note = count_commits_since_starter(repo_dir, starter_commit)
    log_ok, recent_log = get_recent_commits(repo_dir)
    result["recent_commits"] = recent_log.replace("\n", " | ")[:500]

    if starter_commit:
        result["commit_check_method"] = f"commits after starter commit {starter_commit}"
        if commits_since is not None:
            result["commits_since_starter"] = str(commits_since)
            if commits_since > 0:
                result["has_commit_evidence"] = "yes"
                score += 2
            else:
                result["notes"] += "No commits found after starter commit. "
        else:
            result["notes"] += f"Commit check failed: {commit_note}. "
    else:
        result["commit_check_method"] = "fallback: git log exists"
        if log_ok and recent_log.strip():
            result["has_commit_evidence"] = "yes"
            score += 2
            result["notes"] += "Starter commit not provided; awarded commit evidence from git log fallback. "
        else:
            result["notes"] += "Starter commit not provided and git log could not be read. "

    clean, clean_note = is_working_tree_clean(repo_dir)
    result["working_tree_clean"] = "yes" if clean else "no"
    if clean:
        score += 1
    else:
        result["notes"] += f"Working tree: {clean_note}. "

    result["auto_score_out_of_8"] = str(score)
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
        "clone_or_update",
        "helloworld_exists",
        "helloworld_path",
        "helloworld_runs",
        "helloworld_output",
        "commits_since_starter",
        "has_commit_evidence",
        "commit_check_method",
        "working_tree_clean",
        "recent_commits",
        "auto_score_out_of_8",
        "manual_live_question_out_of_2",
        "total_score_out_of_10",
        "notes",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade CPSC 250L Lab 1 student forks.")
    parser.add_argument("--students", required=True, help="Path to students.csv")
    parser.add_argument("--workdir", default="student_repos", help="Folder where repos are cloned")
    parser.add_argument("--report", default="reports/lab01_report.csv", help="Output CSV report path")
    parser.add_argument(
        "--starter-commit",
        default=None,
        help="Optional commit hash from the instructor repo before students edited helloworld.py",
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
        results.append(grade_student(student, workdir, args.starter_commit))

    write_report(report_path, results)
    print(f"\nWrote report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
