# SmarTrip - Tourism Assistant AI Microservice

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![License](https://img.shields.io/badge/License-GPL%203.0-blue.svg)

FastAPI microservice for **AI-assisted travel**: destination and activity recommendations, conversational chat, traveler matching, **seasonal demand / visibility** signals, trends, behavior-driven adaptive UI, and travel-preference questionnaires. ML artifacts load at startup (`ModelManager`); PostgreSQL or SQLite backs connectivity checks and future persistence.

For **cross-repo / AWS** context (ALB, RDS, Learner Lab–style deploy, relation to **voyager-backend-core** and **voyager-infrastructure**), see [`ARCHITECTURE.md`](ARCHITECTURE.md). This repository is the **Python AI** tier (`voyager-ai-service`).

## Table of contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [CORS and Learner Lab](#cors-and-learner-lab)
- [Running the service](#running-the-service)
- [API](#api)
- [Postman and local demos](#postman-and-local-demos)
- [Project layout](#project-layout)
- [Testing](#testing)
- [Deployment](#deployment)
- [Contributors](#contributors)
- [License](#license)

## Features

- **Recommendations**: personalized destinations (with optional **seasonality** on rankings), contextual activities, popular / trending / similar, categories, feedback.
- **Local AI stack (production-oriented)**: `/api/v1/local/*` runs with **Ollama local + embeddings locales + SQLite de memoria IA** para chat y recomendaciones basadas en `user_id`.
- **Seasonality** (`/api/v1/seasonality`): monthly indices (s=12), per-destination profile, naive seasonal forecast, visibility adjustments for operators.
- **Users, matching, trends**: profiles, compatibility, emerging trends digest.
- **Chat**: LLM-backed or offline fallback (configurable).
- **Travel preferences**: multi-step questionnaire sessions.
- **Behavior & adaptive UI**: signals and layout hints.
- **Health**: `/health` reports DB check and `models_loaded`.

## Installation

### Prerequisites

- **Python 3.11+**
- **PostgreSQL** (optional; SQLite is the default for local runs)
- **Docker** (optional)

Redis and external API keys are referenced in settings for future use; the app starts without them for core flows.

### Setup

```bash
git clone https://github.com/LePeanutButter/voyager-ai-service.git
cd voyager-ai-service
python -m .venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
```

Create a **`.env`** file in the project root if you need non-default values (see [Configuration](#configuration)). There is no requirement to copy from `.env.example`.

### Database

- **Default**: `sqlite:///./tourism_assistant.db` (file created on first use).
- **PostgreSQL** (e.g. RDS): set `DB_HOST`, `DB_USERNAME`, `DB_PASSWORD`, and optionally `DB_NAME`, `DB_PORT`, `DB_SSLMODE`, **or** set `DATABASE_URL` explicitly. Then run migrations as needed:

```bash
alembic upgrade head
```

## Configuration

Common variables (see `app/core/config.py` for the full list):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Full SQLAlchemy URL (optional if using `DB_*` or SQLite default) |
| `DB_HOST`, `DB_USERNAME`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT`, `DB_SSLMODE` | Build PostgreSQL URL for RDS-style deploys |
| `MODEL_PATH`, `RECOMMENDATION_MODEL`, … | On-disk ML artifacts under `app/ml/models` |
| `LLM_PROVIDER`, `LLM_API_KEY`, … | Chat / LLM integration |
| `AI_SQLITE_PATH` | SQLite local exclusivo para memoria conversacional IA |
| `OLLAMA_URL`, `LOCAL_MODEL_NAME`, `LOCAL_EMBEDDING_MODEL` | Inferencia y embeddings locales |
| `ALLOWED_ORIGINS` | CORS allowlist; **comma-separated** string or list (e.g. `http://localhost:5173,http://10.0.0.5:5173`) |
| `CORS_ALLOW_ORIGIN_REGEX` | Extra allowed origin pattern (no `*` wildcard) |
| `CORS_ALLOW_EC2_COMPUTE_DNS` | `true` to allow browser origins matching **EC2 public DNS** (`ec2-…amazonaws.com`) only |

## CORS and Learner Lab

Lab environments often use **changing IPs** or **EC2 public DNS**. This service avoids `Access-Control-Allow-Origin: *` while staying practical:

1. **Explicit origins**: set `ALLOWED_ORIGINS` to a CSV list (update when the lab IP changes), e.g. `http://YOUR_PUBLIC_IP:5173`.
2. **EC2 DNS only**: set `CORS_ALLOW_EC2_COMPUTE_DNS=true` if the browser talks to the frontend via the standard `ec2-…compute.amazonaws.com` hostname (not raw IP).
3. **Custom pattern**: set `CORS_ALLOW_ORIGIN_REGEX` to a tight regex (e.g. a fixed lab domain pattern).

Local dev defaults include `http://localhost:3000`, `8080`, and `5173`.

## Running the service

**Development** (reload, binds `127.0.0.1:8000` by default):

```bash
python -m app.main
```

**Production-style**:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Docker**:

```bash
docker build -t voyager-ai-service .
docker run -p 8000:8000 voyager-ai-service
```

**URLs**

- API base: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health` -> `database`, `models_loaded`, etc.

## API

All versioned routes live under **`/api/v1`**. Authentication is not enforced here (unlike voyager-backend-core); treat network placement and API gateway rules as your trust boundary.

### Recommendations (`/api/v1/recommendations`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/destinations/personalized` | Ranked destinations; optional `travel_month`, `apply_seasonality_mitigation` |
| POST | `/activities/contextual` | Activities by location / context |
| POST | `/personalized` | General personalized recommendation payload |
| GET | `/popular/{location}` | Popular activities |
| GET | `/trending` | Trending activities |
| GET | `/similar/{activity_id}` | Similar activities |
| GET | `/categories` | Activity categories |
| POST | `/feedback` | Rating feedback (query params per OpenAPI) |

### Seasonality (`/api/v1/seasonality`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/overview` | All catalog profiles; optional `reference_month` query (1–12) |
| GET | `/destinations/{destination_id}` | Single destination seasonal profile |
| POST | `/forecast` | Naive seasonal forecast (`destination_id`, `start_month`, `horizon_months`) |
| POST | `/visibility-adjustments` | Visibility multipliers for a list of destinations and `travel_month` |

### Other routers

- **Users** `/api/v1/users`
- **Matching** `/api/v1/matching`
- **Trends** `/api/v1/trends`
- **Chat** `/api/v1/chat` (camelCase body: `userId`, `message`)
- **Travel preferences** `/api/v1/travel-preferences`
- **Behavior** `/api/v1/behavior-analysis`
- **Adaptive UI** `/api/v1/adaptive-ui`
- **Local AI + real recommendations** `/api/v1/local`

### Example: personalized destinations with seasonality

```http
POST /api/v1/recommendations/destinations/personalized
Content-Type: application/json

{
  "user_id": "demo-user",
  "max_results": 6,
  "prefer_successful_patterns": true,
  "include_emerging_trends": false,
  "travel_month": 7,
  "apply_seasonality_mitigation": true
}
```

Response cards may include `seasonal_context` (`demand_index`, `phase`, `visibility_multiplier`) when mitigation is on.

## Postman and local demos

- **Collection**: `postman/Voyager-AI-Service.postman_collection.json`
- **Environment**: `postman/Voyager-AI-Service.local.postman_environment.json` (set `rootUrl` / `baseUrl` for your host)

Optional script (useful on Windows for POST bodies):

```bash
set PYTHONIOENCODING=utf-8
python scripts/demo_api_endpoints.py
```

Requires the API running on `http://127.0.0.1:8000` (adjust script if needed).

## Project layout

```
app/
├── main.py                 # FastAPI app, lifespan, CORS, /health
├── core/config.py          # Settings (DB, CORS, ML, LLM, seasonality, …)
├── api/v1/                 # HTTP routers (recommendations, users, matching, …)
├── modules/                # Domain services (recommendations, seasonality, chat, …)
├── ml/                     # ModelManager, artifacts under ml/models/
├── db/                     # SQLAlchemy engine, session, connectivity check
└── …
alembic/                    # Migrations (when using PostgreSQL)
postman/                    # Postman collection + local environment
scripts/                    # EC2 / manual deploy helpers
tests/                      # pytest suite
```

Legacy paths like `app/routes/` or `app/services/` are **not** used; logic lives under `app/api/v1` and `app/modules/`.

## Testing

```bash
pytest
```

Tests live under `tests/` (API, modules, prompts). Coverage thresholds may be enforced via `pytest.ini` / CI — run `pytest -h` in your environment to see active options.

## Deployment

- **Docker**: use the included `Dockerfile`; expose port **8000** (e.g. behind an ALB target group for the AI tier).
- **EC2 / Learner Lab**: see `scripts/ec2-deploy-ai-service.sh` and `scripts/deploy-ai-service-manual.sh` for image + artifact transfer patterns aligned with **voyager-infrastructure**.

Tune `ALLOWED_ORIGINS` / `CORS_*` on the instance to match how clients reach the web UI.

## Contributors

- Andrés Felipe Calderón Ramírez - [AndresFelipeCalderonRamirez](https://github.com/AndresFelipeCalderonRamirez)
- Laura Natalia Perilla Quintero - [Lanapequin](https://github.com/Lanapequin)
- Ricardo Andres Ayala Garzon - [lRicardol](https://github.com/lRicardol)
- Santiago Amaya Zapata - [SantiagoAmaya21](https://github.com/SantiagoAmaya21)
- Santiago Botero Garcia - [LePeanutButter](https://github.com/LePeanutButter)

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.

### License Summary

- **Commercial Use**: Yes
- **Modification**: Yes
- **Distribution**: Yes
- **Private Use**: Yes
- **Liability**: No
- **Warranty**: No

### Copyright

© 2026 Voyager Team. All rights reserved.