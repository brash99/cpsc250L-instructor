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

    myfile = Path(filename)
    if myfile.is_file():
        with open(myfile, "r") as f:
            for line in f:
                line = line.strip()
                if line:  # Check if the line is not blank
                    try:
                        temp = float(line)  # Convert the line to a float
                        temperatures.append(temp)  # Append the temperature to the list
                    except ValueError:
                        print(f"Warning: '{line}' is not a valid number and will be skipped.")

    return temperatures


def compute_average(values):
    """
    Compute the average of a list of numbers.
    """

    if len(values) < 1:
        return 0.0
    return sum(values) / len(values)


def compute_minimum(values):
    """
    Compute the minimum value in a list of numbers.
    """
    # TODO: Replace this with a correct minimum calculation.
    if len(values) < 1:
        return 0.0
    return min(values)


def compute_maximum(values):
    """
    Compute the maximum value in a list of numbers.
    """
    # TODO: Replace this with a correct maximum calculation.
    if len(values) < 1:
        return 0.0
    return max(values)


def print_summary(values):
    """
    Print a formatted summary of the temperature data.
    """
    count = len(values)
    minimum = compute_minimum(values)
    maximum = compute_maximum(values)
    average = compute_average(values)

    # TODO: Improve this output formatting.
    #print("Temperature Summary")
    #print("Number of readings:", count)
    #print("Minimum temperature:", minimum)
    #print("Maximum temperature:", maximum)
    #print("Average temperature:", average)
    print("Temperatures Summary")
    print("Number of readings: {}".format(count))
    print("Minimum temperature: {:.2f}".format(minimum))
    print("Maximum temperature: {:.2f}".format(maximum))
    print("Average temperature: {:.2f}".format(average))


def main():
    """
    Main program function.
    """
    data_file = Path(__file__).resolve().parent.parent / "data" / "temperatures.txt"
    temperatures = read_temperatures(data_file)
    print_summary(temperatures)


if __name__ == "__main__":
    main()
