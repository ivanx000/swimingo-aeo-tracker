# Weekly Runbook

A step-by-step protocol for the weekly AEO visibility capture, for whoever
is running this after Ivan — no coding background required. Every step
below is either **RUN**: type the command, press Enter, read what prints —
or **JUDGMENT**: something only a person can do (asking a question on a
website, deciding whether a result is worth flagging). Steps marked RUN
should each take well under a minute. The manual paste steps are the one
part where timing depends on you — budget more time for those on your
first couple of runs; see the note after Step 2.

If any command errors out with something you don't understand, stop and
message whoever owns this project rather than guessing.

## Before you start

Open a terminal, go to the project folder, and turn on its Python
environment (do this once per terminal session):

```bash
cd path/to/swimingo-aeo-tracker
source .venv/bin/activate
```

You should see `(.venv)` appear at the start of your terminal prompt. If
`.venv` doesn't exist yet, see the Setup section of [README.md](README.md)
first — that's a one-time setup, not a weekly step.

## Step 1 — Gemini capture (RUN)

```bash
python main.py run-gemini
```

This asks all 42 questions to Gemini automatically and saves the answers.
It's safe to run more than once — it won't re-ask questions it already has
an answer for today. Just run it and let it finish.

## Step 2 — ChatGPT, Perplexity, Copilot, AI Overviews (JUDGMENT + RUN)

For each of the four platforms below, run the command, then follow the
on-screen page:

```bash
python main.py capture-web chatgpt
python main.py capture-web perplexity
python main.py capture-web copilot
python main.py capture-web ai_overviews
```

Each command opens a page in your browser showing one question at a time.
For each question:
1. Copy the question text.
2. Go ask it on that platform's actual website (chatgpt.com, perplexity.ai,
   Copilot, or Google — whichever one this command is for).
3. Copy the platform's full answer.
4. Paste it into the big box on the local page and click **Save & Next**.

Click **Skip** if a question won't load properly on a platform — don't
make up an answer. Press Ctrl+C in the terminal to stop early; running the
same command again later picks up where you left off, so you don't have to
finish all four platforms in one sitting.

**On timing:** Steps 1, 3, 4, and 5 in this runbook are fast — a couple of
minutes combined. This step is the long pole: 42 questions × 4 platforms is
168 questions to ask and paste, and each one takes as long as it takes the
AI to answer plus your copy/paste time. Don't rush it to hit a clock —
accuracy of what you paste matters more than speed. If you can only do one
or two platforms in a sitting, that's fine; resume the rest later the same
way.

## Step 3 — Parse the raw responses (RUN)

```bash
python main.py parse
```

If Steps 1–2 all happened on the same calendar day, just run the command
as-is. If your capture stretched across more than one day (e.g. you did
Gemini and ChatGPT on Monday but finished Perplexity/Copilot/AI Overviews
on Tuesday), add every date it touched:

```bash
python main.py parse --dates 2026-08-23,2026-08-24
```

## Step 4 — Generate this week's report (RUN)

```bash
python main.py report
```

(Add the same `--dates` flag as Step 3 if your capture spanned multiple
days.) This prints a summary to your terminal and saves it under
`results/reports/`. Skim it, but the more useful comparison is the diff in
the next step.

## Step 5 — Diff against last week (RUN, then JUDGMENT to read it)

First, find last week's capture dates: run `ls results/raw/` and look at
the filenames — they start with a date. Find the most recent date(s) that
are *not* from the run you just did today; that's your baseline.

```bash
python main.py diff --baseline-dates <last week's date(s)> \
                     --current-dates <today's date(s)> \
                     --label <short name, e.g. week7_vs_week8>
```

Example:
```bash
python main.py diff --baseline-dates 2026-08-23,2026-08-24 \
                     --current-dates 2026-08-30,2026-08-31 \
                     --label week6_vs_week7
```

This prints a report and saves it to `results/reports/<label>_diff.md`.
The rest of this runbook is about how to read that output.

## How to read the diff report

### The visibility percentage

