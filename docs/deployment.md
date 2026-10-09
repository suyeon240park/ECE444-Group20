# Staging deployment (#22)

Staging runs on [Render](https://render.com)'s free tier: the Flask backend as a **web service** and the Expo web build as a **static site**. Both build from `main` of this public repository. CI deploys them after the backend and client jobs pass, so a merge to `main` reaches staging without manual steps.

| | URL |
|---|---|
| App | [STAGING_APP_URL] |
| Backend health check | [STAGING_API_URL]/api/health |

The app's home screen shows the backend's status and commit, and the commit it was built from ("App build …"). After a deploy, both should show the commit at the top of `main`.

## Cost and limits

Free, no card. Limits that matter for us:

- The backend **sleeps after 15 minutes without traffic** and takes about a minute to wake. The first request after a quiet period is slow; the app shows "Checking…" until the backend answers. Q2 response-time measurements must warm the backend first or they measure the wake-up.
- 750 free instance hours per month per workspace, enough for one always-on service.
- No persistent disk. Nothing in the backend writes files, and the in-memory product cache (#14) is lost on every restart or sleep.
- One instance; no scaling.

## How a deploy happens

1. A pull request is merged into `main`.
2. CI (`.github/workflows/ci.yml`) runs the backend and client jobs.
3. If both pass, the `deploy-staging` job calls each service's Render **deploy hook** with `ref=<commit>`, so Render deploys exactly the commit CI tested. A failing `main` is never deployed.
4. Render builds and starts both services; the backend's health check path is `/api/health`.

If the deploy-hook secrets are missing, the job skips with a warning instead of failing.

To redeploy by hand: Render dashboard → service → **Manual Deploy** → *Deploy latest commit*.

## Setting it up from scratch

Needed once; done by one team member with a Render account (sign in with GitHub). Render does not need access to the repository: it is public, so services are created from its URL.

### 1. Backend: web service

Render dashboard → **New** → **Web Service** → **Public Git Repository** → `https://github.com/suyeon240park/ECE444-Group20`.

| Setting | Value |
|---|---|
| Name | `whats-in-my-food-api` (becomes the URL; pick another if taken) |
| Region | Ohio (US East), the closest to Toronto |
| Branch | `main` |
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn wsgi:app` (gunicorn binds to Render's `$PORT` by itself) |
| Instance Type | Free |
| Health Check Path (Advanced) | `/api/health` |
| Auto-Deploy (Advanced, if shown) | Off: CI triggers deploys |

Environment variables:

| Key | Value |
|---|---|
| `PYTHON_VERSION` | `3.12.7` (same minor version as CI) |
| `FLASK_ENV` | `production` |
| `CORS_ORIGINS` | the static site's URL from step 2, e.g. `https://whats-in-my-food.onrender.com` (no trailing slash) |
| `OFF_USER_AGENT` | `WhatsInMyFood/0.1 (<team contact email>)`; Open Food Facts asks for a contact |

Not set on purpose: `GIT_COMMIT` (the backend falls back to Render's `RENDER_GIT_COMMIT`), `DATABASE_URL` (no code uses the database yet), `GEMINI_API_KEY` (no endpoint uses the vision model yet). Every other variable in `backend/.env.example` has a working default.

### 2. Client: static site

**New** → **Static Site** → **Public Git Repository** → same URL.

| Setting | Value |
|---|---|
| Name | `whats-in-my-food` |
| Branch | `main` |
| Root Directory | `client` |
| Build Command | `npm ci && EXPO_PUBLIC_GIT_COMMIT=$RENDER_GIT_COMMIT npm run build:web` |
| Publish Directory | `dist` |
| Auto-Deploy (if shown) | Off |

Environment variables:

| Key | Value |
|---|---|
| `NODE_VERSION` | `22` (same as CI) |
| `EXPO_PUBLIC_API_BASE_URL` | the backend's URL from step 1, e.g. `https://whats-in-my-food-api.onrender.com` (no trailing slash) |

Redirects/Rewrites: add a **Rewrite** from `/*` to `/index.html`, so links to screens added later load the app instead of a 404.

`EXPO_PUBLIC_*` values are compiled into the JavaScript at build time. After changing one, redeploy the static site.

### 3. Point the two services at each other

The URLs exist only after both services are created: set `CORS_ORIGINS` on the backend and `EXPO_PUBLIC_API_BASE_URL` on the client, then **Manual Deploy** both.

### 4. Let CI deploy

Each service → **Settings** → **Deploy Hook** → copy the URL (it looks like `https://api.render.com/deploy/srv-…?key=…`; treat it as a password).

GitHub → repository **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Secret | Value |
|---|---|
| `RENDER_DEPLOY_HOOK_BACKEND` | the web service's deploy hook |
| `RENDER_DEPLOY_HOOK_CLIENT` | the static site's deploy hook |

If the repository's **Settings** tab is not visible to you, the repository owner has to add the secrets.

### 5. Check it

- `[STAGING_API_URL]/api/health` returns `{"status": "ok", "commit": "<sha>", …}`.
- The app URL shows the backend as `ok` with the same commit as "App build". "Unreachable: Failed to fetch" usually means `CORS_ORIGINS` does not exactly match the app's URL.
- After the next merge to `main`, the Actions run shows **Deploy staging** green and both commits update.
