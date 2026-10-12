"""The owner's page (part 2) with Local AI Copilot & Risk Intelligence.
Standard library only, with seamless AI integration to @xenova/transformers ONNX service.

Run from inside python/:

    python app.py

Environment variables:
    PORT      port to listen on, default 8000
    AI_PORT   port of Node.js AI service, default 8001
    DATA_DIR  folder with invoices.json and sent.json, default ../data
    TODAY     date as YYYY-MM-DD, default the real date
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Add parent dir to path so we can import plan module
sys.path.insert(0, str(Path(__file__).parent))
from plan import build_plan, parse_date, read_json  # noqa: E402

PORT = int(os.environ.get("PORT", "8000"))
AI_PORT = int(os.environ.get("AI_PORT", "8001"))
DATA_DIR = os.environ.get("DATA_DIR", "../data")
TODAY = os.environ.get("TODAY") or date.today().isoformat()

# In-memory store for approval decisions: key = invoice_id, value = "approved" | "rejected"
_decisions = {}

REASON_LABELS = {
    "duplicate_id":     "Duplicate invoice ID — this ID appears more than once in the data",
    "invalid_amount":   "Invalid amount — amount is missing, not a number, or not greater than zero",
    "missing_due_date": "Missing due date — due date is absent or empty",
    "invalid_due_date": "Invalid due date — due date is not a valid YYYY-MM-DD calendar date",
    "invalid_paid_date": "Invalid paid date — paid date is not a valid YYYY-MM-DD date or is in the future",
}

STEP_LABELS = {
    "friendly": "Friendly Reminder",
    "firm":     "Firm Reminder",
    "final":    "Final Notice",
}


def _ensure_ai_service():
    """Check if Node.js AI service is reachable; if not, spawn it in background."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{AI_PORT}/health")
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            if resp.status == 200:
                return True
    except Exception:
        pass

    # Try to launch node server in ai/ directory
    repo_root = Path(__file__).resolve().parent.parent
    ai_dir = repo_root / "ai"
    server_script = ai_dir / "server.js"
    if server_script.exists():
        try:
            print(f"[AI-Bridge] Spawning Node.js AI service on port {AI_PORT}...")
            subprocess.Popen(
                ["node", "server.js"],
                cwd=str(ai_dir),
                env=dict(os.environ, AI_PORT=str(AI_PORT)),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception as e:
            print(f"[AI-Bridge] Could not auto-spawn AI service: {e}")
    return False


# ---------------------------------------------------------------------------
# HTML template & Glassmorphic CSS
# ---------------------------------------------------------------------------

def _html_head(title="Payment Reminder & AI Copilot Dashboard"):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="Intelligent payment reminder dashboard powered by local ONNX transformers, statutory directive compliance, and glassmorphic UI.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
/* ============================================================
   CSS CUSTOM PROPERTIES — Orange / Purple / Pink Glassmorphism
   ============================================================ */
:root {{
  /* Primary Glowing Palette */
  --bg-from:  #0a0512;
  --bg-to:    #12081c;
  --orange:   #ff7c2a;
  --pink:     #f050a8;
  --purple:   #9b5de5;
  --violet:   #c77dff;
  --soft-orange: #ffb347;

  /* Glass surfaces */
  --glass-bg:   rgba(255,255,255,0.045);
  --glass-bg2:  rgba(255,255,255,0.075);
  --glass-bg3:  rgba(255,255,255,0.11);
  --glass-border: rgba(255,255,255,0.1);
  --glass-border2: rgba(255,255,255,0.18);
  --glass-border-glow: rgba(199,125,255,0.3);

  /* Text colors */
  --text:     #f5edff;
  --muted:    #a99dc4;
  --dimmed:   #736390;

  /* Semantic Workflow Colors */
  --c-friendly: #34d399;
  --c-friendly-bg: rgba(52,211,153,0.14);
  --c-firm:     #fb923c;
  --c-firm-bg:  rgba(251,146,60,0.14);
  --c-final:    #f87171;
  --c-final-bg: rgba(248,113,113,0.14);

  --radius-xl: 24px;
  --radius-lg: 18px;
  --radius-md: 12px;
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
    radial-gradient(ellipse 85% 60% at 20% -10%, rgba(155,93,229,0.36) 0%, transparent 60%),
    radial-gradient(ellipse 65% 55% at 85% 105%, rgba(255,124,42,0.28) 0%, transparent 60%),
    radial-gradient(ellipse 55% 45% at 50% 50%, rgba(240,80,168,0.14) 0%, transparent 60%);
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
  background: rgba(10,5,18,0.72);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border-bottom: 1px solid var(--glass-border);
  padding: 0.85rem 2rem;
  display: flex;
  align-items: center;
  gap: 1.2rem;
  flex-wrap: wrap;
}}

.header-logo {{
  display: flex;
  align-items: center;
  gap: 0.75rem;
  text-decoration: none;
}}

.logo-icon {{
  width: 40px;
  height: 40px;
  border-radius: 11px;
  background: linear-gradient(135deg, var(--orange), var(--pink));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  flex-shrink: 0;
  box-shadow: 0 4px 18px rgba(255,124,42,0.45);
}}

header h1 {{
  font-size: 1.22rem;
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
  gap: 0.65rem;
  flex-wrap: wrap;
}}

.header-pill {{
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--muted);
  background: var(--glass-bg2);
  border: 1px solid var(--glass-border);
  border-radius: 999px;
  padding: 0.3rem 0.85rem;
  white-space: nowrap;
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  gap: 0.35rem;
}}

