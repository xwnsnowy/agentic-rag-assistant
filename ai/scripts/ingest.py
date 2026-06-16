"""Ingest the LangGraph corpus into Postgres: chunk -> embed -> upsert.

Reads data/manifest.json, chunks each raw markdown file by heading, embeds every
chunk, and writes documents + chunks rows. Idempotent: it resets the tables first
so re-running gives a clean, reproducible corpus (e.g. after adding a real
embedding key).

Usage (from ai/):  python -m scripts.ingest
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chunking import chunk_markdown  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import get_connection, vector_literal  # noqa: E402
from app.embeddings import embed_many  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAW_DIR = DATA_DIR / "raw"
MANIFEST = DATA_DIR / "manifest.json"
EMBED_BATCH = 64


def main() -> None:
    settings = get_settings()
    using_real = bool(settings.embedding_api_key)
    print(
        f"Embeddings: {'REAL ' + settings.embedding_model if using_real else 'FAKE (offline) - set EMBEDDING_API_KEY for real vectors'}"
    )

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Idempotent reset: clean slate for a full corpus re-ingest.
            cur.execute("TRUNCATE chunks, documents RESTART IDENTITY CASCADE")

            total_chunks = 0
            for f in manifest["files"]:
                md = (RAW_DIR / f"{f['slug']}.md").read_text(encoding="utf-8")
                chunks = chunk_markdown(md, source_url=f["url"], page_title=f["title"])
                if not chunks:
                    continue

                cur.execute(
                    "INSERT INTO documents (source_url, title, metadata) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (f["url"], f["title"], json.dumps({"slug": f["slug"]})),
                )
                doc_id = cur.fetchone()[0]

                # Embed in batches, then insert chunk rows.
                for start in range(0, len(chunks), EMBED_BATCH):
                    batch = chunks[start : start + EMBED_BATCH]
                    vectors = embed_many([c.content for c in batch])
                    rows = [
                        (
                            doc_id,
                            c.content,
                            vector_literal(v),
                            json.dumps(
                                {
                                    "page_title": c.page_title,
                                    "section": c.section,
                                    "heading": c.heading,
                                    "source_url": c.source_url,
                                    "slug": f["slug"],
                                    "chunk_index": c.chunk_index,
                                }
                            ),
                        )
                        for c, v in zip(batch, vectors)
                    ]
                    cur.executemany(
                        "INSERT INTO chunks (document_id, content, embedding, metadata) "
                        "VALUES (%s, %s, %s::vector, %s)",
                        rows,
                    )
                total_chunks += len(chunks)
                print(f"  {f['slug']:>18}: {len(chunks):>3} chunks")

            conn.commit()

            cur.execute("SELECT count(*) FROM chunks")
            db_count = cur.fetchone()[0]

    print(f"\nIngested {total_chunks} chunks across {len(manifest['files'])} docs.")
    print(f"chunks table now holds {db_count} rows.")
    if not using_real:
        print("NOTE: vectors are FAKE - re-run after setting EMBEDDING_API_KEY for real retrieval.")


if __name__ == "__main__":
    main()
