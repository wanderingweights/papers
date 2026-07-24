"""Shared arXiv metadata fetching. Imported by arxiv-meta.py and zotero-add.py.

Not a standalone script — the importing script's PEP 723 header supplies pydantic.
"""

from __future__ import annotations

import re
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from html import unescape

from pydantic import BaseModel

API = "https://export.arxiv.org/api/query?id_list={}"
# arXiv 429s the default urllib User-Agent; it wants something identifiable.
HEADERS = {"User-Agent": "papers-store/1.0 (personal reading notes; mailto:subiawaud@gmail.com)"}
ATOM = {"a": "http://www.w3.org/2005/Atom"}
ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
STOPWORDS = {
    "a", "an", "the", "on", "of", "in", "for", "with", "without", "towards",
    "toward", "is", "are", "and", "to", "from", "at", "by", "via", "using",
}


class ArxivPaper(BaseModel):
    arxiv_id: str
    title: str
    authors: list[str]
    published: date
    abstract: str
    year_override: int | None = None
    venue: str = "arXiv preprint"

    @property
    def year(self) -> int:
        return self.year_override or self.published.year

    @property
    def abs_url(self) -> str:
        return f"https://arxiv.org/abs/{self.arxiv_id}"

    @property
    def pdf_url(self) -> str:
        return f"https://arxiv.org/pdf/{self.arxiv_id}"

    @property
    def doi(self) -> str:
        return f"10.48550/arXiv.{self.arxiv_id}"

    @property
    def citekey(self) -> str:
        surname = ascii_slug(self.authors[0].split()[-1]) if self.authors else "anon"
        words = (ascii_slug(w) for w in re.split(r"[\s:—–-]+", self.title))
        word = next((w for w in words if w and w not in STOPWORDS), "paper")
        return f"{surname}{self.year}{word}"

    def frontmatter(self) -> str:
        authors = ", ".join(f'"{a}"' for a in self.authors)
        return "\n".join([
            "---",
            f"citekey: {self.citekey}",
            f'title: "{self.title}"',
            f"authors: [{authors}]",
            f"year: {self.year}",
            f"venue: {self.venue}",
            f"url: {self.abs_url}",
            f"added: {date.today()}",
            "status: queued",
            "rating:",
            "tags: []",
            "related: []",
            "---",
        ])


def ascii_slug(text: str) -> str:
    """Lowercase ASCII alphanumerics only — 'Müller' -> 'muller', 'GPTQ:' -> 'gptq'."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", folded.lower())


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def given_first(author: str) -> str:
    """'Frantar, Elias' -> 'Elias Frantar' (the abs page uses surname-first)."""
    surname, _, given = author.partition(",")
    return f"{given.strip()} {surname.strip()}".strip() if given else author


def get(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def parse_id(identifier: str) -> str:
    match = ARXIV_ID.search(identifier)
    if not match:
        raise SystemExit(f"could not find an arXiv id in {identifier!r}")
    return match.group(1)


def from_api(arxiv_id: str) -> ArxivPaper:
    xml = get(API.format(arxiv_id), timeout=10).decode("utf-8", "replace")
    entry = ET.fromstring(xml).find("a:entry", ATOM)
    if entry is None or squash(entry.findtext("a:title", "", ATOM)) == "Error":
        raise ValueError(f"no arXiv entry for {arxiv_id}")
    return ArxivPaper(
        arxiv_id=arxiv_id,
        title=squash(entry.findtext("a:title", "", ATOM)),
        authors=[squash(a.findtext("a:name", "", ATOM) or "") for a in entry.findall("a:author", ATOM)],
        published=date.fromisoformat(entry.findtext("a:published", "", ATOM)[:10]),
        abstract=squash(entry.findtext("a:summary", "", ATOM)),
    )


def from_abs_page(arxiv_id: str) -> ArxivPaper:
    """Fallback: scrape the citation_* meta tags off the /abs page.

    The export API rate-limits hard from shared/proxied IPs; the abs page does not.
    """
    html = get(f"https://arxiv.org/abs/{arxiv_id}").decode("utf-8", "replace")
    tags = re.findall(r'<meta name="(citation_[a-z_]+)" content="(.*?)"\s*/?>', html, re.DOTALL)
    meta: dict[str, list[str]] = {}
    for key, value in tags:
        meta.setdefault(key, []).append(squash(unescape(value)))
    if "citation_title" not in meta:
        raise ValueError(f"no citation metadata on the abs page for {arxiv_id}")
    published = meta.get("citation_date", ["1970/1/1"])[0]
    return ArxivPaper(
        arxiv_id=arxiv_id,
        title=meta["citation_title"][0],
        authors=[given_first(a) for a in meta.get("citation_author", [])],
        published=date(*(int(part) for part in published.split("/"))),
        abstract=meta.get("citation_abstract", [""])[0],
    )


def fetch(identifier: str) -> ArxivPaper:
    arxiv_id = parse_id(identifier)
    try:
        return from_api(arxiv_id)
    except (OSError, ValueError, ET.ParseError) as exc:
        print(f"export API failed ({exc}); falling back to the abs page", file=sys.stderr)
    try:
        return from_abs_page(arxiv_id)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"could not fetch metadata for {arxiv_id}: {exc}")
