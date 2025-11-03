🧠 Order Orchestration System (Microservices • Resilient • Idempotent • Distributed)

A production-grade order orchestration platform built for real-world constraints:

- Distributed microservices
- Network failures, idempotency, retries, circuit breakers
- Inventory and Payments isolation
- Observability and security foundations
- Docker-based local production environment
- Strong testing culture (unit, API, and resilience tests)

Built with Python, Django, FastAPI, PostgreSQL, Redis, and Docker Compose.

✨ Key Features
| Capability                     | Description                                       |
| ------------------------------ | ------------------------------------------------- |
| 🧾 **Order orchestration**     | Gateway creates and manages orders across services|
| 🏬 **Inventory microservice**  | Stock reservation, idempotent store               |
| 💳 **Payments microservice**   | Payment authorization / failure simulation        |
| 🔁 **Idempotency**             | Safe re-submit of requests via Idempotency-Key    |
| 🧨 **Retries & backoff**       | Exponential retry strategy for upstream calls     |
| 🧯 **Circuit Breaker**         | Fail-open on unstable dependencies                |
| 🧪 **Test suite**              | Unit, API, and resilience tests                   |
| ⚙️ **DB migrations**           | PostgreSQL + Alembic                              |
| 🚦 **Rate limiting**           | DRF throttling (anonymous and scoped)             |
| ⚡ **Redis**                    | Cache + distributed throttling store              |
| 🛡 Security                    | Payload size limits, CORS, headers, HTTPS-ready   |
| 📦 **Docker Compose prod env** | Multiple DBs, migrations, healthchecks            |

🧭 High-Level Architecture
```
      ┌────────────┐
      │   Client   │
      └─────┬──────┘
            │ HTTP
            ▼
 ┌─────────────────────┐        ┌─────────────┐
 │  Django API Gateway │◀──────▶│    Redis    │ (cache, throttling)
 └───────┬─────────────┘        └─────────────┘
         │ Orchestrates
 ┌───────┼────────────┐
 │       │            │
 ▼       ▼            ▼
Inventory Service   Payments Service
 (FastAPI + PG)     (FastAPI + PG)
```
🏎 Tech Stack
Core
| Component               | Tech                              |
| ----------------------- | --------------------------------- |
| API Gateway             | Django REST Framework             |
| Services                | FastAPI                           |
| DB                      | PostgreSQL                        |
| Cache / Throttle store  | Redis                             |
| Migrations              | Django migrations + Alembic       |
| Container orchestration | Docker Compose                    |
| Logging                 | JSON structured logs              |
| Testing                 | pytest, requests, DRF test client |

🚀 Local Development Setup
1️⃣ Requirements
| Dependency            | Version       |
| --------------------- | ------------- |
| Python                | 3.12          |
| PostgreSQL            | 16.x          |
| Docker + Compose      | Latest        |
| GNU Make *(optional)* | For shortcuts |

2️⃣ Clone the project
```bash
git clone https://github.com/your-user/order-orchestration-system.git
cd order-orchestration-system
```

3️⃣ Install Python dependencies (optional for running tests without Docker)
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

🏗 Environment Variables
Local .env example
Create a `.env.dev` file in the project root with the following content:
```env
POSTGRES_DB=orders
POSTGRES_USER=app
POSTGRES_PASSWORD=app
POSTGRES_HOST=db
POSTGRES_PORT=5432

INVENTORY_BASE_URL=http://inventory:9001
PAYMENTS_BASE_URL=http://payments:9002

REDIS_URL=redis://redis:6379/1

DJANGO_SECRET_KEY=dev-secret

# Security relaxed locally
SECURE_SSL_REDIRECT=0
SECURE_HSTS_SECONDS=0
DEBUG=1

```
Production .env example
Create a `.env.prod` file in the project root with the following content:
```env
DJANGO_SECRET_KEY=replace-me
DEBUG=0
ALLOWED_HOSTS=*

POSTGRES_DB=orders
POSTGRES_USER=app
POSTGRES_PASSWORD=app
POSTGRES_HOST=db
POSTGRES_PORT=5432

INVENTORY_BASE_URL=http://inventory:9001
PAYMENTS_BASE_URL=http://payments:9002

REDIS_URL=redis://redis:6379/1

SECURE_SSL_REDIRECT=1
SECURE_HSTS_SECONDS=31536000
CORS_ALLOWED_ORIGINS=https://my-frontend.com
DATA_UPLOAD_MAX_MEMORY_SIZE=1048576

```

🐳 Local Production-like Environment
Spin up the full microservices stack:
```bash
docker compose up --build -d
```
Verify components:
```bash
docker compose ps
```
Run DB migrations:
```bash
docker compose exec web python manage.py migrate
```
Seed test inventory:
```bash
docker compose exec inventory python - <<'PY'
from repo import InventoryRepo
InventoryRepo().upsert("SKU1", 50)
print("✅ Inventory seeded")
PY
```
✅ Health Check
```bash
curl -i http://localhost:8000/health/
```
Response:
```bash
HTTP/1.1 200 OK
{"ok": true}
```

