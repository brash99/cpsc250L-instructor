# Lab 8: OOP Review Challenge


class Book:
    def __init__(self, title, author, year, genre, pages, rating):
        self.title = title
        self.author = author
        self.year = year
        self.genre = genre
        self.pages = pages
        self.rating = rating
        self.quantity = 0

    def add_stock(self, amount):
        """
        Increase quantity by amount.
        """
        self.quantity += amount

    def sell_copies(self, amount):
        """
        Decrease quantity by amount if enough copies are available.

        Return True if the sale succeeds.
        Return False otherwise.
        """

        if amount <= self.quantity:
            self.quantity -= amount
            return True

        return False

    def __str__(self):
        return (
            f"{self.title} by {self.author} ({self.year}) - "
            f"{self.genre}, {self.pages} pages, "
            f"rating: {self.rating}/5, stock: {self.quantity}"
        )



    def __lt__(self, other):
        """
        Compare books alphabetically by title.
        """
        return self.title < other.title

