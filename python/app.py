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
    "duplicate_id":    "Duplicate invoice ID — this ID appears more than once in the data",
    "invalid_amount":  "Invalid amount — amount is missing, not a number, or not greater than zero",
    "missing_due_date":"Missing due date — due date is absent or empty",
    "invalid_due_date":"Invalid due date — due date is not a valid YYYY-MM-DD calendar date",
    "invalid_paid_date":"Invalid paid date — paid date is not a valid YYYY-MM-DD date or is in the future",
}

STEP_LABELS = {
    "friendly": "Friendly Reminder",
    "firm":     "Firm Reminder",
    "final":    "Final Notice",
}


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

def _html_head(title="Payment Reminder Dashboard"):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="Daily payment reminder dashboard: approve or reject firm and final notices, and review skipped invoices.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
/* ============================================================
   CSS CUSTOM PROPERTIES — Orange / Purple / Pink palette
   ============================================================ */
:root {{
  /* Base colours */
  --bg-from:  #0d0714;
  --bg-to:    #140a1f;
  --orange:   #ff7c2a;
  --pink:     #f050a8;
  --purple:   #9b5de5;
  --violet:   #c77dff;
  --soft-orange: #ffb347;

  /* Glass surfaces */
  --glass-bg:   rgba(255,255,255,0.045);
  --glass-bg2:  rgba(255,255,255,0.07);
  --glass-border: rgba(255,255,255,0.1);
  --glass-border2: rgba(255,255,255,0.18);

  /* Text */
  --text:     #f0e6ff;
  --muted:    #a89bc2;
  --dimmed:   #6e5f88;

  /* Semantic */
  --c-friendly: #34d399;
  --c-friendly-bg: rgba(52,211,153,0.13);
  --c-firm:     #fb923c;
  --c-firm-bg:  rgba(251,146,60,0.13);
  --c-final:    #f87171;
  --c-final-bg: rgba(248,113,113,0.13);

  --radius-lg: 20px;
  --radius-md: 14px;
  --radius-sm: 8px;
  --transition: 0.22s cubic-bezier(0.4,0,0.2,1);
}}

/* ============================================================
   RESET & BASE
   ============================================================ */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg-from);
  background-image:
    radial-gradient(ellipse 80% 60% at 20% -10%, rgba(155,93,229,0.35) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 80% 110%, rgba(255,124,42,0.25) 0%, transparent 60%),
    radial-gradient(ellipse 50% 40% at 55% 50%, rgba(240,80,168,0.12) 0%, transparent 60%);
  background-attachment: fixed;
  color: var(--text);
  min-height: 100vh;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}}

/* ============================================================
   HEADER
   ============================================================ */
header {{
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(13,7,20,0.65);
  backdrop-filter: blur(22px) saturate(180%);
  -webkit-backdrop-filter: blur(22px) saturate(180%);
  border-bottom: 1px solid var(--glass-border);
  padding: 0.9rem 2rem;
  display: flex;
  align-items: center;
  gap: 1.2rem;
  flex-wrap: wrap;
}}

.header-logo {{
  display: flex;
  align-items: center;
  gap: 0.7rem;
  text-decoration: none;
}}

.logo-icon {{
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--orange), var(--pink));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  flex-shrink: 0;
  box-shadow: 0 4px 18px rgba(255,124,42,0.4);
}}

header h1 {{
  font-size: 1.2rem;
  font-weight: 800;
  letter-spacing: -0.025em;
  background: linear-gradient(100deg, var(--soft-orange), var(--pink), var(--violet));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}

.header-pills {{
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}}

.header-date {{
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--muted);
  background: var(--glass-bg2);
  border: 1px solid var(--glass-border);
  border-radius: 999px;
  padding: 0.28rem 0.9rem;
  white-space: nowrap;
  backdrop-filter: blur(8px);
}}

/* ============================================================
   MAIN LAYOUT
   ============================================================ */
main {{
  max-width: 980px;
  margin: 0 auto;
  padding: 2rem 1.25rem 5rem;
}}

/* ============================================================
   SECTION HEADINGS
   ============================================================ */
.section-heading {{
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin: 2.5rem 0 1rem;
}}

.section-heading h2 {{
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--muted);
}}

.section-heading .sep {{
  flex: 1;
  height: 1px;
  background: linear-gradient(to right, var(--glass-border), transparent);
}}

/* ============================================================
   BADGE COUNTS
   ============================================================ */
