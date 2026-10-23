"""Tenant-scoped HTTP API. No model execution or arbitrary network fetching."""

import sqlite3
from collections import deque

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models import Dataset, RunRequest, Source
from . import __version__
from .security import Settings
from .store import Conflict, IntegrityError, NotFound, Store


class BodyLimitMiddleware:
    """Bound bodies even when Content-Length is absent or incorrect."""

    def __init__(self, app, max_bytes):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        length = dict(scope.get("headers", [])).get(b"content-length")
        if length is not None:
            try:
                declared = int(length)
                if declared < 0:
                    raise ValueError
            except ValueError:
                return await JSONResponse({"detail": "Invalid content length"}, status_code=400)(scope, receive, send)
            if declared > self.max_bytes:
                return await JSONResponse({"detail": "Request body too large"}, status_code=413)(scope, receive, send)
        buffered = deque()
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            total += len(message.get("body", b""))
            if total > self.max_bytes:
                return await JSONResponse({"detail": "Request body too large"}, status_code=413)(scope, receive, send)
            buffered.append(message)
            if not message.get("more_body", False):
                break

        async def replay():
            return buffered.popleft() if buffered else await receive()

        await self.app(scope, replay, send)


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    store = Store(settings.db_path, settings.audit_key)
    app = FastAPI(title="EDS Assurance", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_body_bytes)
    bearer = HTTPBearer(auto_error=False)

    def require(scope):
        def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
            principal = settings.authenticate(credentials.credentials) if credentials else None
            if principal is None:
                raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
            if scope not in principal.scopes:
                raise HTTPException(status_code=403, detail="Insufficient scope")
            return principal
        return authorize

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(NotFound)
    async def not_found(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse({"detail": "Stored evidence integrity check failed"}, status_code=409)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        errors = [{"location": list(error["loc"]), "message": error["msg"], "type": error["type"]} for error in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.exception_handler(ValueError)
    async def invalid_contract(request, exc):
        return JSONResponse({"detail": "Input does not satisfy the evaluation contract"}, status_code=422)

    @app.exception_handler(sqlite3.OperationalError)
    async def unavailable(request, exc):
        return JSONResponse({"detail": "Storage temporarily unavailable"}, status_code=503)

    @app.get("/healthz")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/readyz")
    def readiness():
        try:
            store.check_ready()
        except (sqlite3.DatabaseError, IntegrityError):
            raise HTTPException(status_code=503, detail="Storage is not ready") from None
        return {"status": "ready"}

    @app.post("/v1/sources", status_code=201)
    def create_source(source: Source, principal=Depends(require("write"))):
        return store.put_source(principal.tenant, source)

    @app.post("/v1/datasets", status_code=201)
    def create_dataset(dataset: Dataset, principal=Depends(require("write"))):
        return store.put_dataset(principal.tenant, dataset)

    @app.get("/v1/datasets/{dataset_id}")
    def get_dataset(dataset_id: str, principal=Depends(require("read"))):
        return store.get_dataset(principal.tenant, dataset_id)

    @app.post("/v1/runs", status_code=201)
    def create_run(body: RunRequest, principal=Depends(require("evaluate"))):
        return store.run(principal.tenant, body)

    @app.get("/v1/runs/{run_id}")
    def get_run(run_id: str, principal=Depends(require("read"))):
        return store.get_run(principal.tenant, run_id)

    @app.get("/v1/audit/checkpoint")
    def checkpoint(principal=Depends(require("read"))):
        return {"verified": True, "checkpoint": store.verify_audit(principal.tenant)}

    return app
