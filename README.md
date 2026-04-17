# ai_knowledge_platform

AI Knowledge Platform is a planned Retrieval-Augmented Generation service. Phase 1 provides
the runnable FastAPI foundation only: project structure, environment configuration, Docker
setup, and a basic health endpoint.

## Current Scope

Implemented:

- Clean modular API structure under `services/api/src/`
  - `app/`: FastAPI app, routers, schemas
  - `services/`: application service layer
  - `core/`: configuration and cross-cutting setup
- Environment-driven settings via `pydantic-settings`
- `GET /api/v1/health`
- API Dockerfile and local Docker Compose setup
- Basic unit and contract tests

Not implemented yet:

- ingestion endpoints
- query endpoints
- auth, rate limiting, caching
- database models and migrations
- worker tasks
- readiness checks against downstream services

## Project Structure

```text
services/
  api/
    Dockerfile
    pyproject.toml
    src/
      app/
      core/
      services/
  worker/
shared/
infra/
  docker/
    .env.example
    docker-compose.yml
  k8s/
tests/
  unit/
  contract/
  integration/
  load/
specs/
```

## Local Development

Install the API package with development dependencies:

```bash
pip install -e "services/api[dev]"
```

Run the API locally:

```bash
PYTHONPATH=services/api/src uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

Expected shape:

```json
{
  "status": "healthy",
  "service": "api",
  "version": "0.1.0",
  "timestamp": "2026-04-17T10:05:00Z"
}
```

## Docker

Create a local environment file:

```bash
cp infra/docker/.env.example infra/docker/.env
```

Start the API:

```bash
docker compose -f infra/docker/docker-compose.yml up --build
```

Then call:

```bash
curl http://localhost:8000/api/v1/health
```

## Tests

```bash
pytest tests/unit tests/contract -v
```
