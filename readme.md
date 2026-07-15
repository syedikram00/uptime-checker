# Uptime Monitor

A self-hosted uptime monitoring service — add URLs, get automatic health checks on a schedule, view uptime history and status on a live dashboard, and receive real-time alerts when something goes down. Built as an end-to-end DevOps project covering the full lifecycle from application code to a production-shaped Kubernetes deployment.

## Architecture

```
                     ┌─────────────────────┐
                     │   Web Dashboard /    │
                     │      REST API        │
                     │     (FastAPI)        │
                     └──────────┬───────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │     PostgreSQL       │
                     │  (monitors + check   │
                     │      history)        │
                     └──────────┬───────────┘
                                ▲
                                │
                     ┌─────────────────────┐
                     │  Checker CronJob     │
                     │ (runs every minute,  │
                     │  pings each URL,     │
                     │  writes results,     │
                     │  fires webhook       │
                     │  alerts on change)   │
                     └─────────────────────┘

         Traffic flow: Domain/Ingress → Service → Pods
```

The API/dashboard and the checker are **fully decoupled**: the dashboard serves requests on demand, while a separate Kubernetes CronJob independently checks every monitored URL on a schedule and writes results directly to the shared database. This means the checking logic keeps running correctly regardless of how many dashboard replicas are up, and avoids the risk of duplicate checks that an in-process scheduler would have if scaled horizontally.

## Tech Stack

| Layer | Tool |
|---|---|
| Application | Python, FastAPI |
| Frontend | Jinja2 templates, HTML/CSS |
| Database | PostgreSQL, SQLAlchemy ORM |
| Scheduled checks | Kubernetes CronJob (standalone Python script) |
| Alerting | Webhooks (Discord) |
| Testing | Pytest |
| Containerization | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Container Registry | Docker Hub |
| Orchestration | Kubernetes (via kind) |
| Ingress | NGINX Ingress Controller |

## Features

- Add, view, and remove monitored URLs through a clean web dashboard
- Automatic health checks every minute, run independently of the API via a Kubernetes CronJob
- Persistent check history and uptime percentage per monitor
- Real-time status indicators (Operational / Down / Pending) with a summary bar
- Webhook alerting on state change (up → down, down → up) — alerts only fire on a genuine change, not on every check, to avoid notification spam
- Full REST API alongside the dashboard, for programmatic access
- Fully containerized and deployed to Kubernetes with Ingress-based routing

## Routes

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Web dashboard — view monitors, status, and uptime |
| POST | `/add-monitor` | Add a monitor via the dashboard form |
| POST | `/delete-monitor/{monitor_id}` | Remove a monitor via the dashboard |
| GET | `/health` | Application health check |
| POST | `/monitors` | Add a monitor (JSON API) |
| GET | `/monitors` | List all monitors (JSON API) |
| GET | `/monitors/{monitor_id}` | Get a single monitor |
| DELETE | `/monitors/{monitor_id}` | Delete a monitor (JSON API) |
| GET | `/monitors/{monitor_id}/checks` | Full check history for a monitor |
| GET | `/monitors/{monitor_id}/uptime` | Uptime percentage and check counts |

## Project Structure

```
uptime-monitor/
├── app/
│   ├── main.py            # FastAPI application: routes, dashboard, API
│   ├── database.py        # SQLAlchemy models and DB connection
│   └── checker.py         # Standalone script: runs one check cycle, used by the CronJob
├── templates/
│   └── index.html         # Dashboard UI (Jinja2 template)
├── static/
│   └── style.css          # Dashboard styling
├── tests/
│   └── test_main.py       # Pytest test suite
├── k8s/
│   ├── postgres-deployment.yml
│   ├── postgres-service.yml
│   ├── app-deployment.yml
│   ├── app-service.yml
│   ├── ingress.yml
│   └── checker-cronjob.yml
├── kind-config.yaml        # kind cluster config with Ingress port mappings
├── Dockerfile               # Builds the API/dashboard image
├── Dockerfile.checker       # Builds the checker image (used by the CronJob)
├── docker-compose.yml       # Local dev: app + Postgres
├── requirements.txt
├── .github/
│   └── workflows/
│       └── ci.yml           # Test, build, and push to Docker Hub on every push
└── README.md
```

