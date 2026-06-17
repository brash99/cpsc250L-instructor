def linear_search(values, target):
    pass


def binary_search(values, target):
    pass


def f(x):
    return x * x - 2


def bisection_root(function, left, right, tolerance):
    pass


def main():
    import random
    values = random.sample(range(0, 10000), 1000)
    values.sort()

    print("Search Tests")
    print("------------")
    print("Linear search for 21:", linear_search(values, 341))
    print("Binary search for 21:", binary_search(values, 341))

    print()
    print("Root Finding")
    print("------------")
    root = bisection_root(f, 1, 2, 0.0001)
    print("Approximate root of x^2 - 2:", root)


main()
