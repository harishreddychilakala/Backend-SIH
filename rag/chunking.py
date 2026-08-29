"""
BIS SmartAI — BIS-Aware Document Chunking Module
Chunks BIS PDF documents into semantically coherent units preserving:
- IS standard numbers and titles
- Section/clause hierarchy
- Requirements, testing clauses, QCO information
- Page boundaries
- Table content association

Configuration:
    CHUNK_SIZE      Target chunk size in characters (default 800)
    CHUNK_OVERLAP   Overlap between consecutive chunks (default 150 chars)
"""
import re
import hashlib
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

# ── Configurable parameters ───────────────────────────────────────────────────
CHUNK_SIZE = 800       # Target chunk size in characters
CHUNK_OVERLAP = 150    # Overlap to preserve context across chunk boundaries
MIN_CHUNK_LENGTH = 80  # Discard chunks shorter than this (avoids garbage chunks)
MAX_CHUNK_LENGTH = 1600  # Hard ceiling — split anything larger

# ── BIS structure patterns ────────────────────────────────────────────────────
IS_NUMBER_PATTERN = re.compile(
    r'\bIS\s*(?:No\.?\s*)?(\d+(?:[:\-]\d+(?:[:\-]\d+)?)?)\b',
    re.IGNORECASE
)
IS_TITLE_PATTERN = re.compile(
    r'(?:Indian Standard|IS)\s*[-—:]\s*(.{10,120})',
    re.IGNORECASE
)
SECTION_PATTERNS = [
    re.compile(r'^\s*(\d+(?:\.\d+)*)\s+([A-Z][A-Za-z\s&,\(\)/\-]{4,80})\s*$', re.MULTILINE),  # "5.2 Requirements"
    re.compile(r'^\s*(SCOPE|REQUIREMENTS?|TESTS?|TESTING|CERTIFICATION|DEFINITIONS?|FOREWORD|ANNEXURE|ANNEX|APPENDIX|CLAUSE|QCO|QUALITY CONTROL|LABORATORY|LABORATORIES|REFERENCES?|BIBLIOGRAPHY|SYMBOLS?|ABBREVIATIONS?)\b', re.IGNORECASE | re.MULTILINE),
]
CLAUSE_PATTERN = re.compile(r'^\s*(\d+(?:\.\d+){1,4})\s', re.MULTILINE)


@dataclass
class DocumentChunk:
    """A single retrievable knowledge unit from a BIS document."""
    domain: str
    document_name: str
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    standard_number: Optional[str] = None
    standard_title: Optional[str] = None
    section: Optional[str] = None
    clause: Optional[str] = None
    chunk_hash: str = ""
    document_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.chunk_hash and self.content:
            self.chunk_hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        self.metadata = {
            "domain": self.domain,
            "document_name": self.document_name,
            "standard_number": self.standard_number,
            "standard_title": self.standard_title,
            "section": self.section,
            "clause": self.clause,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
        }


# ── Utilities ─────────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Normalize whitespace while preserving meaningful line structure."""
    # Collapse multiple blank lines to at most 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove form-feed and other control chars
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Normalize tabs to spaces
    text = text.replace('\t', '  ')
    # Remove trailing whitespace on each line
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    return text.strip()


def _extract_is_number(text: str) -> Optional[str]:
    """Extract the most prominent IS number from a text block."""
    matches = IS_NUMBER_PATTERN.findall(text)
    if matches:
        return f"IS {matches[0]}"
    return None


def _extract_is_title(text: str) -> Optional[str]:
    """Extract a plausible Indian Standard title from a text block."""
    m = IS_TITLE_PATTERN.search(text)
    if m:
        title = m.group(1).strip()
        # Cap at sentence end or 120 chars
        title = re.split(r'[.\n]', title)[0].strip()
        if 10 <= len(title) <= 120:
            return title
    return None


def _detect_section(text: str) -> Optional[str]:
    """Detect the current section heading from a text block."""
    for pattern in SECTION_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group(0).strip()[:100]
    return None


def _detect_clause(text: str) -> Optional[str]:
    """Detect the first clause number in a text block (e.g. '5.2.1')."""
    m = CLAUSE_PATTERN.search(text)
    if m:
        return m.group(1)
    return None


