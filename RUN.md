# AutoScape — Run Guide (Windows / PowerShell)

## Prerequisites

Install the following tools before proceeding:

| Tool | Version | Install |
|------|---------|---------|
| **Python** | 3.12+ | [python.org/downloads](https://www.python.org/downloads/) — check "Add to PATH" during setup |
| **Node.js** | 20+ | [nodejs.org](https://nodejs.org/) — LTS recommended |

`uv` and `pnpm` are installed automatically by `AutoScape.bat` on first run — you do **not** need to install them manually before double-clicking.

AutoScape uses up to four vendor API keys (pay-per-use developer APIs, not chat
subscriptions). For this local install, the launcher/backend read them automatically from one
file per key in the project-root `secrets/` folder. No separate shell environment setup is
required before launching. `backend/.env.local` is optional and only used for manual local
overrides:

| Env var | Used for |
|---------|----------|
| `GOOGLE_API_KEY` | Gemini image models for renders; Gemini text models for Build Sheets |
| `OPENAI_API_KEY` | gpt-image models for renders; GPT text models for Build Sheets |
| `ANTHROPIC_API_KEY` | Claude models for Build Sheets and suggested dimension defaults |
| `PERPLEXITY_API_KEY` | Agent API web search for product research (required for Build Sheets) |

You only need the keys for the vendors you pick. Renders need at least one of Google/OpenAI;
Build Sheets need Perplexity plus whichever text vendor you choose.

Verify your Python and Node installs:

```powershell
python --version   # should print Python 3.12.x
node --version     # should print v20.x or higher
```

### Manual install (advanced / fallback)

If you prefer to install `uv` and `pnpm` yourself before running the launcher — or if the automatic install fails (e.g. network restrictions, permissions) — run:

```powershell
python -m pip install --user uv
npm install -g pnpm
```

Then verify:

```powershell
uv --version
pnpm --version
```

---

## Install dependencies

For normal Windows use, double-clicking `AutoScape.bat` is enough: the launcher installs missing `uv` / `pnpm`, runs the backend through `uv`, installs frontend dependencies with `pnpm`, and starts both services.

For a manual setup or developer workflow, run these commands once after cloning (and again after pulling changes that modify dependencies):

**Terminal 1 — backend:**
```powershell
cd backend
uv sync
uv run alembic upgrade head
```

**Terminal 2 — frontend:**
```powershell
cd frontend
pnpm install
```

---

## Configuration

The normal key location is:

```powershell
secrets\GOOGLE_API_KEY
secrets\OPENAI_API_KEY
secrets\ANTHROPIC_API_KEY
secrets\PERPLEXITY_API_KEY
```

Each file contains only the raw key value: no quotes, no `export`, no `NAME=` prefix.
The filename is the environment variable name, and the file contents are the key value.
The launcher and backend load these files automatically; no manual environment-variable setup is
needed before running `AutoScape.bat` or the developer commands below.
After the app is running, you can also open `http://localhost:5173/settings` to view, update,
test, or clear these keys instead of editing the `secrets/` files manually.

The backend resolves keys in this order:

1. Existing process environment variables.
2. `backend\.env.local`, if present.
3. `secrets\<ENV_VAR_NAME>` files.

Do not create `backend\.env.local` just to provide API keys; the `secrets\` files are the
normal source of truth. `backend\.env.local` is only for deliberate local overrides and uses
standard dotenv `NAME=value` lines if you need that advanced workflow.

Missing keys cause a clear error in the UI when that feature is used; the server still starts
without them. The absence of `backend\.env.local` is not an error when the corresponding key
file exists in `secrets\`.

### Choosing models

Every request lets you pick the exact vendor model, not just the vendor:

- **Renders**: the project page has an Image Provider radio (OpenAI Images / Google Gemini
  Images) plus an **Image model** dropdown listing what that vendor currently offers.
- **Build Sheets**: the Project Dimensions panel has a Materials LLM radio (Anthropic Claude /
  OpenAI GPT / Google Gemini), a **Materials model** dropdown, and a **Product research model**
  dropdown for the Perplexity Agent API (which can route to Perplexity's own Sonar or to
  third-party models such as `openai/...` and `anthropic/...`).

The lists come from `GET /api/models`, which asks each vendor's list-models endpoint with your
key and caches the answer for ten minutes. When a key is missing or a vendor cannot be reached,
a built-in fallback list is shown and the dropdown says so. Your last choices are remembered in
the browser. The Settings page shows every list with a **Refresh models** button, and the
backend logs a `[models]` warning at startup if a default model has disappeared from a vendor.

Defaults live in `backend/app/providers/model_catalog.py` (`PROVIDERS`). Each Design Request
and Build Sheet records the model that produced it.

### Image provider quota guidance

Google's Gemini image models (`gemini-3.1-flash-image` and friends) have **no free-tier
quota**; they need billing enabled on the Google Cloud project tied to `GOOGLE_API_KEY`.
OpenAI image models are pay-per-use as well. If a vendor rejects a request for quota or
billing reasons, AutoScape shows an inline warning and you can switch the Image Provider or
model for that request. Gemini *text* models used for Build Sheets do have a free tier.

---

## Quick start (double-click)

**This is the recommended way to run AutoScape for everyday use.**

1. Complete the Prerequisites and Configuration steps above (one-time setup).
2. Double-click **`AutoScape.bat`** in the project root from Windows Explorer.

Command Prompt equivalent:

```bat
AutoScape.bat
```

The launcher will:
- Load API keys from existing environment variables, optional `backend\.env.local` overrides,
  and the project-root `secrets\` files.
- Check for `uv` and `pnpm`; install them automatically via `pip` / `npm` if not found, printing progress so the install is visible.
- Probe ports 8000–8010 and start the FastAPI backend on the first available port.
- Prepare the database schema on backend startup; the backend log should include `[startup] schema ready, data dir = <abs>, db = <abs>`.
- Start the Vite / React frontend on `http://localhost:5173`.
- Open `http://localhost:5173` in your default browser automatically once the frontend is ready.
- Stream labeled log output (`[backend]` / `[frontend]`) in the console window.

**First run note:** On a machine that has never run AutoScape before, `AutoScape.bat` will print `[setup] uv not found — installing via pip...` (and similarly for `pnpm`) before the normal startup output. This is expected — subsequent launches skip the install step.

**To stop:** close the `AutoScape Launcher` console window. Both backend and frontend processes terminate automatically.

---

## Developer / debug launch

Use this two-terminal flow when you need direct control over each process (live reload, attaching a debugger, inspecting per-process output, etc.).

**Terminal 1 — backend (FastAPI):**
```powershell
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

API available at `http://localhost:8000`  
Interactive API docs at `http://localhost:8000/docs`

**Terminal 2 — frontend (Vite / React):**
```powershell
cd frontend
pnpm dev
```

App available at `http://localhost:5173`

---

## Verification

1. Open `http://localhost:5173` in your browser.
2. Confirm the Projects list page loads with an empty state (no Projects yet).
3. Click **New Project**, fill in an address plus lot and house square footage, upload a Site Photo, and submit — the new Project should appear in the list.
4. Open the Project, click **New Design Request**, choose any Feature Categories, Style, Quality Tier, Image Provider, and Image model, then click **Generate Renders**. A successful request shows 3 renders; if a Design Request errors, the UI shows the structured backend `detail` message naming the cause, such as an image-provider quota or API-key problem, instead of an opaque `Request failed: 500`. The backend logs the full traceback with a short `trace_id` when an unexpected route exception occurs.

If the page doesn't load, check that both terminals show no errors and that ports 8000 and 5173 are not already in use.

---

## Run tests

**Backend:**
```powershell
cd backend
uv run pytest
```

**Frontend:**
```powershell
cd frontend
pnpm test
```

---

## Troubleshooting

### Backend port varies (8000–8010)

On Windows 10/11, the Hyper-V / WinNAT subsystem reserves ranges of TCP ports — port 8000 is commonly excluded, which prevents the backend from binding to it. `AutoScape.bat` handles this automatically by probing ports 8000–8010 and using the first one available.

The launcher always prints a line of the form:

```
[AutoScape] Backend on http://localhost:<port>
```

This is the authoritative source for which port the backend is running on. The frontend's Vite dev-proxy reads `backend/.runtime-port` (written by the launcher) and forwards `/api` and `/images` requests to the correct port automatically — you do not need to update any config manually.

If no port in the 8000–8010 range is free, the launcher exits with an error. Free up a port in that range and re-launch.

### Frontend proxy not reaching the backend

If the frontend loads but API calls fail (network errors in the browser console), the most likely cause is a mismatch between the port the backend is running on and what Vite's proxy is targeting. Re-run `AutoScape.bat` from scratch — the launcher refreshes `backend/.runtime-port` on every startup, which updates the proxy config.
