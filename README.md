# Payment Reminder Assistant

A daily payment-reminder tool for small businesses: a rules engine that decides
which customers need a reminder today, a web page for the owner to review and
approve notices, and research notes on the EU Late Payment Directive.

## How to run

### Tests (from inside `python/`)

```bash
python -m unittest
```

46 tests cover: date validation, bad-data detection, step selection, the
already-sent logic, sorting, message content, and a full integration test
against the sample data.

### Rules engine (from inside `python/`)

```bash
python plan.py --invoices ../data/invoices.json \
               --sent ../data/sent.json \
               --today 2026-10-12 \
               --out ../actions.json
```

Exits 0 on success; exits non-zero with a clear message if a file cannot be
read or `--today` is not a valid date.

### Owner's page (from inside `python/`)

```bash
python app.py
# then open http://localhost:8000/
```

Optional environment variables: `PORT` (default `8000`), `DATA_DIR` (default
`../data`), `TODAY` (default: real today).

## Decisions made

- **Python only** – deleted the TypeScript folder to keep the submission clean.
- **Standard library only** – no third-party packages needed; `requirements.txt`
  is intentionally empty.
- **No AI key required for messages** – messages are generated from templates
  that satisfy every content rule (name, id, due date, amount with currency,
  days overdue; no invented fees, interest, or other figures). The code would
  accept an `OPENAI_API_KEY` environment variable to call an LLM, but falls back
  to the template when no key is present, so it works offline.
- **Approval decisions stored in memory** – the page records approve/reject
  decisions for the current run; they reset when the server restarts, which is
  enough per the spec ("while the app runs is enough").
- **Bad-data priority order** – applied exactly as listed in the README:
  `duplicate_id` → `invalid_amount` → `missing_due_date` → `invalid_due_date`
  → `invalid_paid_date`. Empty string for `paid_date` is treated as "not a date"
  (unpaid), not as `invalid_paid_date`.
- **Lexicographic sort** – both lists are sorted with Python's default string
  sort, so `INV-100` < `INV-99` as required.

## What I would do next

- Persist approval decisions to a database or JSON file so they survive restarts.
- Add an endpoint to mark invoices as paid.
- Send actual emails (SMTP) once approved, and write the result back to `sent.json`.
- Add pagination and search/filter for large invoice sets.
- Add authentication so only the owner can see and approve reminders.
