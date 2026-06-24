# Lab 13: Pandas DataFrame Analysis

## Overview

This lab continues the CPSC 250L emphasis on hands-on programming, iterative development, GitHub, and live checkoff.

Use the feature-branch workflow:

```text
sync fork -> pull -> create branch -> develop -> commit -> test -> merge -> push
```

Create a branch for this lab:

```bash
git checkout main
git fetch upstream
git merge upstream/main
git checkout -b lab13-pandas
```

After completing and testing the lab (while doing
the usual commit/push along the way), merge back into `main`:

```bash
git checkout main
git merge lab13-pandas
```

Then push using PyCharm:

```text
Git -> Push...
```

Do not use terminal `git push` unless you have terminal GitHub authentication configured.


# Learning Objectives

By the end of this lab, you should be able to:

- Load CSV data into a pandas DataFrame
- Inspect a DataFrame
- Select columns
- Create calculated columns
- Filter rows
- Compute summary statistics
- Make a simple plot from DataFrame data

# Assignment

You will analyze a small dataset of daily weather observations.

Files:

```text
starter_code/weather_analysis.py
data/weather_june.csv
```

# Program Requirements

Your program should:

1. Load the CSV file using pandas.
2. Print the first few rows.
3. Compute average high and low temperatures.
4. Add a temperature range column.
5. Find the hottest day.
6. Find days with precipitation.
7. Make a plot of high and low temperatures.

# Required Commits

```text
Commit 1: Load and inspect DataFrame
Commit 2: Add summary statistics
Commit 3: Add filtering and calculated columns
Commit 4: Add plot and cleanup
```

# Instructor Checkoff

Possible live requests:

- Filter days above a threshold.
- Add a new calculated column.
- Change the plot.
- Explain what a DataFrame is.
- Explain the difference between a row and a column.
