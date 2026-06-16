"""Phase 0 Definition-of-Done proof:
  1. Insert one document + one chunk WITH an embedding.
  2. Run a cosine-similarity query and print the nearest chunk.

Usage (from ai/):  python -m scripts.seed_chunk

If EMBEDDING_API_KEY is unset, a deterministic fake embedding is used so this
runs offline (it still exercises the pgvector insert + <=> cosine query path).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import get_connection, vector_literal  # noqa: E402
from app.embeddings import embed  # noqa: E402

SAMPLE = {
    "title": "LangGraph — Graph basics",
    "source_url": "https://langchain-ai.github.io/langgraph/concepts/low_level/",
    "content": (
        "In LangGraph v1.0 you connect the entry point with "
        "add_edge(START, 'node_name'); the older set_entry_point() helper is "
        "deprecated. A StateGraph defines nodes and edges over a shared state."
    ),
}


def main() -> None:
    query = "How do I set the entry point of a LangGraph graph in v1.0?"

    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1) Insert the document.
            cur.execute(
                """
                INSERT INTO documents (source_url, title)
                VALUES (%s, %s)
                RETURNING id
                """,
                (SAMPLE["source_url"], SAMPLE["title"]),
            )
            doc_id = cur.fetchone()[0]

            # 2) Insert the chunk with its embedding (text literal -> ::vector).
            emb = embed(SAMPLE["content"])
            cur.execute(
                """
                INSERT INTO chunks (document_id, content, embedding, metadata)
                VALUES (%s, %s, %s::vector, %s)
                RETURNING id
                """,
                (
                    doc_id,
                    SAMPLE["content"],
                    vector_literal(emb),
                    '{"section": "Graph basics"}',
                ),
            )
            chunk_id = cur.fetchone()[0]
            conn.commit()
            print(f"Inserted document id={doc_id}, chunk id={chunk_id}")

            # 3) Cosine-similarity query. <=> is cosine distance; 1 - distance
            #    gives similarity in [-1, 1] (higher = closer).
            q_emb = embed(query)
            cur.execute(
                """
                SELECT id,
                       LEFT(content, 60) AS preview,
                       1 - (embedding <=> %s::vector) AS cosine_similarity
                FROM chunks
                ORDER BY embedding <=> %s::vector
                LIMIT 3
                """,
                (vector_literal(q_emb), vector_literal(q_emb)),
            )
            print(f"\nTop matches for: {query!r}")
            for row in cur.fetchall():
                print(f"  chunk {row[0]}  sim={row[2]:.4f}  {row[1]}...")


if __name__ == "__main__":
    main()
