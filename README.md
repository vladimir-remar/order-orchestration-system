🧠 Order Orchestration System (Microservices • Resilient • Idempotent • Distributed)

A production-grade order orchestration platform designed with real-world constraints:

- Distributed microservices

- Network failures, idempotency, retries, circuit breakers

- Inventory + Payments isolation

- Observability & security foundations

- Docker-based local prod environment

- Strong testing culture (functional, resilience & unit tests)

Built with Python + Django + FastAPI + PostgreSQL + Redis + Docker Compose.

✨ Key Features
| Capability                     | Description                                       |
| ------------------------------ | ------------------------------------------------- |
| 🧾 **Order orchestration**     | Gateway creates & manages orders across services  |
| 🏬 **Inventory microservice**  | Stock reservation, idempotent store               |
| 💳 **Payments microservice**   | Payment authorization / failure simulation        |
| 🔁 **Idempotency**             | Safe re-submit of requests (API idempotency keys) |
| 🧨 **Retries & backoff**       | Exponential retry strategy for upstream calls     |
| 🧯 **Circuit Breaker**         | Automatic fail-open on unstable dependencies      |
| 🧪 **Test suite**              | Unit + API + resilience tests (timeouts, chaos)   |
| ⚙️ **DB migrations**           | Postgres + Alembic                                |
| 🚦 **Rate limiting**           | DRF throttling (anonymous + scoped)               |
| ⚡ **Redis**                    | Cache + distributed throttling storage            |
| 🛡 Security                    | Payload size limits, CORS, headers, HTTPS-ready   |
| 📦 **Docker Compose prod env** | Multiple DBs, migrations, healthchecks            |

🧭 High-Level Architecture

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

3️⃣ Install Python dependencies
|Optional, useful for running tests without Docker

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

📦 Crear pedido

Endpoint
```bash
POST /api/orders/
```

Headers
```yaml
Content-Type: application/json
Idempotency-Key: <optional string>   # recomendado para reintentos seguros
```

Body
```json
{
  "items": [{"sku": "SKU1", "quantity": 2}],
  "amount_cents": 1500,
  "currency": "EUR"
}
```

Respuesta — 201 Created
```json
{
  "id": "f144be29-7037-4c84-a761-f7e3e2d50425",
  "status": "CONFIRMED",
  "transaction_id": "9f942a4c-8e2a-4a0b-bc39-7b2b54e18e4c"
}
```

Reintento idempotente (misma key y mismo payload) — 200 OK
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

Conflicto de idempotencia (misma key, payload distinto) — 409
```json
{"detail": "IDEMPOTENCY_CONFLICT"}
```

Sin stock — 422
```json
{"detail": "INSUFFICIENT_STOCK"}
```


Pago fallido — 402
```json
{"detail": "PAYMENT_FAILED"}
```

Upstream no disponible — 503
```json
{"detail": "UPSTREAM_UNAVAILABLE"}
```

Validación inválida — 400
```json
{"detail": "...mensaje Pydantic..."}
```

Ejemplos curl
```bash
# crear
curl -s -X POST http://localhost:8000/api/orders/ \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-1001" \
  -d '{"items":[{"sku":"SKU1","quantity":2}],"amount_cents":1500,"currency":"EUR"}' | jq

# reintentar (mismo payload y key)
curl -i -s -X POST http://localhost:8000/api/orders/ \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-1001" \
  -d '{"items":[{"sku":"SKU1","quantity":2}],"amount_cents":1500,"currency":"EUR"}'
```

📜 Listar pedidos

Endpoint
```bash
GET /api/orders/?page=1&page_size=20
```

Respuesta — 200 OK
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
🔍 Detalle de pedido

Endpoint
```bash
GET /api/orders/<uuid>/
```

Respuesta — 200 OK
```json
{
  "id": "f144be29-7037-4c84-a761-f7e3e2d50425",
  "status": "CONFIRMED",
  "amount_cents": 1500,
  "currency": "EUR",
  "transaction_id": "9f942a4c-8e2a-4a0b-bc39-7b2b54e18e4c"
}
```

No encontrado — 404
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

Ejemplo 429
```bash
for i in $(seq 1 30); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Content-Type: application/json" \
    -d '{"items":[{"sku":"SKU1","quantity":1}],"amount_cents":1200,"currency":"EUR"}' \
    http://localhost:8000/api/orders/
done

# ~la 11ª → 429
```

|En producción usamos Redis para que el límite sea global entre workers.

🧰 Endpoints internos (microservicios)

|Normalmente no se exponen públicamente; útiles para debugging local.

Inventory

- `GET /health → {"ok": true}`

- `POST /reserve`
    Body
    ```json
    {"items":[{"sku":"SKU1","quantity":2}]}
    ```

    Respuesta

    - 200 {"reserved": true}

    - 422 {"detail":"INSUFFICIENT_STOCK"}

Seed inventario
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

    Respuesta

    - 200 {"charged": true, "transaction_id":"<uuid>"}

    - 402 {"detail":"PAYMENT_FAILED"}

    - 409 {"detail":"IDEMPOTENCY_CONFLICT"} (si se reutiliza Idempotency-Key con payload distinto)

Idempotency-Key end-to-end

- El Gateway propaga `Idempotency-Key` al Payments service.

🛡️ Seguridad práctica

- CORS: restringido por CORS_ALLOWED_ORIGINS

