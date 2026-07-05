# PlotPilot

## What it is

PlotPilot is a local-first long-form writing system. It gives an author a FastAPI backend, a Vue workspace, and structured tools for novels, chapters, story bibles, knowledge extraction, beat sheets, review, and background generation.

This checkout uses `master` as the active branch.

## Current state

- Backend: Python, FastAPI, uvicorn, Pydantic, SQLite, and optional Qdrant.
- Frontend: Vue 3, TypeScript, Vite, Naive UI, Pinia, Axios, and ECharts.
- AI providers: Anthropic, ByteDance Ark/Doubao, OpenAI embeddings, and local embedding paths are represented in code.
- API entry: `interfaces.main:app`.
- CLI entry: `python -m PlotPilot` style package execution is supported by `__main__.py`, and `cli.py` exposes a `serve` command.
- The backend loads `.env` from the repository root when present.
- The backend starts an autopilot daemon on startup unless disabled with `DISABLE_AUTO_DAEMON=1`.
- Runtime data, logs, model caches, and local databases are expected to live outside the committed source or under ignored local paths.

## Run it

Backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and provide at least one usable LLM provider key for the flows you plan to run.

Start the API:

```bash
DISABLE_AUTO_DAEMON=1 uvicorn interfaces.main:app --host 127.0.0.1 --port 8005 --reload
```

Open `http://127.0.0.1:8005/docs` for the FastAPI docs.

Optional Qdrant service:

```bash
docker compose up -d
```

Optional embedding model setup:

```bash
python scripts/utils/download_embedding_model.py
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Use the Vite URL printed by the frontend command.

## Project layout

```text
domain/              Entities, value objects, repositories, and domain services
application/         Use cases, workflows, DTOs, AI contracts, and engine services
infrastructure/      SQLite persistence, AI providers, vector stores, and storage adapters
interfaces/          FastAPI app, REST routes, middleware, stats, and API responses
scripts/             Setup, migrations, daemon helpers, evaluations, and prototypes
tests/               Unit, integration, and e2e tests
frontend/            Vue 3 workspace
docs/                Architecture, plans, superpower specs, and design notes
docker-compose.yml   Optional Qdrant service
```

## Assets

The repository is mainly application source, not a visual asset package. Frontend public assets are small UI files such as icons and `frontend/public/architecture.html`.

Novel projects, SQLite databases, Qdrant storage, logs, downloaded embedding models, and API credentials are local runtime material. They should not be inferred from this README unless present in the working tree.

## Limitations

- A clean clone needs Python and Node dependencies installed before it can run.
- Useful generation flows require configured LLM credentials.
- Some retrieval and embedding flows require local models or vector-store setup.
- Startup can launch background generation unless `DISABLE_AUTO_DAEMON=1` is set.
- Tests may need local services, fixtures, and provider configuration depending on the selected test set.
- The license file combines Apache 2.0 terms with Commons Clause restrictions. Check `LICENSE` before commercial use.

## Maintainer

Keep the top-level README aligned with `requirements.txt`, `interfaces/main.py`, `frontend/package.json`, and `docker-compose.yml`. Fable5 should read this repository as the current PlotPilot application source on `master`, not as a hosted service, sample-only scaffold, or completed content library.
