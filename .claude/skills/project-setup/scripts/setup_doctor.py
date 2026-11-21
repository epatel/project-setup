#!/usr/bin/env python3
"""Deterministic doctor for setup-todo-list.md (format v1).

Compares the committed master list with the gitignored local copy, runs each
step's read-only `check` command, and prints a flutter-doctor-style report.

Usage:
  setup_doctor.py [--root DIR] [--json] [--no-checks] [--reconcile] [--timeout S]

  --root DIR    project root containing setup-todo-list.md (default: cwd)
  --json        machine-readable output (for agents)
  --no-checks   don't execute check commands (structure comparison only)
  --reconcile   rewrite setup-todo-list.local.md to match the master: add new
                steps as pending, mark removed steps obsolete, refresh fields
                and text from master, keep status/answer lines, set
                last-doctor. Creates the local copy if it is missing. Never
                marks a step done.
  --timeout S   per-check timeout in seconds (default 30)

Exit codes: 0 all good · 1 issues ([✗]) · 2 only updates ([!]) · 3 usage/parse error

Security: check commands come from the repository and run through the shell.
Use --no-checks on repositories you don't trust.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

MASTER_NAME = "setup-todo-list.md"
LOCAL_NAME = "setup-todo-list.local.md"
SUPPORTED_FORMAT = "1"
LOCAL_ONLY_FIELDS = {"status", "answer"}

STEP_RE = re.compile(r"^## \[([A-Za-z0-9][A-Za-z0-9_-]*)\]\s*(.*?)\s*$")
FIELD_RE = re.compile(r"^- ([a-z][a-z0-9_-]*):\s*(.*?)\s*$")
STATUS_RE = re.compile(
    r"^(?P<state>done|skipped|failed|pending|n/a|obsolete)"
    r"(?:\s+@rev(?P<rev>\d+))?"
    r"(?:\s+(?P<date>\d{4}-\d{2}-\d{2}))?"
    r"(?:\s+[—-]+\s+\"?(?P<note>.*?)\"?)?\s*$"
)
FENCE_RE = re.compile(r"^\s*(```|~~~)")

TODAY = dt.date.today().isoformat()


class ParseError(Exception):
    pass


# --------------------------------------------------------------------------- parsing


@dataclass
class Step:
    id: str
    title: str
    header: str
    field_lines: list[str]          # raw "- key: value" lines, in order
    fields: dict[str, str]          # first value per key (answers kept separately)
    answers: list[str]
    body: list[str]                 # everything after the field block

    @property
    def rev(self) -> int:
        try:
            return int(self.fields.get("rev", "1"))
        except ValueError:
            raise ParseError(f"[{self.id}] rev must be an integer, got {self.fields['rev']!r}")

    @property
    def required(self) -> bool:
        return self.fields.get("required", "yes").lower() not in {"no", "false", "optional"}

    @property
    def gate(self) -> str:
        return self.fields.get("gate", "approve")

    @property
    def check(self) -> str | None:
        raw = self.fields.get("check", "manual").strip()
        if raw.lower() in {"manual", "", "—", "-"}:
            return None
        m = re.fullmatch(r"`+(.*?)`+", raw)
        return m.group(1) if m else raw

    @property
    def platforms(self) -> set[str] | None:
        raw = self.fields.get("platforms", "").strip()
        if not raw or raw in {"—", "-", "all"}:
            return None
        return {p.strip().lower() for p in raw.split(",") if p.strip()}

    @property
    def depends(self) -> list[str]:
        raw = self.fields.get("depends", "").strip()
        if not raw or raw in {"—", "-"}:
            return []
        return [d.strip() for d in raw.split(",") if d.strip()]

    @property
    def status(self) -> dict | None:
        raw = self.fields.get("status")
        if raw is None:
            return None
        m = STATUS_RE.match(raw)
        if not m:
            raise ParseError(f"[{self.id}] unrecognised status line: {raw!r}")
        d = m.groupdict()
        d["rev"] = int(d["rev"]) if d["rev"] else None
        return d


@dataclass
class Doc:
    frontmatter: dict[str, str]
    fm_lines: list[str]
    preamble: list[str]
    steps: list[Step] = field(default_factory=list)

    def by_id(self) -> dict[str, Step]:
        return {s.id: s for s in self.steps}


def parse(path: Path) -> Doc:
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    fm: dict[str, str] = {}
    fm_lines: list[str] = []
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            fm_lines.append(lines[i])
            if ":" in lines[i]:
                k, v = lines[i].split(":", 1)
                fm[k.strip()] = v.strip()
            i += 1
        if i >= len(lines):
            raise ParseError(f"{path.name}: unterminated frontmatter")
        i += 1

    # split into preamble + step chunks, ignoring headings inside code fences
    preamble: list[str] = []
    chunks: list[list[str]] = []
    in_fence = False
    for line in lines[i:]:
        if FENCE_RE.match(line):
            in_fence = not in_fence
        if not in_fence and STEP_RE.match(line):
            chunks.append([line])
        elif chunks:
            chunks[-1].append(line)
        else:
            preamble.append(line)

    doc = Doc(fm, fm_lines, preamble)
    seen: set[str] = set()
    for chunk in chunks:
        m = STEP_RE.match(chunk[0])
        sid, title = m.group(1), m.group(2)
        if sid in seen:
            raise ParseError(f"{path.name}: duplicate step id [{sid}]")
        seen.add(sid)
        j = 1
        while j < len(chunk) and not chunk[j].strip():
            j += 1
        field_lines, fields, answers = [], {}, []
        while j < len(chunk) and (fm_ := FIELD_RE.match(chunk[j])):
            key, val = fm_.group(1), fm_.group(2)
            field_lines.append(chunk[j])
            if key == "answer":
                answers.append(chunk[j])
            else:
                fields.setdefault(key, val)
            j += 1
        doc.steps.append(Step(sid, title, chunk[0], field_lines, fields, answers, chunk[j:]))
    return doc


# --------------------------------------------------------------------------- checks


def current_platform() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def run_check(cmd: str, root: Path, timeout: float) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            cmd, shell=True, cwd=root, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"check timed out after {timeout:g}s"
    if r.returncode == 0:
        return True, ""
    tail = (r.stderr.strip() or r.stdout.strip()).splitlines()
    detail = tail[-1][:120] if tail else ""
    return False, f"check exited {r.returncode}" + (f": {detail}" if detail else "")


# --------------------------------------------------------------------------- doctor

SYMBOL = {"ok": "✓", "fail": "✗", "update": "!", "unverified": "~", "info": "-"}


def evaluate(master: Doc, local: Doc | None, root: Path, run_checks: bool, timeout: float) -> list[dict]:
    plat = current_platform()
    local_ids = local.by_id() if local else {}
    results: list[dict] = []

    for s in master.steps:
        ls = local_ids.get(s.id)
        st = ls.status if ls else None
        state = st["state"] if st else None
        srev = st["rev"] if st else None
        r = {
            "id": s.id, "title": s.title, "required": s.required, "gate": s.gate,
            "master_rev": s.rev, "local_status": state, "local_rev": srev,
            "check": s.check, "check_passed": None, "level": None, "reason": None, "note": None,
        }
        results.append(r)

        if s.platforms is not None and plat not in s.platforms:
            r.update(level="info", reason="n/a", note=f"not for {plat}")
            continue

        def check() -> bool | None:
            if not run_checks or s.check is None:
                return None
            ok, detail = run_check(s.check, root, timeout)
            r["check_passed"] = ok
            if not ok:
                r["check_detail"] = detail
            return ok

        if local is None or ls is None or state in (None, "obsolete"):
            ok = check()
            r.update(level="update", reason="new" if local is not None else "not-started",
                     note="new step" + (" (already satisfied)" if ok else "")
                     if local is not None else "setup not started" + (" (already satisfied)" if ok else ""))
            continue

        if state in ("done", "skipped") and (srev or 0) < s.rev:
            r.update(level="update", reason="changed",
                     note=f"changed upstream (rev {srev or '?'} → {s.rev})")
            continue

        if state == "done":
            ok = check()
            if ok is None:
                r.update(level="unverified" if s.check is None else "ok",
                         reason="manual" if s.check is None else "not-checked",
                         note="manual, unverified" if s.check is None else "done (checks skipped)")
            elif ok:
                r.update(level="ok", reason="ok")
            else:
                r.update(level="fail", reason="drift", note=f"drift: {r['check_detail']}")
            continue

        if state == "skipped":
            r.update(level="info", reason="skipped",
                     note="skipped" + (f' — "{st["note"]}"' if st.get("note") else ""))
            continue

        if state == "n/a":  # platform list changed so it now applies
            ok = check()
            r.update(level="update", reason="now-applies", note="now applies to this platform"
                     + (" (already satisfied)" if ok else ""))
            continue

        # pending / failed
        ok = check()
        if ok:
            r.update(level="ok", reason="satisfied-unrecorded",
                     note=f"satisfied, but status is {state}")
        elif s.required:
            extra = f' — "{st["note"]}"' if state == "failed" and st.get("note") else ""
            detail = f"; {r['check_detail']}" if r.get("check_detail") else ""
            r.update(level="fail", reason=state, note=f"not done ({state}{extra}){detail}")
        else:
            r.update(level="info", reason="optional", note="optional, not done")

    # removed upstream
    master_ids = master.by_id()
    for ls in (local.steps if local else []):
        if ls.id in master_ids:
            continue
        st = ls.status
        results.append({
            "id": ls.id, "title": ls.title, "required": ls.required, "gate": ls.gate,
            "master_rev": None, "local_status": st["state"] if st else None,
            "local_rev": st["rev"] if st else None, "check": None, "check_passed": None,
            "level": "info", "reason": "removed", "note": "removed upstream (obsolete)",
        })

    for r in results:
        r["symbol"] = SYMBOL[r["level"]]
    return results


def git_date(path: Path) -> str | None:
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%cs", "--", path.name],
                           cwd=path.parent, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def print_report(master: Doc, local: Doc | None, results: list[dict], master_path: Path, checks: bool) -> None:
    proj = master.frontmatter.get("project", master_path.parent.name)
    date = git_date(master_path)
    print(f"Project setup doctor — {proj}" + (f" (master updated {date})" if date else ""))
    if local is None:
        print(f"No {LOCAL_NAME} yet — setup has not been started.")
    if not checks:
        print("(check commands not run)")
    print()
    w = max((len(r["id"]) for r in results), default=0)
    for r in results:
        line = f"[{r['symbol']}] {r['id']:<{w}}  {r['title']}"
        if r["note"]:
            line += f" — {r['note']}"
        print(line)
    fails = sum(r["level"] == "fail" for r in results)
    updates = sum(r["level"] == "update" for r in results)
    print()
    if not fails and not updates:
        print("No issues found.")
    else:
        print(f"{fails} issue(s), {updates} update(s). Run \"/project-setup\" to resolve.")


# --------------------------------------------------------------------------- reconcile


def trimmed(body: list[str]) -> list[str]:
    body = list(body)
    while body and not body[-1].strip():
        body.pop()
    return body


def shared_fields(s: Step) -> list[str]:
    return [l for l in s.field_lines if FIELD_RE.match(l).group(1) not in LOCAL_ONLY_FIELDS]


def render_step(m: Step, status_line: str, answers: list[str]) -> list[str]:
    return [m.header, *shared_fields(m), status_line, *answers, *trimmed(m.body), ""]


def reconcile(master: Doc, local: Doc | None, local_path: Path) -> list[str]:
    """Rewrite the local copy from master, preserving progress. Returns change log."""
    changes: list[str] = []
    plat = current_platform()
    local_ids = local.by_id() if local else {}
    out: list[str] = ["---"]
    copied_at = (local.frontmatter.get("copied-at") if local else None) or TODAY
    for l in master.fm_lines:
        out.append(l)
    out += [f"local-copy-of: {MASTER_NAME}", f"copied-at: {copied_at}", f"last-doctor: {TODAY}", "---"]
    out += master.preamble

    for m in master.steps:
        ls = local_ids.get(m.id)
        st = ls.status if ls else None
        applies = m.platforms is None or plat in m.platforms
        if st and st["state"] not in ("obsolete",) and not (st["state"] == "n/a" and applies):
            status_line = f"- status: {ls.fields['status']}"
        elif not applies:
            status_line = "- status: n/a — platform"
            if not st or st["state"] != "n/a":
                changes.append(f"[{m.id}] marked n/a (platform)")
        else:
            status_line = "- status: pending"
            changes.append(f"[{m.id}] added as pending" if not st else f"[{m.id}] reset to pending")
        if ls and (ls.title != m.title or trimmed(ls.body) != trimmed(m.body)
                   or shared_fields(ls) != shared_fields(m)):
            changes.append(f"[{m.id}] refreshed from master")
        out += render_step(m, status_line, ls.answers if ls else [])

    master_ids = master.by_id()
    for ls in (local.steps if local else []):
        if ls.id in master_ids:
            continue
        st = ls.status
        if st and st["state"] == "obsolete":
            status_line = f"- status: {ls.fields['status']}"
        else:
            status_line = f"- status: obsolete — removed from master {TODAY}"
            changes.append(f"[{ls.id}] marked obsolete")
        out += render_step(ls, status_line, ls.answers)

    text = "\n".join(out).rstrip("\n") + "\n"
    if local is None:
        changes.insert(0, f"created {LOCAL_NAME}")
    local_path.write_text(text, encoding="utf-8")
    return changes


def gitignore_ok(root: Path) -> bool:
    try:
        r = subprocess.run(["git", "check-ignore", "-q", LOCAL_NAME], cwd=root,
                           capture_output=True, timeout=5)
        if r.returncode in (0, 1):
            return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        pass
    gi = root / ".gitignore"
    return gi.exists() and any(l.strip().lstrip("/") == LOCAL_NAME
                               for l in gi.read_text(encoding="utf-8").splitlines())


# --------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-checks", action="store_true")
    ap.add_argument("--reconcile", action="store_true")
    ap.add_argument("--timeout", type=float, default=30.0)
    a = ap.parse_args(argv)

    root = a.root.resolve()
    master_path, local_path = root / MASTER_NAME, root / LOCAL_NAME
    if not master_path.exists():
        print(f"error: {master_path} not found", file=sys.stderr)
        return 3
    try:
        master = parse(master_path)
        fmt = master.frontmatter.get("setup-format", SUPPORTED_FORMAT)
        if fmt != SUPPORTED_FORMAT:
            raise ParseError(f"{MASTER_NAME}: setup-format {fmt} not supported (expected {SUPPORTED_FORMAT})")
        for s in master.steps:
            _ = s.rev
            if "status" in s.fields:
                raise ParseError(f"{MASTER_NAME}: [{s.id}] has a status line — master must not hold progress")
            for d in s.depends:
                if d not in master.by_id():
                    raise ParseError(f"{MASTER_NAME}: [{s.id}] depends on unknown step [{d}]")
        local = parse(local_path) if local_path.exists() else None
        if local:
            for s in local.steps:
                _ = s.status
    except ParseError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3

    changes: list[str] = []
    if a.reconcile:
        changes = reconcile(master, local, local_path)
        local = parse(local_path)

    results = evaluate(master, local, root, not a.no_checks, a.timeout)
    ignored = gitignore_ok(root)
    fails = sum(r["level"] == "fail" for r in results)
    updates = sum(r["level"] == "update" for r in results)
    code = 1 if fails else 2 if updates else 0

    if a.json:
        json.dump({
            "project": master.frontmatter.get("project", root.name),
            "platform": current_platform(),
            "local_exists": local_path.exists(),
            "local_gitignored": ignored,
            "checks_run": not a.no_checks,
            "reconciled": a.reconcile,
            "reconcile_changes": changes,
            "summary": {"fail": fails, "update": updates,
                        "ok": sum(r["level"] == "ok" for r in results)},
            "steps": results,
            "exit_code": code,
        }, sys.stdout, indent=2, ensure_ascii=False)
        print()
    else:
        print_report(master, local, results, master_path, not a.no_checks)
        if changes:
            print("\nReconciled local copy:")
            for c in changes:
                print(f"  • {c}")
        if local_path.exists() and not ignored:
            print(f"\nwarning: {LOCAL_NAME} is not gitignored — add it to .gitignore")
    return code


if __name__ == "__main__":
    sys.exit(main())
