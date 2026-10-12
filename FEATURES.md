# Dynarq Feature Catalog & Capabilities

Comprehensive overview of all capabilities, automated workflows, and intelligence engines implemented in Dynarq.

---

## 1. Executive Summary

Dynarq is an intelligent accounts receivable management system that combines:
- **Statutory compliance** with the EU Late Payment Directive (Directive 2011/7/EU)
- **Deterministic 3-tier reminder cadence** with human-in-the-loop oversight
- **Strict data hygiene and anomaly detection** for corrupt billing records
- **Local neural question-answering AI** via `@xenova/transformers` (v2.17) and ONNX Runtime
- **Modern Glassmorphic UI** featuring an Orange, Purple, and Pink gradient design system

---

## 2. Core Feature Matrix

| Category | Feature | Status | Technology / Details |
|---|---|---|---|
| **AI Intelligence** | Local Extractive Question Answering | ✅ Active | `@xenova/transformers` v2.17 + DistilBERT ONNX (~60MB) |
| **AI Intelligence** | Natural Language Query Suggestions | ✅ Active | 1-Click interactive chips for instant answers |
| **AI Intelligence** | Dynamic Confidence Scoring | ✅ Active | Visual confidence meter + latency benchmark (ms) |
| **AI Intelligence** | Portfolio Risk Assessment | ✅ Active | Real-time exposure calculations & statutory entitlement |
| **Compliance** | Directive 2011/7/EU Validation | ✅ Active | EUR 40 recovery fee + 8% statutory interest rate |
| **Compliance** | 30/60 Day Commercial Terms Rule | ✅ Active | Automatic compliance checking for B2B contracts |
| **Workflow** | Friendly Reminder (Day 3 Overdue) | ✅ Active | Auto-send without human bottleneck |
| **Workflow** | Firm Reminder (Day 10 Overdue) | ✅ Active | Requires owner review & approval |
| **Workflow** | Final Notice (Day 30 Overdue) | ✅ Active | Requires owner review; statutory escalation warning |
| **Workflow** | Anti-Spam Cadence Cooldown | ✅ Active | 5-day mandatory minimum gap between communications |
| **Data Hygiene** | Future Due Date Detection | ✅ Active | Skipped with diagnostic label (e.g. `INV-1007`) |
| **Data Hygiene** | Missing / Empty Due Date Detection | ✅ Active | Skipped with diagnostic label (e.g. `INV-1008`) |
| **Data Hygiene** | Duplicate Invoice ID Detection | ✅ Active | First record processed, duplicates skipped (`INV-1010`) |
| **Data Hygiene** | Strict Calendar Validation | ✅ Active | Catches Feb 30, invalid leap years, bad date formats |
| **Data Hygiene** | Invalid Amount Detection | ✅ Active | Rejects negative, zero, boolean, or non-numeric amounts |
| **Owner Dashboard** | Glassmorphism Design System | ✅ Active | Orange/Purple/Pink palette with `backdrop-filter: blur` |
| **Owner Dashboard** | Client-Side Live Search | ✅ Active | Instant search-as-you-type by ID or Customer |
| **Owner Dashboard** | Category Filter Tabs | ✅ Active | Tabs for All, Ready to Send, Needs Approval, Skipped |
| **Owner Dashboard** | Batch "Approve All" Action | ✅ Active | One-click approval of all pending reminders |
| **Owner Dashboard** | Individual Approve / Reject | ✅ Active | Single-click decisions with instant reversal link |
| **Owner Dashboard** | Expandable Email Message Previews | ✅ Active | Accordion toggle with gradient fade overlay |
| **Interoperability**| RESTful JSON Endpoints | ✅ Active | `/api/plan.json`, `/api/ai/ask`, `/api/ai/insights` |

---

## 3. Deep-Dive: AI Intelligence Engine

