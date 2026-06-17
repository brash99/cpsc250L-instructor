# Lab 8: Object-Oriented Programming Review Challenge
from book import Book
import csv


def create_inventory():
    """
    Read books from csv file, create and return a list of Book objects.
    """
    books = []


    with open("../data/booklist.csv", "r") as file:
        reader = csv.DictReader(file)

        for row in reader:

            book = Book(
                row["title"],
                row["author"],
                int(row["year"]),
                row["genre"],
                int(row["pages"]),
                float(row["rating"]),
            )

            books.append(book)

    return books


def print_inventory(books):
    """
    Print every book in the inventory.
    """
    for book in books:
        print(book)


def total_inventory(books):
    """
    Return the total number of all books in inventory.
    """
    total = 0

    for book in books:
        total += book.quantity

    return total


def find_by_author(books, author):
    """
    Return a list of books written by the specified author.
    """
    result = []

    for book in books:
        if book.author == author:
            result.append(book)

    return result

#
def find_low_stock(books, threshold):
    """
    Return a list of books whose quantity is less than or equal to threshold.
    """
    result = []

    for book in books:
        if book.quantity <= threshold:
            result.append(book)

    return result


def print_books(books):
    """
    Print a list of books.
    """
    for book in books:
        print(book)


def main():
    inventory = create_inventory()

    print("Full Inventory")
    print("--------------")
    print_inventory(inventory)

    print()
    print("Total inventory:", total_inventory(inventory))

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

#
main()