🔌 API Usage
Base URLs

- Gateway (Django): http://localhost:8000
- Inventory (FastAPI): http://localhost:9001
- Payments (FastAPI): http://localhost:9002

📦 Create order

Endpoint
```bash
POST /api/orders/
```

Headers
```yaml
Content-Type: application/json
Idempotency-Key: <optional string>   # recommended for safe retries
```

Body
```json
{
  "items": [{"sku": "SKU1", "quantity": 2}],
  "amount_cents": 1500,
  "currency": "EUR"
}
```

Response — 201 Created
```json
{
  "id": "f144be29-7037-4c84-a761-f7e3e2d50425",
  "status": "CONFIRMED",
  "transaction_id": "9f942a4c-8e2a-4a0b-bc39-7b2b54e18e4c"
}
```

Idempotent retry (same key and same payload) — 200 OK
```yaml
Idempotent-Replay: true
```
```json
{
  "id": "f144be29-7037-4c84-a761-f7e3e2d50425",
  "status": "CONFIRMED",
  "transaction_id": "9f942a4c-8e2a-4a0b-bc39-7b2b54e18e4c"
}
```

Idempotency conflict (same key, different payload) — 409
```json
{"detail": "IDEMPOTENCY_CONFLICT"}
```

Insufficient stock — 422
```json
{"detail": "INSUFFICIENT_STOCK"}
```

Payment failed — 402
```json
{"detail": "PAYMENT_FAILED"}
```

Upstream unavailable — 503
```json
{"detail": "UPSTREAM_UNAVAILABLE"}
```

Validation error — 400
```json
{"detail": "...Pydantic message..."}
```

curl examples
```bash
# create
curl -s -X POST http://localhost:8000/api/orders/ \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-1001" \
  -d '{"items":[{"sku":"SKU1","quantity":2}],"amount_cents":1500,"currency":"EUR"}' | jq

# retry (same payload and key)
curl -i -s -X POST http://localhost:8000/api/orders/ \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-1001" \
  -d '{"items":[{"sku":"SKU1","quantity":2}],"amount_cents":1500,"currency":"EUR"}'
```

📜 List orders

Endpoint
```bash
GET /api/orders/?page=1&page_size=20
```

Response — 200 OK
```json
{
  "count": 2,
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "id": "f144be29-7037-4c84-a761-f7e3e2d50425",
      "status": "CONFIRMED",
      "amount_cents": 1500,
      "currency": "EUR",
      "transaction_id": "9f942a4c-8e2a-4a0b-bc39-7b2b54e18e4c"
    },
    {
      "id": "c84b0a31-7e36-4fdc-9a6c-27a4202f3b1b",
      "status": "PENDING",
      "amount_cents": 9900,
      "currency": "EUR"
    }
  ]
}
```

curl
```bash
curl -s "http://localhost:8000/api/orders/?page=1&page_size=10" | jq
```

🔍 Order detail

Endpoint
```bash
GET /api/orders/<uuid>/
```

Response — 200 OK
```json
{
  "id": "f144be29-7037-4c84-a761-f7e3e2d50425",
  "status": "CONFIRMED",
  "amount_cents": 1500,
  "currency": "EUR",
  "transaction_id": "9f942a4c-8e2a-4a0b-bc39-7b2b54e18e4c"
}
```

Not found — 404
```json
{"detail":"NOT_FOUND"}
```

curl
```bash
curl -s "http://localhost:8000/api/orders/<uuid>/" | jq
```

🧪 Rate Limiting (DRF Throttling)

- POST /api/orders/ → 10/min (scope orders_create)
- GET /api/orders/ → 120/min (scope orders_list)
- GET /api/orders/<id>/ → 300/min (scope orders_detail)

429 example
```bash
for i in $(seq 1 30); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Content-Type: application/json" \
    -d '{"items":[{"sku":"SKU1","quantity":1}],"amount_cents":1200,"currency":"EUR"}' \
    http://localhost:8000/api/orders/
done

# ~the 11th → 429
```

In production we use Redis so the limit is global across workers.

🧰 Internal endpoints (microservices)

Normally not exposed publicly; useful for local debugging.

Inventory

- `GET /health → {"ok": true}`
- `POST /reserve`
    Body
    ```json
    {"items":[{"sku":"SKU1","quantity":2}]}
    ```

    Response

    - 200 {"reserved": true}
    - 422 {"detail":"INSUFFICIENT_STOCK"}

Seed inventory
```bash
docker compose exec -T inventory \
  python -c "from repo import InventoryRepo; InventoryRepo().upsert('SKU1', 50); print('OK')"
```

Payments

- `GET /health → {"ok": true}`
- `POST /charge`
    Body

    ```json
    {"amount_cents":1500,"currency":"EUR"}
    ```

    Response

    - 200 {"charged": true, "transaction_id":"<uuid>"}
    - 402 {"detail":"PAYMENT_FAILED"}
    - 409 {"detail":"IDEMPOTENCY_CONFLICT"} (when the same Idempotency-Key is reused with a different payload)

Idempotency-Key end-to-end

- The Gateway propagates `Idempotency-Key` to the Payments service.

