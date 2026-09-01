from __future__ import annotations

import hmac
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from watchtower.config import Settings, get_settings
from watchtower.mcp_client import OfficialClickHouseMcpClient
from watchtower.models import (
    AnomalyInjectionRequest,
    Incident,
    IncidentDecisionRequest,
    IncidentStatus,
)
from watchtower.repository import ClickHouseRepository
from watchtower.runtime import WatchtowerRuntime

STATIC_DIR = Path(__file__).parent / "static"


def create_app(runtime: WatchtowerRuntime | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if runtime is None:
            settings = get_settings()
            repository = ClickHouseRepository(settings)
            app.state.runtime = WatchtowerRuntime(
                settings,
                repository,
                OfficialClickHouseMcpClient(settings),
            )
        else:
            app.state.runtime = runtime
        await app.state.runtime.initialize()
        try:
            yield
        finally:
            await app.state.runtime.close()

    app = FastAPI(
        title="WatchTower",
        summary="Human-governed streaming incident intelligence",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    def get_runtime(request: Request) -> WatchtowerRuntime:
        return request.app.state.runtime

    def require_admin(
        request: Request,
        x_watchtower_token: str | None = Header(default=None),
        active_runtime: WatchtowerRuntime = Depends(get_runtime),
    ) -> None:
        settings: Settings = active_runtime.settings
        configured = (
            settings.watchtower_admin_token.get_secret_value()
            if settings.watchtower_admin_token
            else ""
        )
        local_hosts = {"127.0.0.1", "::1", "localhost", "testclient"}
        client_host = request.client.host if request.client else ""
        if not settings.is_production and not configured and client_host in local_hosts:
            return
        if (
            not configured
            or not x_watchtower_token
            or not hmac.compare_digest(
                configured,
                x_watchtower_token,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token required"
            )

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/healthz", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "watchtower"}

    @app.get("/readyz", include_in_schema=False)
    async def readiness(active_runtime: WatchtowerRuntime = Depends(get_runtime)) -> dict[str, str]:
        return {"status": active_runtime.status().status}

    @app.get("/api/dashboard")
    async def dashboard(active_runtime: WatchtowerRuntime = Depends(get_runtime)) -> dict:
        try:
            return await active_runtime.dashboard()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Telemetry backend is unavailable") from exc

    @app.post("/api/admin/inject", dependencies=[Depends(require_admin)])
    async def inject(
        payload: AnomalyInjectionRequest,
        active_runtime: WatchtowerRuntime = Depends(get_runtime),
    ) -> dict[str, str | int | float]:
        try:
            active_runtime.inject(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "status": "armed",
            "kind": payload.kind.value,
            "title_id": payload.title_id,
            "region": payload.region,
            "duration_cycles": payload.duration_cycles,
            "magnitude": payload.magnitude,
        }

    @app.post("/api/admin/tick", dependencies=[Depends(require_admin)])
    async def tick(active_runtime: WatchtowerRuntime = Depends(get_runtime)) -> dict:
        incidents = await active_runtime.tick_if_due(force=True)
        return {"status": "complete", "incidents_created": len(incidents)}

    @app.post(
        "/api/incidents/{incident_id}/approve",
        response_model=Incident,
        dependencies=[Depends(require_admin)],
    )
    async def approve(
        incident_id: UUID,
        payload: IncidentDecisionRequest,
        active_runtime: WatchtowerRuntime = Depends(get_runtime),
    ) -> Incident:
        return await _decide(
            active_runtime,
            incident_id,
            IncidentStatus.APPROVED,
            payload.note,
        )

    @app.post(
        "/api/incidents/{incident_id}/dismiss",
        response_model=Incident,
        dependencies=[Depends(require_admin)],
    )
    async def dismiss(
        incident_id: UUID,
        payload: IncidentDecisionRequest,
        active_runtime: WatchtowerRuntime = Depends(get_runtime),
    ) -> Incident:
        return await _decide(
            active_runtime,
            incident_id,
            IncidentStatus.DISMISSED,
            payload.note,
        )

    return app


async def _decide(
    runtime: WatchtowerRuntime,
    incident_id: UUID,
    decision: IncidentStatus,
    note: str,
) -> Incident:
    try:
        incident = await runtime.decide(incident_id, decision, note)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


app = create_app()
