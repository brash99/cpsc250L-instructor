# Lab 7: Operator Overloading and Object Comparisons


class TimeDuration:
    def __init__(self, hours, minutes, seconds):
        """
        Store a time duration.

        You may assume the input values are non-negative integers.
        """
        pass

    def total_seconds(self):
        """
        Return the total number of seconds represented by this duration.
        """
        pass

    def __str__(self):
        """
        Return a readable string such as:
            1h 05m 09s
        """
        pass

    def __eq__(self, other):
        """
        Return True if two TimeDuration objects represent the same duration.
        """
        pass

    def __lt__(self, other):
        """
        Return True if this duration is shorter than the other duration.
        """
        pass

    def __add__(self, other):
        """
        Return a new TimeDuration object that is the sum of this duration and the other duration.
        """
        pass
