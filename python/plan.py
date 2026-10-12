"""Payment reminder rules engine (part 1).

Run from inside python/:

    python plan.py --invoices ../data/invoices.json --sent ../data/sent.json --today 2026-10-12 --out ../actions.json
"""

import argparse
import json
import sys
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Step ordering (for "highest step reached" logic)
# ---------------------------------------------------------------------------

STEPS = ["friendly", "firm", "final"]
STEP_RANK = {s: i for i, s in enumerate(STEPS)}
STEP_DAYS = {"friendly": 3, "firm": 10, "final": 24}
STEP_NEEDS_APPROVAL = {"friendly": False, "firm": True, "final": True}


def parse_date(s):
    """Return a date object for a YYYY-MM-DD string, or None if invalid/missing."""
    if not s or not isinstance(s, str):
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        # Extra check: strptime accepts "2026-02-30" on some platforms by normalising
        # it, so we re-format and compare.
        if dt.strftime("%Y-%m-%d") != s:
            return None
        return dt.date()
    except ValueError:
        return None


def build_message(invoice, step, days_overdue):
    """Return a plain-text reminder email body for the given step."""
    customer = invoice["customer"]
    inv_id = invoice["id"]
    due_date = invoice["due_date"]
    amount = invoice["amount"]
    currency = invoice["currency"]
    formatted_amount = f"{currency} {amount:,.2f}"

    if step == "friendly":
        subject_line = "Friendly payment reminder"
        body = (
            f"Dear {customer},\n\n"
            f"This is a friendly reminder that invoice {inv_id}, "
            f"due on {due_date}, remains unpaid. "
            f"The outstanding balance is {formatted_amount}. "
            f"The invoice is now {days_overdue} day{'s' if days_overdue != 1 else ''} overdue.\n\n"
            f"Please arrange payment at your earliest convenience. "
            f"If you have already sent payment, kindly disregard this message.\n\n"
            f"Thank you for your business.\n\n"
            f"Kind regards"
        )
    elif step == "firm":
        body = (
            f"Dear {customer},\n\n"
            f"We are writing regarding invoice {inv_id}, "
            f"due on {due_date}, which remains unpaid. "
            f"The outstanding balance of {formatted_amount} is now "
            f"{days_overdue} day{'s' if days_overdue != 1 else ''} overdue.\n\n"
            f"We request that you settle this balance promptly. "
            f"If payment has already been sent, please contact us with the details "
            f"so we can update our records.\n\n"
            f"Please treat this matter as urgent.\n\n"
            f"Regards"
        )
    else:  # final
        body = (
            f"Dear {customer},\n\n"
            f"This is our final notice regarding invoice {inv_id}, "
            f"due on {due_date}, which remains unpaid. "
            f"The outstanding balance of {formatted_amount} is now "
            f"{days_overdue} day{'s' if days_overdue != 1 else ''} overdue.\n\n"
            f"Immediate payment is required. "
            f"Please contact us without delay to arrange settlement of this account.\n\n"
            f"Yours sincerely"
        )
    return body


