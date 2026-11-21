# AI-runnable project setup

[![Audit](https://github.com/epatel/project-setup/actions/workflows/audit.yml/badge.svg)](https://github.com/epatel/project-setup/actions/workflows/audit.yml)

A convention, plus a Claude Code skill, for project setup instructions that an AI agent can run, resume, and re-check, much like `flutter doctor`.

```mermaid
flowchart LR
  M["setup-todo-list.md<br/>(committed, maintainers)"] -- copy on first run --> L["setup-todo-list.local.md<br/>(gitignored, per machine)"]
  L -- "agent runs steps<br/>records status @rev" --> L
  M -- "git pull brings new/changed steps" --> D{doctor}
  L --> D
  D --> R["[✓] ok  [✗] broken/drift<br/>[!] new/changed  [-] optional"]
```

## Add it to a project

Point any coding agent (Claude Code, Codex, Cursor, …) at the adoption instructions:

> See https://raw.githubusercontent.com/epatel/project-setup/main/ADOPT.md and add project setup instructions to this repo.

The agent copies the skill into `.claude/skills/project-setup/`, reads the repo to work out what setup really involves (including things the README leaves out), writes `setup-todo-list.md`, gitignores the local copy and updates the README. It doesn't commit anything; you review the result.

## Install the skill for yourself (Claude Code plugin)

So that `/project-setup` is available in every repo, including ones that haven't adopted it yet:

```
/plugin install project-setup --marketplace epatel/project-setup
```

Or from a shell: `claude plugin marketplace add epatel/project-setup && claude plugin install project-setup@epatel`. Update later with `claude plugin update project-setup@epatel`.

## The idea

- **`setup-todo-list.md`** is committed. Each step has a stable `[id]`, a `rev`, a `gate` (`auto` / `approve` / `input`), a `required` flag, and a read-only `check` command.
- **`setup-todo-list.local.md`** is a gitignored copy. The agent writes `status: done @rev2 2026-11-21` (or `skipped`, `failed`) under each step as it goes, so an interrupted setup can pick up where it stopped.
- **Doctor**: after a pull, the agent compares the two files by id and rev. That surfaces new steps, steps whose rev went up, and removed steps. It then re-runs every `check` to catch drift (e.g. a tool that was later uninstalled).
- **Secrets** go only into `.env` or similar, never into either list.
- The master file opens with a short blockquote of agent instructions, so it works with **any** coding agent. The skill just makes it more reliable.

The full spec is in [`skills/project-setup/references/format.md`](skills/project-setup/references/format.md). For a realistic master file, see [`examples/setup-todo-list.md`](examples/setup-todo-list.md).

## Usage (Claude Code)

| Say | Does |
|---|---|
| `/project-setup` or "set up this project" | Creates the local copy, shows the plan, runs the steps with their gates |
| `/project-setup doctor` or "check my setup" | Report only: new or changed steps plus drift |
| `/project-setup author` or "make a setup list for this repo" | Drafts `setup-todo-list.md` from the README, CI, `.env.example`, etc. |

With the plugin, the full name is `/project-setup:project-setup`. The short `/project-setup` works unless a repo's own copy of the skill uses the same name, in which case the repo's copy wins.

## How often to run doctor

Rarely. Setup steps seldom change, and the agent is told never to run doctor on its own.

- **Normally:** only when you ask for it.
- **Cheap skip:** the local copy records `master-commit`, the master's last commit hash at the last sync. If `git log -1 --format=%h -- setup-todo-list.md` still matches and there are no uncommitted edits, the agent stops there.
- **After a pull**, an optional hook that costs nothing unless the list file changed:

  ```bash
  # .githooks/post-merge
  git diff --quiet ORIG_HEAD HEAD -- setup-todo-list.md ||
    echo "setup-todo-list.md changed — consider: setup doctor"
  ```

`check` commands come from the repo and run through your shell. On a repo you don't trust, read them before letting an agent run doctor.

## Maintainer rules

- Never reuse or rename an `id`. Retire it and add a new one instead.
- Bump `rev` when a step's meaning changes (new minimum version, different command). Don't bump it for wording fixes.
- Every `check` must be read-only, fast, and exit 0 when the step is satisfied.
- `auto` is only for read-only or project-local, reversible steps. Anything global, `sudo`, or networked-with-side-effects is `approve`.

## Repository layout and releases

```
.claude-plugin/        plugin.json + marketplace.json (this repo is both)
skills/project-setup/  the skill (SKILL.md, references/format.md)
ADOPT.md               instructions an agent follows to adopt this in a repo
examples/              sample setup-todo-list.md
.github/               audit workflow + script (CI only)
```

The audit workflow runs on every push, on pull requests, and weekly. It checks the example lists against format v1 (including `bash -n` on every `check`), the skill frontmatter, the manifests (`claude plugin validate --strict`), relative links, and that ADOPT.md's download URLs resolve.

ADOPT.md downloads the skill from the **`v1`** tag, so adopting projects don't pick up unreleased changes. To release: bump `version` in `.claude-plugin/plugin.json`, tag `vX.Y.Z`, and move `v1` (`git tag -f v1 && git push -f origin v1`). Use a new major tag only if the setup-todo-list format changes incompatibly.
