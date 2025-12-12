import json
from typing import Optional

import redis
from sqlalchemy.orm import Session

from app.models.auth import AuditLog
from app.models.customer import Customer, RiskSignal
from app.reliability.idempotency import IdempotencyService
from app.schemas.risk import RiskSignalCreate


class RiskService:
    def __init__(self, db: Session, redis_client: redis.Redis, actor: str):
        self.db = db
        self.redis = redis_client
        self.actor = actor
        self.idempotency = IdempotencyService(redis_client)

    def ingest(self, customer: Customer, payload: RiskSignalCreate, idempotency_key: str) -> RiskSignal:
        existing_response = self.idempotency.check_and_set(idempotency_key)
        if existing_response:
            signal_id = json.loads(existing_response).get("id")
            if signal_id:
                existing = self.db.get(RiskSignal, signal_id)
                if existing:
                    return existing
        signal = RiskSignal(
            customer_id=customer.id,
            signal_type=payload.signal_type,
            payload=json.dumps(payload.payload),
            source_system=payload.source_system,
            request_id=idempotency_key,
        )
        self.db.add(signal)
        self.db.flush()
        self._audit("create", "risk_signal", str(signal.id), payload.payload)
        self.db.commit()
        self.db.refresh(signal)
        self.idempotency.store_response(idempotency_key, json.dumps({"id": signal.id}))
        return signal

    def _audit(self, action: str, entity: str, entity_id: str, payload: dict) -> None:
        record = AuditLog(actor=self.actor, action=action, entity=entity, entity_id=entity_id, payload=json.dumps(payload))
        self.db.add(record)
