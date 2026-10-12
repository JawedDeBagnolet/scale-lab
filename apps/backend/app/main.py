from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import comptes, health, personas, referentiels
from app.auth import auth_middleware
from app.db import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


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
app.include_router(personas.router, prefix="/api/personas", tags=["personas"])
app.include_router(comptes.router, prefix="/api/comptes", tags=["comptes"])
app.include_router(referentiels.router, prefix="/api", tags=["referentiels"])
