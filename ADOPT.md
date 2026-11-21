# Add AI-runnable setup instructions to a project

> **You are a coding agent.** A user pointed you here to add *project-setup*
> to the repository you're working in. Follow the steps below in order. Don't
> commit or push anything. Show the user the result for review at the end.
> This is version **v1** of these instructions.

## What you're adding

- `setup-todo-list.md` (committed): the project's setup steps. Each step has a stable `[id]`, a `rev`, a `gate` (`auto` / `approve` / `input`), a `required` flag and a read-only `check` command.
- `setup-todo-list.local.md` (gitignored): each developer's progress, written by an agent during setup.
- `.claude/skills/project-setup/`: a skill so Claude Code users get `/project-setup` (run, doctor, author). Other agents can follow the list from its built-in instructions.

## Step 1: Install the skill files

Download these files into the repo, keeping the paths:

| Save as | Download from |
|---|---|
| `.claude/skills/project-setup/SKILL.md` | https://raw.githubusercontent.com/epatel/project-setup/v1/skills/project-setup/SKILL.md |
| `.claude/skills/project-setup/references/format.md` | https://raw.githubusercontent.com/epatel/project-setup/v1/skills/project-setup/references/format.md |

If you can't download files, tell the user and skip this step. The setup list works without the skill.

## Step 2: Read the format

Read `.claude/skills/project-setup/references/format.md`, or the URL above if step 1 was skipped. It defines the step fields and gates. Then read the **author** section of `SKILL.md`. Steps 3–5 below summarise it.

## Step 3: Gather what setup really involves

Read the README, CONTRIBUTING, docs/, Makefile / package.json scripts, version files (`.tool-versions`, `.nvmrc`, `pubspec.yaml`, `go.mod`, …), Dockerfiles, `.env.example`, and CI config. CI shows what the project really needs.

Look especially for setup the README leaves out:
- path dependencies and sibling checkouts (`path: ../…`), git submodules
- config files the build needs that aren't in the repo, secrets, API keys
- per-developer config switching (e.g. `make set_*_config`)
- README steps that are outdated. Point these out rather than copying them.

Don't run installs while gathering. Read-only commands like `--version` are fine.

## Step 4: Write `setup-todo-list.md`

At the repo root, using format v1:
- start with the frontmatter (`setup-format: 1`, `project:`) and the agent instructions blockquote from format.md
- one step per verifiable outcome, with a fast, read-only `check` wherever possible
- gates chosen conservatively: `auto` only for read-only or project-local, reversible steps. Anything global, `sudo`, or with side effects is `approve`.
- sensitive inputs marked `(secret)`, never with real values
- stable kebab-case ids, every step at `rev: 1`

## Step 5: Wire it up

1. Add to `.gitignore`:
   ```
   # Local setup progress (project-setup)
   setup-todo-list.local.md
   ```
2. Add or replace the README's setup section with:
   ```markdown
   ### Setup
   Setup steps live in [`setup-todo-list.md`](setup-todo-list.md). An AI agent can run them, and every step also reads as plain manual instructions.
   With Claude Code: `/project-setup` (set up) · `/project-setup doctor` (re-check after a pull that changed the list).
   With any other agent: *"Set up this project using setup-todo-list.md"*.
   ```
   Keep a short manual command summary under it if the old README had one, corrected for anything you found to be outdated.
3. If the repo has `CLAUDE.md` or `AGENTS.md`, add one line:
   `Project setup lives in setup-todo-list.md. Don't run setup doctor unless asked; suggest it if a failure looks like missing tooling.`

## Step 6: Hand over

Show the user:
- the step table (id, title, gate, required, check)
- anything the README left out, and any outdated README steps you corrected
- the files you created or changed

Then offer to run the setup on this machine (`/project-setup`, or follow the list). Don't commit unless the user asks.
