from fastapi import APIRouter, Depends, HTTPException, Security, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services.auth import get_current_user
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db_session),
    current_user=Security(get_current_user, scopes=["customers:write"]),
):
    service = CustomerService(db, actor=current_user.username)
    customer = service.create_customer(payload)
    return customer


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db_session),
    current_user=Security(get_current_user, scopes=["customers:read"]),
):
    service = CustomerService(db, actor=current_user.username)
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
):
    service = CustomerService(db, actor=current_user.username)
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
):
    service = CustomerService(db, actor=current_user.username)
    return service.list_customers(skip, limit)


@router.post("/{customer_id}/deactivate", response_model=CustomerRead)
def deactivate_customer(
    customer_id: int,
    db: Session = Depends(get_db_session),
    current_user=Security(get_current_user, scopes=["deactivate"]),
):
    service = CustomerService(db, actor=current_user.username)
    customer = service.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return service.deactivate_customer(customer)
