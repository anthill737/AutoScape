# AutoScape

AI renders and shopping lists for home projects, outdoor and interior.

AutoScape takes a photo of a yard or a room, lets you pick what you want changed and in what style, and generates three photorealistic renders of the result. From a chosen render it then writes a **Build Sheet**: an itemized materials list with quantities, waste factors, licensed-trade flags, and real products researched from retailers such as Home Depot, Lowe's, IKEA and Wayfair.

Everything runs locally. The only outside calls are to the AI vendors you give it keys for.

## What it does

- **Projects** hold an address, a photo, and a space type chosen at creation.
  - **Outdoor & Landscape**: yards, decks, patios, pools, gardens. Sized by lot and house square footage.
  - **Interior**: Kitchen, Bathroom, Living Room, Bedroom, Home Office, Basement, Laundry / Mudroom or Dining Room, sized by length, width and ceiling height.
- **Design Requests** pick feature categories, a style, a quality tier, and an image vendor and model, then produce three renders. The space type shapes the prompt, so an interior render keeps the walls, windows and doors while an outdoor render keeps the house and lot boundaries.
- **Build Sheets** turn a render into a materials list. A text model drafts the sheet, a web-search model finds matching products, and a validation layer checks the result. Interiors get waste factors and flags for work that needs a licensed trade.
- **Model choice** is per request. Dropdowns list what each vendor currently offers, fetched live and cached. Every render and Build Sheet records the model that made it.
- **Settings page** lets you view, update, test and clear API keys and refresh the model lists in the browser.

## Vendors and keys

| Key | Used for |
|-----|----------|
| `GOOGLE_API_KEY` | Gemini image models for renders; Gemini text models for Build Sheets |
| `OPENAI_API_KEY` | gpt-image models for renders; GPT text models for Build Sheets |
| `ANTHROPIC_API_KEY` | Claude models for Build Sheets and suggested dimension defaults |
| `PERPLEXITY_API_KEY` | Agent API web search for product research (required for Build Sheets) |

You only need the keys for the vendors you use. Renders need at least one of Google or OpenAI. Build Sheets need Perplexity plus one text vendor. Keys live one per file in `secrets/`, named after the variable, and are never committed.

## Quick start (Windows)

1. Install [Python 3.12+](https://www.python.org/downloads/) and [Node.js 20+](https://nodejs.org/).
2. Put your API keys in `secrets/` as described above.
3. Double-click `AutoScape.bat`.

The launcher installs `uv` and `pnpm` if missing, starts the backend on the first free port in 8000 to 8010, starts the frontend on `http://localhost:5173`, and opens it in your browser. `Stop-AutoScape.bat` shuts everything down.

For the two-terminal developer flow, tests, configuration details and troubleshooting, see [RUN.md](RUN.md).

## Layout

```
AutoScape.bat          one-click launcher
Stop-AutoScape.bat     stop all AutoScape processes
RUN.md                 full run guide
backend/               FastAPI + SQLAlchemy + Alembic (Python, managed by uv)
  app/api/             HTTP routes
  app/domain/          space types, retailers, Build Sheet validation
  app/providers/       image, text and search vendor adapters, model catalog
  migrations/          Alembic migrations
  tests/               pytest suite
frontend/              React 18 + TypeScript + Vite + Tailwind (managed by pnpm)
  src/pages/           Projects list, New Project, Project detail, Settings
  src/api/             typed client for the backend
scripts/               PowerShell helpers used by the launchers
secrets/               one file per API key (gitignored)
```

## Tests

```powershell
cd backend;  uv run pytest
cd frontend; pnpm test
```

## License

Copyright (c) 2026 Hillside Ventures LLC. All rights reserved. No license is granted; see [LICENSE](LICENSE).