- Tamaño de payload: 413 si Content-Length > API_MAX_BYTES (por defecto 1MB)

- Headers de seguridad:

    - X-Frame-Options: DENY

    - X-Content-Type-Options: nosniff

    - Referrer-Policy: same-origin

    - Cross-Origin-Opener-Policy: same-origin

    - Strict-Transport-Security (solo bajo HTTPS con SECURE_HSTS_SECONDS > 0)

🧪 Testing
Ejecutar todo (host)
```bash
cd web
pytest -q
```
Ejecutar todo (dentro del contenedor web)
```bash
docker compose exec -T web pytest -q
```
Tests por carpeta/archivo
```bash
# dominio
pytest -q apps/orders/tests/test_domain_service.py

# API create/list/detail
pytest -q apps/orders/tests/test_api_read_orders.py
pytest -q apps/orders/tests/test_api_create_order.py

# idempotencia
pytest -q apps/orders/tests/test_api_idempotency.py

# resiliencia (retries, circuit breaker)
pytest -q apps/orders/tests/test_resilience.py
```
Cobertura
```bash
pytest --maxfail=1 --disable-warnings --cov=apps/orders --cov-report=term-missing
```
Notas útiles

- Los tests de resiliencia no golpean servicios reales: mockean httpx y time.sleep.

- Para acelerar, en settings.py reducimos retries/backoff cuando pytest está presente.

- Usa -vv si necesitas trazas más detalladas.

🧱 Estructura de tests
```bash
web/apps/orders/tests/
  ├─ test_domain_service.py         # orquestación + estados
  ├─ test_api_create_order.py       # POST /api/orders/ (+ pagos/stock)
  ├─ test_api_idempotency.py        # 200/409 según payload
  ├─ test_api_read_orders.py        # GET list + GET detail
  └─ test_resilience.py             # 5xx, reintentos, circuit breaker
```
🧪 Casos clave cubiertos

- Dominio: transición de `PENDING` → `CONFIRMED` / fallos de pago (402) / stock insuficiente (422).

- Idempotencia:

    - Misma key + mismo payload → 200 (replay) + cuerpo original.

    - Misma key + payload distinto → 409 `IDEMPOTENCY_CONFLICT`.

- Resiliencia: reintentos exponenciales en 5xx, no reintentar en 4xx, breaker abre/cierra.

🧰 Troubleshooting
1) 301 a `https://…/health/`

- Causa: `SECURE_SSL_REDIRECT=1` sin proxy TLS.

- Fix rápido en .env del web: SECURE_SSL_REDIRECT=0.

2) 422 `INSUFFICIENT_STOCK` al crear órdenes

- Seed inventario:

    ```bash
    docker compose exec -T inventory \
    python -c "from repo import InventoryRepo; InventoryRepo().upsert('SKU1', 50); print('OK')"
    ```

3) Idempotencia devuelve 409 inesperado

- Asegura misma key + mismo payload (orden y valores exactos).

- Limpia la tabla de idempotencia si cambiaste modelos durante pruebas.

4) Throttling no aplica

- Con varios workers, usa *Redis* como cache (ya configurado).

- Verifica `DEFAULT_THROTTLE_CLASSES` y scopes en `settings.py.`

5) Healthcheck “unhealthy” en inventory/payments

- Si usas python -c urllib.request en healthcheck → no necesitas curl/wget.

- Verifica puertos 9001/9002 y que /health responda 200.

6) DB de orders no levanta / credenciales

- Si el volumen ya existía, puede que el usuario difiera.

- Alinea web/.env(.prod) con POSTGRES_* del servicio db o crea el rol:
    ```bash
    docker compose exec db psql -U <existing_user> -d postgres -c "CREATE ROLE app LOGIN PASSWORD 'app';"
    ```
7) Alembic (MS) recrea tablas / errores de tipos

- Usa `alembic stamp head` si ya existen tablas en esa base.

- Cambios de tipo sensibles (e.g., int → uuid) requieren migración manual (ALTER COLUMN … USING …).

8) 413 Payload Too Large no salta

- Asegura que `ApiSizeLimitMiddleware` esté alto en el `MIDDLEWARE`.

- Confirma `API_MAX_BYTES` en el env del contenedor.

🔒 Seguridad (check rápido)

- CORS: define `CORS_ALLOWED_ORIGINS` (no * en prod).

- Headers: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `COOP` ya activos; `HSTS` solo con HTTPS.

- Size limits: `DATA_UPLOAD_MAX_MEMORY_SIZE`, `API_MAX_BYTES` → 413.

📈 Observabilidad (siguiente bloque sugerido)

- Access logs JSON en web + MS.

- Prometheus:

    - Exporters: Django/DRF, Uvicorn, Postgres, Redis.

    - Métricas dominio: `orders_created_total`, `payments_failed_total`, latencias de upstream.

Grafana: dashboards por servicio + panel de órdenes.

🗺️ Roadmap

- Cancelación y reembolsos del flujo de pedidos.

- Catalog service (productos y precios) con su propia DB.

- Nginx/Traefik con TLS, HSTS y rate limit a nivel edge.

- Background tasks (confirmaciones, compensaciones) con Celery/Redis.

- OpenAPI + client SDKs (Python/TS) autogenerados.

- CI (lint, tests, build, seguridad) + CD (staging/prod).

- Chaos tests (latencias, caídas, particiones de red).

- K8s (opcional): Helm charts, init containers para migraciones.