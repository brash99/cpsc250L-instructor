#!/bin/bash

python3 grade_lab05.py --students students.csv --workdir student_repos --report reports/lab05_report.csv --lab-path labs/lab05_classes_feature_branches
python3 grade_lab04.py --students students.csv --workdir student_repos --report reports/lab04_report.csv --lab-path labs/lab04_csv_file_processing
python3 grade_lab03.py --students students.csv --workdir student_repos --report reports/lab03_report.csv --lab-path labs/lab03_functions_modular_design
python3 grade_lab02.py --students students.csv --workdir student_repos --report reports/lab02_report.csv --lab-path labs/lab02_python_review_git
python3 grade_lab01.py --students students.csv --workdir student_repos --report reports/lab01_report.csv --lab-path labs/lab1_environment_setup