.badge {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.5rem;
  height: 1.5rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0 0.45rem;
  letter-spacing: 0;
}}
.badge-green  {{ background: rgba(52,211,153,0.2);  color: #34d399; }}
.badge-orange {{ background: rgba(251,146,60,0.2);  color: #fb923c; }}
.badge-red    {{ background: rgba(248,113,113,0.2); color: #f87171; }}
.badge-violet {{ background: rgba(199,125,255,0.2); color: var(--violet); }}

/* ============================================================
   GLASS CARDS
   ============================================================ */
.card {{
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  padding: 1.25rem 1.4rem;
  margin-bottom: 0.9rem;
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
  transition: border-color var(--transition), transform var(--transition), box-shadow var(--transition);
  position: relative;
  overflow: hidden;
}}

.card::before {{
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(135deg, rgba(255,255,255,0.04) 0%, transparent 60%);
  pointer-events: none;
}}

.card:hover {{
  border-color: var(--glass-border2);
  transform: translateY(-2px);
  box-shadow: 0 12px 40px rgba(0,0,0,0.35);
}}

/* Left accent bar on cards */
.card.card-friendly {{ border-left: 3px solid var(--c-friendly); }}
.card.card-firm     {{ border-left: 3px solid var(--c-firm); }}
.card.card-final    {{ border-left: 3px solid var(--c-final); }}

/* ============================================================
   CARD INTERNALS
   ============================================================ */
.card-header {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.55rem 1rem;
  margin-bottom: 0.7rem;
}}

.inv-id {{
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.8rem;
  font-weight: 600;
  background: rgba(199,125,255,0.12);
  border: 1px solid rgba(199,125,255,0.25);
  border-radius: var(--radius-sm);
  padding: 0.18rem 0.55rem;
  color: var(--violet);
  letter-spacing: 0.03em;
  flex-shrink: 0;
}}

.customer {{
  font-weight: 700;
  font-size: 1.02rem;
  color: var(--text);
  flex: 1;
  min-width: 120px;
}}

/* ---- Step pills ---- */
.step-pill {{
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  border-radius: 999px;
  padding: 0.22rem 0.8rem;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  flex-shrink: 0;
}}
.step-friendly {{ background: var(--c-friendly-bg); color: var(--c-friendly); border: 1px solid rgba(52,211,153,0.3); }}
.step-firm     {{ background: var(--c-firm-bg);     color: var(--c-firm);     border: 1px solid rgba(251,146,60,0.3); }}
.step-final    {{ background: var(--c-final-bg);    color: var(--c-final);    border: 1px solid rgba(248,113,113,0.3); }}

/* ---- Meta row ---- */
.meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 1.4rem;
  font-size: 0.8rem;
  color: var(--muted);
  margin-bottom: 0.85rem;
}}
.meta span {{
  display: flex;
  align-items: center;
  gap: 0.3rem;
}}
.meta .overdue-days {{
  color: var(--c-firm);
  font-weight: 600;
}}

/* ---- Message box ---- */
.message-label {{
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--dimmed);
  margin-bottom: 0.35rem;
}}

.message-box {{
  background: rgba(0,0,0,0.3);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  padding: 0.85rem 1.1rem;
  font-size: 0.82rem;
  color: var(--muted);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 90px;
  overflow: hidden;
  cursor: pointer;
  transition: max-height 0.4s cubic-bezier(0.4,0,0.2,1), border-color var(--transition), background var(--transition);
  margin-bottom: 0.3rem;
  line-height: 1.7;
  position: relative;
}}
.message-box::after {{
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 2.5rem;
  background: linear-gradient(to top, rgba(0,0,0,0.5), transparent);
  border-radius: 0 0 var(--radius-sm) var(--radius-sm);
  pointer-events: none;
  transition: opacity var(--transition);
}}
.message-box.expanded {{
  max-height: 520px;
}}
.message-box.expanded::after {{
  opacity: 0;
}}
.message-box:hover {{
  border-color: rgba(155,93,229,0.35);
  background: rgba(0,0,0,0.4);
}}
.expand-hint {{
  font-size: 0.7rem;
  color: var(--dimmed);
  margin-bottom: 1rem;
  cursor: pointer;
}}
.expand-hint:hover {{ color: var(--violet); }}

/* ============================================================
   ACTION BUTTONS
   ============================================================ */
.actions-row {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  align-items: center;
  margin-top: 0.2rem;
}}

.btn {{
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border: none;
  border-radius: 10px;
  padding: 0.5rem 1.2rem;
  font-size: 0.83rem;
  font-weight: 700;
  cursor: pointer;
  transition: opacity var(--transition), transform var(--transition), box-shadow var(--transition);
  letter-spacing: 0.01em;
  white-space: nowrap;
}}
.btn:hover   {{ opacity: 0.88; transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.3); }}
.btn:active  {{ transform: translateY(0); box-shadow: none; }}
.btn:focus-visible {{ outline: 2px solid var(--violet); outline-offset: 2px; }}

