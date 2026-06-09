"""
CPSC 250L
Lab 2: Python Review and Git Fundamentals

This program reads temperature data from a text file and computes
basic statistics.

Complete the TODO sections below.
"""

from pathlib import Path


def read_temperatures(filename):
    """
    Read temperature values from a text file.

    Each line of the file should contain one number.

    Parameters
    ----------
    filename : str or Path
        Path to the input data file.

    Returns
    -------
    list of float
        Temperature values read from the file.
    """
    temperatures = []

    # TODO: Open the file and read each line.
    # TODO: Convert each non-blank line to a float.
    # TODO: Append each temperature to the temperatures list.
    with open(filename, "r") as file:
        # 3. Loop through each line in the file
        for line in file:
            # 4. Convert the string to a float and add it to the list
            if line != "\n":
                number = float(line.strip())
                temperatures.append(number)


    return temperatures


def compute_average(values):
    """
    Compute the average of a list of numbers.
    """
    # TODO: Replace this with a correct average calculation.
    return 0.0

def compute_minimum(values):
    """
    Compute the minimum value in a list of numbers.
    """
    # TODO: Replace this with a correct minimum calculation.
    return 0.0


def compute_maximum(values):
    """
    Compute the maximum value in a list of numbers.
    """
    # TODO: Replace this with a correct maximum calculation.
    return 0.0


def print_summary(values):
    """
    Print a formatted summary of the temperature data.
    """
    count = len(values)
    minimum = compute_minimum(values)
    maximum = compute_maximum(values)
    average = compute_average(values)

    # TODO: Improve this output formatting.
    print("Temperature Summary")
    print("Number of readings:", count)
    print("Minimum temperature:", minimum)
    print("Maximum temperature:", maximum)
    print("Average temperature:", average)


def main():
    """
    Main program function.
    """
    data_file = Path(__file__).resolve().parent.parent / "data" / "temperatures.txt"
    temperatures = read_temperatures(data_file)
    print_summary(temperatures)


if __name__ == "__main__":
    main()
