import json
import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.edge_client import EdgeDbClient
from app.models.auth import AuditLog
from app.models.customer import Address, Customer
from app.reliability.circuit_breaker import CircuitOpenError
from app.schemas.customer import AddressCreate, CustomerCreate, CustomerUpdate

logger = logging.getLogger(__name__)


class CustomerService:
    def __init__(self, db: Session, actor: str, edge_db: Optional[EdgeDbClient] = None):
        self.db = db
        self.actor = actor
        self.edge_db = edge_db

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
        # Read-replica path: try the edge replica first for low-latency reads.
        # Falls back to the Postgres primary on any failure or circuit-open.
        if self.edge_db is not None:
            try:
                edge = self.edge_db.get_customer(customer_id)
                if edge is not None:
                    # Construct a detached Customer from the edge row. Addresses
                    # and timestamps are not in the edge read — callers needing
                    # those (the detail endpoint) should use the primary path.
                    # For list-style reads this is the fast path.
                    return Customer(
                        id=edge.id, name=edge.name, email=edge.email,
                        phone=edge.phone, status=edge.status,
                    )
                # Edge said "not found" — trust it only if the circuit is
                # healthy; otherwise fall through to primary for correctness.
            except CircuitOpenError:
                logger.debug("edge circuit open — falling back to primary for customer %s", customer_id)
            except Exception:
                logger.warning("edge read failed — falling back to primary", exc_info=True)
        return self.db.get(Customer, customer_id)

    def list_customers(self, skip: int = 0, limit: int = 50) -> List[Customer]:
        if self.edge_db is not None:
            try:
                edge_rows = self.edge_db.list_customers(skip, limit)
                return [
                    Customer(
                        id=e.id, name=e.name, email=e.email,
                        phone=e.phone, status=e.status,
                    )
                    for e in edge_rows
                ]
            except CircuitOpenError:
                logger.debug("edge circuit open — falling back to primary for list")
            except Exception:
                logger.warning("edge list failed — falling back to primary", exc_info=True)
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
