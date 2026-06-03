def read_temperatures(values):
   #Opens file with a call "filename" and returns the temperature data from the txt file and skips over blanks.
    temperatures = []
    filename = "../data/june_temperatures.txt"
    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            if line != "":
                temperatures.append(int(line))
    return temperatures


def calculate_average(values):
  #a value takes the length of the temperatures and sum is getting the some of all the temperature values and adding them and average is dividing that number by how many values there are.
    a = len(values)
    sum = 0.0
    for i in range(a):
        sum = sum + values[i]
    average = sum / a
    return average

def find_maximum(values):
    #this will automatically give the highest of temperatures
    return max(values)

def find_minimum(values):
    # this will automatically give the lowest of temperatures
    return min(values)

def count_above_threshold(values, threshold):
    #for the temperatures that go above 80 it will count how many there are.
    count = 0
    for i in values:
        if i > threshold:
            count = count + 1
    return count

def print_report(values):
   # this prints the data and result from all previous functions and gives the final product
    print("Temperature Report")
    print("------------------")
    print(f'Average temperature: {calculate_average(values)}')
    print(f'Maximum temperature: {find_maximum(values)}')
    print(f'Minimum temperature: {find_minimum(values)}')
    print(f'Temperatures above 80: {count_above_threshold(values, 80)}')

def main():
    temperatures = read_temperatures("../data/june_temperatures.txt")
    print_report(temperatures)

main()