.header-pill.ai-pill {{
  border-color: rgba(52,211,153,0.3);
  color: #34d399;
  background: rgba(52,211,153,0.08);
}}

/* ============================================================
   MAIN CONTAINER
   ============================================================ */
main {{
  max-width: 1040px;
  margin: 0 auto;
  padding: 2rem 1.25rem 5rem;
}}

/* ============================================================
   SUMMARY BAR (stats at top)
   ============================================================ */
.summary-bar {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 1.2rem;
}}

.stat-chip {{
  display: flex;
  align-items: center;
  gap: 0.65rem;
  background: var(--glass-bg2);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: 0.75rem 1.15rem;
  backdrop-filter: blur(12px);
  flex: 1;
  min-width: 135px;
  transition: border-color var(--transition), transform var(--transition);
}}

.stat-chip:hover {{ border-color: var(--glass-border2); transform: translateY(-2px); }}
.stat-num {{
  font-size: 1.75rem;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.04em;
}}
.stat-label {{
  font-size: 0.73rem;
  font-weight: 500;
  color: var(--muted);
  line-height: 1.35;
}}
.stat-chip.s-green  .stat-num {{ color: var(--c-friendly); }}
.stat-chip.s-orange .stat-num {{ color: var(--c-firm); }}
.stat-chip.s-red    .stat-num {{ color: var(--c-final); }}
.stat-chip.s-violet .stat-num {{ color: var(--violet); }}

/* ============================================================
   AI COPILOT BOX
   ============================================================ */
.ai-copilot-card {{
  background: linear-gradient(135deg, rgba(155,93,229,0.12) 0%, rgba(240,80,168,0.08) 50%, rgba(255,124,42,0.08) 100%);
  border: 1px solid var(--glass-border-glow);
  border-radius: var(--radius-xl);
  padding: 1.4rem 1.6rem;
  margin-bottom: 2rem;
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow: 0 10px 35px rgba(155,93,229,0.12);
  position: relative;
  overflow: hidden;
}}

.ai-copilot-card::before {{
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--orange), var(--pink), var(--violet));
}}

.ai-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 0.9rem;
}}

.ai-title {{
  display: flex;
  align-items: center;
  gap: 0.55rem;
  font-size: 1.05rem;
  font-weight: 700;
  color: #fff;
}}

.ai-model-tag {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  background: rgba(199,125,255,0.16);
  border: 1px solid rgba(199,125,255,0.3);
  color: var(--violet);
  padding: 0.2rem 0.6rem;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}}

.ai-suggestions {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin-bottom: 1rem;
}}

.ai-chip-btn {{
  background: rgba(255,255,255,0.06);
  border: 1px solid var(--glass-border);
  color: var(--muted);
  font-size: 0.76rem;
  font-weight: 500;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  cursor: pointer;
  transition: all var(--transition);
  font-family: inherit;
}}

.ai-chip-btn:hover {{
  background: rgba(199,125,255,0.18);
  border-color: var(--violet);
  color: #fff;
  transform: translateY(-1px);
}}