Each platform's line, e.g. `**perplexity**: 19/42 -> 16/42, -3`, means: out
of the 42 questions, Swimingo was mentioned in 19 of them in the baseline
run and 16 in the current run. Higher is better. This number moves for two
different reasons — genuine improvement/regression in how AI platforms
"see" Swimingo, or plain noise (the same question can get a different
answer next time you ask, especially on platforms that pull live search
results). Don't treat a one- or two-question wobble as a trend.

### What's a meaningful change vs. normal noise

Based on the swings actually observed between Week 1 and Week 6:

- A **platform-level move of more than ~5 percentage points** is worth a
  closer look. Real example: Perplexity dropped from 45% (19/42) to 38%
  (16/42) between Week 1 and Week 6 — a real, noted swing, not noise.
  Smaller moves (ChatGPT's 17%→19%, a 2-point move) are within normal
  noise and don't need action.
- A **question-type-level move is a stronger signal** than a
  platform-level one, because it isn't tied to one platform's quirks.
  Real example: cost-question visibility jumped from 8% (2/25) to 24%
  (6/25) between Week 1 and Week 6 — a genuine, worth-celebrating
  improvement on high buyer-intent questions.
- **Caveat:** if the capture location or account setup changed between
  the two runs being diffed (e.g. different city, brand-new vs. aged
  accounts on Perplexity/Copilot), platform-level deltas are less
  trustworthy — some AI platforms personalize by location. Keep runs as
  consistent as possible (same city, similar account age) so future
  diffs are cleaner to read.

### Where to look for newly-appearing / newly-lost mentions

The diff report has two sections for this:
- **"Newly-appearing Swimingo mentions"** — questions where Swimingo
  wasn't mentioned in the baseline but is now. Good news, but check a
  couple of the underlying answers (open `results/raw/`) to make sure
  the mention looks accurate, not a fluke.
- **"Newly-lost Swimingo mentions"** — questions where Swimingo used to
  be mentioned and now isn't.
- **"Citation source changes"** — for each question, which website
  domains got added or dropped as sources. Look here for new competitors
  showing up, or Swimingo's own site (`swimingo.com`) newly appearing or
  disappearing from citations, flagged inline as
  `[swimingo.com newly cited]` / `[swimingo.com newly dropped]`.

One extra sanity check worth doing on citation changes: when an unfamiliar
domain shows up for a question about a specific city, make sure it's
actually about that city. AI platforms have been observed getting this
wrong before — e.g. an "Aurora" cost question got answered about Aurora,
Colorado and Aurora, Illinois instead of Aurora, Ontario in Week 1, and a
Windsor, Ontario question briefly cited domains that don't look
Windsor-related at all. It's a quick glance, not a deep investigation.

## What to actually act on (checklist)

Go through this list after every diff. Most weeks, none of these will
trigger — that's normal.

- [ ] **Any platform's visibility dropped by more than ~5 points** (e.g.
      the observed Perplexity 45%→38% drop). → Note it in the report and
      mention it to whoever owns content/technical changes that week.
- [ ] **A competitor appears repeatedly across 3 or more platforms** where
      it wasn't showing up before. Real example: British Swim School went
      from not appearing in Week 1's competitor leaderboard at all to a
      top-3 competitor on 4 of 5 platforms by Week 6. → Worth flagging as
      a new competitive threat, not just noise.
  - Check the "Competitor leaderboard" section of `results/reports/<date>_summary_report.md` to spot this.
- [ ] **A question flips from mentioned to not-mentioned on 2 or more
      platforms at the same time.** Real example: the Vancouver
      "where can I find a private swim instructor" question lost Swimingo's
      mention on both AI Overviews and Perplexity between Week 1 and Week 6.
      A single-platform flip is usually noise; two or more at once isn't.
- [ ] **Cost/pricing-question visibility moves noticeably** (up or down).
      These are high buyer-intent questions, so a real move here (like the
      observed 8%→24% jump) matters more than the same-sized move on a
      lower-intent question type.
- [ ] **A newly-cited domain doesn't seem to actually be about the target
      city** (see the Aurora/Windsor note above). → Flag as a possible
      AI geo-confusion issue, not a real competitor gap.

If two or more boxes above get checked in the same week, that's worth a
short written note (a few sentences) alongside that week's report, even if
you're not sure yet what caused it.
