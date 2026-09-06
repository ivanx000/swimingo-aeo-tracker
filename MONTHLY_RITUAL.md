# Monthly Ritual

Three things to do once a month, separate from the weekly capture cycle in
[WEEKLY_RUNBOOK.md](WEEKLY_RUNBOOK.md). None of these need coding skill;
one (freshness touches) needs access to Swimingo's directory-listing
logins.

## 1. Freshness touches — one genuine update per profile

**What this means:** on each external profile below, make one real,
substantive edit — not a no-op save. Examples of genuine: updating a photo,
tweaking the description, adding a new service area, refreshing hours.
Not genuine: opening the page and clicking Save without changing anything.
The point (per the precedent set doing this for Task 6.3) is that a
platform that sees zero edits for months can quietly deprioritize or flag
a listing as stale, and a real edit each month keeps it active and current.

**Which profiles need this:**
- **Wikidata** — Swimingo's Wikidata item.
- **Yellow Pages** — the listing checked by `nap_check.py`
  (`https://www.yellowpages.ca/bus/Ontario/Pickering/Swimingo/104576774.html`
  as of the last NAP report).
- **Yelp** — Swimingo's Yelp business page.
- **Whichever Week 5 directory profiles are confirmed live by then.** Check
  `src/nap/profiles.py` — any `Profile` entry with a real `url` (not `None`)
  is live. As of this handoff that's Intently.co and Yellow Pages;
  Superprof.ca and ChatterBlock are still placeholders (`url=None`). If
  either of those has gone live since, add its freshness touch to this
  month's list too — and update its entry in `src/nap/profiles.py` with the
  real URL and a parser (see the NAP section below) so `nap_check.py`
  starts tracking it automatically.

Note: Wikidata and Yelp are **not** currently checked by `nap_check.py` —
only the profiles registered in `src/nap/profiles.py` are (right now:
Intently, Yellow Pages, Superprof, ChatterBlock). Freshness touches on
Wikidata/Yelp are a manual login-and-edit task, not something a command
verifies for you.

**How to log that it was done:** append one line per profile to
`results/monthly_log.md` (create the file if it doesn't exist yet) with
the date and what you changed, e.g.:
```
2026-09-15 — Wikidata: updated service-area statement to include Metro Vancouver.
2026-09-15 — Yellow Pages: refreshed business description.
2026-09-15 — Yelp: added a new photo.
```
This gives the next person a quick way to confirm the ritual actually
happened each month, and to see at a glance which profile was touched with
what, without digging through platform login histories.

## 2. NAP consistency check

```bash
python nap_check.py
```

Run this from the project root (with the virtual environment active — see
[README.md](README.md) Setup). It checks every profile in
`src/nap/profiles.py` against Swimingo's canonical name, phone, and website
(`src/nap/constants.py`) and prints + saves a report to `results/nap/`.

**Reading the result, per profile:**
- **PASS** on a field — that field matches exactly. Nothing to do.
- **FAIL** on a field — the published value doesn't match canonical. Note
  what it actually says vs. what it should say (the report prints both).
- **NOT_FOUND** — the field wasn't found on the page (e.g. website often
  isn't shown on Yellow Pages listings). Not necessarily a problem, but
  worth a glance if it's a field that used to be found.
- **INACTIVE** / **PLACEHOLDER** / **ERROR** — the profile isn't live, isn't
  set up yet, or the page couldn't be fetched. No NAP data to check yet.

**What a FAIL means and who to tell:** a FAIL on **name** or **website** is
usually something you (or whoever manages that specific directory listing)
can fix directly by logging in and correcting the listing. A FAIL on
**phone**, or any pattern where the correct number simply won't save or
displays wrong across multiple properties, can be a DNS/call-forwarding
configuration issue rather than a listing-content issue — per the Task 4.2
precedent, that class of fix belongs to **Pranav**, not something to try to
fix inside a directory's own listing editor.

Address is intentionally out of scope for this checker (per Task 5.1) —
don't expect it to catch address drift.

## 3. Wikidata review

A quick sanity check, not a full audit: open Swimingo's Wikidata item and
confirm its statements are still accurate — service area, phone, website,
anything else listed. This only needs to happen in depth when something
about the business has actually changed (a new city added, a phone number
changed, etc.); most months this is a 2-minute glance, not a rebuild. If a
statement is stale, fix it directly on Wikidata — that also counts as this
month's Wikidata freshness touch (Section 1), so you don't need to make a
second, separate edit.
