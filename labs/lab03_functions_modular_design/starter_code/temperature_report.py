def read_temperatures(values):
   #Opens file with a call "filename" and returns the temperature date from the txt file and skips over blanks.
    temperatures = []
    filename = "../data/june_temperatures.txt"
    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            if line != "":
                temperatures.append(int(line))
    return(temperatures)

def calculate_average(values):
  #a value takes the length of the temperatures and sum is getting the some of all the temperature values and adding them and average is dividing that number by how many values there are.
    a = len(values)
    sum = 0.0
    for i in values:
        sum = sum + values[i]
    average = sum / a
    return(average)

def find_maximum(values):
    #this will automatically give the highest of temperatures
    return max(values)

def find_minimum(values):
    # this will automatically give the lowest of temperatures
    return min(values)

def count_above_threshold(values, threshold):
    pass

def print_report(values):
    pass

def main():
    temperatures = read_temperatures("../data/june_temperatures.txt")
    print_report(temperatures)

main()
