"""Download the LangGraph v1.0 docs corpus as raw markdown.

Source of truth: the curated `docs/llms.txt` from the langchain-ai/langgraph repo,
pinned to a fixed tag (reproducible). Each entry links to a page on
docs.langchain.com; that site (Mintlify) serves clean markdown when you append
`.md` to the URL — headings + code blocks intact, exactly what heading-based
chunking needs in Phase 1.

Output:
  ai/data/raw/<slug>.md      one markdown file per doc page
  ai/data/manifest.json      provenance: pinned version, source, per-file sizes

Usage (from ai/):  python -m scripts.fetch_corpus
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import truststore

truststore.inject_into_ssl()  # OS trust store (corporate/local CA on this machine)

import httpx  # noqa: E402

# Pin the docs to a specific LangGraph v1.0 release tag for reproducibility.
DOCS_VERSION = "1.0.10"
LLMS_TXT_URL = (
    f"https://raw.githubusercontent.com/langchain-ai/langgraph/{DOCS_VERSION}/docs/llms.txt"
)

# Only fetch pages from the docs site (the API reference / langsmith links point
# at other hosts and are recorded but not downloaded in Phase 0).
DOCS_HOST = "https://docs.langchain.com"

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAW_DIR = DATA_DIR / "raw"
MANIFEST = DATA_DIR / "manifest.json"

LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def slug_for(url: str) -> str:
    """Last path segment of the URL → filename slug."""
    return url.rstrip("/").split("/")[-1] or "index"


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    with httpx.Client(follow_redirects=True, timeout=30) as client:
        index_md = client.get(LLMS_TXT_URL).raise_for_status().text

        # Parse "[title](url)" links; keep docs-site pages, dedupe by URL.
        seen: set[str] = set()
        entries: list[dict] = []
        skipped: list[dict] = []
        for title, url in LINK_RE.findall(index_md):
            if url in seen:
                continue
            seen.add(url)
            record = {"title": title.strip(), "url": url}
            if url.startswith(DOCS_HOST):
                entries.append(record)
            else:
                skipped.append({**record, "reason": "external host (not fetched)"})

        files: list[dict] = []
        for e in entries:
            md_url = e["url"].rstrip("/") + ".md"
            slug = slug_for(e["url"])
            try:
                text = client.get(md_url).raise_for_status().text
            except httpx.HTTPStatusError as exc:
                # A page may not expose a .md variant (renamed/removed); skip it
                # so one bad URL doesn't abort the whole corpus download.
                skipped.append({**e, "md_url": md_url,
                                "reason": f"HTTP {exc.response.status_code}"})
                print(f"  SKIP  {slug} ({exc.response.status_code})")
                continue
            out = RAW_DIR / f"{slug}.md"
            out.write_text(text, encoding="utf-8")
            files.append(
                {
                    "title": e["title"],
                    "slug": slug,
                    "url": e["url"],
                    "md_url": md_url,
                    "path": str(out.relative_to(DATA_DIR.parent)),
                    "bytes": len(text.encode("utf-8")),
                }
            )
            print(f"  saved {slug}.md ({len(text):,} chars)")

    manifest = {
        "corpus": "LangGraph documentation",
        "docs_version": DOCS_VERSION,
        "source_index": LLMS_TXT_URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "doc_count": len(files),
        "total_bytes": sum(f["bytes"] for f in files),
        "files": files,
        "skipped": skipped,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"\nDone: {len(files)} docs, "
        f"{manifest['total_bytes'] / 1024:.0f} KB -> {RAW_DIR}"
    )
    if skipped:
        print(f"Skipped {len(skipped)} external link(s): "
              + ", ".join(s["title"] for s in skipped))
    print(f"Manifest: {MANIFEST}")


if __name__ == "__main__":
    sys.exit(main())
