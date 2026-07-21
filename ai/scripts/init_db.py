"""Apply every migrations/*.sql against DATABASE_URL, in filename order.

Simplest runner that works: every migration file is idempotent (IF NOT EXISTS
everywhere), so we just re-apply all of them on each run — no schema_migrations
bookkeeping table, no Alembic. That trade-off holds as long as migrations stay
idempotent; revisit only if one ever can't be.

Usage (from ai/):  python -m scripts.init_db
"""

import sys
from pathlib import Path

# Allow running as `python -m scripts.init_db` from the ai/ root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_connection  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def main() -> None:
    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migrations:
        raise SystemExit(f"No .sql files found in {MIGRATIONS_DIR}")
    with get_connection() as conn:
        with conn.cursor() as cur:
            for path in migrations:
                cur.execute(path.read_text(encoding="utf-8"))
                print(f"Applied migration: {path.name}")
        conn.commit()


if __name__ == "__main__":
    main()
