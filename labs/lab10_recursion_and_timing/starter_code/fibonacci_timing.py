import time

def fib_recursive(n)
    # TODO: write this function
    pass


def fib_iterative(n):
    # TODO: write this function
    pass


def time_function(function, n):
    # TODO: write this function - google the python time module to figure out how it works
    # TODO: start a timer, call the appropriate function, then stop the timer
    # TODO: return the elapsed time
    return 0

def main():
    values = [5, 10, 20, 25, 30, 35, 40]

    print("Fibonacci Timing")
    print("----------------")
    print("n    recursive_time    iterative_time")

    for n in values:
        recursive_time = time_function(fib_recursive, n)
        iterative_time = time_function(fib_iterative, n)
        if iterative_time != 0:
            speed = recursive_time/iterative_time
        else:
            speed = float("inf")
        print(f"{n:<5} {recursive_time:.8f} seconds    {iterative_time:.8f} seconds     {speed:.1f}")

    # TODO: create a plot which shows both recursive time and iterative time as a function of n
    # TODO: label the x-axis, y-axis, and provide a title
    # TODO: display a legend that will indicate which dataset is which
    # TODO: make the y-axis logarithmic

main()
