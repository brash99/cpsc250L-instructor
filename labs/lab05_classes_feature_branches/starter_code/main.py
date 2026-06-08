# Lab 5 main program
#
# Use this file to create StudentRecord objects and test your class.

from student_record import StudentRecord


def main():
    alice = StudentRecord("Alice Johnson", "A001")
    ben = StudentRecord("Ben Carter", "B002")
    carlos = StudentRecord("Carlos Rivera", "C003")

    alice.add_score(85)
    alice.add_score(90)
    alice.add_score(88)

    ben.add_score(72)
    ben.add_score(78)
    ben.add_score(80)

    carlos.add_score(91)
    carlos.add_score(95)
    carlos.add_score(94)

    print(alice)
    print()
    print(ben)
    print()
    print(carlos)
    print()

    for student in [alice, ben, carlos]:
        print(f"{student.name}: "
              f"    Average: {student.calculate_average():.2f} "
              f"    High: {student.highest_score():.2f} "
              f"    Low: {student.lowest_score():.2f} "
              f"    Grade: {student.letter_grade()}")

main()