.btn-approve {{
  background: linear-gradient(135deg, #10b981, #34d399);
  color: #000;
  box-shadow: 0 3px 14px rgba(16,185,129,0.35);
}}
.btn-reject {{
  background: linear-gradient(135deg, #ef4444, #f87171);
  color: #fff;
  box-shadow: 0 3px 14px rgba(239,68,68,0.35);
}}

/* Decision tags (after decision made) */
.decision-tag {{
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  border-radius: 10px;
  padding: 0.5rem 1.1rem;
  font-size: 0.83rem;
  font-weight: 700;
}}
.decision-approved {{ background: rgba(52,211,153,0.15); color: #34d399; border: 1px solid rgba(52,211,153,0.35); }}
.decision-rejected {{ background: rgba(248,113,113,0.15); color: #f87171; border: 1px solid rgba(248,113,113,0.35); }}

.change-link {{
  font-size: 0.76rem;
  color: var(--dimmed);
  background: none;
  border: none;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
  padding: 0;
  font-family: inherit;
  transition: color var(--transition);
}}
.change-link:hover {{ color: var(--violet); }}

/* ============================================================
   SKIP CARDS
   ============================================================ */
.skip-card {{
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-left: 3px solid rgba(248,113,113,0.5);
  border-radius: var(--radius-md);
  padding: 0.85rem 1.25rem;
  margin-bottom: 0.65rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 1.2rem;
  backdrop-filter: blur(10px);
  transition: border-color var(--transition);
}}
.skip-card:hover {{
  border-color: rgba(248,113,113,0.4);
  border-left-color: #f87171;
}}
.skip-arrow {{
  color: var(--dimmed);
  font-size: 0.9rem;
}}
.skip-reason {{
  font-size: 0.82rem;
  color: var(--muted);
  flex: 1;
}}

/* ============================================================
   EMPTY STATE
   ============================================================ */
.empty-state {{
  text-align: center;
  padding: 2.5rem 1.5rem;
  color: var(--muted);
  border: 1px dashed rgba(255,255,255,0.08);
  border-radius: var(--radius-lg);
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
}}
.empty-state .es-icon {{
  font-size: 2rem;
  margin-bottom: 0.5rem;
  display: block;
}}
.empty-state p {{ font-size: 0.88rem; }}

/* ============================================================
   ERROR BOX
   ============================================================ */
.error-box {{
  background: rgba(239,68,68,0.1);
  border: 1px solid rgba(239,68,68,0.3);
  border-radius: var(--radius-lg);
  padding: 1.3rem 1.6rem;
  color: #f87171;
  backdrop-filter: blur(10px);
  display: flex;
  gap: 0.8rem;
  align-items: flex-start;
}}
.error-box .error-icon {{ font-size: 1.3rem; flex-shrink: 0; }}

/* ============================================================
   SUMMARY BAR (stats at top)
   ============================================================ */
.summary-bar {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}}
.stat-chip {{
  display: flex;
  align-items: center;
  gap: 0.55rem;
  background: var(--glass-bg2);
  border: 1px solid var(--glass-border);
  border-radius: 12px;
  padding: 0.65rem 1.1rem;
  backdrop-filter: blur(12px);
  flex: 1;
  min-width: 130px;
  transition: border-color var(--transition), transform var(--transition);
}}
.stat-chip:hover {{ border-color: var(--glass-border2); transform: translateY(-1px); }}
.stat-num {{
  font-size: 1.7rem;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.04em;
}}
.stat-label {{
  font-size: 0.73rem;
  font-weight: 500;
  color: var(--muted);
  line-height: 1.3;
}}
.stat-chip.s-green  .stat-num {{ color: var(--c-friendly); }}
.stat-chip.s-orange .stat-num {{ color: var(--c-firm); }}
.stat-chip.s-red    .stat-num {{ color: var(--c-final); }}
.stat-chip.s-violet .stat-num {{ color: var(--violet); }}

/* ============================================================
   RESPONSIVE
   ============================================================ */
@media (max-width: 480px) {{
  header {{ padding: 0.8rem 1rem; }}
  header h1 {{ font-size: 1rem; }}
  main {{ padding: 1.5rem 0.85rem 4rem; }}
  .card {{ padding: 1rem 1.05rem; }}
  .btn {{ font-size: 0.78rem; padding: 0.42rem 0.9rem; }}
  .customer {{ font-size: 0.95rem; }}
  .stat-num {{ font-size: 1.4rem; }}
}}
</style>
</head>
<body>
"""


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _get_enriched_plan():
    """Return (plan_dict, error_str). Plan actions are enriched with display fields."""
    try:
        invoices_path = os.path.join(DATA_DIR, "invoices.json")
        sent_path = os.path.join(DATA_DIR, "sent.json")
        invoices = read_json(invoices_path)
        sent = read_json(sent_path)
        plan = build_plan(invoices, sent, TODAY)

        # Build lookup by invoice id (first occurrence wins — duplicates are skipped anyway)
        inv_lookup = {}
        for inv in invoices:
            iid = inv.get("id")
            if iid and iid not in inv_lookup:
                inv_lookup[iid] = inv

        for a in plan["actions"]:
            iid = a["invoice_id"]
            inv = inv_lookup.get(iid, {})
            a["customer"]   = inv.get("customer", "")
            a["due_date"]   = inv.get("due_date", "")
            amt = inv.get("amount", 0)
            cur = inv.get("currency", "")
            try:
                a["amount_fmt"] = f"{cur} {float(amt):,.2f}"
            except (TypeError, ValueError):
                a["amount_fmt"] = ""

        return plan, None
    except SystemExit:
        return None, "Could not read data files. Check that DATA_DIR points to the right folder."
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


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def _render_page(plan, error):
    parts = [_html_head()]

    # Header
    parts.append(f"""
<header>
  <div class="header-logo">
    <div class="logo-icon">&#128179;</div>
    <h1>Payment Reminders</h1>
  </div>
  <div class="header-pills">
    <span class="header-date">&#128197;&nbsp; Today &mdash; {escape(TODAY)}</span>
  </div>
</header>
<main>
""")

    if error:
        parts.append(f"""
<div class="error-box">
  <span class="error-icon">&#9888;&#65039;</span>
  <div><strong>Error loading data</strong><br>{escape(error)}</div>
</div>""")
        parts.append("</main></body></html>")
        return "".join(parts)

    actions = plan["actions"]
    skipped = plan["skipped"]

    needs_approval = [a for a in actions if a["needs_approval"]]
    auto_actions   = [a for a in actions if not a["needs_approval"]]
    approved_count = sum(1 for d in _decisions.values() if d == "approved")
    rejected_count = sum(1 for d in _decisions.values() if d == "rejected")

    # Summary chips
    parts.append('<div class="summary-bar">')
    parts.append(f'<div class="stat-chip s-green"><div class="stat-num">{len(auto_actions)}</div><div class="stat-label">Auto&nbsp;send<br>today</div></div>')
    parts.append(f'<div class="stat-chip s-orange"><div class="stat-num">{len(needs_approval)}</div><div class="stat-label">Awaiting<br>approval</div></div>')
    parts.append(f'<div class="stat-chip s-red"><div class="stat-num">{len(skipped)}</div><div class="stat-label">Skipped<br>invoices</div></div>')
    parts.append(f'<div class="stat-chip s-violet"><div class="stat-num">{approved_count + rejected_count}</div><div class="stat-label">Decisions<br>recorded</div></div>')
    parts.append('</div>')

    # ── Ready to Send (friendly, no approval needed) ──────────────────────
    parts.append(_section_heading("&#128233;&nbsp; Ready to Send", len(auto_actions), "badge-green"))
    if auto_actions:
        for a in auto_actions:
            parts.append(_render_action_card(a, needs_approval=False))
    else:
        parts.append(_empty_state("&#10003;", "No reminders to send automatically today."))

    # ── Needs Approval ────────────────────────────────────────────────────
    parts.append(_section_heading("&#9888;&#65039;&nbsp; Needs Your Approval", len(needs_approval), "badge-orange"))
    if needs_approval:
        for a in needs_approval:
            parts.append(_render_action_card(a, needs_approval=True))
    else:
        parts.append(_empty_state("&#10003;", "No reminders waiting for approval."))

    # ── Skipped ───────────────────────────────────────────────────────────
    parts.append(_section_heading("&#128683;&nbsp; Skipped Invoices", len(skipped), "badge-red"))
    if skipped:
        for s in skipped:
            reason_label = REASON_LABELS.get(s["reason"], s["reason"])
            parts.append(f"""
<div class="skip-card">
  <span class="inv-id">{escape(s["invoice_id"])}</span>
  <span class="skip-arrow">&#8594;</span>
  <span class="skip-reason">{escape(reason_label)}</span>
</div>""")
    else:
        parts.append(_empty_state("&#10003;", "All invoices have valid data."))

    if not actions and not skipped:
        parts.append(_empty_state("&#127881;", "<strong>Nothing to do today!</strong><br>All invoices are either paid, not yet due, or have already had all reminders sent.", margin_top="2rem"))

    parts.append("</main>")
    parts.append("""
<script>
(function () {
  // Toggle message expand/collapse
  document.querySelectorAll('.message-box').forEach(function (box) {
    var hint = box.nextElementSibling;
    box.addEventListener('click', function () {
      var expanded = this.classList.toggle('expanded');
      this.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      if (hint && hint.classList.contains('expand-hint')) {
        hint.textContent = expanded ? 'Click to collapse' : 'Click to expand message';
      }
    });
  });
})();
</script>
</body></html>""")
    return "".join(parts)


def _section_heading(label, count, badge_class):
    return f"""
<div class="section-heading">
  <h2>{label} &nbsp;<span class="badge {badge_class}">{count}</span></h2>
  <div class="sep"></div>
</div>
"""


def _empty_state(icon, text, margin_top="0"):
    style = f'style="margin-top:{margin_top};"' if margin_top != "0" else ""
    return f'<div class="empty-state" {style}><span class="es-icon">{icon}</span><p>{text}</p></div>'


def _render_action_card(a, needs_approval):
    inv_id     = a["invoice_id"]
    step       = a["step"]
    step_label = STEP_LABELS.get(step, step)
    days       = a["days_overdue"]
    message    = escape(a["message"])
    decision   = _decisions.get(inv_id)
    customer   = escape(a.get("customer", ""))
    due_date   = escape(a.get("due_date", ""))
    amount_fmt = escape(a.get("amount_fmt", ""))

    parts = [f'<div class="card card-{step}" id="card-{escape(inv_id)}">']

    # Card header
    parts.append('<div class="card-header">')
    parts.append(f'<span class="inv-id">{escape(inv_id)}</span>')
    parts.append(f'<span class="customer">{customer}</span>')
    parts.append(f'<span class="step-pill step-{step}">{escape(step_label)}</span>')
    parts.append('</div>')

    # Meta row
    parts.append('<div class="meta">')
    parts.append(f'<span>&#128197; Due&nbsp;{due_date}</span>')
    parts.append(f'<span>&#128176;&nbsp;{amount_fmt}</span>')
    parts.append(f'<span class="overdue-days">&#9201;&#65039;&nbsp;{days} day{"s" if days != 1 else ""} overdue</span>')
    parts.append('</div>')

    # Email message preview
    parts.append('<div class="message-label">Email message</div>')
    parts.append(f'<div class="message-box" tabindex="0" role="button" aria-expanded="false">{message}</div>')
    parts.append('<p class="expand-hint">Click to expand message</p>')

    # Approve / Reject buttons
    parts.append('<div class="actions-row">')
    if needs_approval:
        if decision == "approved":
            parts.append('<span class="decision-tag decision-approved">&#10003;&nbsp;Approved</span>')
            parts.append(f'<form method="POST" action="/decide" style="display:inline"><input type="hidden" name="invoice_id" value="{escape(inv_id)}"><input type="hidden" name="decision" value="rejected"><button class="change-link" type="submit">Change to Rejected</button></form>')
        elif decision == "rejected":
            parts.append('<span class="decision-tag decision-rejected">&#10007;&nbsp;Rejected</span>')
            parts.append(f'<form method="POST" action="/decide" style="display:inline"><input type="hidden" name="invoice_id" value="{escape(inv_id)}"><input type="hidden" name="decision" value="approved"><button class="change-link" type="submit">Change to Approved</button></form>')
        else:
            parts.append(f'<form method="POST" action="/decide" style="display:inline"><input type="hidden" name="invoice_id" value="{escape(inv_id)}"><input type="hidden" name="decision" value="approved"><button class="btn btn-approve" type="submit" id="approve-{escape(inv_id)}">&#10003;&nbsp;Approve</button></form>')
            parts.append(f'<form method="POST" action="/decide" style="display:inline"><input type="hidden" name="invoice_id" value="{escape(inv_id)}"><input type="hidden" name="decision" value="rejected"><button class="btn btn-reject" type="submit" id="reject-{escape(inv_id)}">&#10007;&nbsp;Reject</button></form>')
    parts.append('</div>')
    parts.append('</div>')
    return "".join(parts)


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

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
        params  = _parse_post_body(self)
        inv_id  = params.get("invoice_id", "").strip()
        decision = params.get("decision", "").strip()
        if inv_id and decision in ("approved", "rejected"):
            _decisions[inv_id] = decision
        # PRG pattern — redirect back to main page
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    server = ThreadingHTTPServer(("", PORT), Handler)
    print(f"Serving on http://localhost:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
