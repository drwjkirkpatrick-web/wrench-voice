"""
kb.py
=====
Knowledge Base — search engine for local markdown repair docs.

WHY:
Mechanics need torque specs, fluid capacities, and special-tool lists
while their hands are dirty. These live in markdown files so they're
human-readable, version-controllable, and parseable without a database.

HOW:
1. Load all .md files from a directory on first search (lazy)
2. Parse headings (# ## ###) to extract topics
3. Score documents by keyword overlap with query
4. Return snippets around the best match in each doc

WHAT the files look like:
Each .md in kb/ follows a standard heading structure:
  # Engine Name
  ## Overview
  ## Known Issues
  ## Torque Specs
  ## Fluid Capacities
  etc.

The searcher splits on headings, indexes heading text + body text,
and returns the most relevant heading block from each matching file.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SearchResult:
    """One search hit from the knowledge base."""
    title: str
    path: str
    snippet: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "path": self.path,
            "snippet": self.snippet,
            "score": self.score,
        }


class KnowledgeBase:
    """
    Simple inverted-index KB over markdown files.

    No dependencies beyond stdlib. Works offline. Works on any
    device that can run Python 3.10+.
    """

    def __init__(self, kb_dir: str | Path | None = None) -> None:
        """
        Initialize the KB.

        If kb_dir is None, we look for the default ../kb/ relative to
        this file's location.
        """
        if kb_dir is None:
            # NOTE: __file__ exists because this is a real .py file on disk.
            self._kb_dir = Path(__file__).parent.parent / "kb"
        else:
            self._kb_dir = Path(kb_dir)

        self._indexed = False
        self._docs: list[_Document] = []  # Lazy: filled on first search

    # ─── Internal Data Structures ─────────────────────────────────────────────

    @dataclass
    class _Block:
        """One heading + its body."""
        heading: str
        body: str
        level: int

    @dataclass
    class _Document:
        """One parsed markdown file."""
        path: Path
        title: str
        blocks: list["KnowledgeBase._Block"]

    # ─── Indexing ──────────────────────────────────────────────────────────────

    def _ensure_indexed(self) -> None:
        """
        Parse all .md files in the KB directory. Called lazily on first search.

        WHY lazy: Don't waste startup time indexing KB on import.
        Mechanics won't search until they ask a question.
        """
        if self._indexed:
            return

        self._docs = []

        if not self._kb_dir.exists():
            # Graceful degradation: no KB directory = empty results, no crash
            self._indexed = True
            return

        for md_file in sorted(self._kb_dir.glob("*.md")):
            doc = self._parse_md(md_file)
            self._docs.append(doc)

        self._indexed = True

    def _parse_md(self, path: Path) -> "KnowledgeBase._Document":
        """Parse a markdown file into heading blocks."""
        raw = path.read_text(encoding="utf-8")

        # Extract H1 as document title
        title_match = re.search(r"^#\s+(.+)$", raw, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem

        # Split on heading boundaries
        blocks: list[KnowledgeBase._Block] = []
        current_heading = ""
        current_body_lines: list[str] = []
        current_level = 0

        for line in raw.splitlines():
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                # Save previous block
                if current_heading:
                    blocks.append(
                        self._Block(
                            heading=current_heading,
                            body="\n".join(current_body_lines).strip(),
                            level=current_level,
                        )
                    )
                current_level = len(heading_match.group(1))
                current_heading = heading_match.group(2).strip()
                current_body_lines = []
            else:
                current_body_lines.append(line)

        # Flush last block
        if current_heading:
            blocks.append(
                self._Block(
                    heading=current_heading,
                    body="\n".join(current_body_lines).strip(),
                    level=current_level,
                )
            )

        return self._Document(path=path, title=title, blocks=blocks)

    # ─── Search ─────────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """
        Search the KB for documents matching the query.

        Scoring:
        - Title match: +3 points
        - Heading match: +2 points
        - Body word match: +1 point per occurrence
        - Exact phrase in heading: +5 bonus
        """
        self._ensure_indexed()

        if not query.strip():
            return []

        # Prepare query tokens
        query_lower = query.lower()
        tokens = set(query_lower.split())

        scored: list[tuple[float, SearchResult]] = []

        for doc in self._docs:
            best_block_score = 0.0
            best_block_snippet = ""
            best_block_heading = ""

            for block in doc.blocks:
                score = 0.0
                heading_lower = block.heading.lower()
                body_lower = block.body.lower()

                # Title match
                if query_lower in doc.title.lower():
                    score += 3.0

                # Heading word match
                heading_tokens = set(heading_lower.split())
                score += 2.0 * len(tokens & heading_tokens)

                # Exact phrase in heading (big bonus)
                if query_lower in heading_lower:
                    score += 5.0

                # Body word match (1 pt per word, max 10)
                body_tokens = set(body_lower.split())
                overlap = tokens & body_tokens
                score += min(len(overlap), 10.0)

                # Track best block per document
                if score > best_block_score:
                    best_block_score = score
                    best_block_heading = block.heading
                    best_block_snippet = self._extract_snippet(block.body, query_lower)

            if best_block_score > 0:
                scored.append(
                    (
                        best_block_score,
                        SearchResult(
                            title=f"{doc.title} > {best_block_heading}",
                            path=str(doc.path),
                            snippet=best_block_snippet,
                            score=round(best_block_score, 2),
                        ),
                    )
                )

        # Sort descending, take top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        return [result for _, result in scored[:top_k]]

    # ─── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_snippet(body: str, query_lower: str, radius: int = 80) -> str:
        """
        Extract ~radius chars around the first query word match.
        Makes search results useful even if the match is deep in the text.
        """
        idx = body.lower().find(query_lower)
        if idx == -1:
            # No exact match — fall back to first 160 chars
            return body[:160].strip().replace("\n", " ")

        start = max(0, idx - radius)
        end = min(len(body), idx + radius)
        snippet = body[start:end].strip().replace("\n", " ")
        return f"…{snippet}…"

    # ─── Utility ───────────────────────────────────────────────────────────────

    def list_topics(self) -> list[str]:
        """Return all document titles (for CLI discovery)."""
        self._ensure_indexed()
        return [doc.title for doc in self._docs]

    def get_doc(self, title_fragment: str) -> str | None:
        """
        Fetch the full text of a document by title fragment.
        Useful for the CLI `kb` command when the user wants to read everything.
        """
        self._ensure_indexed()
        for doc in self._docs:
            if title_fragment.lower() in doc.title.lower():
                return doc.path.read_text(encoding="utf-8")
        return None
