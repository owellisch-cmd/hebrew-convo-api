# Deploying PlanWise

## Read this first

**Vercel can host the frontend, but not this backend.** Vercel runs serverless
functions with an ephemeral filesystem — the SQLite database file would be wiped
between requests, so logins and saved families would vanish. You need two
services:

| Piece | Where | Why |
|---|---|---|
| React frontend | **Vercel** | Static build, exactly what Vercel is for |
| FastAPI backend + Postgres | **Render** (or Railway / Fly.io) | Needs a long-running process and a real database |

Both have free tiers, and they expire differently — this matters:

| | Vercel Hobby (frontend) | Render free (backend) |
|---|---|---|
| Idle behavior | Stays up forever. Static files on a CDN; nothing to spin down. | **Spins down after ~15 min idle.** Next request takes ~1 min to wake. |
| Expiry | Deployments don't expire from inactivity. | Web service is fine, but **free Postgres expires 30 days after creation**, then a 14-day grace period, then the data is deleted. |
| Monthly cap | Bandwidth/request quotas | 750 instance-hours per workspace per month |

So if the site "times out," it is almost never Vercel. It is the backend either
waking up (wait ~60s and retry) or gone because its database expired.

> ⚠️ **Do not put real employee health data in a public deployment.** This is a
> prototype without encryption at rest, audit logging, or a BAA. Use synthetic
> data (like `sample-bill-liam.pdf`) for demos. See the limitations section in
> README.md.

---

## Step 1 — Deploy the backend (Render)

The repo now has a `render.yaml` blueprint, so Render can create the web service
and the database for you instead of you typing every field.

1. Go to [render.com](https://render.com) and sign in with GitHub.
2. **New → Blueprint**, pick this repo, and set the branch to
   `claude/health-insurance-advisor-h84pyh`.
3. Render reads `render.yaml` and shows it will create `planwise-api` (web
   service) and `planwise-db` (Postgres). It asks you for the values marked
   `sync: false`:
   - `CORS_ORIGINS` — put `http://localhost:5173` for now; you'll change it to
     your Vercel URL in step 3.
   - `ANTHROPIC_API_KEY` — optional. Blank is fine; explanations then come from
     a deterministic template, which is by design.

   `SECRET_KEY` is generated for you and `DATABASE_URL` is wired to the database
   automatically.
4. **Apply.** The first build takes 3–5 minutes.
5. Confirm it works:
   `curl https://YOUR-SERVICE.onrender.com/health` → `{"status":"ok"}`

Keep that URL — the frontend needs it.

<details>
<summary>Manual setup, if you'd rather not use the blueprint</summary>

1. **New → Postgres.** Name it `planwise-db`, free plan. Copy the **Internal
   Database URL** once it provisions.
2. **New → Web Service**, connect this repo.
   - **Branch:** `claude/health-insurance-advisor-h84pyh`
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Environment variables:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Internal Database URL from step 1 |
   | `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `PYTHON_VERSION` | `3.11.9` |
   | `CORS_ORIGINS` | your Vercel URL (set after step 2) |
   | `ANTHROPIC_API_KEY` | optional |

`PYTHON_VERSION` matters: Render otherwise defaults to a newer Python than some
of these pinned dependencies publish wheels for, and the build fails while
compiling `psycopg2`. The blueprint and `backend/.python-version` both set it.

</details>

---

## Step 2 — Deploy the frontend (Vercel)

From your terminal:

```bash
npm install -g vercel
cd ~/Downloads/healthinsuranceadvisor/frontend
vercel login
vercel
```

Answer the prompts (accept the defaults; it will detect Vite). Then set the API
URL and ship a production build:

```bash
vercel env add VITE_API_BASE_URL production
# paste your Render URL, e.g. https://planwise-api.onrender.com

vercel --prod
```

Vercel prints your live URL, e.g. `https://planwise.vercel.app`.

`vercel.json` in this folder already handles SPA routing — without it, reloading
on `/results` would 404.

---

## Step 3 — Let the frontend talk to the backend

Back in Render, set the `CORS_ORIGINS` environment variable to your Vercel URL:

```
CORS_ORIGINS=https://planwise.vercel.app
```

Save — Render redeploys automatically. Without this the browser blocks every API
call and the app will look broken with "Network Error" in the console.

If you use a custom domain later, add it comma-separated:
`CORS_ORIGINS=https://planwise.vercel.app,https://planwise.com`

---

## Redeploying after changes

```bash
# backend: Render auto-deploys on push
git add -A && git commit -m "your change" && git push

# frontend:
cd frontend && vercel --prod
```

---

## Coming back after a few weeks away

Free-tier deployments rot on a schedule. Check in this order:

1. **Is Vercel up?** Open your Vercel URL. If the page renders at all, Vercel is
   fine — it does not expire from inactivity. A page that renders but shows
   "Network Error" is a backend problem, not a Vercel problem.
2. **Is the Render service awake?**
   `curl -m 120 https://YOUR-SERVICE.onrender.com/health`
   The `-m 120` matters — the first request after a spin-down can take a minute.
   Getting `{"status":"ok"}` slowly is success, not a timeout.
3. **Did the database expire?** In the Render dashboard, open `planwise-db`. If
   it says expired or is missing, that's your failure: the service boots but
   every request 500s. Create a new free Postgres, copy its Internal Database
   URL into the web service's `DATABASE_URL`, and redeploy. **The old data is
   gone** — accounts and saved families have to be re-entered. For a demo that
   is usually fine; if you want it to persist, the paid database tier is the
   only way.
4. **Did you blow the 750 hours?** Render suspends free services for the rest of
   the calendar month. The dashboard says so explicitly.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Network Error" / CORS message in console | `CORS_ORIGINS` on Render doesn't exactly match your Vercel URL (check `https://`, no trailing slash) |
| 404 when refreshing `/family` or `/results` | `vercel.json` missing from the deployed frontend |
| First request takes ~60s | Render free tier waking from sleep — expected. The frontend pings `/health` on page load to start the wake early. |
| Everything 500s after weeks of not using it | Free Postgres expired (30 days). See "Coming back after a few weeks away". |
| Render build fails compiling `psycopg2` | `PYTHON_VERSION` not set to 3.11.9 |
| Logins vanish between visits | `DATABASE_URL` still pointing at SQLite instead of Postgres |
| Explanations sound templated | No `ANTHROPIC_API_KEY` set — the fallback text is by design |
