# Demo script

A five-minute walkthrough that touches every feature. Start with `sh install.sh` then
`python3 app.py`, and open <http://localhost:8050>.

## 1. Sign in (`/login`)

- The card names the product and prints `Demo: cenius@cenius.ai / cenius`.
- Click **Show** → the password unmasks; click **Hide** → it masks again.
- Press **Sign in** with empty fields → inline "Email is required." / "Password is
  required." messages, no request is sent.
- Type `cenius@cenius.ai` with a wrong password → one banner: *Email or password is
  incorrect.* The demo credential stays visible.
- Click **Use demo credentials** (or type the credential and press Enter) → you land on
  `/app?tab=overview`.

## 2. Quality overview (`/app?tab=overview`)

- Default dataset is **Billing transactions** — the one with the seeded regression.
- KPI tiles: quality score (81.08%), delta versus the previous run, rules passing (0 / 5),
  rows checked (500) and failing checks.
- The trend chart plots 21 daily points with the 95% target line; the last three points fall
  off a cliff. The selected run is a ringed marker.
- Click an earlier point (e.g. the flat stretch before the drop) → the KPI tiles, the
  *Selected run* panel and the header run context update, and the *Rules* and *Failures*
  tabs now describe that run.
- The **Recent runs** table lists all 21 runs newest first with date, score, rules passed
  and trigger. **Select** on any row scopes the workspace to it.

## 3. Rules (`/app?tab=rules`)

- The table shows each rule's type (Null / Range / Unique), column, parameters, enable
  switch and its outcome for the selected run (passed, or failed + failing row count).
- Click **History** on *Amount between -250 and 5,000* → the 21-run strip turns red for the
  last three runs, and the mini table lists the most recent outcomes with failing counts.
- Toggle a rule's switch → a flash confirms *enabled/disabled*; the next run skips disabled
  rules.
- **Create a rule**: name it, pick *Range check*, choose `amount`, set min `0` and max
  `9000`, press **Create rule** → it appears in the table. Try min `500` / max `100` → the
  inline error "Minimum must be less than the maximum." appears and the rule is not saved.
- Press **Run validation now** (header) → the button shows *Running checks…*, then a flash
  reports the new run, the trend and rule table refresh, and the new run becomes selected.
  Because the source rows have not changed, the score matches the previous run — the engine
  is deterministic.

## 4. Failures (`/app?tab=failures`)

- Header counts: checked rows, failing rows, failing rules, and the selected run.
- The picker lists only failing rules, with their failing row counts. Selecting one loads
  up to 20 sampled rows: row index, column, the bad value (or `(missing)` for nulls) and the
  reason the check failed.
- Switch the dataset to **Orders ledger** and select one of its first three runs → the tab
  shows **No failures in this run** (all rules passed on that run).

## 5. Refresh and sign out

- With any dataset/run selected, refresh the page: the same dataset and run come back (the
  dataset is in the URL, the run in a session store).
- Copy `/app?tab=failures&dataset=2` into a new tab → the workspace opens on the Failures
  tab for Signup cohort.
- **Sign out** (rail) → the session row is deleted and you land on `/login`. Press Back: the
  workspace does not come back.

## Suggested screenshots for the README

| File | Route / state |
|---|---|
| `docs/screenshot-login.png` | `/login` with the demo hint visible |
| `docs/screenshot-overview.png` | `/app?tab=overview&dataset=1` (the regression) |
| `docs/screenshot-rules.png` | `/app?tab=rules&dataset=1` with a rule's history open |
| `docs/screenshot-failures.png` | `/app?tab=failures&dataset=1` with samples loaded |