🛡️ Practical security

- CORS: restricted by CORS_ALLOWED_ORIGINS
- Payload size: 413 if Content-Length > API_MAX_BYTES (default 1MB)
- Security headers:
    - X-Frame-Options: DENY
    - X-Content-Type-Options: nosniff
    - Referrer-Policy: same-origin
    - Cross-Origin-Opener-Policy: same-origin
    - Strict-Transport-Security (only under HTTPS with SECURE_HSTS_SECONDS > 0)

🧪 Testing
Run all (host)
```bash
cd web
pytest -q
```
Run all (inside the web container)
```bash
docker compose exec -T web pytest -q
```
Tests by folder/file
```bash
# domain
pytest -q apps/orders/tests/test_domain_service.py

# API create/list/detail
pytest -q apps/orders/tests/test_api_read_orders.py
pytest -q apps/orders/tests/test_api_create_order.py

# idempotency
pytest -q apps/orders/tests/test_api_idempotency.py

# resilience (retries, circuit breaker)
pytest -q apps/orders/tests/test_resilience.py
```
Coverage
```bash
pytest --maxfail=1 --disable-warnings --cov=apps/orders --cov-report=term-missing
```
Useful notes

- Resilience tests do not hit real services: they mock httpx and time.sleep.
- To speed up, settings.py reduces retries/backoff when pytest is present.
- Use -vv for more detailed traces when needed.

🧱 Test structure
```bash
web/apps/orders/tests/
  ├─ test_domain_service.py         # orchestration + states
  ├─ test_api_create_order.py       # POST /api/orders/ (+ payments/stock)
  ├─ test_api_idempotency.py        # 200/409 depending on payload
  ├─ test_api_read_orders.py        # GET list + GET detail
  └─ test_resilience.py             # 5xx, retries, circuit breaker
```

🧪 Key cases covered

- Domain: transition from `PENDING` → `CONFIRMED` / payment failures (402) / insufficient stock (422).
- Idempotency:
    - Same key + same payload → 200 (replay) + original body.
    - Same key + different payload → 409 `IDEMPOTENCY_CONFLICT`.
- Resilience: exponential retries on 5xx, no retries on 4xx, breaker opens/closes.

🧰 Troubleshooting
1) 301 to `https://…/health/`

- Cause: `SECURE_SSL_REDIRECT=1` without a TLS-terminating proxy.
- Quick fix in web .env: set SECURE_SSL_REDIRECT=0.

2) 422 `INSUFFICIENT_STOCK` when creating orders

- Seed inventory:
    ```bash
    docker compose exec -T inventory \
    python -c "from repo import InventoryRepo; InventoryRepo().upsert('SKU1', 50); print('OK')"
    ```

3) Idempotency returns unexpected 409

- Ensure same key and same payload (exact order and values).
- Clear the idempotency table if you changed models during testing.

4) Throttling not applied

- With multiple workers, use Redis as the cache (already configured).
- Verify `DEFAULT_THROTTLE_CLASSES` and scopes in `settings.py`.

5) Healthcheck reports inventory/payments as “unhealthy”

- If you use `python -c urllib.request` in the healthcheck you don’t need curl/wget.
- Verify ports 9001/9002 and that /health returns 200.

6) Orders DB doesn’t start / credentials

- If the volume already existed, the user may differ.
- Align web/.env(.prod) with POSTGRES_* of the db service or create the role:
    ```bash
    docker compose exec db psql -U <existing_user> -d postgres -c "CREATE ROLE app LOGIN PASSWORD 'app';"
    ```

7) Alembic (MS) recreates tables / type errors

- Use `alembic stamp head` if tables already exist in that database.
- Sensitive type changes (e.g., int → uuid) require manual migration (ALTER COLUMN … USING …).

8) 413 Payload Too Large doesn’t trigger

- Ensure `ApiSizeLimitMiddleware` is high in `MIDDLEWARE`.
- Confirm `API_MAX_BYTES` in the container env.

🔒 Security (quick check)

- CORS: set `CORS_ALLOWED_ORIGINS` (avoid `*` in prod).
- Headers: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `COOP` already active; `HSTS` only with HTTPS.
- Size limits: `DATA_UPLOAD_MAX_MEMORY_SIZE`, `API_MAX_BYTES` → 413.

📈 Observability (suggested next block)

- JSON access logs in web and microservices.
- Prometheus:
    - Exporters: Django/DRF, Uvicorn, Postgres, Redis.
    - Domain metrics: `orders_created_total`, `payments_failed_total`, upstream latencies.
- Grafana: per-service dashboards + orders panel.

🗺️ Roadmap

- Cancelation and refunds in the order flow.
- Catalog service (products and prices) with its own DB.
- Nginx/Traefik with TLS, HSTS, and edge rate limiting.
- Background tasks (confirmations, compensations) with Celery/Redis.
- OpenAPI + auto-generated client SDKs (Python/TS).
- CI (lint, tests, build, security) + CD (staging/prod).
- Chaos tests (latencies, failures, network partitions).
- K8s (optional): Helm charts, init containers for migrations.