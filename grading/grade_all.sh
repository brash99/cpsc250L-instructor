#!/bin/bash

python3 grade_lab08.py --students students.csv --workdir student_repos --report reports/lab08_report.csv --lab-path labs/lab08_oop_review_challenge
python3 grade_lab07.py --students students.csv --workdir student_repos --report reports/lab07_report.csv --lab-path labs/lab07_operator_overloading_comparisons
python3 grade_lab06.py --students students.csv --workdir student_repos --report reports/lab06_report.csv --lab-path labs/lab06_collections_of_objects
python3 grade_lab05.py --students students.csv --workdir student_repos --report reports/lab05_report.csv --lab-path labs/lab05_classes_feature_branches
python3 grade_lab04.py --students students.csv --workdir student_repos --report reports/lab04_report.csv --lab-path labs/lab04_csv_file_processing
python3 grade_lab03.py --students students.csv --workdir student_repos --report reports/lab03_report.csv --lab-path labs/lab03_functions_modular_design
python3 grade_lab02.py --students students.csv --workdir student_repos --report reports/lab02_report.csv --lab-path labs/lab02_python_review_git
python3 grade_lab01.py --students students.csv --workdir student_repos --report reports/lab01_report.csv --lab-path labs/lab1_environment_setup
