<<<<<<< HEAD
# tval-microservices
This repo is created to code and test for TOSEM AI-SE paper.
=======
# TVAL Microservices (Research Prototype)

This repository contains a **minimal, runnable prototype** of the Trust-Verified Agentic Lifecycle (TVAL)
from the paper draft. It simulates a retail-fintech pipeline (Payments → Risk → Ledger) with an **Agent Hub**
that proposes configuration changes, verifies them with **OPA policy**, and logs **justification traces**.

> ⚠️ Research prototype — designed for review reproducibility, not for production.

## Stack
- Python 3.11 + FastAPI for microservices
- PostgreSQL 15 for ledger storage
- Prometheus for metrics scraping
- OPA (Open Policy Agent) for policy verification
- Locust for workload generation
- Docker Compose for local orchestration

## Quick start

```bash
# 1) Build & run
docker compose up --build -d

# 2) Check health
curl -s http://localhost:8081/health
curl -s http://localhost:8082/health
curl -s http://localhost:8083/health
curl -s http://localhost:9090  # Prometheus UI

# 3) Run load (in a new terminal)
docker compose run --rm loadgen locust -f /app/locustfile.py --headless -u 50 -r 10 -t 2m --host http://payments:8000

# 4) Agent proposals (watch the folder)
docker compose logs -f agent
```

## Services & Ports
- `payments` (FastAPI) — `localhost:8081`
- `risk` (FastAPI) — `localhost:8082`
- `ledger` (FastAPI) — `localhost:8083`
- `prometheus` — `localhost:9090`
- `opa` — `localhost:8181`

## What the Agent does
- Observes key metrics from Prometheus (p95 latency, error rate)
- Plans a change (e.g., payments in-process concurrency)
- Verifies the change by querying **OPA** with `policy.rego`
- If allowed, writes a YAML manifest to `agent/manifests/` and a JSON **justification** to `agent/logs/`
- All justifications conform to `schemas/justification_schema.json`

## Minimal Experiments
Use the locust workload above, then summarize results:

```bash
docker compose run --rm agent python /app/agent.py --summarize
```

This prints a compact CSV including the **Trust Index** used in the paper (policy compliance, approval consistency, rollback rate).

## Notes
- Prometheus is configured to scrape `/metrics` of all services.
- For simplicity, the agent simulates "apply" by writing manifests; in Kubernetes this would be `kubectl apply`.
- The prototype avoids heavyweight embeddings; justification vectors are placeholders (zero-vector) to keep it lightweight.

## License
MIT (research prototype)
>>>>>>> c55500e (chore: initial commit (apply agent robustness fixes))
