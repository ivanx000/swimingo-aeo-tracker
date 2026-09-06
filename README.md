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

If you're picking this repo up for the first time, read
[WEEKLY_RUNBOOK.md](WEEKLY_RUNBOOK.md) (the recurring capture cycle) and
[MONTHLY_RITUAL.md](MONTHLY_RITUAL.md) (freshness/NAP/Wikidata upkeep) after
this file.

## Setup

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The retrieval simulator drives a real Chromium browser to scrape pages, so
its browser binary needs a one-time install after `pip install`:

```bash
playwright install chromium
```

Copy `.env.example` to `.env` and add a free-tier Gemini API key (used only
by `main.py run-gemini`; every other tool in this repo runs fully locally
with no API key):

```bash
cp .env.example .env
# then edit .env and set GEMINI_API_KEY=...
```

Get a key at https://aistudio.google.com/apikey if you don't have one.

## Data files

- `data/questions.json` — the 42 buyer questions (id, city, persona, type, question).
- `data/competitors.json` — known competitors and their domains. Add more
  competitors here at any time; no code changes needed.
- `data/competitor_urls.json` — competitor pages (incl. per-city pages) used
  by the retrieval simulator, ranked by citation count from Week 1 results.

## Tool 1: the tracking harness (`main.py`)

This is the core weekly tool: it asks the same 42 questions on 5 AI
platforms, extracts whether Swimingo was mentioned, and builds a summary
report. See [WEEKLY_RUNBOOK.md](WEEKLY_RUNBOOK.md) for the full step-by-step
protocol; this section explains what each step does.

**1. Gemini (automated):**
```bash
python main.py run-gemini
```
Asks every question via the Gemini API and saves raw responses to
`results/raw/<date>_gemini_raw.json`. Safe to re-run — it skips questions
already answered today. Example of one saved entry:
```json
{
  "question_id": 1,
  "platform": "gemini",
  "date": "2026-08-23",
  "raw_response": "Finding a private swim instructor in Toronto depends on whether you have access to a private/condo pool or if you need to rent lane space. Here are the best places to look, ranging from specialized private companies to independent instructors.\n\n### 1. Dedicated Private Swim Lesson Companies\n..."
}
```

**2. ChatGPT, Perplexity, Copilot, AI Overviews (manual):**
```bash
python main.py capture-web chatgpt
python main.py capture-web perplexity
python main.py capture-web copilot
python main.py capture-web ai_overviews
```
Opens a local web page (`http://127.0.0.1:8765`, stdlib `http.server` only,
no new dependency) showing one question at a time with its full text, a
"Question X of 42" indicator, and a large paste box. Ask the question on
that platform's website, paste the response, and click **Save & Next** (or
press Cmd/Ctrl+Enter). Click **Skip** to leave a question for later.
`--port <n>` picks a different port and `--no-browser` skips auto-opening
the tab. Stop with Ctrl+C and rerun to resume — already-captured questions
aren't re-shown. Writes to the same `results/raw/<date>_<platform>_raw.json`
schema as `run-gemini`, so the parse/report pipeline needs no changes.

*Deprecated fallback* — a terminal-based version of the same flow,
`python main.py capture <platform> [--method editor|clipboard]`, is kept in
case the web tool misbehaves; not the recommended path anymore.

**3. Parse raw responses:**
```bash
python main.py parse
```
Scans today's `results/raw/*_raw.json` files and extracts whether Swimingo
was mentioned, which competitors were mentioned, and which domains were
cited, saving `results/parsed/*_parsed.json` files. If capturing all 5
platforms spanned more than one calendar day, pass every date it touched:
`python main.py parse --dates 2026-08-23,2026-08-24`.

**4. Generate the report:**
```bash
python main.py report
```
Builds `results/reports/<date>_summary_report.md` — visibility by platform,
by question type, by persona, a competitor leaderboard, top cited domains,
and a list of "gap" questions where Swimingo was absent but a competitor was
mentioned. Also prints the report to the terminal. Use the same `--dates`
flag as `parse` to combine a capture round that spanned multiple days into
one report. Real excerpt from `results/reports/2026-08-23_to_2026-08-24_summary_report.md`:
```
**Overall Swimingo visibility: 26% (54/210 responses)**

## Visibility by platform
- **ai_overviews**: 71% (30/42)
- **chatgpt**: 19% (8/42)
- **copilot**: 0% (0/42)
- **gemini**: 0% (0/42)
- **perplexity**: 38% (16/42)

## Visibility by question type
- **comparison**: 20% (5/25)
- **cost**: 24% (6/25)
- **discovery**: 28% (25/90)
- **logistics**: 40% (14/35)
- **trust**: 11% (4/35)
```

Steps 1, 3, and 4 can be run together (minus the manual platforms):
```bash
python main.py run-all
```

