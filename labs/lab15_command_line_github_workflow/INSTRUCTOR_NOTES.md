# Instructor Notes: Lab 15

## Purpose

This lab is intentionally different from earlier labs.

The primary goal is not programming syntax.

The primary goal is developer independence.

Students should leave this lab understanding that:

- Git is fundamentally command-line software
- IDEs are interfaces layered on top of Git
- command-line tools are powerful and flexible
- they are capable of managing their own workflow

## Important Pedagogical Point

The course intentionally began with:
- PyCharm-managed authentication
- GUI-assisted workflows

This reduced operational complexity during the early labs.

Now that students understand Git concepts, we remove the abstraction layer and expose the underlying workflow directly.

This progression is intentional and pedagogically important.

## Recommended Instructor Framing

Emphasize:

"At the beginning of the course, we intentionally simplified the tooling so that you could focus on programming.

Now you understand enough to control the workflow directly."

Students often find this empowering.

## Suggested Live Questions

- What does `origin` mean?
- Why are branches useful?
- What does `git status` actually tell you?
- Why do professional developers still use terminals?
- What advantages does the command line provide?

## Common Problems

### `gh` not found

GitHub CLI is not installed or not on PATH.

### `git push` permission problems

Usually fixed automatically by:

```bash
gh auth login
```

### Wrong repository

Students may accidentally be inside the wrong directory.

Use:

```bash
pwd
```

and:

```bash
git remote -v
```

## Suggested Final Discussion

The terminal is not "old technology."

It is:
- composable
- automatable
- scriptable
- universal

Many professional development workflows are still fundamentally command-line based.