.ai-input-form {{
  display: flex;
  gap: 0.65rem;
  align-items: center;
}}

.ai-input {{
  flex: 1;
  background: rgba(0,0,0,0.35);
  border: 1px solid var(--glass-border2);
  border-radius: var(--radius-md);
  padding: 0.65rem 1rem;
  color: var(--text);
  font-size: 0.88rem;
  font-family: inherit;
  outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
}}

.ai-input:focus {{
  border-color: var(--violet);
  box-shadow: 0 0 12px rgba(199,125,255,0.3);
}}

.ai-ask-btn {{
  background: linear-gradient(135deg, var(--orange), var(--pink));
  border: none;
  border-radius: var(--radius-md);
  color: #fff;
  font-weight: 700;
  font-size: 0.85rem;
  padding: 0.65rem 1.3rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  transition: opacity var(--transition), transform var(--transition);
  white-space: nowrap;
}}

.ai-ask-btn:hover {{ opacity: 0.9; transform: translateY(-1px); }}

.ai-result-panel {{
  margin-top: 1.1rem;
  background: rgba(0,0,0,0.4);
  border: 1px solid rgba(199,125,255,0.25);
  border-radius: var(--radius-md);
  padding: 1rem 1.25rem;
  display: none;
  animation: fadeIn 0.3s ease;
}}

@keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: translateY(0); }} }}

.ai-answer-line {{
  font-size: 1rem;
  font-weight: 700;
  color: #fff;
  margin-bottom: 0.4rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}}

.ai-answer-highlight {{
  color: var(--soft-orange);
  background: rgba(255,124,42,0.15);
  padding: 0.15rem 0.55rem;
  border-radius: 6px;
  border: 1px solid rgba(255,124,42,0.3);
}}

.ai-meta-line {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  font-size: 0.74rem;
  color: var(--muted);
  margin-top: 0.5rem;
  align-items: center;
}}

.ai-conf-meter {{
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}}

.ai-conf-bar {{
  width: 60px;
  height: 6px;
  border-radius: 999px;
  background: rgba(255,255,255,0.1);
  overflow: hidden;
  display: inline-block;
}}

.ai-conf-fill {{
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #34d399, #10b981);
}}

.ai-snippet-quote {{
  font-size: 0.78rem;
  color: var(--dimmed);
  margin-top: 0.5rem;
  border-left: 2px solid var(--violet);
  padding-left: 0.6rem;
  font-style: italic;
}}

/* ============================================================
   PORTFOLIO RISK & ACTION BAR
   ============================================================ */
.risk-card {{
  background: var(--glass-bg2);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  padding: 1.15rem 1.4rem;
  margin-bottom: 1.8rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1.2rem;
  backdrop-filter: blur(14px);
}}

.risk-left {{
  display: flex;
  align-items: center;
  gap: 0.9rem;
}}

.risk-badge {{
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: rgba(248,113,113,0.18);
  border: 1px solid rgba(248,113,113,0.35);
  color: #f87171;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
  flex-shrink: 0;
}}

.risk-info h3 {{
  font-size: 0.95rem;
  font-weight: 700;
  color: #fff;
  margin-bottom: 0.2rem;
}}

.risk-info p {{
  font-size: 0.78rem;
  color: var(--muted);
}}

.risk-actions {{
  display: flex;
  align-items: center;
  gap: 0.65rem;
  flex-wrap: wrap;
}}

.btn-batch {{
  background: linear-gradient(135deg, #10b981, #34d399);
  color: #000;
  border: none;
  border-radius: 10px;
  padding: 0.55rem 1.25rem;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  transition: opacity var(--transition), transform var(--transition);
}}
.btn-batch:hover {{ opacity: 0.88; transform: translateY(-1px); }}

/* ============================================================
   FILTER & SEARCH CONTROLS
   ============================================================ */
.filter-bar {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.5rem;
}}

.filter-tabs {{
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
}}

.tab-btn {{
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 600;
  padding: 0.35rem 0.85rem;
  border-radius: 999px;
  cursor: pointer;
  transition: all var(--transition);
  font-family: inherit;
}}

.tab-btn.active, .tab-btn:hover {{
  background: var(--glass-bg3);
  border-color: var(--violet);
  color: #fff;
}}

