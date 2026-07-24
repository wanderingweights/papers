#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2"]
# ///
"""Save an arXiv paper into a running Zotero, PDF attached.

Usage:
    papers/bin/zotero-add.py 2312.07950 --tags quantization ptq
    papers/bin/zotero-add.py https://arxiv.org/abs/2210.17323 --year 2023 --venue "ICLR 2023"
    papers/bin/zotero-add.py 2312.07950 --force     # add even if already present

Zotero must be running (its connector server listens on 127.0.0.1:23119).

How this works — the connector protocol is not obvious, so: one `sessionID`
ties the calls together. `/connector/saveItems` creates the parent item, keyed
by the `id` we assign it. Zotero does NOT fetch the PDF itself; the client
streams the bytes to `/connector/saveAttachment`, with the metadata in an
`X-Metadata` HEADER (not the body) and `parentItemID` set to that same key.
`/connector/saveAttachmentFromResolver` is the endpoint that looks like it
should do the download for you — it 500s on arXiv preprints.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from arxiv import ArxivPaper, fetch

CONNECTOR = "http://127.0.0.1:23119/connector/"
ZOTERO_DB = Path("/home/ww/Zotero/zotero.sqlite")
HEADERS = {
    "Content-Type": "application/json",
    "X-Zotero-Connector-API-Version": "3",
    "User-Agent": "Zotero Connector",
}


def post(endpoint: str, payload: dict, timeout: int = 60) -> tuple[int, str]:
    request = urllib.request.Request(
        CONNECTOR + endpoint, data=json.dumps(payload).encode(), headers=HEADERS
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def post_bytes(endpoint: str, metadata: dict, body: bytes, content_type: str) -> tuple[int, str]:
    request = urllib.request.Request(
        CONNECTOR + endpoint,
        data=body,
        headers={
            "Content-Type": content_type,
            "X-Metadata": json.dumps(metadata),
            "X-Zotero-Connector-API-Version": "3",
            "User-Agent": "Zotero Connector",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def already_present(arxiv_id: str) -> bool:
    """Check a read-only snapshot of the live Zotero DB for this arXiv id."""
    if not ZOTERO_DB.exists():
        return False
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "zotero.sqlite"
        shutil.copy(ZOTERO_DB, copy)
        with sqlite3.connect(copy) as db:
            rows = db.execute(
                """
                select 1 from itemData d
                join fields f on f.fieldID = d.fieldID
                join itemDataValues v on v.valueID = d.valueID
                join items i on i.itemID = d.itemID
                where f.fieldName = 'archiveID' and v.value = ?
                  and i.itemID not in (select itemID from deletedItems)
                """,
                (f"arXiv:{arxiv_id}",),
            ).fetchall()
    return bool(rows)


def zotero_item(paper: ArxivPaper, tags: list[str]) -> dict:
    return {
        "id": paper.citekey,  # the connector key saveAttachment resolves parentItemID against
        "itemType": "preprint",
        "title": paper.title,
        "creators": [
            {"firstName": " ".join(name.split()[:-1]), "lastName": name.split()[-1], "creatorType": "author"}
            for name in paper.authors
        ],
        "date": paper.published.isoformat(),
        "repository": "arXiv",
        "archiveID": f"arXiv:{paper.arxiv_id}",
        "DOI": paper.doi,
        "url": paper.abs_url,
        "abstractNote": paper.abstract,
        "tags": [{"tag": tag} for tag in tags],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identifier", help="arXiv id or abs/pdf URL")
    parser.add_argument("--tags", nargs="*", default=[], help="tags to apply in Zotero")
    parser.add_argument("--year", type=int, help="override the year (affects the citekey)")
    parser.add_argument("--venue", help="override the venue")
    parser.add_argument("--no-pdf", action="store_true", help="metadata only")
    parser.add_argument("--force", action="store_true", help="add even if already in the library")
    args = parser.parse_args()

    paper = fetch(args.identifier)
    paper.year_override = args.year
    if args.venue:
        paper.venue = args.venue

    if not args.force and already_present(paper.arxiv_id):
        print(f"already in Zotero: arXiv:{paper.arxiv_id} ({paper.citekey}) — use --force to add anyway")
        return 0

    session = str(uuid.uuid4())
    status, body = post("saveItems", {
        "sessionID": session,
        "uri": paper.abs_url,
        "items": [zotero_item(paper, args.tags)],
    })
    if status != 201:
        print(f"saveItems failed [{status}] {body}", file=sys.stderr)
        return 1
    print(f"item saved: {paper.citekey} — {paper.title}")

    if args.no_pdf:
        return 0

    try:
        pdf = urllib.request.urlopen(
            urllib.request.Request(paper.pdf_url, headers={"User-Agent": HEADERS["User-Agent"]}),
            timeout=120,
        ).read()
    except OSError as exc:
        print(f"PDF download failed ({exc}); item saved without it", file=sys.stderr)
        return 1
    if not pdf.startswith(b"%PDF"):
        print(f"{paper.pdf_url} did not return a PDF; item saved without it", file=sys.stderr)
        return 1

    status, body = post_bytes(
        "saveAttachment",
        {"sessionID": session, "parentItemID": paper.citekey,
         "title": "Preprint PDF", "url": paper.pdf_url},
        pdf,
        "application/pdf",
    )
    if status != 201:
        print(f"attachment failed [{status}] {body}; item saved without PDF", file=sys.stderr)
        return 1
    print(f"PDF attached: {len(pdf) / 1_000_000:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
