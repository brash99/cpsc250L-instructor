# Lab 15: Command-Line GitHub Workflow and Developer Independence

## Overview

At the beginning of this course, PyCharm handled most GitHub interactions for you.

Over the past four weeks, you have learned:

- Python programming
- Git
- GitHub
- feature branches
- merging
- object-oriented programming
- data analysis
- debugging
- software workflow skills

In this final lab, you will take direct control of your GitHub workflow from the command line.

The goal of this lab is not just to complete another programming assignment.

The goal is to demonstrate that you can now function as an independent developer using professional command-line tools.

---

# Learning Objectives

By the end of this lab, you should be able to:

- Use GitHub CLI (`gh`)
- Authenticate GitHub access from the terminal
- Use Git entirely from the command line
- Create branches from the terminal
- Commit and push changes from the terminal
- Understand local vs remote repositories
- Understand Git remotes and branches
- Use common terminal commands comfortably
- Recognize the power and flexibility of command-line tooling

---

# Important Philosophy

PyCharm is a powerful development tool.

However:

```text
PyCharm is not the source of truth.
Git is the source of truth.
GitHub is the remote hosting service.
```

PyCharm is simply one interface layered on top of Git.

Professional programmers frequently use command-line tools because they are:

- flexible
- composable
- scriptable
- fast
- available on nearly every system

This lab is designed to help you become comfortable with that workflow.

---

# Part 1: Verify Git Installation

Open a terminal.

## Windows

You may use:

- PyCharm terminal
- Command Prompt
- PowerShell

## macOS

You may use:

- PyCharm terminal
- Terminal.app

Run:

```bash
git --version
```

You should see output similar to:

```text
git version 2.43.0
```

---

# Part 2: Install GitHub CLI

GitHub CLI is an official command-line tool provided by GitHub.

It allows your terminal to communicate directly with GitHub.

## Windows

Go to:

```text
https://cli.github.com/
```

Install using the Windows installer.

OR use:

```bash
winget install GitHub.cli
```

---

## macOS

If you have Homebrew installed:

```bash
brew install gh
```

Otherwise, download the installer from:

```text
https://cli.github.com/
```

---

# Part 3: Verify GitHub CLI Installation

Run:

```bash
gh --version
```

You should see version information.

---

# Part 4: Authenticate With GitHub

Run:

```bash
gh auth login
```

You will be asked several questions.

Recommended answers:

## GitHub Host

```text
GitHub.com
```

## Preferred Protocol

```text
HTTPS
```

## Authenticate Git With GitHub Credentials?

```text
Yes
```

## Authentication Method

```text
Login with a web browser
```

A browser window should open.

Log into GitHub and authorize GitHub CLI.

---

# Part 5: Verify Authentication

Run:

```bash
gh auth status
```

You should see confirmation that you are logged into GitHub.

At this point, your terminal should now be able to communicate directly with GitHub.

---

# Part 6: Explore Your Repository

Navigate to your course repository.

Run the following commands:

```bash
git status
```

```bash
git branch
```

```bash
git remote -v
```

```bash
git log --oneline
```

Discuss:

- What is the current branch?
- What is `origin`?
- What does `git status` tell you?
- What does the commit history represent?

---

# Part 7: Create a Command-Line Branch

Create a new branch:

```bash
git checkout -b lab15-cli-workflow
```

Verify the branch:

```bash
git branch
```

The current branch should appear with an asterisk (`*`).

---

# Part 8: Edit a File

Open:

```text
starter_files/reflection.txt
```

Add a short reflection about the course.

Suggested topics:

- What programming concept was most difficult?
- What skill improved the most?
- What surprised you about Git or GitHub?
- What do you now understand that you did not understand four weeks ago?

Save the file.

---

# Part 9: Complete a Pure Command-Line Git Workflow

Use ONLY terminal commands for this section.

## Check Status

```bash
git status
```

## Stage Files

```bash
git add .
```

## Commit Changes

```bash
git commit -m "Complete Lab 15 command-line workflow"
```

## Push Branch to GitHub

```bash
git push --set-upstream origin lab15-cli-workflow
```

This should now work directly from the terminal.

No PyCharm push interface should be required.

---

# Part 10: Verify the Push

Go to GitHub in your browser.

Verify that:

- the branch exists
- the commit exists
- your updated file appears online

---

# Part 11: Explore GitHub CLI

Try the following commands:

## View Repository Information

```bash
gh repo view
```

## View Authentication Status

```bash
gh auth status
```

## View Pull Requests

```bash
gh pr list
```

## View Issues

```bash
gh issue list
```

Some repositories may not contain issues or pull requests.

That is okay.

---

# Part 12: Useful Terminal Commands

Try the following commands.

## Show Current Directory

```bash
pwd
```

## List Files

### Windows

```bash
dir
```

### macOS

```bash
ls
```

## Create a Directory

```bash
mkdir practice_folder
```

## Remove the Directory

### Windows

```bash
rmdir practice_folder
```

### macOS

```bash
rm -r practice_folder
```

## Find Python Files

### macOS/Linux

```bash
find . -name "*.py"
```

### Windows PowerShell

```bash
Get-ChildItem -Recurse -Filter *.py
```

---

# Part 13: Reflection Questions

Discuss the following:

1. Why do professional developers often use command-line tools?
2. What advantages does Git provide?
3. What is the difference between local and remote repositories?
4. Why are branches useful?
5. Why might a developer use both an IDE and a terminal?

---

# Instructor Checkoff

Be prepared to demonstrate:

- `gh auth status`
- `git status`
- `git branch`
- `git log --oneline`
- successful command-line `git push`
- ability to create a branch from the terminal
- ability to explain `origin`
- ability to explain local vs remote repositories

Possible live requests include:

- create a new branch
- make another commit
- push another change
- explain the current Git branch
- explain how GitHub CLI works

---

# Congratulations

You have completed the final CPSC 250L lab.

You now have experience with:

- Python programming
- Git
- GitHub
- branches and merges
- object-oriented programming
- data analysis
- command-line development workflow

Most importantly, you have developed the ability to learn and work independently using professional tools.
