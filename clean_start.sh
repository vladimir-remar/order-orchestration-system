docker compose down -v --remove-orphans && \
docker rmi order-orchestration-system-web order-orchestration-system-inventory order-orchestration-system-payments && \
docker volume rm order-orchestration-system_orders_pg && \
docker compose -f docker-compose.prod.yml up -d --build && \
echo "Waiting for services to be ready..." && \
sleep 10 && \
# docker compose run --rm web python -m pytest -vv && \
docker compose -f docker-compose.prod.yml exec -T inventory python - <<'PY'
from repo import InventoryRepo
InventoryRepo().upsert("SKU1", 50)
print("SKU1=50 OK")
PY
curl -s -X POST http://localhost:8000/api/orders/ \
  -H "Content-Type: application/json" \
  -d '{"items":[{"sku":"SKU1","quantity":1}], "amount_cents":1200, "currency":"EUR"}'