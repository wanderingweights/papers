# Papers

One markdown file per paper, named by citekey (`frantar2023gptq.md`). Plain
text, greppable, diffable, readable by Claude. The PDF is not the record — the
note is.

## The rules

1. **A paper cannot leave `queued` with an empty `## Claim`.** One sentence,
   in your own words, saying what the paper asserts. If you can't write it, you
   didn't read it — leave it `queued`.
2. **`skimmed` is a legitimate terminal state.** Most papers should end there.
   Deciding not to go deeper is information; record why in `## Doubts`.
3. **Never fabricate an opinion.** `## Steal` and `## Doubts` hold Chris's
   views only. If a section wasn't actually discussed, leave the `-`.

## Status ladder

Maps onto Keshav's three passes:

| status          | meaning                                                   |
| --------------- | --------------------------------------------------------- |
| `queued`        | in the pile, metadata only, not yet opened                 |
| `skimmed`       | pass 1–2: title/abstract/figures/conclusion, claim written |
| `read`          | pass 3: mechanism understood, could defend the evidence    |
| `reimplemented` | wrote code against it                                      |
| `dropped`       | deliberately abandoned — say why in `## Doubts`            |

## Layout

```
papers/
  <citekey>.md     one note per paper
  _template.md     the skeleton
  index.md         GENERATED — do not hand-edit
  bin/reindex.py   regenerates index.md from frontmatter
  bin/arxiv-meta.py  arXiv id/URL -> frontmatter fields
  pdfs/            optional, gitignored
```

## Usage

Talk to Claude about a paper, then `/paper <url>` — it writes or updates the
note from the discussion. See `~/.claude/skills/paper/SKILL.md`.

Manually:

```bash
python3 papers/bin/arxiv-meta.py 2210.17323   # fetch metadata
python3 papers/bin/reindex.py                 # rebuild index.md
rg -l 'status: queued' papers/                # what's in the pile
rg -i 'quantization' papers/*.md              # search notes
```

## Citekeys

`<firstauthorlastname><year><firstsignificanttitleword>`, lowercase, ASCII —
e.g. `frantar2023gptq`.

Better BibTeX's *default* formula is `auth.lower + shorttitle(3,3) + year`
(→ `frantarGPTQAccuratePost2023`), which is not this. To make Zotero agree with
the store, set the BBT citation key formula to:

```
auth.lower + year + shorttitle(1,1).lower
```

Zotero → Settings → Better BibTeX → Citation keys → Citation key formula.
Do this before importing a library; changing it later does not regenerate
existing keys (you'd have to select all items → right-click → Refresh).
