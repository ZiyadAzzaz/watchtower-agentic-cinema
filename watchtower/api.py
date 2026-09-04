from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from functools import lru_cache
from pathlib import Path
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from watchtower.config import Settings, get_settings
from watchtower.mcp_client import OfficialClickHouseMcpClient
from watchtower.models import (
    AnomalyInjectionRequest,
    Incident,
    IncidentDecisionRequest,
    IncidentStatus,
)
from watchtower.ratelimit import SlidingWindowLimiter
from watchtower.repository import ClickHouseRepository
from watchtower.runtime import WatchtowerRuntime

STATIC_DIR = Path(__file__).parent / "static"
LOGGER = logging.getLogger(__name__)


def _asset_fingerprint() -> str:
    """Short digest of the front-end assets.

    A browser that cached an old bundle can keep serving it even after the
    response headers change, which leaves a returning visitor running last
    week's JavaScript. Appending a content digest gives each build its own URL,
    which no cache can confuse with the previous one.
    """
    digest = hashlib.sha256()
    for name in sorted(("app.js", "styles.css")):
        path = STATIC_DIR / name
        if path.exists():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


@lru_cache(maxsize=1)
def _index_html() -> str:
    version = _asset_fingerprint()
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for name in ("app.js", "styles.css"):
        html = html.replace(f"/assets/{name}", f"/assets/{name}?v={version}")
    return html


def _token_matches(configured: str, presented: str | None) -> bool:
    """Constant-time compare that tolerates any bytes a client can send.

    hmac.compare_digest raises TypeError on a str containing non-ASCII, so the
    comparison is done on UTF-8 bytes. Otherwise a caller could turn a rejected
    credential into a 500 just by sending a non-ASCII header.
    """
    if not configured or not presented:
        return False
    return hmac.compare_digest(configured.encode("utf-8"), presented.encode("utf-8"))


INITIALIZATION_ATTEMPTS = 6


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
        app.state.initialization_error = None
        app.state.initialization_task = None
        active_settings = app.state.runtime.settings
        app.state.demo_limiter = (
            SlidingWindowLimiter(
                active_settings.watchtower_demo_rate_limit,
                active_settings.watchtower_demo_rate_window_seconds,
            )
            if active_settings.watchtower_demo_token
            else None
        )
        # A published key is discoverable by anyone, so the burst limit is
        # backed by a hard ceiling on a day's model spend.
        app.state.demo_daily_limiter = (
            SlidingWindowLimiter(active_settings.watchtower_demo_daily_limit, 86400)
            if active_settings.watchtower_demo_token
            else None
        )
        if app.state.runtime.settings.is_production:
            # Cloud Run must begin listening before a sleeping remote datastore
            # finishes waking. Readiness and operational endpoints remain closed
            # until initialization completes successfully.
            async def initialize_runtime() -> None:
                # A scaled-to-zero ClickHouse Cloud service can take minutes to
                # wake, so the first connection attempts are retried instead of
                # failing the deployment.
                delay = 5.0
                for attempt in range(1, INITIALIZATION_ATTEMPTS + 1):
                    try:
                        await app.state.runtime.initialize()
                        app.state.initialization_error = None
                        return
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        app.state.initialization_error = exc
                        LOGGER.exception(
                            "WatchTower runtime initialization failed (attempt %s/%s)",
                            attempt,
                            INITIALIZATION_ATTEMPTS,
                        )
                        if attempt == INITIALIZATION_ATTEMPTS:
                            return
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, 30.0)

            app.state.initialization_task = asyncio.create_task(initialize_runtime())
        else:
            await app.state.runtime.initialize()
        try:
            yield
        finally:
            task = app.state.initialization_task
            if task is not None and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
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
        # The dashboard is redeployed often. Without revalidation a returning
        # visitor can run last week's JavaScript against this week's API, so
        # the shell and its assets must be checked against their ETag every
        # time. Responses stay cheap because unchanged files return 304.
        if request.url.path == "/" or request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    def get_runtime(request: Request) -> WatchtowerRuntime:
        task = request.app.state.initialization_task
        if task is not None:
            if not task.done():
                raise HTTPException(status_code=503, detail="Runtime is initializing")
            if request.app.state.initialization_error is not None:
                raise HTTPException(status_code=503, detail="Runtime initialization failed")
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
        if _token_matches(configured, x_watchtower_token):
            return

        # The demo key is public so judges can run the loop themselves. It
        # authorises exactly the same actions, but only at a bounded rate.
        demo = (
            settings.watchtower_demo_token.get_secret_value()
            if settings.watchtower_demo_token
            else ""
        )
        if _token_matches(demo, x_watchtower_token):
            return "demo"

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin token required")

    def require_metered_admin(
        request: Request,
        credential: str = Depends(require_admin),
    ) -> None:
        """Guard the two actions that invoke Gemini.

        Recording a human decision is never metered: approving or dismissing is
        the point of the product, costs nothing, and a judge must always be able
        to finish the loop they started.
        """
        if credential != "demo":
            return
        daily = request.app.state.demo_daily_limiter
        if daily is not None and not daily.try_acquire():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "The shared demo key has reached its daily ceiling on new "
                    "investigations. This cap exists so a public key can never run up an "
                    "unbounded model bill. Run WatchTower locally with docker compose for "
                    "unlimited use, or use the deployment's own operator key."
                ),
                headers={"Retry-After": str(daily.retry_after_seconds())},
            )
        limiter = request.app.state.demo_limiter
        if limiter is not None and not limiter.try_acquire():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "The shared demo key limits how often a new investigation may be "
                    "started, so a public credential cannot run up model cost. Approving "
                    "and dismissing are never limited. Try again shortly, or run "
                    "WatchTower locally with docker compose for unlimited use."
                ),
                headers={"Retry-After": str(limiter.retry_after_seconds())},
            )

    @app.get("/", include_in_schema=False)
    async def index() -> HTMLResponse:
        return HTMLResponse(_index_html())

    # Cloud Run's serverless frontend answers the exact path "/healthz" itself,
    # so the same handler is also published under a non-reserved path.
    @app.get("/healthz", include_in_schema=False)
    @app.get("/health", include_in_schema=False)
    @app.get("/api/healthz", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "watchtower"}

    @app.get("/readyz", include_in_schema=False)
    @app.get("/ready", include_in_schema=False)
    @app.get("/api/readyz", include_in_schema=False)
    async def readiness(request: Request) -> dict[str, str]:
        active_runtime = get_runtime(request)
        return {"status": active_runtime.status().status}

    @app.get("/api/activity")
    async def activity(active_runtime: WatchtowerRuntime = Depends(get_runtime)) -> dict:
        """What the agent pipeline is doing right now. Read-only and public."""
        return active_runtime.activity

    @app.get("/api/dashboard")
    async def dashboard(active_runtime: WatchtowerRuntime = Depends(get_runtime)) -> dict:
        try:
            return await active_runtime.dashboard()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Telemetry backend is unavailable") from exc

    @app.post("/api/admin/inject", dependencies=[Depends(require_metered_admin)])
    async def inject(
        payload: AnomalyInjectionRequest,
        active_runtime: WatchtowerRuntime = Depends(get_runtime),
    ) -> dict[str, str | int | float]:
        try:
            await active_runtime.inject(payload)
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

    @app.post("/api/admin/tick", dependencies=[Depends(require_metered_admin)])
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
