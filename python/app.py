"""The owner's page (part 2). Standard library only, no install needed.

Run from inside python/:

    python app.py

Environment variables:
    PORT      port to listen on, default 8000
    DATA_DIR  folder with invoices.json and sent.json, default ../data
    TODAY     date as YYYY-MM-DD, default the real date
"""

import json
import os
import sys
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Add parent dir to path so we can import plan module
sys.path.insert(0, str(Path(__file__).parent))
from plan import build_plan, parse_date, read_json  # noqa: E402

PORT = int(os.environ.get("PORT", "8000"))
DATA_DIR = os.environ.get("DATA_DIR", "../data")
TODAY = os.environ.get("TODAY") or date.today().isoformat()

# In-memory store for approval decisions: key = invoice_id, value = "approved" | "rejected"
_decisions = {}

REASON_LABELS = {
    "duplicate_id": "Duplicate invoice ID — this ID appears more than once in the data",
    "invalid_amount": "Invalid amount — amount is missing, not a number, or not greater than zero",
    "missing_due_date": "Missing due date — due date is absent or empty",
    "invalid_due_date": "Invalid due date — due date is not a valid YYYY-MM-DD calendar date",
    "invalid_paid_date": "Invalid paid date — paid date is not a valid YYYY-MM-DD date or is in the future",
}

STEP_LABELS = {
    "friendly": "Friendly reminder",
    "firm": "Firm reminder",
    "final": "Final notice",
}


