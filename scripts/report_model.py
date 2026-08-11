"""Small, dependency-free parser for Hybrid Deep Research report artifacts."""
from __future__ import annotations

import re
from dataclasses import dataclass

CITATION_RE = re.compile(r"\[(S\d+)\]")
CLAIM_MARKER_RE = re.compile(r"<!--\s*claims:\s*([C\d,\s]+)\s*-->", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s)>]+")
SOURCES_HEADINGS = {"sources", "references", "fuentes", "referencias"}
SOURCE_LINE_RE = re.compile(
    r"^\s*(?:[-*+]\s+)?\[(S\d+)\]\s+(.+?)\s+[—–-]\s+(https?://\S+?)(?:\s+\(.*\))?\s*$"
)
TABLE_DELIM_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
LIST_RE = re.compile(r"^\s*[-*+]\s+")
STEP_RE = re.compile(r"^\s*\d+[.)]\s+")
QUOTE_RE = re.compile(r"^\s*>\s?")


@dataclass(frozen=True)
class NarrativeBlock:
    line: int
    kind: str
    text: str
    source_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values, text[end + 5 :]


def find_sources_heading(body: str) -> re.Match[str] | None:
    for match in re.finditer(r"(?mi)^##\s+([^\n#]+?)\s*$", body):
        if match.group(1).strip().casefold() in SOURCES_HEADINGS:
            return match
    return None


def split_sources(body: str) -> tuple[str, str]:
    match = find_sources_heading(body)
    if not match:
        return body, ""
    return body[: match.start()], body[match.end() :]


def parse_sources_section(text: str) -> tuple[dict[str, str], list[str]]:
    entries: dict[str, str] = {}
    errors: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = SOURCE_LINE_RE.match(stripped)
        if not match:
            continue
        source_id, _title, url = match.groups()
        url = url.rstrip(".,;:")
        if source_id in entries:
            errors.append(f"duplicate source entry: {source_id}")
        else:
            entries[source_id] = url
    return entries, errors


def _claim_ids(text: str) -> tuple[str, ...]:
    ids: list[str] = []
    for marker in CLAIM_MARKER_RE.findall(text):
        ids.extend(re.findall(r"C\d+", marker, flags=re.IGNORECASE))
    return tuple(dict.fromkeys(x.upper() for x in ids))


def _block(line: int, kind: str, text: str) -> NarrativeBlock:
    return NarrativeBlock(
        line=line,
        kind=kind,
        text=text.strip(),
        source_ids=tuple(dict.fromkeys(CITATION_RE.findall(text))),
        claim_ids=_claim_ids(text),
    )


def scan_narrative_blocks(markdown: str) -> list[NarrativeBlock]:
    """Return factual Markdown blocks, including lists, steps and table rows."""
    lines = markdown.splitlines()
    blocks: list[NarrativeBlock] = []
    paragraph: list[str] = []
    paragraph_start = 0
    in_fence = False

    def flush() -> None:
        nonlocal paragraph, paragraph_start
        if paragraph:
            blocks.append(_block(paragraph_start, "prose", " ".join(x.strip() for x in paragraph)))
        paragraph = []
        paragraph_start = 0

    i = 0
    while i < len(lines):
        line_no = i + 1
        raw = lines[i]
        stripped = raw.strip()
        if stripped.startswith("```"):
            flush()
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        if not stripped:
            flush()
            i += 1
            continue
        if stripped.startswith("#") or stripped.startswith(("<details", "</details", "<summary", "</summary")):
            flush()
            i += 1
            continue
        if stripped.startswith("|"):
            flush()
            # Header rows are structural when immediately followed by a delimiter row.
            if i + 1 < len(lines) and TABLE_DELIM_RE.match(lines[i + 1].strip()):
                i += 2
                continue
            if TABLE_DELIM_RE.match(stripped):
                i += 1
                continue
            blocks.append(_block(line_no, "table", raw))
            i += 1
            continue
        if LIST_RE.match(raw):
            flush()
            blocks.append(_block(line_no, "list", raw))
            i += 1
            continue
        if STEP_RE.match(raw):
            flush()
            blocks.append(_block(line_no, "step", raw))
            i += 1
            continue
        if QUOTE_RE.match(raw):
            flush()
            blocks.append(_block(line_no, "blockquote", raw))
            i += 1
            continue
        if not paragraph:
            paragraph_start = line_no
        paragraph.append(raw)
        i += 1
    flush()
    return blocks


def is_exempt_block(block: NarrativeBlock) -> bool:
    text = CLAIM_MARKER_RE.sub("", block.text).strip()
    text = LIST_RE.sub("", text)
    text = STEP_RE.sub("", text)
    text = QUOTE_RE.sub("", text)
    return text.startswith(("Method:", "Note:", "Método:", "Nota:"))
