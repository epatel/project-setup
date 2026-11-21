# Add AI-runnable setup instructions to a project

> **You are a coding agent.** A user sent you to this page. The user wants
> you to add *project-setup* to the current repository. Do the steps below.
> Do not make a commit. Do not push. At the end, show the result to the user.

## The files that you add

- `setup-todo-list.md`: This file is in the repository. It contains the setup steps of the project. Each step has a gate (`auto`, `approve` or `input`) and a `check` command. The `check` command does not change files.
- `setup-todo-list.local.md`: This file is not in the repository. It contains the setup progress of one developer. It has one line for each step. An agent writes the lines during the setup.
- `.claude/skills/project-setup/`: This folder contains a skill. With the skill, Claude Code users get the command `/project-setup` (run, doctor, author). Other agents use the instructions at the start of the list.

## Step 1: Install the skill files

Download the two files below into the repository. Keep the paths.

| Save as | Download from |
|---|---|
| `.claude/skills/project-setup/SKILL.md` | https://raw.githubusercontent.com/epatel/project-setup/v1.1.1/skills/project-setup/SKILL.md |
| `.claude/skills/project-setup/references/format.md` | https://raw.githubusercontent.com/epatel/project-setup/v1.1.1/skills/project-setup/references/format.md |

If you cannot write the files, read the two files from the URLs. Then continue.

## Step 2: Do the author mode of the skill

1. Read `references/format.md`.
2. Read the section **Mode: author** in `SKILL.md`.
3. Do all the instructions in that section.

In summary, the author mode tells you to do these tasks:

- Find all the setup steps of the project. Include the steps that the README does not show.
- Write `setup-todo-list.md`. Start the file with the agent instructions from format.md.
- Add the local progress file to `.gitignore`.
- Update the setup section of the README.

## Step 3: Show the result to the user

1. Show the table of steps to the user.
2. Tell the user which steps the README did not show or showed incorrectly.
3. Show the list of files that you made or changed.
4. Ask the user if you must do the setup on this computer now. Use `/project-setup`, or do the steps in the list.

Do not make a commit if the user does not tell you to make one.
