"""
Section-aware sliding-window chunker.

Because parser.py converts tables to "Label: Value" lines, every line carries
a clear semantic meaning. This chunker groups lines into logical sections and
never splits a section across a chunk boundary — keeping every Label:Value pair
intact inside the same chunk.

Algorithm:
  1. Split text into lines.
  2. Detect section boundaries (blank lines, ALL-CAPS headers, "---" dividers).
  3. Accumulate sections into a chunk until CHUNK_SIZE (in chars ≈ tokens×4) is reached.
  4. At boundary: close current chunk, copy last CHUNK_OVERLAP chars as overlap prefix.
  5. Attach metadata to each chunk.
"""

from __future__ import annotations

import re
from backend.config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_LEN


def chunk_text(raw_text: str, doc_id: str) -> list[dict]:
    """
    Split raw_text into overlapping chunks.

    Returns a list of dicts:
      {
        "chunk_id":   str,
        "doc_id":     str,
        "text":       str,
        "char_start": int,
        "char_end":   int,
      }
    """
    sections = _split_into_sections(raw_text)
    chunks   = _pack_sections(sections, doc_id)
    return chunks


# ── Section splitting ──────────────────────────────────────────────────────────

def _split_into_sections(text: str) -> list[str]:
    """
    Group consecutive lines into sections separated by:
      - One or more blank lines
      - A "---" page-break divider inserted by the parser
      - An ALL-CAPS line with no colon (document-level header)
    """
    lines = text.splitlines()
    sections: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()

        is_divider   = stripped in ("---", "")
        is_caps_hdr  = (
            stripped
            and stripped == stripped.upper()
            and ":" not in stripped
            and len(stripped) > 2
        )

        if is_divider or is_caps_hdr:
            if current:
                sections.append("\n".join(current))
                current = []
            if is_caps_hdr:
                # The header itself starts the next section
                current.append(line)
        else:
            current.append(line)

    if current:
        sections.append("\n".join(current))

    # Remove whitespace-only sections
    return [s for s in sections if s.strip()]


# ── Chunk packing ──────────────────────────────────────────────────────────────

def _pack_sections(sections: list[str], doc_id: str) -> list[dict]:
    """
    Greedily fill chunks with whole sections.
    When a section would overflow, close the current chunk and start a new one
    with an overlap prefix taken from the end of the previous chunk.
    """
    # Use char count as a proxy for tokens (1 token ≈ 4 chars)
    max_chars     = CHUNK_SIZE * 4
    overlap_chars = CHUNK_OVERLAP * 4

    chunks: list[dict] = []
    current_lines: list[str] = []
    current_len = 0
    char_cursor = 0
    chunk_index = 0

    def flush(start: int) -> int:
        nonlocal chunk_index
        text = "\n".join(current_lines).strip()
        if len(text) >= MIN_CHUNK_LEN:
            end = start + len(text)
            chunks.append({
                "chunk_id":   f"{doc_id}_chunk_{chunk_index}",
                "doc_id":     doc_id,
                "text":       text,
                "char_start": start,
                "char_end":   end,
            })
            chunk_index += 1
            return end
        return start

    overlap_prefix: list[str] = []

    for section in sections:
        section_len = len(section)

        # If adding this section overflows, flush first
        if current_len + section_len > max_chars and current_lines:
            char_cursor = flush(char_cursor)

            # Build overlap prefix from tail of flushed chunk
            last_text = "\n".join(current_lines)
            tail = last_text[-overlap_chars:] if len(last_text) > overlap_chars else last_text
            overlap_prefix = [tail] if tail.strip() else []

            current_lines = list(overlap_prefix)
            current_len   = sum(len(l) for l in current_lines)

        # If a single section is larger than max_chars, hard-split it
        if section_len > max_chars:
            sub_chunks = _hard_split(section, max_chars, overlap_chars)
            for sub in sub_chunks:
                if len(sub.strip()) >= MIN_CHUNK_LEN:
                    end = char_cursor + len(sub)
                    chunks.append({
                        "chunk_id":   f"{doc_id}_chunk_{chunk_index}",
                        "doc_id":     doc_id,
                        "text":       sub.strip(),
                        "char_start": char_cursor,
                        "char_end":   end,
                    })
                    chunk_index += 1
                    char_cursor = end
            current_lines = []
            current_len   = 0
            continue

        current_lines.append(section)
        current_len += section_len

    # Flush remaining
    if current_lines:
        flush(char_cursor)

    return chunks


def _hard_split(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Split a single oversized section by characters with overlap."""
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        parts.append(text[start:end])
        new_start = end - overlap_chars
        if new_start <= start:   # no forward progress — stop to avoid infinite loop
            break
        start = new_start
    return parts
