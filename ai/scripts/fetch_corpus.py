"""Download the LangGraph docs corpus as raw markdown — v1.0 or v0.2.

v1.0 (default): the curated `docs/llms.txt` from the langchain-ai/langgraph repo,
pinned to a fixed tag (reproducible). Each entry links to a page on
docs.langchain.com; that site (Mintlify) serves clean markdown when you append
`.md` to the URL — headings + code blocks intact, exactly what heading-based
chunking needs in Phase 1.

v0.2 (--docs-version 0.2): the docs *site* for 0.2 is gone (the live site serves
1.x), so the source of truth is the GitHub repo itself at the final 0.2 release
tag. We fetch ~10 `docs/docs/concepts/*.md` pages chosen to topically mirror the
v1.0 twelve. Concepts pages only: 0.2's how-to docs are Jupyter notebooks, and
converting those buys nothing (see PHASE_3.md risk #1). These pages are
mkdocs-material markdown (content tabs, admonitions), which the chunker
preprocesses. Note: 0.2 has no subgraphs.md — subgraphs live as a section of
low_level.md, so low_level + multi_agent cover that topic.

Output:
  v1.0: ai/data/raw/<slug>.md      + ai/data/manifest.json
  v0.2: ai/data/raw-0.2/<slug>.md  + ai/data/manifest-0.2.json
Both manifests pin the exact git tag for provenance.

Usage (from ai/):  python -m scripts.fetch_corpus [--docs-version {1.0,0.2}]
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import truststore

truststore.inject_into_ssl()  # OS trust store (corporate/local CA on this machine)

import httpx  # noqa: E402

# Pin each corpus to a specific release tag for reproducibility.
DOCS_VERSION = "1.0.10"
V02_TAG = "0.2.76"  # final 0.2.x release — the most mature state of the 0.2 docs

LLMS_TXT_URL = (
    f"https://raw.githubusercontent.com/langchain-ai/langgraph/{DOCS_VERSION}/docs/llms.txt"
)

# Only fetch pages from the docs site (the API reference / langsmith links point
# at other hosts and are recorded but not downloaded in Phase 0).
DOCS_HOST = "https://docs.langchain.com"

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RAW_DIR = DATA_DIR / "raw"
MANIFEST = DATA_DIR / "manifest.json"
RAW_DIR_02 = DATA_DIR / "raw-0.2"
MANIFEST_02 = DATA_DIR / "manifest-0.2.json"

LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
H1_RE = re.compile(r"^#\s+(.*\S)\s*$", re.MULTILINE)

# The ~10 v0.2 concepts pages that topically mirror the v1.0 corpus
# (overview, graph-api, streaming, persistence, add-memory, workflows-agents,
# use-subgraphs, ...). Verified to exist at tag 0.2.76.
V02_SLUGS = [
    "high_level",         # ~ overview
    "low_level",          # ~ graph-api (includes the 0.2 Subgraphs section)
    "agentic_concepts",   # ~ workflows-agents
    "streaming",          # ~ streaming
    "persistence",        # ~ persistence
    "memory",             # ~ add-memory
    "human_in_the_loop",  # 0.2 HIL idioms (interrupt_before etc.)
    "multi_agent",        # ~ use-subgraphs / multi-agent patterns
    "breakpoints",        # 0.2-era breakpoint/interrupt API
    "time-travel",        # checkpoint replay idioms
]


def slug_for(url: str) -> str:
    """Last path segment of the URL → filename slug."""
    return url.rstrip("/").split("/")[-1] or "index"


def fetch_v1() -> None:
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


def fetch_v02() -> None:
    RAW_DIR_02.mkdir(parents=True, exist_ok=True)

    raw_base = f"https://raw.githubusercontent.com/langchain-ai/langgraph/{V02_TAG}/docs/docs/concepts"
    # Citation URL: the pinned GitHub blob — stable and clickable, unlike the
    # retired 0.2 docs site.
    blob_base = f"https://github.com/langchain-ai/langgraph/blob/{V02_TAG}/docs/docs/concepts"

    files: list[dict] = []
    skipped: list[dict] = []
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        for slug in V02_SLUGS:
            raw_url = f"{raw_base}/{slug}.md"
            try:
                text = client.get(raw_url).raise_for_status().text
            except httpx.HTTPStatusError as exc:
                skipped.append({"slug": slug, "md_url": raw_url,
                                "reason": f"HTTP {exc.response.status_code}"})
                print(f"  SKIP  {slug} ({exc.response.status_code})")
                continue
            h1 = H1_RE.search(text)
            title = h1.group(1).strip() if h1 else slug.replace("_", " ").title()
            out = RAW_DIR_02 / f"{slug}.md"
            out.write_text(text, encoding="utf-8")
            files.append(
                {
                    "title": title,
                    "slug": slug,
                    "url": f"{blob_base}/{slug}.md",
                    "md_url": raw_url,
                    "path": str(out.relative_to(DATA_DIR.parent)),
                    "bytes": len(text.encode("utf-8")),
                }
            )
            print(f"  saved {slug}.md ({len(text):,} chars)")

    manifest = {
        "corpus": "LangGraph documentation (v0.2 concepts)",
        "docs_version": V02_TAG,
        "source_index": raw_base,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "doc_count": len(files),
        "total_bytes": sum(f["bytes"] for f in files),
        "files": files,
        "skipped": skipped,
    }
    MANIFEST_02.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nDone: {len(files)} docs, {manifest['total_bytes'] / 1024:.0f} KB -> {RAW_DIR_02}")
    if skipped:
        print(f"Skipped {len(skipped)}: " + ", ".join(s["slug"] for s in skipped))
    print(f"Manifest: {MANIFEST_02}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs-version", choices=["1.0", "0.2"], default="1.0")
    args = parser.parse_args()
    if args.docs_version == "0.2":
        fetch_v02()
    else:
        fetch_v1()


if __name__ == "__main__":
    sys.exit(main())
