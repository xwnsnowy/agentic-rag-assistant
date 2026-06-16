"""Heading-based markdown chunking.

Rules (from CLAUDE.md):
  - Chunk by heading/section, never split a code block mid-way.
  - Keep the heading together with its content.
  - Attach metadata per chunk: page title, section breadcrumb, source URL (+anchor).

The corpus is Mintlify-flavoured markdown (.md). We strip the injected
"Documentation Index" blockquote, drop standalone MDX wrapper tags / anchors
(remembering the anchor id for deep-link citations), then split on H1/H2/H3
boundaries. Long sections are further packed to a size budget, but a fenced code
block is always treated as one atomic unit and never broken.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})")
ANCHOR_RE = re.compile(r'^<a\s+id="([^"]+)"\s*/>$')
# A line that is only an opening/closing MDX (JSX) wrapper tag, e.g. <CodeGroup>,
# </Expandable>, <Tip>. Uppercase first letter distinguishes MDX components from
# real HTML we want to keep. Self-closing tags are handled separately.
MDX_WRAPPER_RE = re.compile(r"^</?[A-Z][A-Za-z0-9]*(\s[^>]*)?>$")
INLINE_TAG_RE = re.compile(r"<[^>]+>")

# Default packing budget (characters, a rough proxy for tokens at ~4 chars/token).
MAX_CHARS = 2000
# Drop chunks shorter than this (heading-only / empty sections) unless they carry
# a code block — too small to be useful retrieval units.
MIN_CHARS = 80
SPLIT_LEVELS = (1, 2, 3)


@dataclass
class Chunk:
    content: str
    page_title: str
    section: str  # breadcrumb of H2 > H3 (empty for the H1 intro)
    source_url: str  # includes #anchor when known
    heading: str
    chunk_index: int

    @property
    def char_len(self) -> int:
        return len(self.content)


def clean_heading_text(text: str) -> str:
    """Strip inline JSX/HTML from a heading so the breadcrumb reads cleanly."""
    return INLINE_TAG_RE.sub("", text).strip()


def _strip_doc_index(lines: list[str]) -> list[str]:
    """Drop the leading Mintlify 'Documentation Index' blockquote, if present."""
    if not lines or "Documentation Index" not in lines[0]:
        return lines
    i = 0
    while i < len(lines) and (lines[i].startswith(">") or lines[i].strip() == ""):
        i += 1
    return lines[i:]


def _iter_lines_with_code_state(lines: list[str]):
    """Yield (line, in_code) tracking fenced-code regions correctly."""
    fence: str | None = None
    for line in lines:
        m = FENCE_RE.match(line)
        if m:
            marker = m.group(2)
            if fence is None:
                fence = marker[0]  # opening fence
                yield line, True
                continue
            if marker[0] == fence:
                fence = None  # closing fence
                yield line, True
                continue
        yield line, fence is not None


@dataclass
class _Section:
    heading: str
    section: str
    anchor: str | None
    lines: list[str]


def _split_sections(lines: list[str], split_levels) -> tuple[str, list[_Section]]:
    """Split markdown into sections at the given heading levels.

    Returns (page_title, sections). The first H1 becomes the page title.
    """
    page_title = ""
    crumb: dict[int, str] = {}
    pending_anchor: str | None = None
    sections: list[_Section] = []
    current = _Section(heading="", section="", anchor=None, lines=[])

    for line, in_code in _iter_lines_with_code_state(lines):
        if not in_code:
            stripped = line.strip()

            am = ANCHOR_RE.match(stripped)
            if am:
                pending_anchor = am.group(1)
                continue  # drop the anchor line, remember its id

            if MDX_WRAPPER_RE.match(stripped):
                continue  # drop standalone MDX wrapper tags (keep their inner content)

            hm = HEADING_RE.match(line)
            if hm:
                level = len(hm.group(1))
                text = clean_heading_text(hm.group(2))
                if level == 1 and not page_title:
                    page_title = text
                if level in split_levels:
                    # finalize previous section
                    if current.lines or current.heading:
                        sections.append(current)
                    # update breadcrumb: set this level, clear deeper ones
                    crumb[level] = text
                    for deeper in [k for k in crumb if k > level]:
                        del crumb[deeper]
                    breadcrumb = " > ".join(
                        crumb[k] for k in sorted(crumb) if k >= 2
                    )
                    current = _Section(
                        heading=text,
                        section=breadcrumb,
                        anchor=pending_anchor,
                        lines=[line],
                    )
                    pending_anchor = None
                    continue

        current.lines.append(line)

    if current.lines or current.heading:
        sections.append(current)
    return page_title, sections


def _atomic_blocks(lines: list[str]) -> list[str]:
    """Group section body into atomic blocks: fenced code = one block; otherwise
    paragraphs separated by blank lines. Code blocks are never split."""
    blocks: list[str] = []
    buf: list[str] = []
    code_buf: list[str] = []
    in_code = False

    def flush_buf():
        nonlocal buf
        text = "\n".join(buf).strip("\n")
        if text.strip():
            blocks.append(text)
        buf = []

    for line, code_state in _iter_lines_with_code_state(lines):
        if code_state:
            if not in_code:  # opening a code block: flush pending prose first
                flush_buf()
                in_code = True
            code_buf.append(line)
            # detect close: code_state stays True on the closing fence line, then
            # the next line will be code_state False — handle by peeking marker
            if FENCE_RE.match(line) and len(code_buf) > 1:
                blocks.append("\n".join(code_buf))
                code_buf = []
                in_code = False
            continue
        if line.strip() == "":
            flush_buf()
        else:
            buf.append(line)
    if code_buf:
        blocks.append("\n".join(code_buf))
    flush_buf()
    return blocks


def _pack_blocks(blocks: list[str], max_chars: int) -> list[str]:
    """Greedily pack atomic blocks into pieces up to max_chars. A single block
    larger than max_chars (e.g. a big code listing) becomes its own piece."""
    pieces: list[str] = []
    cur: list[str] = []
    size = 0
    for b in blocks:
        blen = len(b)
        if cur and size + blen > max_chars:
            pieces.append("\n\n".join(cur))
            cur, size = [], 0
        cur.append(b)
        size += blen + 2
    if cur:
        pieces.append("\n\n".join(cur))
    return pieces


def chunk_markdown(
    md: str,
    *,
    source_url: str,
    page_title: str | None = None,
    split_levels: tuple[int, ...] = SPLIT_LEVELS,
    max_chars: int = MAX_CHARS,
    min_chars: int = MIN_CHARS,
) -> list[Chunk]:
    """Split one markdown document into heading-based chunks with metadata."""
    lines = _strip_doc_index(md.splitlines())
    parsed_title, sections = _split_sections(lines, split_levels)
    title = page_title or parsed_title or source_url

    chunks: list[Chunk] = []
    idx = 0
    for sec in sections:
        body = "\n".join(sec.lines).strip()
        if not body:
            continue
        url = f"{source_url}#{sec.anchor}" if sec.anchor else source_url
        # Heading line is part of sec.lines[0]; pack the whole section.
        blocks = _atomic_blocks(sec.lines)
        pieces = _pack_blocks(blocks, max_chars) or [body]
        for j, piece in enumerate(pieces):
            content = piece.strip()
            # Skip trivially small chunks (heading-only) unless they carry code.
            if len(content) < min_chars and "```" not in content:
                continue
            heading = sec.heading + (" (cont.)" if j > 0 else "")
            chunks.append(
                Chunk(
                    content=content,
                    page_title=title,
                    section=sec.section,
                    source_url=url,
                    heading=heading,
                    chunk_index=idx,
                )
            )
            idx += 1
    return chunks
