# Lab 8: OOP Review Challenge


class Book:
    def __init__(self, title, author, year, genre, pages, rating):
        pass

    def add_stock(self, amount):
        """
        Increase quantity by amount.
        """
        pass

    def sell_copies(self, amount):
        """
        Decrease quantity by amount if enough copies are available.

        Return True if the sale succeeds.
        Return False otherwise.
        """
        pass

    def __str__(self):
        pass

    def __lt__(self, other):
        """
        Compare books alphabetically by title.
        """
        pass
