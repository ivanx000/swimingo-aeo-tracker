# swimingo-aeo-tracker

Tracks Swimingo's visibility across AI answer engines (Gemini, ChatGPT,
Perplexity, Copilot, Google AI Overviews) for a fixed set of buyer questions
about private swim lessons in the Greater Toronto Area and Metro Vancouver.

This is Week 1 of an 8-week AEO/LLM visibility project: it establishes a
baseline of how often Swimingo (vs. competitors) gets mentioned or cited
when people ask AI assistants swim-lesson-related questions. The same tool
is meant to be **re-run identically in Week 8** so the two reports can be
compared to measure improvement.

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

## Running a full weekly cycle

1. **Gemini (automated):**
   ```bash
   python main.py run-gemini
   ```
   Asks every question via the Gemini API and saves raw responses to
   `results/<date>_gemini_raw.json`. Safe to re-run — it skips questions
   already answered today.

2. **ChatGPT, Perplexity, Copilot, AI Overviews (manual):**
   ```bash
   python main.py capture chatgpt
   python main.py capture perplexity
   python main.py capture copilot
   python main.py capture ai_overviews
   ```
   For each platform, manually ask every printed question on that
   platform's website, then paste the full response back into the
   terminal and type `END` on its own line to finish (blank lines within
   the paste are kept as part of the response). Type `SKIP` to skip a
   question. Each command can be stopped and resumed later without
   redoing finished questions.

3. **Parse raw responses:**
   ```bash
   python main.py parse
   ```
   Scans today's `*_raw.json` files and extracts whether Swimingo was
   mentioned, which competitors were mentioned, and which domains were
   cited, saving `*_parsed.json` files.

4. **Generate the report:**
   ```bash
   python main.py report
   ```
   Builds `results/<date>_summary_report.md` — visibility by platform,
   by question type, by persona, a competitor leaderboard, top cited
   domains, and a list of "gap" questions where Swimingo was absent but a
   competitor was mentioned. Also prints the report to the terminal.

Steps 1, 3, and 4 can be run together (minus the manual platforms):

```bash
python main.py run-all
```

## Week 8 comparison

Run the exact same cycle again in Week 8. Because every result file is
date-stamped (`results/<date>_...`), both weeks' raw data, parsed data,
and summary reports stay side by side in `results/` for a direct before
vs. after comparison.
