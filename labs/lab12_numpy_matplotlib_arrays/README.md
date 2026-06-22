# Lab 12: NumPy Arrays and Matplotlib Plotting

## Overview

This lab continues the CPSC 250L emphasis on hands-on programming, iterative development, GitHub, and live checkoff.

As usual, we will use the feature-branch workflow:

```text
sync fork -> pull -> create branch -> develop -> commit -> test -> merge -> push
```

However, today we will begin by syncing our fork at the command line (as opposed to within PyCharm!).
The first step is to make sure that my CPSC 250L repo is defined as the appropriate upstream repo:

```bash
git remote -v
```

You should see something like:

```text
origin	https://github.com/edwardbrash/cpsc250L.git (fetch)
origin	https://github.com/edwardbrash/cpsc250L.git (push)
upstream	https://github.com/brash99/cpsc250L.git (fetch)
upstream	https://github.com/brash99/cpsc250L.git (push)
```

If you do *not* see the upstream repo, establish it with:

```bash
git remote add upstream https://github.com/brash99/cpsc250L.git
```

Once we are sure that the upstream repo is defined properly, sync
your fork by doing:

```bash
git checkout main
git fetch upstream
git merge upstream/main
```

Create a new branch for this lab:

```bash
git checkout -b lab12-numpy-plotting
```

After completing and testing the lab (while doing
the usual commit/push along the way), merge back into `main`:

```bash
git checkout main
git merge lab12-numpy-plotting
```

Then push using PyCharm (we will use PyCharm for 
this last part, still, to avoid authentication issues!):

```text
Git -> Push...
```

Do not use terminal `git push` unless you have terminal GitHub authentication configured.


# Learning Objectives

By the end of this lab, you should be able to:

- Create NumPy arrays
- Perform array calculations
- Generate data for a function
- Make a matplotlib plot
- Save a plot as an image file

# Assignment

You will model the motion of an object under constant acceleration.

You will use NumPy arrays to compute position and velocity values and matplotlib to plot the results.

# Program Requirements

Your program should:

1. Create a time array.
2. Compute position and velocity arrays.
3. Print selected values.
4. Plot position versus time.
5. Plot velocity versus time.
6. Save the plots as PNG files.

# Required Commits

```text
Commit 1: Add NumPy array calculations
Commit 2: Add position plot
Commit 3: Add velocity plot
Commit 4: Save plots and cleanup
```

# Instructor Checkoff

Possible live requests:

- Change the acceleration.
- Change the time interval.
- Add a title or axis label.
- Save a new plot.
- Explain why array operations are useful.
