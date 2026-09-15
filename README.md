# Orchestrator Service

Stateless orchestrator microservice built with FastAPI following the classic
MVC pattern. It receives uploaded PDFs and coordinates a three-stage pipeline
against internal microservices over async HTTP (`httpx`), and runs behind the
Traefik reverse proxy.

## Architecture (MVC)

- `routers/` - thin route definitions, no business logic
- `controllers/` - orchestration: the pipeline brain (validate → extract → store)
- `models/` - data contracts (PDF, PipelineResult, internal DTOs)
- `views/` - response serialization (success 201/200, errors 400/422/503)
- `services/` - HTTP clients for the internal microservices (retries/backoff)
- `config.py` - settings from env (Pydantic Settings)
- `exceptions.py` - `PipelineError`, `BusinessRejection`, `ServiceError`
- `main.py` - FastAPI app (mounts routers, registers exception handlers)

The service is stateless: no database or local cache.

## Commands

```sh
cp .env.example .env
uv sync
uv run uvicorn orchestrator.main:app --reload
uv run pytest
uv run ruff check src/orchestrator
uv run mypy src/orchestrator --exclude tests
```

## Endpoints

- `POST /api/v1/uploads` (multipart `file`) - runs the pipeline on a PDF and
  returns `201` with `{status, id, filename, checksum, message}`

Error codes: `400` (validation / duplicate document), `422` (invalid request),
`503` (pipeline upstream unavailable).

## Docker + Traefik

```sh
docker network create traefik-net
docker compose up -d --build
```

Traefik routes the service using the labels declared in `docker-compose.yml`
(ingress `web`, host rule `orchestrator.localhost`).