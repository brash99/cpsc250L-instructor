#!/usr/bin/env python3
"""
summarize_autogrades.py

Create a summary table of autograded scores from multiple lab report CSV files.

Expected input files:
    lab01_report.csv
    lab02_report.csv
    ...
or any files matching:
    lab*_report.csv

Each lab report should contain:
    name
    github_username
    type                 optional
    auto_score_out_of_N  e.g. auto_score_out_of_8, auto_score_out_of_29

The script writes:
    autograde_summary.csv

Example:

python summarize_autogrades.py \
    --reports-dir reports \
    --output reports/autograde_summary.csv \
    --exclude-test
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple


AUTO_SCORE_PATTERN = re.compile(r"^auto_score_out_of_(\d+(?:\.\d+)?)$")


def lab_sort_key(path: Path) -> Tuple[int, str]:
    match = re.search(r"lab(\d+)", path.name.lower())
    if match:
        return int(match.group(1)), path.name
    return 9999, path.name


def find_auto_score_column(fieldnames: List[str]) -> Tuple[str, float]:
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
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}"


def read_lab_report(path: Path, exclude_test: bool = False) -> Tuple[str, float, Dict[str, Dict[str, str]]]:
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

            account_type = (row.get("type") or "student").strip().lower()
            if exclude_test and account_type == "test":
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


def build_summary(report_paths: List[Path], exclude_test: bool = False) -> Tuple[List[str], List[Dict[str, str]]]:
    lab_info = []
    students: Dict[str, Dict[str, object]] = {}

    for path in sorted(report_paths, key=lab_sort_key):
        lab_label, max_points, rows = read_lab_report(path, exclude_test=exclude_test)
        lab_info.append((lab_label, max_points))

        for username, row in rows.items():
            if username not in students:
                students[username] = {
                    "name": row["name"],
                    "github_username": username,
                    "type": row.get("type", "student"),
                    "_scores": {},
                }

            if row["name"]:
                students[username]["name"] = row["name"]

            students[username]["_scores"][lab_label] = row["score_float"]

    total_possible = sum(max_points for _, max_points in lab_info)

    headers = ["name", "github_username", "type"]

    for lab_label, max_points in lab_info:
        headers.append(f"{lab_label} out of {format_score(max_points)}")

    headers.extend(["autograded_total", "autograded_possible", "autograded_percent"])

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

        row["autograded_total"] = format_score(total)
        row["autograded_possible"] = format_score(total_possible)
        row["autograded_percent"] = f"{100.0 * total / total_possible:.2f}" if total_possible else ""

        output_rows.append(row)

    return headers, output_rows


def write_summary(path: Path, headers: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize CPSC 250L autograded lab scores.")
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
        "--exclude-test",
        action="store_true",
        help="Exclude rows where type == test",
    )
    args = parser.parse_args()

    reports_dir = Path(args.reports_dir)
    report_paths = sorted(reports_dir.glob(args.pattern), key=lab_sort_key)

    if not report_paths:
        raise SystemExit(f"No report files found in {reports_dir} matching {args.pattern}")

    headers, rows = build_summary(report_paths, exclude_test=args.exclude_test)
    write_summary(Path(args.output), headers, rows)

    print(f"Processed {len(report_paths)} lab reports.")
    print(f"Wrote summary: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