def build_plan(invoices, sent, today_str):
    """Return the plan for `today` as a dict with keys today, actions and skipped.

    invoices: the list from invoices.json
    sent:     the list from sent.json
    today_str: a date string, YYYY-MM-DD (already validated by the caller)
    """
    today = parse_date(today_str)
    if today is None:
        raise ValueError(f"Invalid today date: {today_str!r}")

    # ------------------------------------------------------------------
    # 1. Detect duplicate ids (every copy is skipped; listed once)
    # ------------------------------------------------------------------
    id_count = {}
    for inv in invoices:
        inv_id = inv.get("id")
        if inv_id is not None:
            id_count[inv_id] = id_count.get(inv_id, 0) + 1

    duplicate_ids = {k for k, v in id_count.items() if v > 1}

    # ------------------------------------------------------------------
    # 2. Build a set of (invoice_id, step) that have already been sent,
    #    ignoring entries for unknown ids or invalid steps.
    # ------------------------------------------------------------------
    valid_invoice_ids = {inv.get("id") for inv in invoices if inv.get("id")}
    sent_set = set()
    for entry in sent:
        sid = entry.get("invoice_id")
        sstep = entry.get("step")
        if sid in valid_invoice_ids and sstep in STEP_RANK:
            sent_set.add((sid, sstep))

    # ------------------------------------------------------------------
    # 3. Process each invoice
    # ------------------------------------------------------------------
    actions = []
    skipped = []
    seen_duplicate_ids = set()  # to list each duplicate id only once

    for inv in invoices:
        inv_id = inv.get("id")

        # --- Bad data: duplicate_id ---
        if inv_id in duplicate_ids:
            if inv_id not in seen_duplicate_ids:
                skipped.append({"invoice_id": inv_id, "reason": "duplicate_id"})
                seen_duplicate_ids.add(inv_id)
            continue

        # --- Bad data: invalid_amount ---
        amount = inv.get("amount")
        if amount is None or not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
            skipped.append({"invoice_id": inv_id, "reason": "invalid_amount"})
            continue

        # --- Bad data: missing_due_date ---
        raw_due = inv.get("due_date")
        if raw_due is None or raw_due == "":
            skipped.append({"invoice_id": inv_id, "reason": "missing_due_date"})
            continue

        # --- Bad data: invalid_due_date ---
        due_date = parse_date(raw_due)
        if due_date is None:
            skipped.append({"invoice_id": inv_id, "reason": "invalid_due_date"})
            continue

        # --- Bad data: invalid_paid_date ---
        raw_paid = inv.get("paid_date")
        if raw_paid is not None and raw_paid != "":
            paid_date = parse_date(raw_paid)
            if paid_date is None or paid_date > today:
                skipped.append({"invoice_id": inv_id, "reason": "invalid_paid_date"})
                continue
        else:
            paid_date = None  # null or missing means unpaid

        # --- Paid ---
        if paid_date is not None:
            # paid_date is on or before today → skip
            continue

        # --- Days overdue ---
        days_overdue = (today - due_date).days

        # --- Not yet overdue enough ---
        if days_overdue < 3:
            continue

        # --- Determine highest step reached ---
        highest_step = None
        for step in reversed(STEPS):  # final → firm → friendly
            if days_overdue >= STEP_DAYS[step]:
                highest_step = step
                break

        if highest_step is None:
            continue

        # --- Check if that step (or higher) already sent ---
        highest_rank = STEP_RANK[highest_step]
        already_sent = any(
            (inv_id, s) in sent_set and STEP_RANK[s] >= highest_rank
            for s in STEPS
        )
        if already_sent:
            continue

        # --- Plan the action ---
        message = build_message(inv, highest_step, days_overdue)
        actions.append({
            "invoice_id": inv_id,
            "step": highest_step,
            "needs_approval": STEP_NEEDS_APPROVAL[highest_step],
            "days_overdue": days_overdue,
            "message": message,
        })

    # Sort both lists by invoice_id (plain text / lexicographic order)
    actions.sort(key=lambda x: x["invoice_id"])
    skipped.sort(key=lambda x: x["invoice_id"])

    return {"today": today_str, "actions": actions, "skipped": skipped}


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: could not parse JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Plan today's payment reminders.")
    parser.add_argument("--invoices", required=True, help="path to invoices.json")
    parser.add_argument("--sent", required=True, help="path to sent.json")
    parser.add_argument("--today", required=True, help="date as YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="path to write the plan JSON")
    args = parser.parse_args()

    # Validate --today
    if parse_date(args.today) is None:
        print(f"Error: --today must be a valid YYYY-MM-DD date, got: {args.today!r}", file=sys.stderr)
        sys.exit(1)

    invoices = read_json(args.invoices)
    sent = read_json(args.sent)
    plan = build_plan(invoices, sent, args.today)

    try:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2)
            f.write("\n")
    except OSError as e:
        print(f"Error: could not write output file {args.out}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote plan to {args.out}")


if __name__ == "__main__":
    main()
