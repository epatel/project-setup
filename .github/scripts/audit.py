#!/usr/bin/env python3
"""CI audit for this repo (not shipped to users).

Checks:
  1. every setup-todo-list*.md (except .local) follows format v1
  2. every check command is valid shell syntax (bash -n)
  3. each setup list's agent blockquote matches the canonical one in format.md
  4. example progress files (*.local.md) use the progress-line format
     (plugin, marketplace and SKILL.md are checked by `claude plugin validate`)
  5. relative links in *.md resolve
  6. raw.githubusercontent.com URLs in ADOPT.md point at files that exist here

Exit 1 with a list of problems, 0 when clean.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = "epatel/project-setup"
problems: list[str] = []


def bad(where: Path | str, msg: str) -> None:
    rel = where.relative_to(ROOT) if isinstance(where, Path) else where
    problems.append(f"{rel}: {msg}")


def frontmatter(text: str) -> dict[str, str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end < 0:
        return None
    fm = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def md_files() -> list[Path]:
    return [p for p in ROOT.rglob("*.md") if ".git" not in p.parts]


# --------------------------------------------------------------------- 1 + 2
STEP = re.compile(r"^## \[([^\]]*)\]\s*(.*)$")
FIELD = re.compile(r"^- ([a-z][a-z0-9_-]*):\s*(.*)$")
ALLOWED = {
    "gate": {"auto", "approve", "input"},
    "required": {"yes", "no"},
}
PLATFORMS = {"macos", "linux", "windows"}
KNOWN_FIELDS = {"required", "gate", "rev", "check", "inputs", "platforms", "depends"}


def audit_setup_list(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    fm = frontmatter(text)
    if not fm or fm.get("setup-format") != "1":
        bad(path, "frontmatter must contain 'setup-format: 1'")
    if "Agents:" not in text:
        bad(path, "missing the agent instructions blockquote")

    steps: dict[str, dict[str, str]] = {}
    cur = None
    in_fields = False
    in_fence = False
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        if in_fence:
            continue
        if m := STEP.match(line):
            cur = m.group(1)
            if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", cur):
                bad(path, f"line {n}: step id [{cur}] must be kebab-case")
            if cur in steps:
                bad(path, f"line {n}: duplicate step id [{cur}]")
            if not m.group(2).strip():
                bad(path, f"line {n}: step [{cur}] has no title")
            steps[cur] = {}
            in_fields = True
            continue
        if cur and in_fields:
            if m := FIELD.match(line):
                steps[cur][m.group(1)] = m.group(2)
            elif line.strip():
                in_fields = False

    if not steps:
        bad(path, "no steps found")
    for sid, f in steps.items():
        where = f"[{sid}]"
        for k in f:
            if k in ("status", "answer"):
                bad(path, f"{where} has a '{k}' line — progress belongs in the .local copy")
            elif k not in KNOWN_FIELDS:
                bad(path, f"{where} unknown field '{k}'")
        for k, allowed in ALLOWED.items():
            if k in f and f[k] not in allowed:
                bad(path, f"{where} {k}: '{f[k]}' not in {sorted(allowed)}")
        if not re.fullmatch(r"[1-9]\d*", f.get("rev", "1")):
            bad(path, f"{where} rev must be a positive integer")
        if "platforms" in f:
            extra = {p.strip() for p in f["platforms"].split(",")} - PLATFORMS
            if extra:
                bad(path, f"{where} unknown platforms {sorted(extra)}")
        for d in [d.strip() for d in f.get("depends", "").split(",")]:
            if d and d not in ("—", "-") and d not in steps:
                bad(path, f"{where} depends on unknown step [{d}]")
        if f.get("gate") == "input" and not f.get("inputs"):
            bad(path, f"{where} gate is input but no 'inputs' listed")
        chk = f.get("check", "manual")
        if chk != "manual":
            m = re.fullmatch(r"`(.+)`", chk)
            if not m:
                bad(path, f"{where} check must be `command` in backticks or 'manual'")
            else:
                r = subprocess.run(["bash", "-n", "-c", m.group(1)], capture_output=True, text=True)
                if r.returncode:
                    bad(path, f"{where} check is not valid shell: {r.stderr.strip()}")


# --------------------------------------------------------------------- 3 + 4
FORMAT = ROOT / "skills/project-setup/references/format.md"
PROGRESS = re.compile(
    r"^- ([a-z0-9]+(?:-[a-z0-9]+)*): (pending|n/a|(?:done|skipped|failed) @rev[1-9]\d* \d{4}-\d{2}-\d{2})( — .+)?$"
)


def blockquote(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if l.startswith(">"))


def audit_canonical_block(path: Path) -> None:
    canon = blockquote(FORMAT.read_text(encoding="utf-8"))
    if blockquote(path.read_text(encoding="utf-8")) != canon:
        bad(path, "agent blockquote differs from the canonical block in format.md")


def step_ids(path: Path) -> list[str]:
    return re.findall(r"^## \[([^\]]+)\]", path.read_text(encoding="utf-8"), re.M)


def audit_progress(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    fm = frontmatter(text) or {}
    for k in ("setup-progress", "master-commit", "last-doctor"):
        if k not in fm:
            bad(path, f"frontmatter missing '{k}'")
    seen = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("- "):
            m = PROGRESS.match(line)
            if not m:
                bad(path, f"line {n}: not a valid progress line: {line!r}")
            else:
                seen.append(m.group(1))
    master = path.with_name(path.name.replace(".local.md", ".md"))
    if master.exists():
        ids = step_ids(master)
        if missing := [i for i in ids if i not in seen]:
            bad(path, f"no progress line for steps {missing}")
        if extra := [i for i in seen if i not in ids]:
            bad(path, f"progress lines for unknown steps {extra}")


# --------------------------------------------------------------------- 5 + 6
LINK = re.compile(r"\]\(([^)\s]+)\)")
RAW = re.compile(rf"https://raw\.githubusercontent\.com/{re.escape(REPO)}/[^/\s]+/([^\s)`\"']+)")


def audit_links() -> None:
    for p in md_files():
        text = re.sub(r"^[ \t]*(```|~~~).*?^[ \t]*\1", "", p.read_text(encoding="utf-8"), flags=re.M | re.S)
        for target in LINK.findall(text):
            if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                continue
            path = target.split("#", 1)[0]
            if path and not (p.parent / path).exists():
                bad(p, f"broken relative link: {target}")
    adopt = ROOT / "ADOPT.md"
    if not adopt.exists():
        bad(adopt, "missing")
        return
    urls = RAW.findall(adopt.read_text(encoding="utf-8"))
    if not urls:
        bad(adopt, "no raw file URLs found")
    for rel in urls:
        if not (ROOT / rel).exists():
            bad(adopt, f"raw URL points at missing file: {rel}")


def main() -> int:
    lists = [p for p in md_files()
             if p.name.startswith("setup-todo-list") and not p.name.endswith(".local.md")]
    if not lists:
        bad("examples/", "no setup-todo-list*.md to audit")
    for p in lists:
        audit_setup_list(p)
        audit_canonical_block(p)
    for p in [p for p in md_files() if p.name.endswith(".local.md")]:
        audit_progress(p)
    audit_links()
    if problems:
        print(f"Audit found {len(problems)} problem(s):")
        for msg in problems:
            print(f"  ✗ {msg}")
        return 1
    print(f"Audit clean: {len(lists)} setup list(s), progress files, links.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
