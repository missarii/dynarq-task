# Payment Reminder Assistant & AI Copilot

A daily payment-reminder and receivables recovery assistant for small businesses:
- **A deterministic rules engine** that computes reminder plans aligned with the EU Late Payment Directive (Directive 2011/7/EU).
- **A modern Glassmorphism Owner Dashboard** in vibrant orange, purple, and pink tones, with real-time search, category filtering, and batch approvals.
- **An embedded Local AI Copilot** running `@xenova/transformers` (v2.17) and `Xenova/distilbert-base-uncased-distilled-squad` (~60MB quantized ONNX) for sub-150ms extractive Question Answering with 0 cloud calls.
- **Exhaustive research notes & compliance audit** in `RESEARCH.md`.
- **Complete AI architectural blueprint** in `AI_WORKFLOW.md`.
- **Full catalog of capabilities** in `FEATURES.md`.

---

## How to run

### 1. Run all unit tests (from inside `python/`)

```bash
cd python
python -m unittest -v
```

46 unit tests cover date validation, bad-data detection, step selection, cooldown and already-sent logic, sorting, message templating, and full integration tests against sample data.

---

### 2. Run the rules engine CLI

```bash
cd python
python plan.py --invoices ../data/invoices.json \
               --sent ../data/sent.json \
               --today 2026-10-12 \
               --out ../actions.json
```

Outputs the daily action plan into `actions.json`. Exits 0 on success; exits non-zero with diagnostic messaging on invalid arguments.

---

### 3. Run the Owner Web Dashboard & AI Copilot

The web dashboard and local AI engine can be launched in seconds:

#### Option A: Quick Start (Python auto-spawns the AI service)
```bash
cd python
python app.py
```
Open **`http://localhost:8000/`** in your browser. `app.py` automatically checks for and launches the Node.js AI service if it is not already running!

#### Option B: Run Services Explicitly
```bash
# Terminal 1: Start the Node.js AI Service (port 8001)
cd ai
npm start

# Terminal 2: Start the Python Dashboard (port 8000)
cd python
python app.py
```

Environment variables:
- `PORT`: Python dashboard port (default `8000`)
- `AI_PORT`: Node.js AI microservice port (default `8001`)
- `DATA_DIR`: Folder containing `invoices.json` and `sent.json` (default `../data`)
- `TODAY`: ISO reference date (default: today's real date)

---

## AI Architecture & Key Features

- **Embedded Neural Model:** `Xenova/distilbert-base-uncased-distilled-squad` (~60MB quantized) executing via ONNX Runtime Web/Node directly in Node.js.
- **Zero Cloud Leakage:** 100% of customer names, invoices, amounts, and questions stay entirely on the local machine.
- **Interactive UI Drawer:** Clickable chips for instant queries (statutory interest, compensation fee, debtor amounts, skipped reason).
- **Portfolio Risk Intelligence:** Instant at-risk exposure calculation and top-exposure debtor highlight (Northwind Ltd).
- **Batch Actions:** "Approve All Pending" button for quick clearance of daily notices.
- **Live Search & Category Filtering:** Instant search by Invoice ID or Customer Name with tab filtering.

For full architectural details, see [AI_WORKFLOW.md](AI_WORKFLOW.md).
For a full list of features, see [FEATURES.md](FEATURES.md).

---

## Design & Engineering Decisions

1. **Deterministic Rules + Extractive Neural QA:**
   - Calculations, validation, and reminder escalations are 100% deterministic (no hallucination risk).
   - The neural model is purely extractive (SQuAD format), locating exact figures (e.g. `40 EUR`, `8 percentage points`, `32 days`).
2. **Standard Library Python + High-Performance Node ONNX:**
   - Python backend relies strictly on the standard library (`http.server`, `urllib`).
   - Node.js AI service hosts the `@xenova/transformers` ONNX runtime for sub-150ms inference.
3. **Glassmorphism Aesthetic:**
   - Multi-layer translucent glass surfaces with backdrop blur (`backdrop-filter: blur(24px)`).
   - Curated Orange, Purple, and Pink gradient palette with semantic color bars (Teal = Friendly, Orange = Firm, Red = Final).
4. **Approval Decisions in Memory:**
   - Fast state tracking during server runtime; allows changing or reversing decisions at any time.
5. **Strict Data Hygiene Priority:**
   - `duplicate_id` &rarr; `invalid_amount` &rarr; `missing_due_date` &rarr; `invalid_due_date` &rarr; `invalid_paid_date`.
