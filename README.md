# High-Reliability Customer Profile API

## Architecture Overview
- **FastAPI** service with PostgreSQL via SQLAlchemy 2.0 and Redis for cache/idempotency/rate limiting.
- **Celery** workers handle asynchronous enrichment with retry/backoff and circuit breaker around external calls.
- **Auth**: JWT for human/admin users and API-key option for service-to-service clients with scoped permissions.
- **Reliability**: Redis-backed idempotency for risk signals, token bucket rate limiting, circuit breaker for enrichment, structured logging, and audit logging on all writes.
- **Observability**: health/readiness endpoints and Prometheus metrics.

## Idempotency Strategy
- Risk signal ingestion requires `Idempotency-Key` header or `request_id` field.
- Redis `setnx` used to reserve key; duplicate requests return previously stored payload.

## Rate Limiting Approach
- Redis-based per-client buckets (1-minute windows). Default 100 req/min; per-client overrides possible via configuration.

## Circuit Breaker + Retry
- Enrichment task wraps external provider in circuit breaker with timeout simulation. Celery retries with exponential backoff; open breaker defers processing.

## Running Locally
1. Create `.env` with `database_url`, `redis_url`, and `jwt_secret`.
2. `docker-compose up --build` to start API, Redis, Postgres, and worker.
3. API available at `http://localhost:8000`.

## Tests
- Run `pytest` for unit/integration (requires docker services for integration tests).

## Example Requests
```
# Create customer
curl -X POST http://localhost:8000/customers \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Jane","email":"jane@example.com","phone":"+100000000","addresses":[{"line1":"1 Main","city":"NYC","state":"NY","postal_code":"10001","country":"US"}]}'

# Ingest risk signal
curl -X POST http://localhost:8000/customers/1/risk-signals \
  -H "Idempotency-Key: event-123" \
  -H "X-API-Key: <api key>" \
  -d '{"signal_type":"device","payload":{"ip":"1.1.1.1"},"source_system":"fraud"}'
```