## Running Locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
docker compose up -d postgres
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/` for the dashboard.

To also run a check manually (outside the CronJob, for testing):
```bash
python -m app.checker
```

## Running Tests

```bash
python -m pytest tests/test_main.py
```

## Running with Docker Compose (app + Postgres together)

```bash
docker compose up --build
```

Visit `http://localhost:8000/`. Data persists in a Docker volume across restarts.

## CI/CD Pipeline

On every push, GitHub Actions:
1. Spins up a Postgres service container for the test run
2. Runs the pytest suite
3. Builds the Docker image
4. Pushes it to Docker Hub as `ikramsyed/uptime-monitor:latest`

See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Deploying to Kubernetes (kind)

**1. Create a kind cluster with Ingress-ready port mappings:**
```bash
kind create cluster --name uptime-cluster --config kind-config.yaml
```

**2. Deploy Postgres:**
```bash
kubectl apply -f k8s/postgres-deployment.yml
kubectl apply -f k8s/postgres-service.yml
```

**3. Deploy the app:**
```bash
kubectl apply -f k8s/app-deployment.yml
kubectl apply -f k8s/app-service.yml
```

**4. Install the NGINX Ingress Controller (kind-specific manifest):**
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/refs/heads/main/deploy/static/provider/kind/deploy.yaml

kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
```

**5. Apply the Ingress rule:**
```bash
kubectl apply -f k8s/ingress.yml
```

**6. Deploy the scheduled checker:**
```bash
kubectl apply -f k8s/checker-cronjob.yml
```

**7. Access the app:**
```bash
curl http://localhost/health
```
Or open `http://localhost/` in a browser.

**8. Verify the checker is running on schedule:**
```bash
kubectl get cronjobs
kubectl get jobs
kubectl get pods
```
A new pod should appear roughly once a minute, run briefly, and complete.

## Why a CronJob Instead of an In-Process Scheduler

The first version of this project ran checks using an in-process background scheduler (APScheduler) inside the same FastAPI process serving the dashboard. This works for a single instance, but doesn't hold up in a real deployment: if the app scales to multiple replicas, every replica would run its own scheduler and duplicate every check and every alert. Moving the check logic into a separate script, run independently by a Kubernetes CronJob, removes that coupling entirely — the API can scale freely without affecting how checks are run, and checks run exactly once per interval regardless of how many app replicas exist.

## Alerting Behavior

Alerts fire only on a **state change** — a monitor going from up to down, or down to up — not on every single check. This is a deliberate design choice to avoid notification spam: a site that stays down for an hour triggers exactly one "down" alert and one "back up" alert, not one every check cycle.

## What This Project Demonstrates

- Building a REST API with a server-rendered dashboard, backed by a persistent relational database
- Designing a decoupled, horizontally-scalable architecture (API vs. scheduled worker) instead of a monolithic in-process scheduler
- Debugging real dependency and environment issues (Python version compatibility across httpx, psycopg, and SQLAlchemy; container networking; Docker Compose service DNS)
- Writing Kubernetes manifests from scratch: Deployment, Service, Ingress, and CronJob
- Managing multi-service state in Kubernetes (app + database + scheduled job, correctly wired via Service DNS)
- Recovering from real infrastructure failures (stale cluster networking, port conflicts between multiple local clusters, image pull failures) by diagnosing root cause rather than guessing
- Setting up CI/CD with a database service container for integration testing, and publishing to Docker Hub
- Implementing alerting logic that avoids duplicate/spam notifications by detecting state changes rather than reporting raw status on every check

## Future Improvements

- Public, shareable status pages per user
- User accounts and authentication
- Paid tiers (more monitors, faster check intervals, SMS alerts) via Stripe
- Prometheus + Grafana for monitoring the monitor itself (meta, but valuable)
- Horizontal Pod Autoscaling on the API based on real traffic
- Email alerting as an alternative to webhooks
