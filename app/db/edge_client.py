"""libSQL edge read-replica client.

A low-latency read path that mirrors CustomerService's read methods against a
libSQL/Turso edge replica (HTTP wire protocol). Reads hit the edge replica
first; on failure the CircuitBreaker opens and callers fall through to the
primary Postgres session. Writes always go to the primary.

This is the real implementation behind the project's "distributed edge SQLite"
claim — it replaces the old 12-line src/edge_db_client.py stub, which was
orphaned (nothing imported it) and only used stdlib sqlite3 in-memory.

Design notes
------------
- Uses libsql_client.create_client_sync (synchronous) because the app's data
  layer is synchronous SQLAlchemy. The async Client exists for future use.
- The client is optional: when EDGE_DB_URL is unset, get_edge_db() returns None
  and CustomerService reads go straight to Postgres (no behavior change).
- The CircuitBreaker is shared across calls so a persistently-down replica
  stops costing a failed round-trip on every read.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.reliability.circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)

# Module-level breaker so all edge reads share one failure window. Tuned for
# fast trip: edge replicas are nice-to-have, not critical — three failures in
# a row should open the circuit and let reads fall back to the primary.
_edge_breaker = CircuitBreaker(failure_threshold=3, recovery_time=30)


@dataclass
class EdgeCustomer:
    """Read-shape returned by the edge client. The edge replica mirrors the
    primary schema, so all columns needed for CustomerRead are present."""

    id: int
    name: str
    email: str
    phone: str
    status: str
    is_active: bool = True


class EdgeDbClient:
    """Read-only access to the libSQL edge replica.

    Constructed lazily (no connection until the first execute()). Callers
    should catch CircuitOpenError / Exception and fall back to the primary.
    """

    def __init__(self, url: str, auth_token: Optional[str] = None) -> None:
        # Imported here so the module imports cleanly even when libsql_client
        # is absent (e.g. a stripped CI image). The error surfaces at first use.
        from libsql_client import create_client_sync

        self._client = create_client_sync(url, auth_token=auth_token)

    def get_customer(self, customer_id: int) -> Optional[EdgeCustomer]:
        """Return the customer from the edge replica, or None if not found.

        Raises CircuitOpenError if the breaker is open, or any exception from
        the underlying HTTP call on failure. Callers must handle both.
        """
        def _read() -> Optional[EdgeCustomer]:
            rs = self._client.execute(
                "SELECT id, name, email, phone, status FROM customers WHERE id = ?",
                [customer_id],
            )
            if not rs.rows:
                return None
            row = rs.rows[0]
            status = str(row[4]) if len(row) > 4 else "active"
            return EdgeCustomer(
                id=int(row[0]),
                name=str(row[1]),
                email=str(row[2]),
                phone=str(row[3]),
                status=status,
                is_active=(status == "active"),
            )

        return _edge_breaker.call(_read)

    def list_customers(
        self, skip: int = 0, limit: int = 50
    ) -> list[EdgeCustomer]:
        """Return a page of customers from the edge replica."""

        def _read() -> list[EdgeCustomer]:
            rs = self._client.execute(
                "SELECT id, name, email, phone, status FROM customers "
                "ORDER BY id LIMIT ? OFFSET ?",
                [limit, skip],
            )
            out = []
            for r in rs.rows:
                status = str(r[4]) if len(r) > 4 else "active"
                out.append(EdgeCustomer(
                    id=int(r[0]),
                    name=str(r[1]),
                    email=str(r[2]),
                    phone=str(r[3]),
                    status=status,
                    is_active=(status == "active"),
                ))
            return out

        return _edge_breaker.call(_read)

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            logger.warning("edge client close failed", exc_info=True)
