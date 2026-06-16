# Lab 10: Recursion and Timing Experiments

## Overview

This lab continues the CPSC 250L emphasis on hands-on programming, iterative development, GitHub, and live checkoff.

Use the feature-branch workflow:

```text
sync fork -> pull -> create branch -> develop -> commit -> test -> merge -> push
```

Create a branch for this lab:

```bash
git checkout -b lab10-recursion
```

After completing and testing the lab, merge back into `main`:

```bash
git checkout main
git merge lab10-recursion
```

Then push using PyCharm:

```text
Git -> Push...
```

Do not use terminal `git push` unless you have terminal GitHub authentication configured.


# Learning Objectives

By the end of this lab, you should be able to:

- Write simple recursive functions
- Identify base cases and recursive cases
- Compare recursive and iterative solutions
- Use timing measurements
- Explain why some recursive algorithms are inefficient

# Assignment

You will complete timing experiments for Fibonacci numbers.

The starter code includes:

```text
starter_code/fibonacci_timing.py
```

# Program Requirements

Your program should:

1. Implement `fib_recursive(n)`.
2. Implement `fib_iterative(n)`.
3. Time both versions.
4. Print a table comparing runtime.
5. Avoid running the recursive version for values that are too large.

# Required Commits

```text
Commit 1: Add recursive Fibonacci
Commit 2: Add iterative Fibonacci
Commit 3: Add timing code
Commit 4: Add output table and cleanup
```

# Instructor Checkoff

Possible live requests:

- Explain the base case.
- Explain the recursive case.
- Add a new `n` value to test.
- Explain why recursive Fibonacci becomes slow.
- Modify the table formatting.
