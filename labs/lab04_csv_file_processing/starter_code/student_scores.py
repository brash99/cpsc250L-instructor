# Lab 4: File I/O and CSV Data Processing
#
# Complete this program so that it reads quiz score data from a CSV file,
# cleans the data, computes student averages, and prints a report.

import csv

def clean_score(score_text):
    """
    Convert a score string into an integer.

    If the score is missing or invalid, return None.
    """
    if score_text is None:
        return None
    score_text = score_text.strip()
    if score_text == "":
        return None
    try:
        return int(score_text)
    except ValueError:
        return None


def calculate_average(scores):
    """
    Calculate the average of a list of numeric scores.

    If the list is empty, return None.
    """
    if scores is None:
        return None
    valid_scores = [score for score in scores if score is not None]
    if not valid_scores:
        return None
    return sum(valid_scores) / len(valid_scores)


def read_scores(filename):
    """
    Read student quiz scores from a CSV file.

    Return a list of dictionaries.

    Each dictionary should contain:
        "name": student name
        "scores": list of valid numeric quiz scores
        "average": student average

    So, the returned list of dictionaries should look like:
    [
        {
            "name": "Alice",
            "scores": [85, 90, 78],
            "average": 84.33
        },
        {
            "name": "Bob",
            "scores": [92, None, 88],
            "average": 90.0
        },
        ...
    ]
    """

    with open(filename) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        records = []
        # skip header
        csv_header = next(csv_reader)
        for row in csv_reader:
            name = row[0]
            score_texts = row[1:]
            scores = [clean_score(score) for score in score_texts]
            average = calculate_average(scores)
            record = {
                "name": name,
                "scores": scores,
                "average": average
            }
            records.append(record)
    return records



def letter_grade(average):
    """
    Return a simple letter grade based on the average.

    Suggested scale:
        A: average >= 87
        B: average >= 77
        C: average >= 67
        D: average >= 57
        F: otherwise

    If the average is None, return "N/A".
    """
    if average is None:
        return "N/A"
    elif average >= 87:
        return "A"
    elif average >= 77:
        return "B"
    elif average >= 67:
        return "C"
    elif average >= 57:
        return "D"
    else:
        return "F"


def print_student_report(records):
    """
    Print one line of output for each student.
    """
    for record in records:
        name = record["name"]
        average = record["average"]
        grade = letter_grade(average)
        print(f"{name}: Average = {average:.2f} Grade = {grade}")


def print_class_summary(records):
    """
    Print a summary for the whole class.

    Include:
        number of students
        class average
        highest average
        lowest average
    """
    averages = [record["average"] for record in records if record["average"] is not None]
    num_students = len(records)
    class_average = calculate_average(averages)
    highest_average = max(averages) if averages else None
    lowest_average = min(averages) if averages else None

    print(f"Number of students: {num_students}")
    print(f"Class average: {class_average:.2f}" if class_average is not None else "Class average: N/A")
    print(f"Highest average: {highest_average:.2f}" if highest_average is not None else "Highest average: N/A")
    print(f"Lowest average: {lowest_average:.2f}" if lowest_average is not None else "Lowest average: N/A")


def main():
    filename = "../data/quiz_scores.csv"

    records = read_scores(filename)

    print_student_report(records)
    print()
    print_class_summary(records)


main()
