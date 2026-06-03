def read_temperatures(filename):
    with open(filename, 'r') as file:
        temperatures = []
        for line in file:
            try:
                temp = float(line.strip())
                temperatures.append(temp)
            except ValueError:
                print(f"Warning: '{line.strip()}' is not a valid number and will be skipped.")
    return temperatures

def calculate_average(values):
    return sum(values) / len(values) if values else 0

def find_maximum(values):
    return 0

def find_minimum(values):
    return 0

def count_above_threshold(values, threshold):
    return 0

def print_report(values):
    average = calculate_average(values)
    maximum = find_maximum(values)
    minimum = find_minimum(values)
    above_threshold_count = count_above_threshold(values, 30)  # Example threshold

    print(f"Average Temperature: {average:.2f}")
    print(f"Maximum Temperature: {maximum:.2f}")
    print(f"Minimum Temperature: {minimum:.2f}")
    print(f"Number of Days Above 30°C: {above_threshold_count}")

def main():
    temperatures = read_temperatures("../data/june_temperatures.txt")
    print_report(temperatures)

main()
