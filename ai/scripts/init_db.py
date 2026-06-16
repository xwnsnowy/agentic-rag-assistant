"""Apply migrations/001_init.sql against DATABASE_URL.

Usage (from ai/):  python -m scripts.init_db
"""

import sys
from pathlib import Path

# Allow running as `python -m scripts.init_db` from the ai/ root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_connection  # noqa: E402

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "001_init.sql"


def main() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    print(f"Applied migration: {MIGRATION.name}")


if __name__ == "__main__":
    main()
