"""Tests for the libSQL edge read-replica client and its circuit-breaker fallback.

These tests run without a real Turso/libSQL instance: they stub the underlying
sync client so the HTTP layer is never hit. They verify:
  - the edge client correctly maps libSQL rows to EdgeCustomer
  - the circuit breaker opens after repeated failures
  - CustomerService falls back to the primary session when the edge fails

The fallback path is the whole point of the read-replica pattern: a down
replica must never break reads.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make `app/` importable when running pytest from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


# ── Fake libsql_client module so the import in edge_client succeeds ─────────
# We install this BEFORE importing edge_client so its `from libsql_client import
# create_client_sync` resolves to our fake. This avoids a network/HTTP dependency.

def _install_fake_libsql():
    fake = types.ModuleType("libsql_client")

    class FakeResultSet:
        def __init__(self, rows=None, columns=None):
            self.rows = rows or []
            self.columns = columns or []
            self.rows_affected = 0
            self.last_insert_rowid = None

    class FakeClientSync:
        def __init__(self):
            self.execute = MagicMock(return_value=FakeResultSet())
        def close(self):
            pass

    def create_client_sync(url, auth_token=None, tls=None):
        return FakeClientSync()

    fake.create_client_sync = create_client_sync
    fake.FakeClientSync = FakeClientSync
    fake.FakeResultSet = FakeResultSet
    sys.modules["libsql_client"] = fake

_install_fake_libsql()


def _make_row(values):
    """libsql rows support index access; emulate that."""
    class _Row:
        def __init__(self, vals): self._vals = vals
        def __getitem__(self, i): return self._vals[i]
        def __len__(self): return len(self._vals)
    return _Row(values)


# ── Tests ────────────────────────────────────────────────────────────────────

def test_edge_get_customer_maps_row_correctly():
    from app.db import edge_client
    # Reset the shared breaker so prior tests don't bleed state.
    edge_client._edge_breaker = edge_client.CircuitBreaker(failure_threshold=3, recovery_time=30)

    client = edge_client.EdgeDbClient("http://fake", auth_token="t")
    fake_rs = sys.modules["libsql_client"].FakeResultSet(
        rows=[_make_row([42, "Ada", "ada@example.com", "555-0100", "active"])]
    )
    client._client.execute = MagicMock(return_value=fake_rs)

    result = client.get_customer(42)
    assert result is not None
    assert result.id == 42
    assert result.name == "Ada"
    assert result.email == "ada@example.com"
    assert result.phone == "555-0100"
    assert result.status == "active"
    assert result.is_active is True


def test_edge_get_customer_returns_none_when_missing():
    from app.db import edge_client
    edge_client._edge_breaker = edge_client.CircuitBreaker(failure_threshold=3, recovery_time=30)

    client = edge_client.EdgeDbClient("http://fake")
    fake_rs = sys.modules["libsql_client"].FakeResultSet(rows=[])
    client._client.execute = MagicMock(return_value=fake_rs)

    assert client.get_customer(999) is None


def test_edge_list_customers_maps_multiple_rows():
    from app.db import edge_client
    edge_client._edge_breaker = edge_client.CircuitBreaker(failure_threshold=3, recovery_time=30)

    client = edge_client.EdgeDbClient("http://fake")
    fake_rs = sys.modules["libsql_client"].FakeResultSet(rows=[
        _make_row([1, "Ada", "ada@x.com", "555", "active"]),
        _make_row([2, "Bob", "bob@x.com", "556", "inactive"]),
    ])
    client._client.execute = MagicMock(return_value=fake_rs)

    rows = client.list_customers(skip=0, limit=10)
    assert len(rows) == 2
    assert rows[0].id == 1 and rows[0].is_active is True
    assert rows[1].id == 2 and rows[1].is_active is False
    assert rows[1].status == "inactive"


def test_circuit_opens_after_repeated_failures():
    """Three failures should open the breaker; the fourth call raises
    CircuitOpenError instead of hitting the replica again."""
    from app.db import edge_client
    from app.reliability.circuit_breaker import CircuitOpenError, CircuitState

    edge_client._edge_breaker = edge_client.CircuitBreaker(failure_threshold=3, recovery_time=30)

    client = edge_client.EdgeDbClient("http://fake")
    client._client.execute = MagicMock(side_effect=ConnectionError("replica down"))

    # First three calls fail (real exceptions propagate so the caller can fall back).
    for _ in range(3):
        try:
            client.get_customer(1)
        except ConnectionError:
            pass

    assert edge_client._edge_breaker.state == CircuitState.OPEN

    # Fourth call should short-circuit with CircuitOpenError, not ConnectionError.
    raised = False
    try:
        client.get_customer(1)
    except CircuitOpenError:
        raised = True
    assert raised, "expected CircuitOpenError after breaker opens"


def test_customer_service_falls_back_to_primary_on_edge_failure():
    """The key invariant: when the edge read raises, get_customer must still
    return from the primary session rather than propagating the error."""
    from app.db.edge_client import EdgeDbClient
    from app.db import edge_client
    from app.reliability.circuit_breaker import CircuitBreaker
    from app.services.customer_service import CustomerService

    edge_client._edge_breaker = CircuitBreaker(failure_threshold=3, recovery_time=30)

    # A primary session that returns a customer on .get()
    fake_primary = MagicMock()
    fake_primary.get.return_value = MagicMock(id=7, name="Primary User")

    # An edge client whose execute always fails.
    edge = EdgeDbClient("http://fake")
    edge._client.execute = MagicMock(side_effect=ConnectionError("replica down"))

    service = CustomerService(db=fake_primary, actor="tester", edge_db=edge)
    result = service.get_customer(7)
    assert result is not None
    assert result.id == 7
    # The primary was consulted as the fallback.
    fake_primary.get.assert_called_once()
