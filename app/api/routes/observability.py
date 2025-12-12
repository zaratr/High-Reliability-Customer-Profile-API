from fastapi import APIRouter
from prometheus_client import CollectorRegistry, Counter, generate_latest
from starlette.responses import PlainTextResponse

router = APIRouter(tags=["observability"])
requests_counter = Counter("api_requests_total", "Total API requests", registry=CollectorRegistry())


@router.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/metrics")
async def metrics():
    content = generate_latest(requests_counter)._bytes.decode()
    return PlainTextResponse(content, media_type="text/plain; version=0.0.4")
