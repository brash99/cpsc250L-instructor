# Lab 14: Curve Fitting and Linear Regression

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
git checkout -b lab14-regression
```

After completing and testing the lab (while doing
the usual commit/push along the way), merge back into `main`:

```bash
git checkout main
git merge lab14-regression
```

Then push using PyCharm:

```text
Git -> Push...
```

Do not use terminal `git push` unless you have terminal GitHub authentication configured.


# Learning Objectives

By the end of this lab, you should be able to:

- Load paired x-y data
- Plot data points
- Fit a line to data
- Interpret slope and intercept
- Compute predicted values
- Plot data and fitted model together
- Compute residuals

# Assignment

You will analyze a small dataset relating study time to exam score.

Files:

```text
starter_code/regression_analysis.py
data/study_scores.csv
```

# Program Requirements

Your program should:

1. Load the CSV data.
2. Plot study hours versus exam score.
3. Fit a linear model.
4. Print slope and intercept.
5. Compute predicted scores.
6. Compute residuals.
7. Plot data and fitted line.
8. Save the plot.

# Required Commits

```text
Commit 1: Load and plot data
Commit 2: Add linear fit
Commit 3: Add predictions and residuals
Commit 4: Add final plot and cleanup
```

# Instructor Checkoff

Possible live requests:

- Predict the score for a new study time.
- Explain slope and intercept.
- Add a residual plot.
- Change the dataset.
- Explain what residuals represent.
