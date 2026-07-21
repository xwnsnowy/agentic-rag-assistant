-- 002: make the corpus version-aware so LangGraph v0.2 docs can live beside v1.0.
-- Idempotent: safe to run multiple times.
--
-- Design decision: docs_version is a FIRST-CLASS INDEXED COLUMN, not a key in
-- the metadata JSONB. Version is a filter predicate on every retrieval query
-- (WHERE docs_version = %s), not descriptive metadata — it wants real planner
-- statistics and a cheap btree index, not a metadata->>'docs_version' text
-- extraction per row. The value is *also* mirrored into metadata at ingest
-- time so eval code that only reads metadata needs no change.
--
-- DEFAULT '1.0' backfills every existing row, which makes the deploy safe in
-- either order: code that predates the column ignores it; code that follows it
-- sees every pre-existing row correctly labelled as the v1.0 corpus it is.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS docs_version TEXT NOT NULL DEFAULT '1.0';

ALTER TABLE chunks
    ADD COLUMN IF NOT EXISTS docs_version TEXT NOT NULL DEFAULT '1.0';

CREATE INDEX IF NOT EXISTS chunks_docs_version_idx ON chunks (docs_version);
