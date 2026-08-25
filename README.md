# swimingo-aeo-tracker

Tracks Swimingo's visibility across AI answer engines (Gemini, ChatGPT,
Perplexity, Copilot, Google AI Overviews) for a fixed set of buyer questions
about private swim lessons in the Greater Toronto Area and Metro Vancouver.

This is an 8-week AEO/LLM visibility project. Week 1 established a baseline
of how often Swimingo (vs. competitors) gets mentioned or cited when people
ask AI assistants swim-lesson-related questions; the same capture cycle is
re-run in later weeks so the reports can be diffed to measure improvement.
Alongside the capture/report pipeline, the repo also has a local RAG
retrieval simulator and a NAP (name/phone/site) consistency checker.

## Setup

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your free-tier Gemini API key:

```bash
cp .env.example .env
# then edit .env and set GEMINI_API_KEY=...
```

## Data files

- `data/questions.json` — the 42 buyer questions (id, city, persona, type, question).
- `data/competitors.json` — known competitors and their domains. Add more
  competitors here at any time; no code changes needed.
- `data/competitor_urls.json` — competitor pages (incl. per-city pages) used
  by the retrieval simulator, ranked by citation count from Week 1 results.

## Weekly capture cycle (`main.py`)

1. **Gemini (automated):**
   ```bash
   python main.py run-gemini
   ```
   Asks every question via the Gemini API and saves raw responses to
   `results/raw/<date>_gemini_raw.json`. Safe to re-run — it skips
   questions already answered today.

2. **ChatGPT, Perplexity, Copilot, AI Overviews (manual):**
   ```bash
   python main.py capture chatgpt
   python main.py capture perplexity
   python main.py capture copilot
   python main.py capture ai_overviews
   ```
   For each platform, manually ask every printed question on that
   platform's website. Two capture methods avoid the truncation that can
   happen pasting a long response directly into the terminal:
   - `editor` (default): each question opens a temp file in your text
     editor (respects `$EDITOR`; otherwise falls back to TextEdit on
     macOS, notepad on Windows, or nano elsewhere) -- paste the response
     below the marker line, then save and close the file to continue.
   - `clipboard` (`--method clipboard`): copy the response to your
     clipboard, then press Enter in the terminal; the tool reads it
     straight from the clipboard via `pyperclip`.

   Either way, leave the response empty (or type `SKIP`) to skip a
   question. Each command can be stopped and resumed later without
   redoing finished questions.

3. **Parse raw responses:**
   ```bash
   python main.py parse
   ```
   Scans today's `results/raw/*_raw.json` files and extracts whether
   Swimingo was mentioned, which competitors were mentioned, and which
   domains were cited, saving `results/parsed/*_parsed.json` files. If
   capturing all 5 platforms spanned more than one calendar day, pass every
   date it touched: `python main.py parse --dates 2026-07-23,2026-07-24`.

4. **Generate the report:**
   ```bash
   python main.py report
   ```
   Builds `results/reports/<date>_summary_report.md` — visibility by platform,
   by question type, by persona, a competitor leaderboard, top cited
   domains, and a list of "gap" questions where Swimingo was absent but a
   competitor was mentioned. Also prints the report to the terminal. Use
   the same `--dates` flag as `parse` to combine a capture round that
   spanned multiple days into one report.

Steps 1, 3, and 4 can be run together (minus the manual platforms):

```bash
python main.py run-all
```

## Comparing runs (`main.py diff`)

```bash
python main.py diff
```

Diffs a baseline run against a later run, per-question and per-platform:
visibility deltas, newly-appearing/lost Swimingo mentions, and citation
source changes. With no flags it defaults to Week 1 vs. Week 6
(`src/diff_runs.py`'s `WEEK1_DATES`/`WEEK6_DATES`). To diff other runs:

```bash
python main.py diff --baseline-dates 2026-07-23,2026-07-24 \
                     --current-dates 2026-08-23,2026-08-24 \
                     --label week1_vs_week6
```

Saves `results/reports/<label>_diff.md` and `<label>_diff.json`, and prints
the Markdown report to stdout.

Because every result file is date-stamped
(`results/raw/<date>_..._raw.json`, etc.), every week's raw data, parsed
data, and summary reports stay side by side in `results/raw/`,
`results/parsed/`, and `results/reports/` for direct comparison.

## Retrieval simulator (`retrieval.py`)

A separate CLI (kept independent from `main.py` on purpose) that simulates
local RAG retrieval over Swimingo's and competitors' web content, to see
which pages would surface for each buyer question.

```bash
python retrieval.py scrape [--force]   # scrape Swimingo + competitor pages, cache to scraped_content/
python retrieval.py embed              # chunk scraped pages, embed, store in chroma_db/
python retrieval.py score              # query all 42 buyer questions, save results/retrieval/retrieval_scoreboard_<date>.json
```

`scraped_content/` and `chroma_db/` are local caches (gitignored) — delete
them to force a clean rebuild, or use `scrape --force` to re-scrape without
touching the embedding store.

## NAP consistency checker (`nap_check.py`)

```bash
python nap_check.py
```

Fetches each profile page listed in `src/nap/profiles.py` (Intently,
Yellow Pages, Superprof, ChatterBlock, ...) and diffs the published
name/phone/website against the canonical values in `src/nap/constants.py`.
Saves `results/nap/<date>_nap_report.json` and `.md`, and prints the report.
Address is intentionally out of scope for now. Add a new profile to check by
appending one `Profile` entry to `src/nap/profiles.py` — no other code
changes needed; leave `url=None` with a `placeholder_note` for a listing
that isn't live yet.

## Project layout

```
main.py                 # weekly capture/parse/report/diff CLI
retrieval.py             # RAG retrieval simulator CLI
nap_check.py              # NAP consistency checker CLI
src/gemini_runner.py      # Gemini automated capture
src/manual_capture.py     # ChatGPT/Perplexity/Copilot/AI Overviews manual capture
src/parser.py             # raw -> parsed result extraction
src/report.py             # summary report generation
src/diff_runs.py          # baseline-vs-current run diffing
src/retrieval/            # scraper, chunker, embedder, ChromaDB store, scoreboard
src/nap/                  # profile registry, per-site parsers, checker
data/                      # questions, competitors, competitor URLs
results/raw/               # raw platform responses, date-stamped
results/parsed/            # extracted mentions/citations, date-stamped
results/reports/           # summary + diff reports
results/retrieval/         # retrieval scoreboards
results/nap/                # NAP consistency reports
```
