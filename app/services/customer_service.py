import json
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import AuditLog
from app.models.customer import Address, Customer
from app.schemas.customer import AddressCreate, CustomerCreate, CustomerUpdate


class CustomerService:
    def __init__(self, db: Session, actor: str):
        self.db = db
        self.actor = actor

    def _audit(self, action: str, entity: str, entity_id: str, payload: dict) -> None:
        record = AuditLog(actor=self.actor, action=action, entity=entity, entity_id=entity_id, payload=json.dumps(payload))
        self.db.add(record)

    def create_customer(self, data: CustomerCreate) -> Customer:
        customer = Customer(name=data.name, email=data.email, phone=data.phone, status="active")
        self.db.add(customer)
        self.db.flush()
        for addr in data.addresses:
            address = Address(customer_id=customer.id, **addr.dict())
            self.db.add(address)
        self._audit("create", "customer", str(customer.id), customer.__dict__)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def get_customer(self, customer_id: int) -> Optional[Customer]:
        return self.db.get(Customer, customer_id)

    def list_customers(self, skip: int = 0, limit: int = 50) -> List[Customer]:
        stmt = select(Customer).offset(skip).limit(limit)
        return list(self.db.scalars(stmt))

    def update_customer(self, customer: Customer, data: CustomerUpdate) -> Customer:
        for field, value in data.dict(exclude_unset=True).items():
            setattr(customer, field, value)
        self._audit("update", "customer", str(customer.id), data.dict(exclude_unset=True))
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def deactivate_customer(self, customer: Customer) -> Customer:
        customer.status = "inactive"
        self._audit("deactivate", "customer", str(customer.id), {"status": "inactive"})
        self.db.commit()
        self.db.refresh(customer)
        return customer
