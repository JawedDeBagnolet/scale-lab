from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (
    comptes, comportements, crm, dashboard, health, iphones, liens, logs,
    personas, posting, proxies, referentiels, scenarios, settings,
    statistiques, targets, veille,
)
from app.auth import auth_middleware
from app.db import engine as db_engine
from app.services.engine import engine as execution_engine
from app.services.usb import usb_monitor
from app.ws import ws_logs


@asynccontextmanager
async def lifespan(app: FastAPI):
    await execution_engine.start()
    await usb_monitor.start()
    yield
    await usb_monitor.stop()
    await execution_engine.stop()
    await db_engine.dispose()


app = FastAPI(title="Scale Lab API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://scalelab.win", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(auth_middleware)


# Les erreurs retournent toujours {"error": "message"}
@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"] if p != "body")
        parts.append(f"{loc}: {err['msg']}" if loc else err["msg"])
    return JSONResponse(status_code=422, content={"error": "; ".join(parts) or "validation error"})


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"error": "integrity constraint violated"})


app.include_router(health.router, tags=["health"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(personas.router, prefix="/api/personas", tags=["personas"])
app.include_router(comptes.router, prefix="/api/comptes", tags=["comptes"])
app.include_router(referentiels.router, prefix="/api", tags=["referentiels"])
app.include_router(targets.router, prefix="/api/targets", tags=["targets"])
app.include_router(comportements.router, prefix="/api/presets", tags=["comportements"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(proxies.router, prefix="/api/proxies", tags=["proxies"])
app.include_router(iphones.router, prefix="/api/iphones", tags=["iphones"])
app.include_router(statistiques.router, prefix="/api/stats", tags=["statistiques"])
app.include_router(liens.router, prefix="/api/liens", tags=["liens"])
app.include_router(crm.router, prefix="/api/crm", tags=["crm"])
app.include_router(veille.router, prefix="/api/veille", tags=["veille"])
app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
app.include_router(posting.router, prefix="/api/posting", tags=["posting"])

# WebSocket (pas d'auth — le gateway proxy le WS séparément)
app.websocket("/ws/logs")(ws_logs)
