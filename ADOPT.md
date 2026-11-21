# Add AI-runnable setup instructions to a project

> **You are a coding agent.** A user pointed you here to add *project-setup*
> to the repository you're working in. Follow the steps below. Don't commit or
> push anything. Show the user the result for review at the end.

## What you're adding

- `setup-todo-list.md` (committed): the project's setup steps, each with a gate (`auto` / `approve` / `input`) and a read-only `check` command.
- `setup-todo-list.local.md` (gitignored): each developer's progress, one line per step, written by an agent during setup.
- `.claude/skills/project-setup/`: a skill so Claude Code users get `/project-setup` (run, doctor, author). Other agents follow the list from the instructions built into it.

## Step 1: Install the skill files

Download these files into the repo, keeping the paths:

| Save as | Download from |
|---|---|
| `.claude/skills/project-setup/SKILL.md` | https://raw.githubusercontent.com/epatel/project-setup/v1.1.1/skills/project-setup/SKILL.md |
| `.claude/skills/project-setup/references/format.md` | https://raw.githubusercontent.com/epatel/project-setup/v1.1.1/skills/project-setup/references/format.md |

If you can't write files there, read both files from the URLs instead and continue.

## Step 2: Follow author mode

Read `references/format.md`, then follow **Mode: author** in `SKILL.md` from start to finish: gather, draft, wire up, hand over. In short:
- Work out what setup really involves, including what the README leaves out.
- Write `setup-todo-list.md` starting with the canonical agent block.
- Gitignore the local progress file.
- Update the README's setup section.

## Step 3: Hand over

Show the user the step table, anything the README left out or got wrong, and the files you created or changed. Then offer to run the setup on this machine (`/project-setup`, or follow the list). Don't commit unless the user asks.
