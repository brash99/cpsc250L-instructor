import time

def fib_recursive(n):
    pass


def fib_iterative(n):
    pass


def time_function(function, n):
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


main()
