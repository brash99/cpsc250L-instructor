#!/usr/bin/env python3
"""
summarize_autogrades.py

Create a summary table of autograded scores from multiple lab report CSV files.

This version ALWAYS includes the test account and uses the row with:

    type == test

as the normalization standard.

Example:
    If the test account earned 136 autograded points out of 144 possible,
    then all student percentages are computed as:

        normalized_percent = student_autograded_total / 136 * 100

Expected input files:
    lab01_report.csv
    lab02_report.csv
    ...
or any files matching:
    lab*_report.csv

Each lab report should contain:
    name
    github_username
    type                 optional but required for normalization
    auto_score_out_of_N  e.g. auto_score_out_of_8, auto_score_out_of_29

The script writes:
    autograde_summary.csv

Example:

python summarize_autogrades.py \
    --reports-dir reports \
    --output reports/autograde_summary.csv

Optional:
    Use --test-username edwardbrash if you prefer to identify the test account
    by GitHub username instead of relying only on type=test.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple


AUTO_SCORE_PATTERN = re.compile(r"^auto_score_out_of_(\d+(?:\.\d+)?)$")


def lab_sort_key(path: Path) -> Tuple[int, str]:
    """
    Sort lab01_report.csv, lab02_report.csv, etc. numerically.
    """
    match = re.search(r"lab(\d+)", path.name.lower())
    if match:
        return int(match.group(1)), path.name
    return 9999, path.name


def find_auto_score_column(fieldnames: List[str]) -> Tuple[str, float]:
    """
    Find the auto_score_out_of_N column and return (column_name, max_points).
    """
    matches = []

    for field in fieldnames:
        match = AUTO_SCORE_PATTERN.match(field)
        if match:
            matches.append((field, float(match.group(1))))

    if not matches:
        raise ValueError(f"No auto_score_out_of_N column found. Columns were: {fieldnames}")

    if len(matches) > 1:
        raise ValueError(f"Multiple auto_score_out_of_N columns found: {[m[0] for m in matches]}")

    return matches[0]


def safe_float(value: str) -> float:
    value = (value or "").strip()
    if value == "":
        return 0.0
    return float(value)


def format_score(value: float) -> str:
    """
    Avoid ugly .0 values when scores are whole numbers.
    """
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}"


def read_lab_report(path: Path) -> Tuple[str, float, Dict[str, Dict[str, str]]]:
    """
    Read one lab report and return:

        lab_label, max_points, student score data

    student score data maps github_username -> row info.
    """
    lab_match = re.search(r"lab(\d+)", path.name.lower())
    lab_label = f"Lab {int(lab_match.group(1))}" if lab_match else path.stem

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header row")

        fieldnames = reader.fieldnames

        if "github_username" not in fieldnames:
            raise ValueError(f"{path} is missing github_username column")

        if "name" not in fieldnames:
            raise ValueError(f"{path} is missing name column")

        score_col, max_points = find_auto_score_column(fieldnames)

        rows: Dict[str, Dict[str, str]] = {}

        for row in reader:
            username = (row.get("github_username") or "").strip()
            if not username:
                continue

            score = safe_float(row.get(score_col, "0"))

            rows[username] = {
                "name": (row.get("name") or "").strip(),
                "github_username": username,
                "type": row.get("type", "student").strip() or "student",
                "score": format_score(score),
                "score_float": str(score),
            }

        return lab_label, max_points, rows


def identify_test_student(
    output_rows: List[Dict[str, str]],
    test_username: str | None = None,
) -> Dict[str, str]:
    """
    Identify the normalization row.

    Priority:
        1. --test-username, if provided
        2. first row with type == test
    """
    if test_username:
        for row in output_rows:
            if row["github_username"].strip().lower() == test_username.strip().lower():
                return row

        raise ValueError(f"No row found with github_username == {test_username!r}")

    test_rows = [
        row for row in output_rows
        if row.get("type", "").strip().lower() == "test"
    ]

    if not test_rows:
        raise ValueError(
            "No test account found. Mark the test account with type=test "
            "in students.csv / lab reports, or pass --test-username USERNAME."
        )

    if len(test_rows) > 1:
        names = ", ".join(row["github_username"] for row in test_rows)
        raise ValueError(
            f"Multiple rows have type=test: {names}. "
            "Use --test-username USERNAME to choose one."
        )

    return test_rows[0]


def build_summary(
    report_paths: List[Path],
    test_username: str | None = None,
) -> Tuple[List[str], List[Dict[str, str]]]:
    """
    Build summary rows across all lab reports.
    """
    lab_info = []
    students: Dict[str, Dict[str, object]] = {}

    for path in sorted(report_paths, key=lab_sort_key):
        lab_label, max_points, rows = read_lab_report(path)
        lab_info.append((lab_label, max_points))

        for username, row in rows.items():
            if username not in students:
                students[username] = {
                    "name": row["name"],
                    "github_username": username,
                    "type": row.get("type", "student"),
                    "_scores": {},
                }

            # Prefer a non-empty name if encountered later.
            if row["name"]:
                students[username]["name"] = row["name"]

            # Prefer type=test if it ever appears in any lab report.
            if row.get("type", "").strip().lower() == "test":
                students[username]["type"] = "test"

            students[username]["_scores"][lab_label] = row["score_float"]

    raw_possible = sum(max_points for _, max_points in lab_info)

    headers = ["name", "github_username", "type"]

    for lab_label, max_points in lab_info:
        headers.append(f"{lab_label} out of {format_score(max_points)}")

    headers.extend([
        "raw_autograded_total",
        "raw_autograded_possible",
        "normalization_source",
        "normalized_possible",
        "normalized_percent",
    ])

    output_rows: List[Dict[str, str]] = []

    for username in sorted(students, key=lambda u: str(students[u]["name"]).lower() or u.lower()):
        student = students[username]
        scores = student["_scores"]

        row: Dict[str, str] = {
            "name": str(student["name"]),
            "github_username": username,
            "type": str(student.get("type", "student")),
        }

        total = 0.0

        for lab_label, max_points in lab_info:
            col = f"{lab_label} out of {format_score(max_points)}"
            raw_score = scores.get(lab_label, "")

            if raw_score == "":
                row[col] = ""
            else:
                score_value = float(raw_score)
                total += score_value
                row[col] = format_score(score_value)

        row["raw_autograded_total"] = format_score(total)
        row["raw_autograded_possible"] = format_score(raw_possible)

        output_rows.append(row)

    test_row = identify_test_student(output_rows, test_username=test_username)
    normalized_possible = float(test_row["raw_autograded_total"])

    if normalized_possible <= 0:
        raise ValueError(
            f"Test account {test_row['github_username']} has zero normalized possible points."
        )

    normalization_source = f"{test_row['name']} ({test_row['github_username']})"

    for row in output_rows:
        total = float(row["raw_autograded_total"])

        row["normalization_source"] = normalization_source
        row["normalized_possible"] = format_score(normalized_possible)
        row["normalized_percent"] = f"{100.0 * total / normalized_possible:.2f}"

    return headers, output_rows


def write_summary(path: Path, headers: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize CPSC 250L autograded lab scores using a test account for normalization."
    )

    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Directory containing lab*_report.csv files",
    )

    parser.add_argument(
        "--output",
        default="reports/autograde_summary.csv",
        help="Output summary CSV path",
    )

    parser.add_argument(
        "--pattern",
        default="lab*_report.csv",
        help="Glob pattern for lab report files",
    )

    parser.add_argument(
        "--test-username",
        default=None,
        help="Optional GitHub username for the test account. If omitted, uses type=test.",
    )

    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    report_paths = sorted(reports_dir.glob(args.pattern), key=lab_sort_key)

    if not report_paths:
        raise SystemExit(f"No report files found in {reports_dir} matching {args.pattern}")

    headers, rows = build_summary(report_paths, test_username=args.test_username)
    write_summary(Path(args.output), headers, rows)

    test_row = identify_test_student(rows, test_username=args.test_username)

    print(f"Processed {len(report_paths)} lab reports.")
    print(f"Normalization source: {test_row['name']} ({test_row['github_username']})")
    print(f"Normalized possible: {test_row['raw_autograded_total']}")
    print(f"Wrote summary: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
