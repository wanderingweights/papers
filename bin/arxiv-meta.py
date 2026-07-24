#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2"]
# ///
"""Fetch arXiv metadata and print a ready-to-paste frontmatter block.

Usage:
    papers/bin/arxiv-meta.py 2210.17323
    papers/bin/arxiv-meta.py https://arxiv.org/abs/2210.17323v2 --abstract
    papers/bin/arxiv-meta.py 2210.17323 --year 2023 --venue "ICLR 2023"

The citekey is `<lastname><year><titleword>`. Better BibTeX must be configured
with `auth.lower + year + shorttitle(1,1).lower` to generate matching keys —
that is NOT its default formula.
"""

from __future__ import annotations

import argparse

from arxiv import fetch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identifier", help="arXiv id or abs/pdf URL")
    parser.add_argument("--abstract", action="store_true", help="also print the abstract")
    parser.add_argument("--year", type=int, help="override the year (use the venue year once published)")
    parser.add_argument("--venue", help="override the venue, e.g. 'ICLR 2023'")
    args = parser.parse_args()

    paper = fetch(args.identifier)
    paper.year_override = args.year
    if args.venue:
        paper.venue = args.venue
    print(paper.frontmatter())
    print(f"\n# {paper.title}")
    if args.abstract:
        print(f"\n<!-- abstract\n{paper.abstract}\n-->")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