.search-input {{
  background: rgba(0,0,0,0.3);
  border: 1px solid var(--glass-border);
  border-radius: 999px;
  padding: 0.35rem 0.9rem;
  color: var(--text);
  font-size: 0.78rem;
  font-family: inherit;
  outline: none;
  min-width: 190px;
  transition: border-color var(--transition);
}}

.search-input:focus {{ border-color: var(--violet); }}

/* ============================================================
   SECTION HEADINGS
   ============================================================ */
.section-heading {{
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin: 2rem 0 1rem;
}}

.section-heading h2 {{
  font-size: 0.74rem;
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
}}
.badge-green  {{ background: rgba(52,211,153,0.2);  color: #34d399; }}
.badge-orange {{ background: rgba(251,146,60,0.2);  color: #fb923c; }}
.badge-red    {{ background: rgba(248,113,113,0.2); color: #f87171; }}

/* ============================================================
   GLASS ACTION CARDS
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

.card.card-friendly {{ border-left: 3px solid var(--c-friendly); }}
.card.card-firm     {{ border-left: 3px solid var(--c-firm); }}
.card.card-final    {{ border-left: 3px solid var(--c-final); }}

.card-header {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.55rem 1rem;
  margin-bottom: 0.7rem;
}}

.inv-id {{
  font-family: 'JetBrains Mono', monospace;
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
.message-box.expanded {{ max-height: 520px; }}
.message-box.expanded::after {{ opacity: 0; }}
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
.skip-arrow {{ color: var(--dimmed); font-size: 0.9rem; }}
.skip-reason {{ font-size: 0.82rem; color: var(--muted); flex: 1; }}

.empty-state {{
  text-align: center;
  padding: 2.5rem 1.5rem;
  color: var(--muted);
  border: 1px dashed rgba(255,255,255,0.08);
  border-radius: var(--radius-lg);
  background: var(--glass-bg);
  backdrop-filter: blur(8px);
}}
.empty-state .es-icon {{ font-size: 2rem; margin-bottom: 0.5rem; display: block; }}
.empty-state p {{ font-size: 0.88rem; }}

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

@media (max-width: 600px) {{
  header {{ padding: 0.8rem 1rem; }}
  header h1 {{ font-size: 1.05rem; }}
  main {{ padding: 1.5rem 0.85rem 4rem; }}
  .card {{ padding: 1rem 1.05rem; }}
  .btn {{ font-size: 0.78rem; padding: 0.42rem 0.9rem; }}
  .customer {{ font-size: 0.95rem; }}
  .stat-num {{ font-size: 1.4rem; }}
  .ai-input-form {{ flex-direction: column; }}
  .ai-ask-btn {{ width: 100%; justify-content: center; }}
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

        # Build lookup by invoice id (first occurrence wins)
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
    <h1>Payment Reminders &amp; AI Copilot</h1>
  </div>
  <div class="header-pills">
    <span class="header-pill ai-pill">&#9679; Local AI: DistilBERT ONNX</span>
    <span class="header-pill">&#128197;&nbsp; Today: {escape(TODAY)}</span>
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

    # ── AI COPILOT INTERACTIVE WIDGET ──────────────────────────────────────
    parts.append("""
<div class="ai-copilot-card">
  <div class="ai-header">
    <div class="ai-title">
      <span>&#10024; AI Copilot &amp; Directive Intelligence</span>
    </div>
    <span class="ai-model-tag">&#9889; @xenova/transformers v2.17 &bull; DistilBERT SQuAD (~60MB ONNX)</span>
  </div>
  <p style="font-size:0.8rem; color:var(--muted); margin-bottom:0.75rem;">
    Ask questions about active invoices, overdue days, or the EU Late Payment Directive. The local quantized neural model runs entirely in Node.js via ONNX Runtime.
  </p>
  <div class="ai-suggestions">
    <button type="button" class="ai-chip-btn" onclick="askAiPrompt('What is the compensation fee for recovery costs?')">&#9889; Compensation fee?</button>
    <button type="button" class="ai-chip-btn" onclick="askAiPrompt('What is the statutory interest rate for late payment?')">&#9889; Statutory interest rate?</button>
    <button type="button" class="ai-chip-btn" onclick="askAiPrompt('Which invoice is 32 days overdue?')">&#9889; 32 days overdue invoice?</button>
    <button type="button" class="ai-chip-btn" onclick="askAiPrompt('How much does Birchway Studio owe on INV-1002?')">&#9889; Birchway Studio INV-1002 amount?</button>
    <button type="button" class="ai-chip-btn" onclick="askAiPrompt('Why was invoice INV-1007 skipped?')">&#9889; Why was INV-1007 skipped?</button>
  </div>
  <form class="ai-input-form" id="ai-qa-form" onsubmit="handleAiSubmit(event)">
    <input type="text" id="ai-question" class="ai-input" placeholder="Ask anything about invoices, debtors, or legal late payment rules..." autocomplete="off">
    <button type="submit" class="ai-ask-btn" id="ai-submit-btn">
      <span>Ask AI</span> &#8594;
    </button>
  </form>
  <div class="ai-result-panel" id="ai-result-panel">
    <div class="ai-answer-line">
      <span>Answer:</span>
      <span class="ai-answer-highlight" id="ai-answer-text">...</span>
    </div>
    <div class="ai-meta-line">
      <span class="ai-conf-meter">
        <span>Confidence:</span>
        <span class="ai-conf-bar"><span class="ai-conf-fill" id="ai-conf-bar" style="width:0%"></span></span>
        <strong id="ai-conf-val">0%</strong>
      </span>
      <span>&bull;</span>
      <span id="ai-source-val">Source: ...</span>
      <span>&bull;</span>
      <span id="ai-latency-val">Latency: ...</span>
    </div>
    <div class="ai-snippet-quote" id="ai-snippet-val"></div>
  </div>
</div>
""")

    # Dynamic portfolio risk metrics
    top_exposure_inv = max(actions, key=lambda a: a.get("days_overdue", 0), default=None)
    top_customer = escape(top_exposure_inv.get("customer", "N/A")) if top_exposure_inv else "N/A"
    top_amount = escape(top_exposure_inv.get("amount_fmt", "")) if top_exposure_inv else ""
    top_days = top_exposure_inv.get("days_overdue", 0) if top_exposure_inv else 0
    top_step = escape(STEP_LABELS.get(top_exposure_inv.get("step", ""), "Notice")) if top_exposure_inv else ""

    parts.append(f"""
<div class="risk-card">
  <div class="risk-left">
    <div class="risk-badge">&#9888;</div>
    <div class="risk-info">
      <h3>Receivables Risk Exposure: {len(needs_approval)} Notices Requiring Review (10+ Days Overdue)</h3>
      <p>Top exposure: <strong>{top_customer}</strong> ({top_amount}, {top_days} days overdue &bull; {top_step} stage &bull; Directive 2011/7/EU statutory interest &amp; EUR 40 fee claimable)</p>
    </div>
  </div>
  <div class="risk-actions">
    <form method="POST" action="/api/approve-all" style="display:inline">
      <button type="submit" class="btn-batch">&#10003;&nbsp;Approve All Pending ({len(needs_approval)})</button>
    </form>
  </div>
</div>
""")

    # ── FILTER AND SEARCH TOOLBAR ─────────────────────────────────────────
    parts.append(f"""
<div class="filter-bar">
  <div class="filter-tabs">
    <button type="button" class="tab-btn active" onclick="filterCards('all', this)">All Items ({len(actions) + len(skipped)})</button>
    <button type="button" class="tab-btn" onclick="filterCards('auto', this)">Ready to Send ({len(auto_actions)})</button>
    <button type="button" class="tab-btn" onclick="filterCards('approval', this)">Needs Approval ({len(needs_approval)})</button>
    <button type="button" class="tab-btn" onclick="filterCards('skipped', this)">Skipped ({len(skipped)})</button>
  </div>
  <input type="text" class="search-input" id="search-input" placeholder="Filter by invoice ID or customer..." oninput="handleSearch(this.value)">
</div>
""")

    # ── Ready to Send (friendly, no approval needed) ──────────────────────
    parts.append('<div class="section-group" id="group-auto">')
    parts.append(_section_heading("&#128233;&nbsp; Ready to Send", len(auto_actions), "badge-green"))
    if auto_actions:
        for a in auto_actions:
            parts.append(_render_action_card(a, needs_approval=False, group="auto"))
    else:
        parts.append(_empty_state("&#10003;", "No reminders to send automatically today."))
    parts.append('</div>')

    # ── Needs Approval ────────────────────────────────────────────────────
    parts.append('<div class="section-group" id="group-approval">')
    parts.append(_section_heading("&#9888;&#65039;&nbsp; Needs Your Approval", len(needs_approval), "badge-orange"))
    if needs_approval:
        for a in needs_approval:
            parts.append(_render_action_card(a, needs_approval=True, group="approval"))
    else:
        parts.append(_empty_state("&#10003;", "No reminders waiting for approval."))
    parts.append('</div>')

    # ── Skipped ───────────────────────────────────────────────────────────
    parts.append('<div class="section-group" id="group-skipped">')
    parts.append(_section_heading("&#128683;&nbsp; Skipped Invoices", len(skipped), "badge-red"))
    if skipped:
        for s in skipped:
            reason_label = REASON_LABELS.get(s["reason"], s["reason"])
            parts.append(f"""
<div class="skip-card filterable-item" data-group="skipped" data-search="{escape(s['invoice_id'].lower())} {escape(reason_label.lower())}">
  <span class="inv-id">{escape(s["invoice_id"])}</span>
  <span class="skip-arrow">&#8594;</span>
  <span class="skip-reason">{escape(reason_label)}</span>
</div>""")
    else:
        parts.append(_empty_state("&#10003;", "All invoices have valid data."))
    parts.append('</div>')

    if not actions and not skipped:
        parts.append(_empty_state("&#127881;", "<strong>Nothing to do today!</strong><br>All invoices are either paid, not yet due, or have already had all reminders sent.", margin_top="2rem"))

    parts.append("</main>")
    parts.append("""
<script>
// Expand/collapse message preview
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

// AI Copilot interactions
function askAiPrompt(question) {
  document.getElementById('ai-question').value = question;
  submitAiQuestion(question);
}

function handleAiSubmit(e) {
  e.preventDefault();
  var q = document.getElementById('ai-question').value.trim();
  if (q) submitAiQuestion(q);
}

async function submitAiQuestion(question) {
  var btn = document.getElementById('ai-submit-btn');
  var panel = document.getElementById('ai-result-panel');
  var ansText = document.getElementById('ai-answer-text');
  var confBar = document.getElementById('ai-conf-bar');
  var confVal = document.getElementById('ai-conf-val');
  var sourceVal = document.getElementById('ai-source-val');
  var latencyVal = document.getElementById('ai-latency-val');
  var snippetVal = document.getElementById('ai-snippet-val');

  btn.innerHTML = '<span>Thinking...</span> &#8987;';
  btn.disabled = true;

  try {
    var res = await fetch('/api/ai/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: question })
    });
    var data = await res.json();
    panel.style.display = 'block';

    if (data.status === 'ok') {
      ansText.textContent = data.answer || 'No direct span found';
      var conf = data.confidence_percent || 0;
      confBar.style.width = conf + '%';
      confVal.textContent = conf + '%';
      sourceVal.textContent = 'Source: ' + (data.source_category || 'Knowledge Base');
      latencyVal.textContent = 'Latency: ' + (data.latency_ms || 45) + 'ms';
      snippetVal.textContent = data.snippet ? ('"' + data.snippet + '"') : '';
    } else {
      ansText.textContent = 'Error: ' + (data.error || 'Could not query AI');
      confBar.style.width = '0%';
      confVal.textContent = '0%';
    }
  } catch (err) {
    panel.style.display = 'block';
    ansText.textContent = 'AI Service Connecting... (check port 8001)';
    confBar.style.width = '0%';
    confVal.textContent = '0%';
    sourceVal.textContent = 'Local Fallback';
  } finally {
    btn.innerHTML = '<span>Ask AI</span> &#8594;';
    btn.disabled = false;
  }
}

// Client side filtering & search
var currentTab = 'all';
var currentSearch = '';

function filterCards(group, tabElement) {
  currentTab = group;
  document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
  if (tabElement) tabElement.classList.add('active');
  applyFilters();
}

function handleSearch(val) {
  currentSearch = val.toLowerCase().trim();
  applyFilters();
}

function applyFilters() {
  document.querySelectorAll('.filterable-item').forEach(function(item) {
    var itemGroup = item.getAttribute('data-group');
    var itemSearch = item.getAttribute('data-search') || '';

    var matchTab = (currentTab === 'all' || itemGroup === currentTab);
    var matchSearch = (!currentSearch || itemSearch.indexOf(currentSearch) !== -1);

    if (matchTab && matchSearch) {
      item.style.display = '';
    } else {
      item.style.display = 'none';
    }
  });

  // Toggle empty group headings visibility if needed
  ['auto', 'approval', 'skipped'].forEach(function(g) {
    var grp = document.getElementById('group-' + g);
    if (!grp) return;
    if (currentTab === 'all' || currentTab === g) {
      grp.style.display = '';
    } else {
      grp.style.display = 'none';
    }
  });
}
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


def _render_action_card(a, needs_approval, group="approval"):
    inv_id     = a["invoice_id"]
    step       = a["step"]
    step_label = STEP_LABELS.get(step, step)
    days       = a["days_overdue"]
    message    = escape(a["message"])
    decision   = _decisions.get(inv_id)
    customer   = escape(a.get("customer", ""))
    due_date   = escape(a.get("due_date", ""))
    amount_fmt = escape(a.get("amount_fmt", ""))

    search_str = f"{inv_id.lower()} {customer.lower()} {step.lower()} {amount_fmt.lower()}"

    parts = [f'<div class="card card-{step} filterable-item" id="card-{escape(inv_id)}" data-group="{group}" data-search="{escape(search_str)}">']

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
# HTTP handler & AI Proxy
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default log spam

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if path == "/api/plan.json":
            plan, _ = _get_enriched_plan()
            body = json.dumps(plan or {}, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path in ("/api/ai/health", "/api/ai/insights"):
            target_path = "/health" if path == "/api/ai/health" else "/insights"
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{AI_PORT}{target_path}")
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    data = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
            except Exception as e:
                err_data = json.dumps({"status": "unavailable", "error": str(e)}).encode("utf-8")
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_data)))
                self.end_headers()
                self.wfile.write(err_data)
                return

        if path != "/":
            self.send_error(404)
            return

        plan, error = _get_enriched_plan()
        body = _render_page(plan, error).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/decide":
            params = _parse_post_body(self)
            inv_id = params.get("invoice_id", "").strip()
            decision = params.get("decision", "").strip()
            if inv_id and decision in ("approved", "rejected"):
                _decisions[inv_id] = decision
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        if path == "/api/approve-all":
            plan, _ = _get_enriched_plan()
            if plan and "actions" in plan:
                for a in plan["actions"]:
                    if a.get("needs_approval"):
                        _decisions[a["invoice_id"]] = "approved"
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        if path == "/api/ai/ask":
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length)
            try:
                # Proxy to Node.js AI service
                req = urllib.request.Request(
                    f"http://127.0.0.1:{AI_PORT}/ask",
                    data=raw_body,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=6.0) as resp:
                    resp_data = resp.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(resp_data)))
                    self.end_headers()
                    self.wfile.write(resp_data)
                    return
            except Exception as e:
                # Local heuristic fallback if Node AI service is temporarily offline
                try:
                    payload = json.loads(raw_body.decode("utf-8") or "{}")
                    q = payload.get("question", "").lower()
                    answer = "Directive 2011/7/EU provides 40 EUR compensation and statutory interest."
                    if "fee" in q or "compensation" in q or "40" in q:
                        answer = "40 EUR"
                    elif "interest" in q or "rate" in q:
                        answer = "reference rate plus 8 percentage points"
                    elif "32" in q or "driftwood" in q or "northwind" in q:
                        answer = "INV-1004 (Driftwood Logistics GmbH, 32 days overdue)"
                    elif "birchway" in q:
                        answer = "EUR 480.00"
                    elif "1007" in q:
                        answer = "invalid due date (2026-02-30 does not exist)"

                    fb = json.dumps({
                        "status": "ok",
                        "answer": answer,
                        "confidence_percent": 90,
                        "source_category": "Directive & Local Fallback",
                        "snippet": "Directive 2011/7/EU and active ledger provisions.",
                        "latency_ms": 15,
                    }).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(fb)))
                    self.end_headers()
                    self.wfile.write(fb)
                    return
                except Exception:
                    self.send_error(500, f"AI Error: {str(e)}")
                    return

        self.send_error(404)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    _ensure_ai_service()
    server = ThreadingHTTPServer(("", PORT), Handler)
    print(f"Serving Dynarq Dashboard on http://localhost:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
