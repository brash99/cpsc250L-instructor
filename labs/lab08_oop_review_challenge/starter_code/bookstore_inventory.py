# Lab 8: Object-Oriented Programming Review Challenge

from book import Book


def create_inventory():
    """
    Read books from csv file, create and return a list of Book objects.
    """
    books = []

    return books


def print_inventory(books):
    """
    Print every book in the inventory.
    """
    pass


def total_inventory(books):
    """
    Return the total number of all books in inventory.
    """
    pass


def find_by_author(books, author):
    """
    Return a list of books written by the specified author.
    """
    pass


def find_low_stock(books, threshold):
    """
    Return a list of books whose quantity is less than or equal to threshold.
    """
    pass


def print_books(books):
    """
    Print a list of books.
    """
    pass


def main():
    inventory = create_inventory()

    print("Full Inventory")
    print("--------------")
    print_inventory(inventory)

    print()
    print("Total inventory:", total_inventory_value(inventory))

    print()
    print("Books by Octavia Butler")
    print("-----------------------")
    print_books(find_by_author(inventory, "Octavia Butler"))

    print()
    print("Low Stock Books")
    print("---------------")
    print_books(find_low_stock(inventory, 3))

    print()
    print("Sorted by Title")
    print("---------------")
    sorted_books = sorted(inventory)
    print_books(sorted_books)


main()
