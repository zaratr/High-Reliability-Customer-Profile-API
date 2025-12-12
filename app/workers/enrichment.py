import json
import time

from celery import Celery, Task
from celery.utils.log import get_task_logger

from app.core.config import get_settings
from app.reliability.circuit_breaker import CircuitBreaker, CircuitOpenError

settings = get_settings()
celery_app = Celery(
    "enrichment",
    broker=settings.celery_broker_url or settings.redis_url,
    backend=settings.celery_result_backend or settings.redis_url,
)
logger = get_task_logger(__name__)
breaker = CircuitBreaker()


class EnrichmentTask(Task):
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 60
    retry_kwargs = {"max_retries": 5}

    def run(self, signal_id: int, payload: str) -> str:  # type: ignore[override]
        try:
            return breaker.call(lambda: self._process(signal_id, payload))
        except CircuitOpenError:
            logger.warning("circuit open; deferring", extra={"signal_id": signal_id})
            raise self.retry(countdown=30)

    def _process(self, signal_id: int, payload: str) -> str:
        # Simulated external call
        time.sleep(0.1)
        logger.info("enriched", extra={"signal_id": signal_id})
        return json.dumps({"status": "completed"})


celery_app.tasks.register(EnrichmentTask())
