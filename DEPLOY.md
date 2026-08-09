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

Both have free tiers. Render's free tier sleeps after ~15 minutes idle, so the
first request after a nap takes ~30s to wake — fine for a demo, not for a real
user base.

> ⚠️ **Do not put real employee health data in a public deployment.** This is a
> prototype without encryption at rest, audit logging, or a BAA. Use synthetic
> data (like `sample-bill-liam.pdf`) for demos. See the limitations section in
> README.md.

---

## Step 1 — Deploy the backend (Render)

1. Go to [render.com](https://render.com) and sign in with GitHub.
2. **New → Postgres.** Name it `planwise-db`, pick the free plan, create it.
   Copy the **Internal Database URL** when it finishes provisioning.
3. **New → Web Service**, and connect this GitHub repo.
   - **Branch:** `claude/health-insurance-advisor-h84pyh`
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Under **Environment**, add:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Internal Database URL from step 2 |
   | `SECRET_KEY` | run `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `CORS_ORIGINS` | leave blank for now — you'll set it in step 3 |
   | `ANTHROPIC_API_KEY` | optional; enables Claude-written explanations |

5. Deploy. When it's live, confirm it works:
   `curl https://YOUR-SERVICE.onrender.com/health` → `{"status":"ok"}`

Keep that URL — the frontend needs it.

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

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Network Error" / CORS message in console | `CORS_ORIGINS` on Render doesn't exactly match your Vercel URL (check `https://`, no trailing slash) |
| 404 when refreshing `/family` or `/results` | `vercel.json` missing from the deployed frontend |
| First request takes ~30s | Render free tier waking from sleep — expected |
| Logins vanish between visits | `DATABASE_URL` still pointing at SQLite instead of Postgres |
| Explanations sound templated | No `ANTHROPIC_API_KEY` set — the fallback text is by design |
