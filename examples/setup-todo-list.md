---
setup-format: 1
project: example-flutter-app
---

# Project setup

> **Agents:** copy this file to `setup-todo-list.local.md` (it is gitignored)
> and work through the steps in order. In the copy, add `- status: done @revN <date>`
> (or `skipped` / `failed` with a reason) under each step as you go.
> Respect `gate`: `auto` = just run it, `approve` = show the commands and
> wait for a yes, `input` = ask for the listed values first. Never write secrets
> into either file. To re-check later ("doctor"), compare the copy with this file
> by step id and `rev`, and re-run each `check` command.
>
> **Humans:** every step below is plain instructions. Follow them by hand if you prefer.

## [git-hooks] Install git hooks
- required: yes
- gate: auto
- rev: 1
- check: `test "$(git config core.hooksPath)" = ".githooks"`

Point git at the repo's hooks: `git config core.hooksPath .githooks`

## [flutter-sdk] Install Flutter SDK 3.24+
- required: yes
- gate: approve
- rev: 2
- check: `flutter --version 2>/dev/null | grep -Eq "Flutter 3\.(2[4-9]|[3-9][0-9])"`

macOS: `brew install --cask flutter`. Linux: follow https://docs.flutter.dev/get-started/install/linux.
(rev 2: minimum raised from 3.19 to 3.24.)

## [cocoapods] Install CocoaPods
- required: yes
- gate: approve
- rev: 1
- platforms: macos
- depends: flutter-sdk
- check: `command -v pod`

`brew install cocoapods`

## [pub-get] Fetch Dart dependencies
- required: yes
- gate: auto
- rev: 1
- depends: flutter-sdk
- check: `test .dart_tool/package_config.json -nt pubspec.lock`

`flutter pub get`

## [env-file] Create .env
- required: yes
- gate: input
- rev: 1
- inputs: API_BASE_URL — "Backend URL (default https://staging.example.com)", API_KEY (secret) — "Staging API key, ask in #backend"
- check: `grep -q '^API_KEY=.' .env && grep -q '^API_BASE_URL=.' .env`

Copy `.env.example` to `.env` and fill in the values.

## [firebase-cli] Install Firebase CLI (for push notification work)
- required: no
- gate: approve
- rev: 1
- check: `command -v firebase`

`npm install -g firebase-tools`, then `firebase login` (interactive: ask the user to run it with `! firebase login`).

## [vpn-access] Request VPN access
- required: no
- gate: approve
- rev: 1
- check: manual

Only needed to hit the internal staging DB. File a ticket at https://it.example.com/vpn. The agent can't do this step; ask the user to confirm once it's done.