def _html_head(title="Payment Reminder Dashboard"):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="Daily payment reminder dashboard: see which customers need reminders, approve or reject firm and final notices, and review skipped invoices.">
<style>
  :root {{
    --bg: #0f1117;
    --surface: #1a1d2e;
    --surface2: #252840;
    --border: #2e3250;
    --accent: #6c63ff;
    --accent2: #a78bfa;
    --green: #22c55e;
    --yellow: #f59e0b;
    --red: #ef4444;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --radius: 12px;
    --transition: 0.2s ease;
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    min-height: 100vh;
    line-height: 1.6;
  }}
  header {{
    background: linear-gradient(135deg, #1a1d2e 0%, #252840 100%);
    border-bottom: 1px solid var(--border);
    padding: 1.25rem 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
  }}
  header h1 {{
    font-size: 1.35rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    background: linear-gradient(135deg, #a78bfa, #6c63ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }}
  .header-date {{
    margin-left: auto;
    font-size: 0.85rem;
    color: var(--muted);
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.25rem 0.85rem;
    white-space: nowrap;
  }}
  main {{ max-width: 960px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }}
  .section-title {{
    font-size: 1rem;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 2rem 0 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}
  .badge {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.5rem;
    height: 1.5rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 0 0.4rem;
  }}
  .badge-purple {{ background: #6c63ff33; color: #a78bfa; }}
  .badge-yellow {{ background: #f59e0b22; color: #f59e0b; }}
  .badge-red {{ background: #ef444422; color: #ef4444; }}
  .badge-green {{ background: #22c55e22; color: #22c55e; }}
  .badge-gray {{ background: #94a3b822; color: #94a3b8; }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.1rem 1.2rem;
    margin-bottom: 0.75rem;
    transition: border-color var(--transition);
  }}
  .card:hover {{ border-color: var(--accent); }}
  .card-header {{
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 0.5rem 1rem;
    margin-bottom: 0.6rem;
  }}
  .inv-id {{
    font-family: monospace;
    font-size: 0.85rem;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.15rem 0.5rem;
    color: var(--accent2);
    flex-shrink: 0;
  }}
  .customer {{ font-weight: 600; font-size: 1rem; }}
  .meta {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem 1.2rem;
    font-size: 0.82rem;
    color: var(--muted);
    margin-bottom: 0.75rem;
  }}
  .meta span {{ display: flex; align-items: center; gap: 0.3rem; }}
  .step-pill {{
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    border-radius: 999px;
    padding: 0.2rem 0.7rem;
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }}
  .step-friendly {{ background: #22c55e22; color: #22c55e; }}
  .step-firm {{ background: #f59e0b22; color: #f59e0b; }}
  .step-final {{ background: #ef444422; color: #ef4444; }}
  .message-box {{
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.8rem 1rem;
    font-size: 0.83rem;
    color: var(--muted);
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 160px;
    overflow-y: auto;
    cursor: pointer;
    transition: max-height var(--transition), border-color var(--transition);
    margin-bottom: 0.75rem;
  }}
  .message-box.expanded {{ max-height: 600px; }}
  .message-box:hover {{ border-color: var(--accent); }}
  .expand-hint {{
    font-size: 0.75rem;
    color: var(--muted);
    margin-bottom: 0.75rem;
    margin-top: -0.4rem;
  }}
  .actions-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
  }}
  .btn {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border: none;
    border-radius: 8px;
    padding: 0.45rem 1rem;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity var(--transition), transform var(--transition);
  }}
  .btn:hover {{ opacity: 0.85; transform: translateY(-1px); }}
  .btn:active {{ transform: translateY(0); }}
  .btn:focus-visible {{
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }}
  .btn-approve {{ background: #22c55e; color: #000; }}
  .btn-reject {{ background: #ef4444; color: #fff; }}
  .decision-tag {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border-radius: 8px;
    padding: 0.45rem 1rem;
    font-size: 0.85rem;
    font-weight: 600;
  }}
  .decision-approved {{ background: #22c55e22; color: #22c55e; border: 1px solid #22c55e44; }}
  .decision-rejected {{ background: #ef444422; color: #ef4444; border: 1px solid #ef444444; }}
  .change-link {{
    font-size: 0.78rem;
    color: var(--muted);
    background: none;
    border: none;
    cursor: pointer;
    text-decoration: underline;
    padding: 0;
  }}
  .change-link:hover {{ color: var(--accent2); }}
  .empty-state {{
    text-align: center;
    padding: 2.5rem 1rem;
    color: var(--muted);
    border: 1px dashed var(--border);
    border-radius: var(--radius);
  }}
  .empty-state .emoji {{ font-size: 2rem; margin-bottom: 0.5rem; }}
  .error-box {{
    background: #ef444415;
    border: 1px solid #ef444444;
    border-radius: var(--radius);
    padding: 1.2rem 1.4rem;
    color: #ef4444;
  }}
  .skip-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 0.85rem 1.2rem;
    margin-bottom: 0.6rem;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 1rem;
  }}
  .skip-reason {{ font-size: 0.85rem; color: var(--muted); }}
  @media (max-width: 480px) {{
    header {{ padding: 1rem; }}
    header h1 {{ font-size: 1.1rem; }}
    .card {{ padding: 0.9rem 1rem; }}
    .btn {{ font-size: 0.8rem; padding: 0.4rem 0.8rem; }}
  }}
</style>
</head>
<body>
"""


def _get_plan_or_error():
    try:
        invoices_path = os.path.join(DATA_DIR, "invoices.json")
        sent_path = os.path.join(DATA_DIR, "sent.json")
        invoices = read_json(invoices_path)
        sent = read_json(sent_path)
        return build_plan(invoices, sent, TODAY), None
    except SystemExit:
        return None, "Could not read data files. Check that DATA_DIR is set correctly and the files exist."
    except Exception as exc:
        return None, f"Unexpected error: {escape(str(exc))}"


def _render_page(plan, error):
    parts = [_html_head()]
    parts.append(f"""
<header>
  <h1>&#128179; Payment Reminder Dashboard</h1>
  <span class="header-date">&#128197; Today: {escape(TODAY)}</span>
</header>
<main>
""")

    if error:
        parts.append(f'<div class="error-box"><strong>&#9888;&#65039; Error:</strong> {escape(error)}</div>')
        parts.append("</main></body></html>")
        return "".join(parts)

    actions = plan["actions"]
    skipped = plan["skipped"]

    # ------------------------------------------------------------------ Actions
    needs_approval = [a for a in actions if a["needs_approval"]]
    auto_actions = [a for a in actions if not a["needs_approval"]]

    # --- Ready to send (friendly, no approval needed) ---
    parts.append(f'<div class="section-title">&#128233; Ready to Send <span class="badge badge-green">{len(auto_actions)}</span></div>')
    if auto_actions:
        for a in auto_actions:
            parts.append(_render_action_card(a, needs_approval=False))
    else:
        parts.append('<div class="empty-state"><div class="emoji">&#10003;</div><p>No reminders to send automatically today.</p></div>')

    # --- Needs approval ---
    parts.append(f'<div class="section-title">&#9888;&#65039; Needs Your Approval <span class="badge badge-yellow">{len(needs_approval)}</span></div>')
    if needs_approval:
        for a in needs_approval:
            parts.append(_render_action_card(a, needs_approval=True))
    else:
        parts.append('<div class="empty-state"><div class="emoji">&#10003;</div><p>No reminders waiting for approval.</p></div>')

    # --- Skipped ---
    parts.append(f'<div class="section-title">&#9888; Skipped Invoices <span class="badge badge-red">{len(skipped)}</span></div>')
    if skipped:
        for s in skipped:
            reason_label = REASON_LABELS.get(s["reason"], s["reason"])
            parts.append(f"""
<div class="skip-card">
  <span class="inv-id">{escape(s["invoice_id"])}</span>
  <span class="skip-reason">&#8594; {escape(reason_label)}</span>
</div>""")
    else:
        parts.append('<div class="empty-state"><div class="emoji">&#10003;</div><p>All invoices have valid data.</p></div>')

    if not actions and not skipped:
        parts.append("""
<div class="empty-state" style="margin-top:2rem;">
  <div class="emoji">&#127881;</div>
  <p><strong>Nothing to do today!</strong><br>All invoices are either paid, not yet due, or have had all reminders sent.</p>
</div>""")

    parts.append("</main>")
    parts.append("""
<script>
document.querySelectorAll('.message-box').forEach(function(box) {
  box.addEventListener('click', function() {
    this.classList.toggle('expanded');
  });
  box.setAttribute('title', 'Click to expand/collapse');
});
</script>
</body></html>""")
    return "".join(parts)


def _render_action_card(a, needs_approval):
    inv_id = a["invoice_id"]
    step = a["step"]
    step_label = STEP_LABELS.get(step, step)
    step_class = f"step-{step}"
    days = a["days_overdue"]
    message = escape(a["message"])

    decision = _decisions.get(inv_id)

    parts = [f'<div class="card" id="card-{escape(inv_id)}">']
    parts.append(f'<div class="card-header">')
    parts.append(f'<span class="inv-id">{escape(inv_id)}</span>')
    parts.append(f'<span class="customer">{escape(a.get("customer", ""))}</span>')
    parts.append(f'<span class="step-pill {step_class}">{escape(step_label)}</span>')
    parts.append('</div>')

    parts.append('<div class="meta">')
    parts.append(f'<span>&#128197; Due: {escape(a.get("due_date", ""))}</span>')
    parts.append(f'<span>&#128176; {escape(a.get("amount_fmt", ""))}</span>')
    parts.append(f'<span>&#9201;&#65039; {days} day{"s" if days != 1 else ""} overdue</span>')
    parts.append('</div>')

    parts.append(f'<div class="message-box" tabindex="0" role="button" aria-expanded="false">{message}</div>')
    parts.append('<p class="expand-hint">Click message to expand</p>')

    parts.append('<div class="actions-row">')
    if needs_approval:
        if decision == "approved":
            parts.append(f'<span class="decision-tag decision-approved">&#10003; Approved</span>')
            parts.append(f'<form method="POST" action="/decide" style="display:inline"><input type="hidden" name="invoice_id" value="{escape(inv_id)}"><input type="hidden" name="decision" value="rejected"><button class="change-link" type="submit">Change to Rejected</button></form>')
        elif decision == "rejected":
            parts.append(f'<span class="decision-tag decision-rejected">&#10007; Rejected</span>')
            parts.append(f'<form method="POST" action="/decide" style="display:inline"><input type="hidden" name="invoice_id" value="{escape(inv_id)}"><input type="hidden" name="decision" value="approved"><button class="change-link" type="submit">Change to Approved</button></form>')
        else:
            parts.append(f'<form method="POST" action="/decide" style="display:inline"><input type="hidden" name="invoice_id" value="{escape(inv_id)}"><input type="hidden" name="decision" value="approved"><button class="btn btn-approve" type="submit" id="approve-{escape(inv_id)}">&#10003; Approve</button></form>')
            parts.append(f'<form method="POST" action="/decide" style="display:inline"><input type="hidden" name="invoice_id" value="{escape(inv_id)}"><input type="hidden" name="decision" value="rejected"><button class="btn btn-reject" type="submit" id="reject-{escape(inv_id)}">&#10007; Reject</button></form>')
    parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)


def _enrich_actions(actions):
    """Attach human-readable amount and other display fields to actions."""
    for a in actions:
        # The plan doesn't store amount/due_date directly in actions,
        # so we re-read from the data for display purposes
        pass  # data is embedded in the message; we'll parse from plan data


def _get_enriched_plan():
    """Return the plan enriched with display fields from the raw invoice data."""
    try:
        invoices_path = os.path.join(DATA_DIR, "invoices.json")
        sent_path = os.path.join(DATA_DIR, "sent.json")
        invoices = read_json(invoices_path)
        sent = read_json(sent_path)
        plan = build_plan(invoices, sent, TODAY)

        # Build a lookup by invoice id for display data
        inv_lookup = {}
        for inv in invoices:
            iid = inv.get("id")
            if iid and iid not in inv_lookup:
                inv_lookup[iid] = inv

        for a in plan["actions"]:
            iid = a["invoice_id"]
            inv = inv_lookup.get(iid, {})
            a["customer"] = inv.get("customer", "")
            a["due_date"] = inv.get("due_date", "")
            amt = inv.get("amount", 0)
            cur = inv.get("currency", "")
            try:
                a["amount_fmt"] = f"{cur} {float(amt):,.2f}"
            except (TypeError, ValueError):
                a["amount_fmt"] = ""

        return plan, None
    except SystemExit:
        return None, "Could not read data files. Check that DATA_DIR is set correctly and the files exist."
    except Exception as exc:
        return None, f"Unexpected error: {str(exc)}"


def _parse_post_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length).decode("utf-8")
    params = {}
    for pair in raw.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[_url_decode(k)] = _url_decode(v)
    return params


def _url_decode(s):
    import urllib.parse
    return urllib.parse.unquote_plus(s)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default request logging

    def do_GET(self):
        if self.path not in ("/", "/favicon.ico"):
            self.send_error(404)
            return
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        plan, error = _get_enriched_plan()
        body = _render_page(plan, error).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/decide":
            self.send_error(404)
            return
        params = _parse_post_body(self)
        inv_id = params.get("invoice_id", "").strip()
        decision = params.get("decision", "").strip()
        if inv_id and decision in ("approved", "rejected"):
            _decisions[inv_id] = decision
        # Redirect back to main page
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


def main():
    server = ThreadingHTTPServer(("", PORT), Handler)
    print(f"Serving on http://localhost:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
