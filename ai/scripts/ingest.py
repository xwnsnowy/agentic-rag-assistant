"""Ingest one version of the LangGraph corpus into Postgres: chunk -> embed -> upsert.

Per-version replacement, not a global reset: `DELETE FROM documents WHERE
docs_version = %s` (the FK cascade clears that version's chunks), then
re-insert that version only. Idempotent at version granularity — re-running
`--docs-version 0.2` can never touch the v1.0 rows or their (paid-for)
embeddings. The old whole-corpus TRUNCATE survives behind the explicit
`--all` flag as a deliberate escape hatch; it re-embeds EVERYTHING, so it
costs real money and should be rare.

docs_version is written to the first-class column on documents+chunks (the
retrieval filter) and mirrored into chunks.metadata so eval code that only
reads metadata needs no change.

Usage (from ai/):
  python -m scripts.ingest                     # v1.0 (default)
  python -m scripts.ingest --docs-version 0.2  # v0.2 only, v1.0 untouched
  python -m scripts.ingest --all               # full reset: truncate + every version
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chunking import chunk_markdown  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import get_connection, vector_literal  # noqa: E402
from app.embeddings import embed_many  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
EMBED_BATCH = 64

# label -> (manifest, raw dir, mkdocs-material preprocessing?)
VERSIONS: dict[str, dict] = {
    "1.0": {"manifest": DATA_DIR / "manifest.json", "raw": DATA_DIR / "raw", "mkdocs": False},
    "0.2": {"manifest": DATA_DIR / "manifest-0.2.json", "raw": DATA_DIR / "raw-0.2", "mkdocs": True},
}


def ingest_version(cur, version: str, *, manifest_path: Path, raw_dir: Path, mkdocs: bool) -> int:
    """Replace one docs_version inside an open transaction. Returns chunk count.

    Kept as a function taking a cursor so the throwaway-label safety check in
    the S2.0 verification could exercise the exact DELETE+INSERT path.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Per-version replacement: documents cascade-deletes this version's chunks.
    cur.execute("DELETE FROM documents WHERE docs_version = %s", (version,))

    total_chunks = 0
    for f in manifest["files"]:
        md = (raw_dir / f"{f['slug']}.md").read_text(encoding="utf-8")
        chunks = chunk_markdown(md, source_url=f["url"], page_title=f["title"], mkdocs=mkdocs)
        if not chunks:
            continue

        cur.execute(
            "INSERT INTO documents (source_url, title, metadata, docs_version) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (f["url"], f["title"], json.dumps({"slug": f["slug"]}), version),
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
                            # Mirrored so metadata-only readers (eval) see it too.
                            "docs_version": version,
                        }
                    ),
                    version,
                )
                for c, v in zip(batch, vectors)
            ]
            cur.executemany(
                "INSERT INTO chunks (document_id, content, embedding, metadata, docs_version) "
                "VALUES (%s, %s, %s::vector, %s, %s)",
                rows,
            )
        total_chunks += len(chunks)
        print(f"  {f['slug']:>18}: {len(chunks):>3} chunks")
    return total_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-version", choices=sorted(VERSIONS), default="1.0")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Full reset: TRUNCATE both tables and re-ingest every version. "
        "Re-embeds the whole corpus (costs money); the per-version default never does.",
    )
    args = parser.parse_args()

    settings = get_settings()
    using_real = bool(settings.embedding_api_key)
    print(
        f"Embeddings: {'REAL ' + settings.embedding_model if using_real else 'FAKE (offline) - set EMBEDDING_API_KEY for real vectors'}"
    )

    targets = sorted(VERSIONS) if args.all else [args.docs_version]

    with get_connection() as conn:
        with conn.cursor() as cur:
            if args.all:
                cur.execute("TRUNCATE chunks, documents RESTART IDENTITY CASCADE")

            total = 0
            for version in targets:
                spec = VERSIONS[version]
                print(f"\nIngesting docs_version={version}")
                total += ingest_version(
                    cur, version,
                    manifest_path=spec["manifest"], raw_dir=spec["raw"], mkdocs=spec["mkdocs"],
                )

            conn.commit()

            cur.execute("SELECT docs_version, count(*) FROM chunks GROUP BY 1 ORDER BY 1")
            print("\nchunks by docs_version:", cur.fetchall())

    print(f"Ingested {total} chunks for version(s): {', '.join(targets)}.")
    if not using_real:
        print("NOTE: vectors are FAKE - re-run after setting EMBEDDING_API_KEY for real retrieval.")


if __name__ == "__main__":
    main()
