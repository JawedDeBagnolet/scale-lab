import hmac

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings


async def auth_middleware(request: Request, call_next):
    # Health check et preflight CORS : pas d'auth
    if request.url.path == "/health" or request.method == "OPTIONS":
        return await call_next(request)

    # Le gateway envoie le token dans X-Scale-Token.
    # Une HTTPException levee dans un middleware n'est pas interceptee par les
    # exception handlers FastAPI (-> 500) : on retourne la reponse directement.
    token = request.headers.get("X-Scale-Token", "")
    if not hmac.compare_digest(token.encode(), settings.api_secret.encode()):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})

    return await call_next(request)
