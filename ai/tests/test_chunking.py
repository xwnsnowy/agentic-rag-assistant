"""Unit tests for the heading-based chunker (app/chunking.py).

Pure: no DB, no network. These pin down the CLAUDE.md chunking rules:
never split a fenced code block, keep headings with their bodies, drop
trivially small prose chunks, and attach citation-grade metadata.
"""

from app.chunking import MAX_CHARS, MIN_CHARS, chunk_markdown

URL = "https://example.com/docs/page"


def test_oversized_code_block_is_never_split():
    """A fenced code block longer than MAX_CHARS must stay one atomic chunk."""
    code_lines = [f"value_{i} = compute_something({i})  # keep the block long" for i in range(60)]
    code_block = "```python\n" + "\n".join(code_lines) + "\n```"
    assert len(code_block) > MAX_CHARS  # sanity: the block really exceeds the budget

    md = f"# Page\n\n## Big listing\n\n{code_block}\n"
    chunks = chunk_markdown(md, source_url=URL)

    # Exactly one chunk carries the code, and it carries ALL of it, fences intact.
    code_chunks = [c for c in chunks if "```python" in c.content]
    assert len(code_chunks) == 1
    assert code_chunks[0].content == code_block


def test_heading_stays_attached_to_its_body():
    body = (
        "LangGraph models an agent as a state machine. "
        "Nodes are functions, edges are transitions, and state flows through them."
    )
    md = f"# Page\n\n## Core concepts\n\n{body}\n\n```python\nfrom langgraph.graph import StateGraph\n```\n"
    chunks = chunk_markdown(md, source_url=URL)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.content.startswith("## Core concepts")
    assert body in chunk.content
    assert "StateGraph" in chunk.content  # prose + code packed together
    assert chunk.heading == "Core concepts"


def test_short_prose_dropped_but_short_code_kept():
    md = (
        "# Page\n\n"
        "## Placeholder\n\nTBD\n\n"  # < MIN_CHARS, no code -> dropped
        "## Snippet\n\n```python\nx = 1\n```\n"  # < MIN_CHARS but has code -> kept
    )
    chunks = chunk_markdown(md, source_url=URL)

    headings = [c.heading for c in chunks]
    assert "Placeholder" not in headings
    assert "Snippet" in headings
    kept = next(c for c in chunks if c.heading == "Snippet")
    assert len(kept.content) < MIN_CHARS  # it was kept BECAUSE of the code, not size


def test_breadcrumb_tracks_h2_h3_and_resets_on_new_h2():
    pad = "This body sentence is padding so the chunk clears the minimum size gate. " * 2
    md = (
        "# Guide\n\n"
        f"## Alpha\n\n{pad}\n\n"
        f"### Beta\n\n{pad}\n\n"
        f"## Gamma\n\n{pad}\n"
    )
    chunks = chunk_markdown(md, source_url=URL)
    by_heading = {c.heading: c for c in chunks}

    assert by_heading["Alpha"].section == "Alpha"
    assert by_heading["Beta"].section == "Alpha > Beta"  # H2 > H3 breadcrumb
    assert by_heading["Gamma"].section == "Gamma"  # new H2 clears the stale H3


def test_metadata_page_title_anchor_url_and_index():
    pad = "Padding sentence so this section survives the minimum-chunk-size filter. " * 2
    md = (
        "# My Page Title\n\n"
        f'<a id="setup-anchor" />\n\n## Setup\n\n{pad}\n\n'
        f"## Usage\n\n{pad}\n"
    )
    chunks = chunk_markdown(md, source_url=URL)
    by_heading = {c.heading: c for c in chunks}

    # Page title parsed from the H1 when not passed explicitly.
    assert all(c.page_title == "My Page Title" for c in chunks)
    # The <a id=...> anchor right before a heading becomes a deep-link #fragment.
    assert by_heading["Setup"].source_url == f"{URL}#setup-anchor"
    # A section without an anchor keeps the plain page URL.
    assert by_heading["Usage"].source_url == URL
    # chunk_index increases monotonically across the page.
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    # An explicit page_title argument overrides the parsed H1.
    override = chunk_markdown(md, source_url=URL, page_title="Override")
    assert all(c.page_title == "Override" for c in override)
