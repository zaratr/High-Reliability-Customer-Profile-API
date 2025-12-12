import redis
from fastapi import HTTPException

from app.reliability.rate_limiter import RateLimiter


def test_rate_limit_exceeded(monkeypatch):
    r = redis.Redis(host='localhost', decode_responses=True)
    limiter = RateLimiter(r, default_limit=1)
    limiter.check('client')
    try:
        limiter.check('client')
        assert False, 'expected exception'
    except HTTPException as exc:
        assert exc.status_code == 429
