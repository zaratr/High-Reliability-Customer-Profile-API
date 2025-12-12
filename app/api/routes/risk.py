from fastapi import APIRouter, Depends, Header, HTTPException, Security, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_redis
from app.models.customer import Customer
from app.reliability.rate_limiter import RateLimiter
from app.schemas.risk import RiskSignalCreate, RiskSignalRead
from app.services.auth import api_key_auth, get_current_user
from app.services.risk_service import RiskService

router = APIRouter(prefix="/customers/{customer_id}/risk-signals", tags=["risk"])


@router.post("", response_model=RiskSignalRead, status_code=status.HTTP_201_CREATED)
def ingest_risk_signal(
    customer_id: int,
    payload: RiskSignalCreate,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db_session),
    redis=Depends(get_redis),
    current_user=Security(get_current_user, scopes=["signals:write"], auto_error=False),
    api_client=Depends(api_key_auth),
):
    limiter = RateLimiter(redis)
    client_key = api_client.client_id if api_client else current_user.username
    limiter.check(client_key, limit=None)

    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer not found")

    key = idempotency_key or payload.request_id
    if not key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency key required")

    service = RiskService(db, redis, actor=client_key)
    signal = service.ingest(customer, payload, key)
    # enqueue job stub
    return RiskSignalRead(
        id=signal.id,
        customer_id=customer.id,
        signal_type=signal.signal_type,
        payload=payload.payload,
        source_system=signal.source_system,
        request_id=signal.request_id,
        received_at=signal.received_at,
    )
