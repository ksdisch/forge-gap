"""check_docs.py — a freshness check for the learning spine (docs/).

Run anytime:  uv run check_docs.py

This is a smoke alarm, not a commit gate — it never blocks your work. It catches the main
way the docs can fall behind the code:

  Coverage — every stage marked done (done) in docs/ROADMAP.md should have a matching
  "## S<n>" section in docs/LEARNING.md. A shipped-but-undocumented stage is a GAP.

It also prints, for your eye only, when source and docs were each last changed, so you can
judge whether the spine is keeping pace. The exit code is non-zero only on a coverage gap,
so this can be wired into CI later if you ever want the hard gate.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
ROADMAP = ROOT / "docs" / "ROADMAP.md"
LEARNING = ROOT / "docs" / "LEARNING.md"

# A roadmap row counts as "done" if it carries this marker; LEARNING sections look like "## S2 ...".
DONE_MARKER = "✅"  # the green check used in ROADMAP.md status column
STAGE = re.compile(r"\bS\d+\b")


def git(*args: str) -> str:
    """Run a git command in the repo and return its trimmed stdout (empty string on error)."""
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return out.stdout.strip()


def done_stages() -> list[str]:
    """Stage ids (e.g. 'S2') on rows marked done in docs/ROADMAP.md, in order."""
    stages: list[str] = []
    for line in ROADMAP.read_text(encoding="utf-8").splitlines():
        if DONE_MARKER in line:
            m = STAGE.search(line)
            if m:
                stages.append(m.group())
    return stages


def documented_stages() -> set[str]:
    """Stage ids that have a '## S<n>' section heading in docs/LEARNING.md."""
    text = LEARNING.read_text(encoding="utf-8")
    return set(re.findall(r"^##\s+(S\d+)\b", text, flags=re.MULTILINE))


def main() -> int:
    print("Learning-spine freshness check\n" + "-" * 31)

    for path in (ROADMAP, LEARNING):
        if not path.exists():
            print(f"  [FAIL] missing {path.relative_to(ROOT)}")
            return 1

    done = done_stages()
    documented = documented_stages()
    gaps: list[str] = []

    print("Coverage — every done stage is written up in LEARNING.md")
    for s in done:
        ok = s in documented
        print(f"  [{'ok  ' if ok else 'GAP '}] {s}")
        if not ok:
            gaps.append(f"{s} is marked done in ROADMAP.md but has no section in LEARNING.md")

    # For-your-eye-only recency (never fails the run): when did source vs docs last change?
    src_date = git("log", "-1", "--format=%cs", "--", "*.py") or "unknown"
    doc_date = git("log", "-1", "--format=%cs", "--", "docs/") or "unknown"
    print(f"\nRecency (FYI) — last source change: {src_date}  |  last docs change: {doc_date}")

    print("\n" + "-" * 31)
    if gaps:
        print(f"{len(gaps)} coverage gap(s) — the spine is behind the code:")
        for g in gaps:
            print(f"  - {g}")
        return 1
    print(f"Spine is current — all {len(done)} shipped stage(s) documented ({', '.join(done)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