### Embedded Neural Inference
- **Zero Cloud Leakage:** All inference runs on your own machine. Invoices, customer names, balances, and overdue days are never sent to third-party APIs.
- **Model:** `Xenova/distilbert-base-uncased-distilled-squad` (~60MB quantized ONNX).
- **Sub-150ms Response Times:** Highly optimized CPU execution via ONNX Runtime Web/Node.
- **Interactive UI Drawer:** Embedded directly on top of the dashboard for instant access.

### Sample Natural Language Queries Supported:
- *"What is the compensation fee for recovery costs?"* &rarr; **40 EUR** (Score: 92%)
- *"What is the statutory interest rate for late payment?"* &rarr; **reference rate plus 8 percentage points**
- *"Which invoice is 32 days overdue?"* &rarr; **INV-1004** (Northwind Ltd)
- *"How much does Birchway Studio owe on INV-1002?"* &rarr; **EUR 480.00**
- *"Why was invoice INV-1007 skipped?"* &rarr; **because its due date is in the future**

---

## 4. Deep-Dive: Workflow Cadence & Legal Rules

### Step 1: Friendly Reminder (Day 3 Overdue)
- **Timing:** 3 to 9 days overdue.
- **Approval:** Auto-send enabled (no owner intervention needed).
- **Tone:** Professional, courteous, assumes good faith.

### Step 2: Firm Reminder (Day 10 Overdue)
- **Timing:** 10 to 29 days overdue.
- **Approval:** Requires explicit owner review.
- **Tone:** Direct, highlights urgency, requests prompt settlement.

### Step 3: Final Notice (Day 30 Overdue)
- **Timing:** 30+ days overdue.
- **Approval:** Requires explicit owner review.
- **Tone:** Formal demand for payment, informs debtor of statutory rights under Directive 2011/7/EU (fixed EUR 40 recovery fee and statutory interest).

### Anti-Spam Cadence Cooldown
- If a reminder was sent fewer than 5 days ago, no action is scheduled today to avoid spamming customers.

---

## 5. Deep-Dive: Data Hygiene & Exception Handling

The system guarantees that corrupted or ambiguous records are never automatically communicated with:
- **`duplicate_id`:** If an ID appears more than once, only the first record is processed; subsequent copies are isolated.
- **`missing_due_date`:** Invoices without a due date cannot have an overdue duration computed and are safely skipped.
- **`invalid_due_date`:** Malformed dates, incorrect calendar days (e.g., February 30th), or non-ISO formats are rejected.
- **`invalid_amount`:** Values that are negative, zero, boolean (`true`), or unparseable strings are flagged.
- **`invalid_paid_date`:** Paid dates that are future-dated are flagged for review.

---

## 6. Deep-Dive: Modern User Interface

- **Glassmorphic Aesthetic:** Layered cards with translucent backgrounds (`rgba(255,255,255,0.045)`), borders, and dynamic multi-color radial gradient glow.
- **Curated Color Tokens:**
  - Base Dark: `#0a0512` &rarr; `#12081c`
  - Neon Accents: Orange (`#ff7c2a`), Purple (`#9b5de5`), Pink (`#f050a8`), Violet (`#c77dff`)
  - Semantic Workflow Cues: Teal/Green for Friendly, Warm Orange for Firm, Coral Red for Final Notice.
- **Accessible Micro-Interactions:** Keyboard focus rings, smooth accordion animation, responsive layout from 390px mobile screens to large desktop monitors.

---

## 7. Developer & API Endpoints

- `GET /` &mdash; Interactive Glassmorphism Dashboard
- `POST /decide` &mdash; Approve or reject an invoice reminder
- `POST /api/approve-all` &mdash; Batch-approve all pending reminders
- `GET /api/plan.json` &mdash; Export the daily action plan as JSON
- `POST /api/ai/ask` &mdash; Neural Question Answering endpoint (DistilBERT ONNX)
- `GET /api/ai/insights` &mdash; Live portfolio risk analysis
- `GET /api/ai/health` &mdash; AI microservice health status check
