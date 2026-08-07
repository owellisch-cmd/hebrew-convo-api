# Health Insurance Advisor

Helps employees pick between HMO/EPO/PPO health insurance options for
themselves and their family based on their financial situation and expected
medical usage, instead of guessing. Employees enter their family and medical
history (or upload past expense data), and the app runs a transparent
cost simulation across the available plans, recommends one, and explains why
in plain English.

## What it does

- **Family & medical history** — add family members, their ongoing
  conditions, medications, and expected care usage for the year (visits,
  prescriptions, planned procedures).
- **Past expense upload** — upload a CSV or PDF export of past medical
  expenses; it's parsed and categorized automatically (best-effort keyword
  matching — review what it extracted).
- **Cost simulation** — a rule-based engine (`backend/app/services/recommendation.py`)
  runs each family's expected usage through every plan's actual premium,
  deductible, coinsurance, copays, and out-of-pocket max, and reports an
  expected cost, a best case, and a worst case (a large unplanned medical
  event) per plan — so the tradeoff between a cheap plan and a protective one
  is visible, not hidden.
- **Plain-English recommendation** — Claude (`claude-opus-5`) turns the
  numbers into a short explanation of why the recommended plan fits this
  family. Falls back to a templated explanation if no API key is configured.

## Scope and limitations — read before relying on this

- **This is a planning estimate, not a quote.** Unit costs (cost per doctor
  visit, ER visit, prescription, etc.) are rough national averages, not your
  employer's actual insurer contract rates. Always confirm real numbers with
  your benefits team before enrolling.
- **The four sample plans are placeholders.** Replace `backend/app/data/plans.json`
  with your employer's actual plan options (premiums, deductibles,
  copays, coinsurance, OOP max) before using this for a real enrollment
  decision.
- **No real medical record integration.** This app supports self-reported
  conditions/medications and CSV/PDF expense uploads that live in its own
  database — it does **not** connect to an insurer, provider, or EHR system
  (Epic, Cerner, FHIR, etc.). That kind of integration requires a signed
  Business Associate Agreement, encryption/audit infrastructure, and legal
  review that's out of scope for this build. The data model here (family
  member → conditions/medications/expenses) is structured so a real
  integration could plug in later.
- **Not HIPAA-certified infrastructure.** This is a working prototype:
  passwords are hashed, JWTs are used for auth, and CORS is scoped — but
  there's no encryption-at-rest, audit logging, breach-notification process,
  or the other controls a production system handling real employee health
  data would need. Treat data entered here as sensitive and don't deploy it
  publicly without a proper security review.
- **CSV/PDF parsing is a heuristic**, not a certified claims parser. It
  looks for an "amount" column (or the first dollar-looking value on each
  line of a PDF) and guesses a category from keywords. Always sanity-check
  what got extracted on the Medical Expenses page.

## Architecture

```
backend/   FastAPI + SQLAlchemy (SQLite by default) + JWT auth
  app/
    models.py           SQLAlchemy tables
    schemas.py           Pydantic request/response models
    routers/              auth, family, expenses, plans, recommend
    services/
      parsing.py          CSV/PDF expense parser
      recommendation.py    cost simulation engine
      llm.py                Claude explanation (claude-opus-5)
    data/plans.json       sample plan definitions — replace with real ones

frontend/  React + TypeScript + Vite
  src/
    pages/    Login, Register, Family, Expenses, Results
    api/      axios client with JWT attached
    context/  auth state
```

## Running it locally

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Optionally set ANTHROPIC_API_KEY in .env for LLM-generated explanations.
# Without it, a templated explanation is used instead — the app still works.
uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000` (interactive API docs at `/docs`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` and expects the backend at
`http://localhost:8000` (see `frontend/.env`).

### Try it

1. Register an account.
2. On **Family**, add each family member, their conditions/medications, and
   expected care usage for the year.
3. Optionally upload a past expenses CSV/PDF on **Medical Expenses**, or add
   totals manually.
4. Open **Recommendation** to see the cost comparison and explanation.

## Customizing plan options

Edit `backend/app/data/plans.json`. Each plan needs: `monthly_premium_family`,
`deductible_family`, `oop_max_family`, `coinsurance`, whether it
`uses_copays` (and the copay amounts if so), `requires_referral`, and
`out_of_network_coverage`. No database migration needed — it's read fresh on
each request.

## Next steps (not built here)

- Real EHR/insurer integration (FHIR, insurer claims APIs) — requires BAAs
  and compliance work beyond this prototype.
- Per-employee/per-tier premium data pulled from your actual carrier
  contract instead of the sample `plans.json`.
- Admin UI for HR to manage plan options without editing JSON directly.
- Audit logging and encryption-at-rest for production deployment.
