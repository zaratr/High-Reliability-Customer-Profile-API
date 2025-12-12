import pytest

from app.reliability.circuit_breaker import CircuitBreaker, CircuitOpenError


def test_circuit_opens_after_failures():
    breaker = CircuitBreaker(failure_threshold=2, recovery_time=5)

    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
    with pytest.raises(RuntimeError):
        breaker.call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))

    assert breaker.state.value == 'open'
    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: None)
