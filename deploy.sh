#!/usr/bin/env bash
# One-command deploy from a Mac (or any machine with git + Node).
#
#   ./deploy.sh
#
# 1. Pushes the code you have checked out to the branch Render deploys from,
#    so the backend (FastAPI) redeploys automatically.
# 2. Builds and ships the frontend to Vercel production.
#
# Safe to re-run. It refuses to overwrite the deploy branch if someone else
# pushed to it in the meantime (no force-push).

set -euo pipefail

DEPLOY_BRANCH="claude/health-insurance-advisor-h84pyh"
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

say()  { printf "\n\033[1;32m==> %s\033[0m\n" "$*"; }
fail() { printf "\n\033[1;31mError:\033[0m %s\n" "$*" >&2; exit 1; }

# --- tools ------------------------------------------------------------------
command -v git  >/dev/null || fail "git is missing. Run: xcode-select --install"
command -v node >/dev/null || fail "Node.js is missing. Install it from https://nodejs.org (LTS), or: brew install node"
command -v npm  >/dev/null || fail "npm is missing (it comes with Node.js)."
if ! command -v vercel >/dev/null; then
  say "Installing the Vercel CLI (npm install -g vercel)"
  npm install -g vercel || fail "Could not install the Vercel CLI. Try: sudo npm install -g vercel"
fi

# --- 1. GitHub (triggers the Render backend redeploy) ------------------------
say "Checking GitHub access"
if ! git ls-remote --exit-code origin >/dev/null 2>&1; then
  fail "Git can't reach GitHub with your credentials.
  Easiest fix:  brew install gh && gh auth login   (choose GitHub.com, HTTPS, log in with browser)
  Then run ./deploy.sh again."
fi

if [ -n "$(git status --porcelain)" ]; then
  say "Committing your local changes"
  git add -A
  git commit -m "Update from local machine"
fi

say "Pushing to GitHub branch $DEPLOY_BRANCH"
git fetch origin "$DEPLOY_BRANCH"
if ! git merge-base --is-ancestor "origin/$DEPLOY_BRANCH" HEAD; then
  fail "The $DEPLOY_BRANCH branch on GitHub has changes this folder doesn't have.
  Run: git pull origin $DEPLOY_BRANCH   then ./deploy.sh again."
fi
git push origin "HEAD:$DEPLOY_BRANCH"
echo "Pushed. Render redeploys the backend automatically (3-5 minutes; watch it at https://dashboard.render.com)."

# --- 2. Vercel (frontend) ----------------------------------------------------
cd "$ROOT/frontend"

say "Installing frontend dependencies"
npm install

say "Checking the frontend builds"
npm run build

if [ ! -d .vercel ]; then
  say "Linking this folder to your Vercel project"
  echo "When asked 'Link to existing project?' answer YES and pick your existing PlanWise project,"
  echo "so it keeps the VITE_API_BASE_URL setting that points at your Render backend."
  vercel link
fi

say "Deploying frontend to Vercel production"
vercel --prod

say "Done"
echo "Open your Vercel URL, log in, and click 'Practice Simulator' in the top bar."
echo "If the page shows an error at first, the Render backend is still redeploying or waking up; wait a minute and refresh."
