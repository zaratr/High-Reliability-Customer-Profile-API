# High-Reliability Customer Profile API

A FastAPI customer-profile service built around **production reliability patterns**:
circuit breaking, idempotency, and rate limiting — with an optional **libSQL/Turso
edge read-replica** for low-latency reads that falls back to the primary on failure.

> Reliability is the headline, not edge compute. The edge read-replica is a
> latency optimization layered on top of a defensible reliability core.

## Architecture

```
  Client
    │
    ▼
  FastAPI ── rate limiter (Redis) ── idempotency (Redis)
    │
    ├── CustomerService.get_customer(id)
    │       │
    │       ▼  try edge first
    │     EdgeDbClient ──[CircuitBreaker]──▶ libSQL/Turso edge replica
    │       │                                       │
    │       │ (on failure / circuit open)           │ HTTP wire protocol
    │       ▼                                       │ (WASM-compatible)
    │     fallback ────────────────────────────────┘
    │       │
    │       ▼
    │     Postgres primary (SQLAlchemy, source of truth)
    │
    └── writes always go to Postgres primary
```

## What's real

| Component | Status | Where |
|---|---|---|
| **Circuit breaker** | ✅ real (46 LOC) | `app/reliability/circuit_breaker.py` |
| **Idempotency** | ✅ real (Redis-backed, 27 LOC) | `app/reliability/idempotency.py` |
| **Rate limiter** | ✅ real (Redis fixed-window, 27 LOC) | `app/reliability/rate_limiter.py` |
| **libSQL edge read-replica** | ✅ real (HTTP wire protocol) | `app/db/edge_client.py` |
| **Read-replica fallback** | ✅ wired into CustomerService | `app/services/customer_service.py` |
| **Rate limiting on writes** | ✅ wired into POST/PATCH routes | `app/api/routes/customers.py` |
| **Idempotency on deactivate** | ✅ wired via Idempotency-Key header | `app/api/routes/customers.py` |

### Reliability primitives — wired into the request path

- **Rate limiter**: `POST /customers` and `PATCH /customers/{id}` are rate-limited
  per user (20/min default) via Redis fixed-window counters.
- **Idempotency**: `POST /customers/{id}/deactivate` accepts an `Idempotency-Key`
  header; repeated requests with the same key return 409 instead of double-processing.
- **Circuit breaker**: edge-replica reads are wrapped in a shared breaker
  (3 failures → open → 30s recovery). When open, reads fall back to Postgres
  without a failed round-trip.

### Edge read-replica — optional, with graceful fallback

When `EDGE_DB_URL` is set, `CustomerService` reads try the libSQL/Turso edge
replica first. On any failure (network, circuit-open, query error), reads fall
back to the Postgres primary — the replica is a latency optimization, never a
dependency that can break reads. When `EDGE_DB_URL` is unset, the app behaves
exactly as before (Postgres-only).

The edge client uses the libSQL **HTTP wire protocol** (`libsql-client`), which
is WASM-compatible — the same protocol the `licensing-workflow-system` edge
client uses.

## Quick start

```bash
# Install
pip install -e .  # or: poetry install

# Configure (Postgres + Redis required; edge replica optional)
export DATABASE_URL="postgresql://user:pass@host/db"
export REDIS_URL="redis://localhost:6379"
export JWT_SECRET="..."
# Optional edge read-replica:
# export EDGE_DB_URL="libsql://your-db.turso.io"
# export EDGE_DB_TOKEN="..."

# Run
uvicorn app.main:app --reload
```

## Tests

```bash
pytest tests/unit/ -v
```

The edge-client tests use an in-process fake of the libSQL client — no network
or Turso instance required. They verify row mapping, circuit-breaker opening,
and the critical read-replica fallback to the primary.

## Tech stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy 2.0
- **Primary DB**: PostgreSQL (source of truth for all writes)
- **Edge read-replica**: libSQL/Turso (optional, HTTP wire protocol)
- **Reliability**: Redis (rate limiting, idempotency), in-process circuit breaker
- **Observability**: Prometheus client, structured logging (structlog)
