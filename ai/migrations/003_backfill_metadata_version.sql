-- Mirror docs_version into chunks.metadata for rows that predate the column.
--
-- 002 added the first-class docs_version column with DEFAULT '1.0', which
-- backfilled the existing v1.0 rows correctly. Ingest also mirrors the value
-- into metadata so code that only reads metadata needs no change — but the 244
-- v1.0 chunks were deliberately NOT re-ingested (re-embedding costs money), so
-- only the v0.2 rows carried the mirrored key.
--
-- That left a trap: "metadata has no docs_version" silently meant "1.0", a
-- special case every metadata reader would have to remember. Backfilling is a
-- pure UPDATE — it touches no embedding — so the invariant becomes simple:
-- every chunk carries docs_version in both the column and metadata.
--
-- Idempotent: the WHERE clause skips rows that already have the key.

UPDATE chunks
SET metadata = metadata || jsonb_build_object('docs_version', docs_version)
WHERE NOT (metadata ? 'docs_version');
