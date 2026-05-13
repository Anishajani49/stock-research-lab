# Deploying Stock Research Lab

Your two best free options are **Render** (easiest — no Docker needed) and **Fly.io**
(slightly more setup, but doesn't sleep). The repo includes config for both.

> **Why not Vercel / Netlify / Cloudflare Pages?**
> Those platforms host *static sites* or *short-lived serverless functions*.
> This app is a Python web service with ~300 MB of dependencies (pandas, numpy,
> yfinance, pypdf, trafilatura) and 8-15 second response times. It won't fit in
> Vercel's 250 MB / 10 s serverless limits. You need a real "always-on" web
> service host.

---

## Option 1 — Render.com (recommended, 5 minutes)

**Free tier reality check:** the service sleeps after 15 minutes of inactivity,
so the *first* request after a quiet period takes ~30 s to wake up. After
that it's fast again. Upgrade to **Starter ($7/mo)** to keep it always-warm.

### Steps

1. **Push the repo to GitHub** (skip if it's already there):
   ```bash
   cd ~/Desktop/stock-research-assistant
   git init                       # if needed
   git add .
   git commit -m "Initial deploy"
   gh repo create stock-research-lab --public --source=. --push
   # or: create the repo manually on github.com and `git remote add origin … && git push -u origin main`
   ```

2. **Sign up** at <https://render.com> (free, GitHub login works).

3. **Create a Blueprint deploy**:
   - Top right: **New + → Blueprint**
   - Connect your GitHub account
   - Pick your `stock-research-lab` repo
   - Render reads `render.yaml` automatically — click **Apply**

4. **Wait for the first build** (~5 minutes). When it goes green you'll get a URL like
   `https://stock-research-lab.onrender.com`. That's your live site.

5. **Auto-deploy on push** is on by default — every `git push origin main` rebuilds.

### Custom domain (optional)
In the Render dashboard → your service → **Settings → Custom Domains → Add**. You'll
get DNS instructions; point a CNAME record from your registrar.

---

## Option 2 — Fly.io (no sleep, free tier)

Fly's free tier includes 3 small VMs with 256 MB RAM each. The app needs ~512 MB
under load, so you'll likely want their `shared-cpu-1x` with 1 GB (still in the
free allotment for a single VM at the time of writing).

```bash
# 1. Install the CLI
brew install flyctl              # or: curl -L https://fly.io/install.sh | sh

# 2. Sign in
fly auth signup                  # or: fly auth login

# 3. From the project root, create + deploy
cd ~/Desktop/stock-research-assistant
fly launch --no-deploy           # answer the prompts; pick a region near India (sin/bom)
# Edit fly.toml if needed (recommended: VM size 1 GB)
fly deploy
```

The included `Dockerfile` is what Fly builds. After deploy you get a
`https://your-app.fly.dev` URL.

---

## Option 3 — Hugging Face Spaces (no sleep, free, public)

Best if you want a *learning portfolio* page. Comes with a `huggingface.co/spaces/...`
URL. Works via Docker.

1. Create a new **Space** at <https://huggingface.co/new-space>
2. Pick **Docker** as the SDK
3. Push the repo content into it (it gives you the git-push instructions)
4. The included `Dockerfile` runs as-is. Space exposes port 7860 by default — change
   `EXPOSE 8000` to `EXPOSE 7860` in the Dockerfile and the `PORT` env to `7860`.

---

## Option 4 — Local Docker test (sanity check before pushing to a host)

Run the production container on your laptop to make sure everything works
before paying any platform attention:

```bash
cd ~/Desktop/stock-research-assistant
docker build -t stock-research-lab .
docker run --rm -p 8000:8000 stock-research-lab
# open http://localhost:8000
```

If this works, every cloud host will work — the image is portable.

---

## What you DON'T need in cloud

- **Ollama** — the LLM is local-only. The `/api/analyze` endpoint already
  defaults to `skip_llm=true`, and the frontend always sets it. So cloud
  deploys don't talk to any LLM at all. Everything is deterministic.
- **Streamlit** — the new web UI replaces it. The slim production requirements
  (`requirements-prod.txt`) deliberately exclude `streamlit`, `Pillow`,
  `pytesseract`, and `pandas-ta` to keep the image small.
- **A database server** — we use SQLite for the evidence store, written to
  ephemeral disk. On a cloud host this resets between deploys. That's fine —
  it's a cache, not a system of record.

---

## Known gotchas after deploying

1. **yfinance rate limits from cloud IPs.** Yahoo Finance occasionally throttles
   requests from datacenter IP ranges. We cache market data for 30 min and
   fundamentals for 6 h, which reduces hit rate. If you see 429s in the logs,
   they'll usually clear themselves after a few minutes.

2. **First request after idle is slow on Render free.** ~30 s cold start. To
   avoid: upgrade to Starter, or hit `/api/health` with an uptime monitor
   (e.g. UptimeRobot free) every 10 min.

3. **No persistent disk.** Annual-report PDFs you analyse aren't stored —
   they're processed in memory and discarded. That's by design.

4. **Public URL.** Anyone can hit your `/api/analyze`. For a personal portfolio
   this is fine. If you ever wanted to limit it, the cheapest way is putting
   Cloudflare in front of the Render URL and using its WAF rules.

---

## Quick post-deploy checklist

After your first deploy, verify these in the browser:

- [ ] `/` — landing page loads with search box
- [ ] `/dashboard?ticker=RELIANCE` — analysis runs end-to-end (~15 s the first time)
- [ ] `/learn` — pattern gallery renders, clicking a card shows the detail
- [ ] `/annual-report` — page loads
- [ ] `/glossary` — terms load
- [ ] `/api/health` — returns `{"status":"ok"}`
