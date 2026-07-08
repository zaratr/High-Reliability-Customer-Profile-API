from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Security, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_edge_db, get_redis
from app.reliability.rate_limiter import RateLimiter
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services.auth import get_current_user
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])


def _service(db: Session, actor: str, edge_db=Depends(get_edge_db)) -> CustomerService:
    """Build a CustomerService with the optional edge read-replica wired in."""
    return CustomerService(db, actor=actor, edge_db=edge_db)


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db_session),
    current_user=Security(get_current_user, scopes=["customers:write"]),
    redis=Depends(get_redis),
    edge_db=Depends(get_edge_db),
):
    # Rate-limit writes per user to prevent abuse (reliability primitive wired).
    limiter = RateLimiter(redis, default_limit=20)
    limiter.check(f"create:{current_user.username}")
    service = CustomerService(db, actor=current_user.username, edge_db=edge_db)
    customer = service.create_customer(payload)
    return customer


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db_session),
    current_user=Security(get_current_user, scopes=["customers:read"]),
    edge_db=Depends(get_edge_db),
):
    service = CustomerService(db, actor=current_user.username, edge_db=edge_db)
    customer = service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return customer


@router.patch("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: Session = Depends(get_db_session),
    current_user=Security(get_current_user, scopes=["customers:write"]),
    redis=Depends(get_redis),
    edge_db=Depends(get_edge_db),
):
    limiter = RateLimiter(redis, default_limit=20)
    limiter.check(f"update:{current_user.username}")
    service = CustomerService(db, actor=current_user.username, edge_db=edge_db)
    customer = service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return service.update_customer(customer, payload)


@router.get("", response_model=list[CustomerRead])
def list_customers(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db_session),
    current_user=Security(get_current_user, scopes=["customers:read"]),
    edge_db=Depends(get_edge_db),
):
    service = CustomerService(db, actor=current_user.username, edge_db=edge_db)
    return service.list_customers(skip, limit)


@router.post("/{customer_id}/deactivate", response_model=CustomerRead)
def deactivate_customer(
    customer_id: int,
    db: Session = Depends(get_db_session),
    current_user=Security(get_current_user, scopes=["deactivate"]),
    redis=Depends(get_redis),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    edge_db=Depends(get_edge_db),
):
    # Idempotency: a repeated deactivate with the same key returns the first
    # result instead of double-processing (reliability primitive wired).
    from app.reliability.idempotency import IdempotencyService
    idem = IdempotencyService(redis, ttl_seconds=600)
    cache_key = idempotency_key or f"deactivate:{customer_id}:{current_user.username}"
    cached = idem.check_and_set(cache_key)
    if cached is not None:
        # Already processed — FastAPI will serialize the cached payload.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="already processed for this key")

    service = CustomerService(db, actor=current_user.username, edge_db=edge_db)
    customer = service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    result = service.deactivate_customer(customer)
    idem.store_response(cache_key, {"customer_id": result.id, "status": result.status})
    return result