## Tool 2: comparing runs (`main.py diff`)

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
the Markdown report to stdout. Real excerpt from
`results/reports/week1_vs_week6_diff.md`:
```
## Visibility by platform (baseline -> current)
- **ai_overviews**: 26/42 -> 30/42, +4
- **chatgpt**: 7/42 -> 8/42, +1
- **copilot**: 0/42 -> 0/42, 0
- **gemini**: 0/42 -> 0/42, 0
- **perplexity**: 19/42 -> 16/42, -3

## Newly-appearing Swimingo mentions (absent in baseline, present in current)
- [ai_overviews] Q5: "how much do private swim lessons cost in Mississauga"
- [ai_overviews] Q26: "how much do private swim lessons cost in Vancouver"
```

Because every result file is date-stamped (`results/raw/<date>_..._raw.json`,
etc.), every week's raw data, parsed data, and summary reports stay side by
side in `results/raw/`, `results/parsed/`, and `results/reports/` for direct
comparison. See [WEEKLY_RUNBOOK.md](WEEKLY_RUNBOOK.md) for how to read a diff
report and what's worth acting on.

## Tool 3: the retrieval simulator (`retrieval.py`)

A separate CLI (kept independent from `main.py` on purpose) that simulates
local RAG retrieval over Swimingo's and competitors' web content — i.e.
which pages would actually surface for each buyer question if an AI
answer engine were retrieving from a vector index of these sites, rather
than relying on live web search.

```bash
python retrieval.py scrape [--force]   # scrape Swimingo + competitor pages, cache to scraped_content/
python retrieval.py embed              # chunk scraped pages, embed, store in chroma_db/
python retrieval.py score              # query all 42 buyer questions, save results/retrieval/retrieval_scoreboard_<date>.json
```
`scrape` needs the `playwright install chromium` step from Setup above —
it launches a real headless Chromium instance to render each page.
`scraped_content/` and `chroma_db/` are local caches (gitignored) — delete
them to force a clean rebuild, or use `scrape --force` to re-scrape without
touching the embedding store.

`score` also writes `results/retrieval/close_losing_detail_<date>.md`, which
shows the actual winning and Swimingo passages side by side for every
question where Swimingo placed outside the top 2 or wasn't retrieved at all.
Real excerpt from `results/retrieval/retrieval_scoreboard_2026-08-04.json`:
```json
{
  "summary": { "total_questions": 42, "winning": 27, "close": 10, "losing": 5 },
  "questions": [
    {
      "question_id": 1,
      "city": "Toronto",
      "question": "where can I find a private swim instructor in Toronto",
      "swimingo_rank": 3,
      "classification": "close",
      "beaten_by": ["aquamobileswim.com"]
    }
  ]
}
```

## Tool 4: the NAP consistency checker (`nap_check.py`)

```bash
python nap_check.py
```
Fetches each profile page listed in `src/nap/profiles.py` and diffs the
published name/phone/website against the canonical values in
`src/nap/constants.py`. Saves `results/nap/<date>_nap_report.json` and
`.md`, and prints the report. Address is intentionally out of scope for now.
Add a new profile to check by appending one `Profile` entry to
`src/nap/profiles.py` — no other code changes needed; leave `url=None` with
a `placeholder_note` for a listing that isn't live yet. Real excerpt from
`results/nap/2026-08-22_nap_report.md`:
```
## Yellow Pages / 411.ca
URL: https://www.yellowpages.ca/bus/Ontario/Pickering/Swimingo/104576774.html
- name: PASS
- phone: PASS
- website: NOT_FOUND (canonical: "https://www.swimingo.com")
```
See [MONTHLY_RITUAL.md](MONTHLY_RITUAL.md) for what a FAIL result means and
who to escalate it to.

## Project layout

```
main.py                   # weekly capture/parse/report/diff CLI
retrieval.py               # RAG retrieval simulator CLI
nap_check.py                # NAP consistency checker CLI
src/gemini_runner.py        # Gemini automated capture
src/capture_web.py          # ChatGPT/Perplexity/Copilot/AI Overviews manual capture (local web page)
src/manual_capture.py       # same, terminal-based (deprecated fallback)
src/parser.py                # raw -> parsed result extraction
src/report.py                 # summary report generation
src/diff_runs.py              # baseline-vs-current run diffing
src/retrieval/                 # scraper, chunker, embedder, ChromaDB store, scoreboard
src/nap/                        # profile registry, per-site parsers, checker
data/                             # questions, competitors, competitor URLs
results/raw/                      # raw platform responses, date-stamped
results/parsed/                   # extracted mentions/citations, date-stamped
results/reports/                  # summary + diff reports
results/retrieval/                # retrieval scoreboards
results/nap/                      # NAP consistency reports
```
