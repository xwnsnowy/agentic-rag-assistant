"""Run the migration workbench on a Python file from the CLI.

Usage (from ai/):
  python -m scripts.migrate_ask path/to/snippet.py

Consistent with ask.py / agent_ask.py: a thin CLI mirror of the endpoint so
the graph can be exercised without the web stack.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import observability as obs  # noqa: E402
from app.migrate import run_migrate  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m scripts.migrate_ask path/to/snippet.py")
        raise SystemExit(2)
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"not a file: {path}")
        raise SystemExit(2)

    # utf-8-sig: Windows editors (and PowerShell's utf8 Set-Content) prepend a
    # BOM, which is invisible in the file but breaks ast.parse on the string.
    res = run_migrate(path.read_text(encoding="utf-8-sig"))
    obs.flush()

    # cp1252 consoles must never crash the report (arrows/checkmarks in docs text).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    if res.error:
        print(f"rejected: {res.error}")
        raise SystemExit(1)

    print(f"findings  : {[(f['symbol'], f['status']) for f in res.findings] or 'none'}")
    print(f"attempts  : {res.attempts}  verified: {res.verified}")
    if res.changes:
        print("\nchanges:")
        for c in res.changes:
            marks = "".join(f"[{n}]" for n in c["citations"])
            print(f"  - {c['description']} {marks}".rstrip())
    if res.caveats:
        print("\ncaveats:")
        for cv in res.caveats:
            print(f"  - {cv}")
    if res.citations:
        print("\nsources:")
        for s in res.citations:
            print(f"  [{s['n']}] {s['page_title']} — {s['heading']} ({s['source_url']})")
    print("\n" + (res.diff if res.diff else "no changes — code returned unchanged"))


if __name__ == "__main__":
    main()
