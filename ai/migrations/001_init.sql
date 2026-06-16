-- Phase 0 schema: pgvector + documents + chunks
-- Idempotent: safe to run multiple times.

-- 1) Enable pgvector (Neon: extension is available, just needs enabling).
CREATE EXTENSION IF NOT EXISTS vector;

-- 2) documents: one row per source doc (a LangGraph docs page).
--    chunks reference this so we can trace a chunk back to its page.
CREATE TABLE IF NOT EXISTS documents (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_url  TEXT,
    title       TEXT,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3) chunks: the retrieval unit. embedding dim must match the embedding model
--    (text-embedding-3-small = 1536). tsv powers the keyword side of hybrid
--    search in Phase 1 (Reciprocal Rank Fusion of pgvector + full-text).
CREATE TABLE IF NOT EXISTS chunks (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id BIGINT REFERENCES documents(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    embedding   vector(1536),
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4) Indexes.
-- Full-text (GIN) for the keyword side of hybrid search.
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING GIN (tsv);

-- Vector ANN index. HNSW with cosine distance (vector_cosine_ops) matches the
-- <=> operator we query with. Built now; fine for the small Phase 0 corpus and
-- scales into Phase 1.
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
