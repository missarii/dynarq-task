# Dynarq — Payment Reminder Assistant & Local AI Copilot

An intelligent daily accounts receivable and payment-reminder platform designed for small businesses:
- **Deterministic Rules Engine:** Automatically generates compliant daily reminder plans adhering to the EU Late Payment Directive (Directive 2011/7/EU).
- **Glassmorphism Owner Dashboard:** A modern UI with an Orange, Purple, and Pink gradient theme, instant search, workflow filtering, and batch approval controls.
- **Embedded Local Neural AI Copilot:** Powered by `@xenova/transformers` (v2.17) running `Xenova/distilbert-base-uncased-distilled-squad` (~60MB quantized ONNX) in Node.js via ONNX Runtime Web/Node for sub-150ms extractive Question Answering with zero cloud dependencies.
- **Portfolio Risk Intelligence:** Instant at-risk exposure tracking, priority debtor highlighting, and statutory compensation entitlement calculations.
- **Strict Data Hygiene:** Built-in validation catching corrupt, missing, future, and duplicate records.

---

## Quick Navigation

- [How to Run Locally](#how-to-run-locally)
  - [Prerequisites](#prerequisites)
  - [Option A: One-Command Start (Recommended)](#option-a-one-command-start-recommended)
  - [Option B: Step-by-Step Setup](#option-b-step-by-step-setup)
  - [Running Unit Tests](#running-unit-tests)
  - [Running Rules Engine CLI](#running-rules-engine-cli)
- [System Architecture](#system-architecture)
- [Local AI Copilot Details](#local-ai-copilot-details)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [Design Decisions & Compliance](#design-decisions--compliance)
- [Documentation Index](#documentation-index)

---

## How to Run Locally

### Prerequisites

- **Python 3.9+** (Standard library only; no external Python packages needed!)
- **Node.js 18+** & **npm** (for the local ONNX transformers service)

---

### Option A: One-Command Start (Recommended)

1. Clone or navigate to the repository directory:
   ```bash
   cd dynarq-task
   ```

2. Install Node.js AI dependencies once:
   ```bash
   cd ai
   npm install
   cd ..
   ```

3. Launch the application:
   ```bash
   cd python
   python app.py
   ```
   > **Note:** `app.py` automatically detects if the Node.js AI microservice is running. If not, it spawns `node server.js` in the background automatically!

4. Open your browser and go to:
   👉 **`http://localhost:8000/`**

---

### Option B: Step-by-Step Setup (Virtual Environment & Explicit Services)

If you prefer using a Python virtual environment and running each service in its own terminal:

#### 1. Setup Python Virtual Environment
```bash
# From dynarq-task root:
python3 -m venv venv
source venv/bin/activate
```

#### 2. Setup Node.js AI Microservice
```bash
cd ai
npm install
npm start
```
*The AI service will start listening on `http://127.0.0.1:8001` and cache the quantized DistilBERT ONNX model in memory.*

#### 3. Start Python Web Dashboard
In a second terminal window (with virtualenv activated):
```bash
source venv/bin/activate
cd python
python app.py
```
*The web dashboard is now live on `http://localhost:8000/`.*

---

### Running Unit Tests

Run the full automated test suite from inside `python/`:

```bash
cd python
python -m unittest -v
```

All **46 unit tests** will run and pass in under 0.01 seconds. The test suite verifies:
- Strict ISO date parsing and calendar validation (e.g., February 30th rejection, leap year checks)
- Bad-data detection priority (`duplicate_id` &rarr; `invalid_amount` &rarr; `missing_due_date` &rarr; `invalid_due_date` &rarr; `invalid_paid_date`)
- 3-stage reminder cadence (Friendly at Day 3, Firm at Day 10, Final at Day 30)
- Human-in-the-loop approval classification (Friendly = auto-send; Firm & Final = requires owner approval)
- 5-day mandatory cadence cooldown to prevent customer spam
- Message templating accuracy with statutory compliance (no invented interest or unauthorized fees)
- Lexicographical sorting order
- Full end-to-end integration against the sample invoice dataset

---

### Running Rules Engine CLI

Generate the daily reminder plan via command-line interface:

```bash
cd python
python plan.py --invoices ../data/invoices.json \
               --sent ../data/sent.json \
               --today 2026-10-12 \
               --out ../actions.json
```

- Generates `actions.json` with two top-level lists: `actions` (ready to send or awaiting approval) and `skipped` (data errors).
- Exits with returncode `0` on success; exits non-zero with clear diagnostics if inputs are invalid.

---

## Verifying Endpoints with cURL

You can verify all endpoints directly from your command line:

```bash
# 1. Main Dashboard HTML
curl -s http://localhost:8000/ | head -20

# 2. Local AI Health Check
curl -s http://localhost:8000/api/ai/health

# 3. Query Local AI (Extractive Question Answering)
curl -s -X POST http://localhost:8000/api/ai/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the compensation fee for recovery costs?"}'

# 4. Query Portfolio Risk Intelligence
curl -s http://localhost:8000/api/ai/insights

# 5. Export Daily Plan as JSON
curl -s http://localhost:8000/api/plan.json
```

---

## System Architecture

```text
dynarq-task/
├── ai/
│   ├── package.json          # Defines @xenova/transformers v2.17 dependency
│   └── server.js             # Local Node.js ONNX QA microservice (port 8001)
├── python/
│   ├── app.py                # Web server, glassmorphism UI, AI proxy (port 8000)
│   ├── plan.py               # Deterministic planning engine & CLI
│   ├── requirements.txt      # Standard library only (no external packages needed)
│   └── tests/
│       └── test_plan.py      # Comprehensive 46-test unit test suite
├── data/
│   ├── invoices.json         # Invoice ledger records
│   └── sent.json             # Communication history log
├── sources/
│   ├── late-payment-directive.md  # Official Directive 2011/7/EU source
│   └── owner-note.md              # Owner's initial requirements and misconceptions
├── AI_WORKFLOW.md            # Detailed AI architecture, ONNX pipeline & QA docs
├── FEATURES.md               # Complete catalog of all features & capabilities
├── RESEARCH.md               # Legal directive compliance research & citations
└── README.md                 # Primary system guide and run instructions
```

---

## Local AI Copilot Details

- **Library:** `@xenova/transformers` (version 2.17)
- **Model:** `Xenova/distilbert-base-uncased-distilled-squad` (~60MB quantized int8 ONNX)
- **Runtime:** ONNX Runtime Web/Node running inside Node.js
- **Capabilities:**
  - **Zero Data Leakage:** Customer accounts, invoice IDs, and debts are never transmitted over the internet.
  - **Deterministic Span Extraction:** Directly extracts accurate answers from context without hallucination.
  - **Sub-150ms Inference:** Runs on standard CPU without GPU requirements.
  - **Interactive Suggestions:** 1-click prompt chips on dashboard (Statutory interest rate, EUR 40 recovery fee, overdue days, skipped reasons).

See [`AI_WORKFLOW.md`](AI_WORKFLOW.md) for full architecture diagrams and token scoring formulas.

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port for the Python web dashboard |
| `AI_PORT` | `8001` | Port for the Node.js AI microservice |
| `DATA_DIR` | `../data` | Directory containing `invoices.json` and `sent.json` |
| `TODAY` | Current Date (`YYYY-MM-DD`) | Reference date for calculating days overdue |

Example running on custom ports:
```bash
PORT=9000 AI_PORT=9001 TODAY=2026-10-12 python app.py
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Responsive Glassmorphism owner dashboard |
| `POST`| `/decide` | Approve or reject a notice (`invoice_id`, `decision`) |
| `POST`| `/api/approve-all` | Batch-approve all pending review notices in one click |
| `POST`| `/api/ai/ask` | Local Extractive Question Answering (DistilBERT ONNX) |
| `GET` | `/api/ai/insights` | Portfolio risk exposure summary and statutory entitlements |
| `GET` | `/api/ai/health` | AI microservice uptime, model status, and runtime info |
| `GET` | `/api/plan.json` | Daily reminder action plan in structured JSON |

---

## Design Decisions & Compliance

1. **Directive 2011/7/EU Alignment:**
   - Under Article 6, creditors are entitled to a **minimum fixed sum of EUR 40** for recovery costs without the necessity of a reminder.
   - Under Article 2 & 12, statutory interest runs at the **ECB reference rate plus 8 percentage points**.
   - Standard commercial terms are **30 calendar days**, with a strict maximum of **60 calendar days** unless expressly agreed.
2. **Zero Third-Party Python Dependencies:**
   - The Python application relies exclusively on the standard library (`http.server`, `urllib`, `json`, `datetime`).
3. **Glassmorphism Aesthetic:**
   - Orange, Purple, and Pink glowing accents with translucent glass surfaces (`backdrop-filter: blur(24px)`).
   - Distinct left accent color bars for each workflow step (Teal = Friendly, Orange = Firm, Coral Red = Final).
   - Accessible expand/collapse message accordions and responsive layout from mobile (390px) to desktop.

---

## Documentation Index

- **[`AI_WORKFLOW.md`](AI_WORKFLOW.md)** &mdash; AI system architecture, neural pipeline mechanics, dynamic knowledge ranking, and benchmarks.
- **[`FEATURES.md`](FEATURES.md)** &mdash; Full feature matrix and capabilities breakdown.
- **[`RESEARCH.md`](RESEARCH.md)** &mdash; Research questions answered with official citations from Directive 2011/7/EU.
- **[`sources/late-payment-directive.md`](sources/late-payment-directive.md)** &mdash; Primary EU Directive source text.
- **[`sources/owner-note.md`](sources/owner-note.md)** &mdash; Original business notes and requirements.