def _is_valid_chunk(text: str) -> bool:
    """Return True if the chunk has meaningful content worth indexing."""
    stripped = text.strip()
    if len(stripped) < MIN_CHUNK_LENGTH:
        return False
    # Reject chunks that are mostly whitespace or special characters
    alpha_count = sum(1 for c in stripped if c.isalpha())
    if alpha_count < 20:
        return False
    return True


def _split_text_with_overlap(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split text into overlapping chunks, trying to break at paragraph boundaries.
    Respects MAX_CHUNK_LENGTH as a hard ceiling.
    """
    paragraphs = re.split(r'\n\n+', text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If a single paragraph exceeds max, split it by sentence
        if len(para) > MAX_CHUNK_LENGTH:
            sentences = re.split(r'(?<=[.!?])\s+', para)
            for sentence in sentences:
                if len(current) + len(sentence) + 2 > chunk_size and current:
                    chunks.append(current.strip())
                    # Overlap: keep last `overlap` chars as seed for next chunk
                    current = current[-overlap:] + "\n" + sentence if overlap > 0 else sentence
                else:
                    current = (current + "\n" + sentence).strip() if current else sentence
            continue

        if len(current) + len(para) + 2 > chunk_size and current:
            chunks.append(current.strip())
            current = current[-overlap:] + "\n\n" + para if overlap > 0 else para
        else:
            current = (current + "\n\n" + para).strip() if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks


# ── Page-by-page chunking ─────────────────────────────────────────────────────

class BISChunker:
    """
    Converts a list of (page_number, page_text) tuples from a BIS PDF
    into a list of DocumentChunk objects with full metadata.
    """

    def __init__(
        self,
        domain: str,
        document_name: str,
        document_hash: str = "",
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ):
        self.domain = domain
        self.document_name = document_name
        self.document_hash = document_hash
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Running context that updates as we process pages
        self._current_standard_number: Optional[str] = None
        self._current_standard_title: Optional[str] = None
        self._current_section: Optional[str] = None

    def chunk_pages(self, pages: List[tuple]) -> List[DocumentChunk]:
        """
        Args:
            pages: List of (page_number: int, text: str) tuples.
        Returns:
            List of DocumentChunk objects ready for embedding + storage.
        """
        all_chunks: List[DocumentChunk] = []
        chunk_index = 0

        for page_num, raw_text in pages:
            if not raw_text or not raw_text.strip():
                continue

            text = _clean_text(raw_text)

            # Update running context from this page
            is_num = _extract_is_number(text)
            if is_num:
                self._current_standard_number = is_num
            is_title = _extract_is_title(text)
            if is_title:
                self._current_standard_title = is_title
            section = _detect_section(text)
            if section:
                self._current_section = section

            # Split page text into overlapping chunks
            sub_chunks = _split_text_with_overlap(
                text,
                chunk_size=self.chunk_size,
                overlap=self.chunk_overlap,
            )

            for sub_text in sub_chunks:
                if not _is_valid_chunk(sub_text):
                    continue

                # Try to refine context from the sub-chunk itself
                local_is = _extract_is_number(sub_text) or self._current_standard_number
                local_section = _detect_section(sub_text) or self._current_section
                local_clause = _detect_clause(sub_text)

                chunk = DocumentChunk(
                    domain=self.domain,
                    document_name=self.document_name,
                    chunk_index=chunk_index,
                    content=sub_text,
                    page_number=page_num,
                    standard_number=local_is,
                    standard_title=self._current_standard_title,
                    section=local_section,
                    clause=local_clause,
                    document_hash=self.document_hash,
                )
                all_chunks.append(chunk)
                chunk_index += 1

        logger.info(
            f"Chunked '{self.document_name}': {len(pages)} pages → {len(all_chunks)} chunks"
        )
        return all_chunks


def chunk_document(
    domain: str,
    document_name: str,
    pages: List[tuple],
    document_hash: str = "",
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[DocumentChunk]:
    """
    Convenience function to chunk a BIS document given its pages.
    Args:
        domain: e.g. "Electrical", "Iron & Steel"
        document_name: filename of the PDF
        pages: List of (page_number, text) tuples
        document_hash: SHA-256 of the full document for idempotency
        chunk_size: target chunk size in chars
        chunk_overlap: overlap between chunks in chars
    Returns:
        List of DocumentChunk objects
    """
    chunker = BISChunker(
        domain=domain,
        document_name=document_name,
        document_hash=document_hash,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return chunker.chunk_pages(pages)
