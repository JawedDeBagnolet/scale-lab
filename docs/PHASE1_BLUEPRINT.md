# Phase 1 — Blueprint d'execution

Objectif : valider le pipeline complet (front → gateway → tunnel → backend → PostgreSQL)
sur un module simple (Personas CRUD + Comptes CRUD).

## Pre-requis

- VPS `77.42.124.107` avec acces root
- Compte Cloudflare avec le domaine `scalelab.win` ajoute
- Repo GitHub prive `scale-lab` cree et connecte a Cloudflare Pages
- Cle SSH du VPS ajoutee sur GitHub
- Node.js 20+ et Python 3.11+ sur la machine de dev

---

## Etape 0 : Git + monorepo

### Initialisation du repo

```bash
mkdir scale-lab && cd scale-lab
git init

# Structure monorepo
mkdir -p apps/web apps/gateway apps/backend docs
```

### .gitignore

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
*.egg

# Node
node_modules/
dist/
.wrangler/

# Env
.env
.env.local
.env.production

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Alembic
alembic/versions/__pycache__/
```

### Premier commit + push

```bash
cp /chemin/vers/CLAUDE.md .
cp /chemin/vers/PHASE1_BLUEPRINT.md docs/
git add .
git commit -m "chore: init monorepo scale-lab"
git branch -M main
git remote add origin git@github.com:<USERNAME>/scale-lab.git
git push -u origin main
```

### GitHub Actions — deploy gateway (`.github/workflows/deploy-gateway.yml`)

```yaml
name: Deploy Gateway
on:
  push:
    branches: [main]
    paths: ['apps/gateway/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: cd apps/gateway && npm ci && npm run deploy
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CF_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CF_ACCOUNT_ID }}
```

### GitHub Actions — deploy backend VPS (`.github/workflows/deploy-backend.yml`)

```yaml
name: Deploy Backend
on:
  push:
    branches: [main]
    paths: ['apps/backend/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1
        with:
          host: 77.42.124.107
          username: root
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /root/scale-lab
            git pull origin main
            cd apps/backend
            source .venv/bin/activate
            pip install -r requirements.txt --break-system-packages
            sudo systemctl restart scalelab-api
```

### Secrets GitHub a configurer

Dans le repo GitHub > Settings > Secrets and variables > Actions :

| Secret           | Valeur                                                              |
|------------------|---------------------------------------------------------------------|
| CF_API_TOKEN     | <CF_API_TOKEN>             |
| CF_ACCOUNT_ID    | <CF_ACCOUNT_ID>                                   |
| VPS_SSH_KEY      | Contenu de `~/.ssh/id_ed25519` (cle PRIVEE) de la machine de dev   |

Note : le front-end est deploye automatiquement par Cloudflare Pages (connecte au repo),
pas besoin de GitHub Action pour ca.

### Workflow de branches

- `main` = production (deploy auto sur push)
- `dev` = developpement (merge dans main quand pret)
- Feature branches pour les gros morceaux (`feat/personas`, `feat/comptes`, etc.)

---

## Etape 1 : PostgreSQL sur le VPS

```bash
ssh root@77.42.124.107

# Installer PostgreSQL
sudo apt update && sudo apt install -y postgresql postgresql-contrib

# Creer la base et l'utilisateur
sudo -u postgres psql <<SQL
CREATE USER scalelab WITH PASSWORD '<POSTGRES_PASSWORD>';
CREATE DATABASE scalelab OWNER scalelab;
GRANT ALL PRIVILEGES ON DATABASE scalelab TO scalelab;
\c scalelab
GRANT ALL ON SCHEMA public TO scalelab;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
SQL

# Verifier
psql -U scalelab -d scalelab -h localhost -c "SELECT 1;"
```

---

## Etape 2 : Cloudflare Tunnel sur le VPS

```bash
# Installer cloudflared
curl -L --output cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Authentifier (ouvre un lien a cliquer dans le navigateur)
cloudflared tunnel login

# Creer le tunnel
cloudflared tunnel create scale-lab
# -> Note le TUNNEL_ID affiche

# Router le DNS
cloudflared tunnel route dns scale-lab vps.scalelab.win

# Configuration
cat > ~/.cloudflared/config.yml <<EOF
tunnel: <TUNNEL_ID>
credentials-file: /root/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: vps.scalelab.win
    service: http://localhost:8000
  - service: http_status:404
EOF

# Installer comme service systemd
sudo cloudflared service install
sudo systemctl enable --now cloudflared

# Verifier
curl https://vps.scalelab.win/   # doit retourner 404 (FastAPI pas encore lance)
```

---

## Etape 3 : Backend FastAPI

### Structure

```
apps/backend/
  app/
    __init__.py
    main.py           # FastAPI app, lifespan, middlewares, routers
    config.py          # Settings (pydantic-settings, .env)
    db.py              # Engine async, session factory, Base
    auth.py            # Middleware auth (X-Scale-Token)
    api/
      __init__.py
      health.py        # GET /health
      personas.py      # CRUD /api/personas
      comptes.py       # CRUD /api/comptes
    models/
      __init__.py
      persona.py       # SQLAlchemy model Persona
      compte.py        # SQLAlchemy model Compte
      marche.py        # SQLAlchemy model Marche
      niche.py         # SQLAlchemy model Niche
    schemas/
      __init__.py
      persona.py       # Pydantic schemas PersonaCreate/Update/Out
      compte.py        # Pydantic schemas CompteCreate/Update/Out
    services/
      __init__.py
  alembic/
    env.py
    versions/
  alembic.ini
  requirements.txt
  .env
```

### requirements.txt

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.35
asyncpg==0.29.0
alembic==1.13.0
pydantic==2.9.0
pydantic-settings==2.5.0
python-jose[cryptography]==3.3.0
httpx==0.27.0
```

### .env

```env
DATABASE_URL=postgresql+asyncpg://scalelab:<POSTGRES_PASSWORD>@localhost/scalelab
API_SECRET=<API_SECRET>
```

### app/config.py

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    api_secret: str

    class Config:
        env_file = ".env"

settings = Settings()
```

### app/db.py

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_size=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

### app/auth.py

```python
from fastapi import Request, HTTPException

async def auth_middleware(request: Request, call_next):
    # Health check : pas d'auth
    if request.url.path == "/health":
        return await call_next(request)

    # Le gateway envoie le token dans X-Scale-Token
    from app.config import settings
    token = request.headers.get("X-Scale-Token", "")
    if token != settings.api_secret:
        raise HTTPException(status_code=401, detail="unauthorized")

    return await call_next(request)
```

### app/main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db import engine
from app.auth import auth_middleware
from app.api import health, personas, comptes

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

app.include_router(health.router, tags=["health"])
app.include_router(personas.router, prefix="/api/personas", tags=["personas"])
app.include_router(comptes.router, prefix="/api/comptes", tags=["comptes"])
```

### app/models/persona.py

```python
from sqlalchemy import String, Integer, Text, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
from app.db import Base
import uuid
from datetime import datetime, UTC

class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prs_id: Mapped[str | None] = mapped_column(String(100))              # OnlyChat ID
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(7))                  # hex #6d5ef0
    market: Mapped[str | None] = mapped_column(String(10))                # code marche (US, FR...)
    city: Mapped[str | None] = mapped_column(String(100))
    age: Mapped[int | None] = mapped_column(Integer)
    platforms: Mapped[list[str] | None] = mapped_column(ARRAY(String))    # ["ig", "th", "x"]
    niches: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))      # IDs niches
    bios: Mapped[dict | None] = mapped_column(JSONB, default=list)        # [{platform, text}]
    prompt: Mapped[str | None] = mapped_column(Text)                      # AI prompt
    funnel: Mapped[str | None] = mapped_column(Text)
    telegram: Mapped[dict | None] = mapped_column(JSONB, default=dict)    # {bot, username, chat_id, langue, groupe, topic}
    photo_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relations
    comptes: Mapped[list["Compte"]] = relationship(back_populates="persona", lazy="selectin")
```

### app/models/compte.py

```python
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMPTZ
from app.db import Base
import uuid
from datetime import datetime, UTC

class Compte(Base):
    __tablename__ = "comptes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    handle: Mapped[str] = mapped_column(String(100))
    persona_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"))
    plateforme: Mapped[str] = mapped_column(String(10))                    # ig, th, x
    workflow: Mapped[str] = mapped_column(String(20), default="Onboarding")  # Onboarding, Warmup, Actif
    status: Mapped[str] = mapped_column(String(20), default="ok")          # ok, session, error, suspendu
    device_id: Mapped[str | None] = mapped_column(String(100))
    proxy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    env: Mapped[dict | None] = mapped_column(JSONB, default=dict)          # config environnement (GoLogin etc.)
    sessions: Mapped[int] = mapped_column(Integer, default=0)
    follows: Mapped[int] = mapped_column(Integer, default=0)
    creds_encrypted: Mapped[dict | None] = mapped_column(JSONB)            # {password, two_fa, token} chiffre
    created_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMPTZ, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relations
    persona: Mapped["Persona | None"] = relationship(back_populates="comptes", lazy="selectin")
```

### app/models/marche.py

```python
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Marche(Base):
    __tablename__ = "marches"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    langue: Mapped[str | None] = mapped_column(String(5))
    fuseau: Mapped[str | None] = mapped_column(String(50))
```

### app/models/niche.py

```python
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Niche(Base):
    __tablename__ = "niches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(100), unique=True)
```

### app/schemas/persona.py

```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class PersonaBase(BaseModel):
    first_name: str
    last_name: str | None = None
    color: str | None = None
    market: str | None = None
    city: str | None = None
    age: int | None = None
    platforms: list[str] | None = None
    niches: list[int] | None = None
    bios: list[dict] | None = None
    prompt: str | None = None
    funnel: str | None = None
    telegram: dict | None = None
    photo_url: str | None = None
    prs_id: str | None = None

class PersonaCreate(PersonaBase):
    pass

class PersonaUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    color: str | None = None
    market: str | None = None
    city: str | None = None
    age: int | None = None
    platforms: list[str] | None = None
    niches: list[int] | None = None
    bios: list[dict] | None = None
    prompt: str | None = None
    funnel: str | None = None
    telegram: dict | None = None
    photo_url: str | None = None
    prs_id: str | None = None

class CompteOut(BaseModel):
    id: UUID
    handle: str
    plateforme: str
    workflow: str
    status: str
    model_config = {"from_attributes": True}

class PersonaOut(PersonaBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    comptes: list[CompteOut] = []
    model_config = {"from_attributes": True}
```

### app/schemas/compte.py

```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class CompteBase(BaseModel):
    handle: str
    persona_id: UUID | None = None
    plateforme: str       # ig, th, x
    workflow: str | None = "Onboarding"
    status: str | None = "ok"
    device_id: str | None = None
    proxy_id: UUID | None = None
    env: dict | None = None
    sessions: int | None = 0
    follows: int | None = 0

class CompteCreate(CompteBase):
    pass

class CompteUpdate(BaseModel):
    handle: str | None = None
    persona_id: UUID | None = None
    plateforme: str | None = None
    workflow: str | None = None
    status: str | None = None
    device_id: str | None = None
    proxy_id: UUID | None = None
    env: dict | None = None
    sessions: int | None = None
    follows: int | None = None

class CompteOut(CompteBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
```

### app/api/health.py

```python
from fastapi import APIRouter
from datetime import datetime, UTC

router = APIRouter()

@router.get("/health")
async def health():
    return {"ok": True, "ts": datetime.now(UTC).isoformat()}
```

### app/api/personas.py

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models.persona import Persona
from app.schemas.persona import PersonaCreate, PersonaUpdate, PersonaOut
from uuid import UUID

router = APIRouter()

@router.get("/", response_model=list[PersonaOut])
async def list_personas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Persona).order_by(Persona.first_name))
    return result.scalars().all()

@router.get("/{persona_id}", response_model=PersonaOut)
async def get_persona(persona_id: UUID, db: AsyncSession = Depends(get_db)):
    p = await db.get(Persona, persona_id)
    if not p:
        raise HTTPException(404, "persona not found")
    return p

@router.post("/", response_model=PersonaOut, status_code=201)
async def create_persona(data: PersonaCreate, db: AsyncSession = Depends(get_db)):
    p = Persona(**data.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p

@router.patch("/{persona_id}", response_model=PersonaOut)
async def update_persona(persona_id: UUID, data: PersonaUpdate, db: AsyncSession = Depends(get_db)):
    p = await db.get(Persona, persona_id)
    if not p:
        raise HTTPException(404, "persona not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return p

@router.delete("/{persona_id}", status_code=204)
async def delete_persona(persona_id: UUID, db: AsyncSession = Depends(get_db)):
    p = await db.get(Persona, persona_id)
    if not p:
        raise HTTPException(404, "persona not found")
    await db.delete(p)
    await db.commit()
```

### app/api/comptes.py

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models.compte import Compte
from app.schemas.compte import CompteCreate, CompteUpdate, CompteOut
from uuid import UUID

router = APIRouter()

@router.get("/", response_model=list[CompteOut])
async def list_comptes(
    persona_id: UUID | None = Query(None),
    plateforme: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    q = select(Compte).order_by(Compte.handle)
    if persona_id:
        q = q.where(Compte.persona_id == persona_id)
    if plateforme:
        q = q.where(Compte.plateforme == plateforme)
    result = await db.execute(q)
    return result.scalars().all()

@router.get("/{compte_id}", response_model=CompteOut)
async def get_compte(compte_id: UUID, db: AsyncSession = Depends(get_db)):
    c = await db.get(Compte, compte_id)
    if not c:
        raise HTTPException(404, "compte not found")
    return c

@router.post("/", response_model=CompteOut, status_code=201)
async def create_compte(data: CompteCreate, db: AsyncSession = Depends(get_db)):
    c = Compte(**data.model_dump())
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c

@router.patch("/{compte_id}", response_model=CompteOut)
async def update_compte(compte_id: UUID, data: CompteUpdate, db: AsyncSession = Depends(get_db)):
    c = await db.get(Compte, compte_id)
    if not c:
        raise HTTPException(404, "compte not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    await db.commit()
    await db.refresh(c)
    return c

@router.delete("/{compte_id}", status_code=204)
async def delete_compte(compte_id: UUID, db: AsyncSession = Depends(get_db)):
    c = await db.get(Compte, compte_id)
    if not c:
        raise HTTPException(404, "compte not found")
    await db.delete(c)
    await db.commit()
```

### Alembic setup

```bash
cd apps/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

alembic init alembic
```

Editer `alembic.ini` :
```ini
sqlalchemy.url = postgresql+asyncpg://scalelab:<POSTGRES_PASSWORD>@localhost/scalelab
```

Editer `alembic/env.py` : importer Base et tous les modeles pour l'autogenerate.
```python
from app.db import Base
from app.models.persona import Persona
from app.models.compte import Compte
from app.models.marche import Marche
from app.models.niche import Niche

target_metadata = Base.metadata
```

Utiliser le runner async dans `env.py` (`run_async_migrations`).

```bash
# Generer la migration initiale
alembic revision --autogenerate -m "001_initial_personas_comptes"
alembic upgrade head
```

### Seed data

```bash
psql -U scalelab -d scalelab -h localhost <<SQL
INSERT INTO niches (label) VALUES
  ('Fitness'),('Fashion'),('Cosplay'),('Gamer'),('Lifestyle'),
  ('Model'),('Travel'),('Artistic'),('Alt/Goth'),('Luxury'),
  ('ASMR'),('Dance'),('Comedy'),('Couple'),('Feet'),
  ('Curvy'),('Petite'),('Mature'),('Latina'),('Asian'),
  ('Ebony'),('Redhead'),('Blonde');

INSERT INTO marches (code, label, langue, fuseau) VALUES
  ('US', 'United States', 'en', 'America/New_York'),
  ('UK', 'United Kingdom', 'en', 'Europe/London'),
  ('FR', 'France', 'fr', 'Europe/Paris'),
  ('DE', 'Germany', 'de', 'Europe/Berlin'),
  ('AU', 'Australia', 'en', 'Australia/Sydney'),
  ('CA', 'Canada', 'en', 'America/Toronto');
SQL
```

### Lancer le backend

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Tester via le tunnel
curl -H "X-Scale-Token: <API_SECRET>" \
  https://vps.scalelab.win/health
```

### Systemd service (production)

```ini
# /etc/systemd/system/scalelab-api.service
[Unit]
Description=Scale Lab API
After=postgresql.service cloudflared.service

[Service]
User=root
WorkingDirectory=/root/scale-lab/apps/backend
ExecStart=/root/scale-lab/apps/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
EnvironmentFile=/root/scale-lab/apps/backend/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now scalelab-api
```

---

## Etape 4 : Gateway Worker (Hono)

### Structure

```
apps/gateway/
  src/
    index.ts
  package.json
  tsconfig.json
  wrangler.toml
```

### package.json

```json
{
  "name": "scale-lab-gateway",
  "private": true,
  "scripts": {
    "dev": "wrangler dev",
    "deploy": "wrangler deploy"
  },
  "dependencies": {
    "hono": "^4.6.0"
  },
  "devDependencies": {
    "@cloudflare/workers-types": "^4.20240925.0",
    "wrangler": "^3.80.0"
  }
}
```

### wrangler.toml

```toml
name = "scale-lab-gateway"
main = "src/index.ts"
compatibility_date = "2024-09-01"

[vars]
API_BASE = "https://vps.scalelab.win"
API_SECRET = "<API_SECRET>"

[[kv_namespaces]]
binding = "CACHE"
id = "15ea593d7838454dabd796d8e34669f4"

routes = [
  { pattern = "api.scalelab.win/*", zone_name = "scalelab.win" }
]
```

### src/index.ts

```typescript
import { Hono } from 'hono'
import { cors } from 'hono/cors'

type Env = {
  API_BASE: string
  API_SECRET: string
  CACHE: KVNamespace
}

const app = new Hono<{ Bindings: Env }>()

// CORS
app.use('*', cors({
  origin: ['https://scalelab.win', 'http://localhost:5173'],
  allowMethods: ['GET', 'POST', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'Authorization'],
}))

// Auth : verifie le token de l'app
app.use('/api/*', async (c, next) => {
  const token = c.req.header('Authorization')?.replace('Bearer ', '')
  if (token !== c.env.API_SECRET) {
    return c.json({ error: 'unauthorized' }, 401)
  }
  await next()
})

// Proxy /api/* vers le backend VPS via le tunnel
app.all('/api/*', async (c) => {
  const url = new URL(c.req.url)
  const target = `${c.env.API_BASE}${url.pathname}${url.search}`

  const headers: Record<string, string> = {
    'X-Scale-Token': c.env.API_SECRET,
  }
  const ct = c.req.header('Content-Type')
  if (ct) headers['Content-Type'] = ct

  const resp = await fetch(target, {
    method: c.req.method,
    headers,
    body: ['GET', 'HEAD'].includes(c.req.method) ? undefined : await c.req.arrayBuffer(),
  })

  // Forward la reponse telle quelle
  const respHeaders = new Headers(resp.headers)
  respHeaders.delete('content-encoding') // evite les problemes de double compression

  return new Response(resp.body, {
    status: resp.status,
    headers: respHeaders,
  })
})

// Health du gateway lui-meme
app.get('/health', (c) => c.json({ ok: true, layer: 'gateway', ts: Date.now() }))

export default app
```

### Deploiement

```bash
cd apps/gateway
npm install
npm run deploy
```

### DNS Cloudflare

Dans le dashboard Cloudflare > scalelab.win > DNS, ajouter :

| Type  | Nom  | Contenu                                                | Proxy    |
|-------|------|--------------------------------------------------------|----------|
| CNAME | api  | scale-lab-gateway.timothee-aubree3.workers.dev         | Proxied  |

Tester :
```bash
curl -H "Authorization: Bearer <API_SECRET>" \
  https://api.scalelab.win/api/personas
```

---

## Etape 5 : Front-end React

### Initialisation

```bash
npm create vite@latest web -- --template react-ts
cd web
npm install react-router-dom@6 zustand @tanstack/react-query
npm install -D tailwindcss @tailwindcss/vite
```

### Structure

```
apps/web/
  src/
    App.tsx
    main.tsx
    modules/
      dashboard/     DashboardPage.tsx
      comptes/       ComptesPage.tsx
      personas/      PersonasPage.tsx    <-- fonctionnel Phase 1
      posting/       PostingPage.tsx
      veille/        VeillePage.tsx
      statistiques/  StatistiquesPage.tsx
      crm/           CrmPage.tsx
      liens/         LiensPage.tsx
      logs/          LogsPage.tsx
      targets/       TargetsPage.tsx
      scenarios/     ScenariosPage.tsx
      comportements/ ComportementsPage.tsx
      proxies/       ProxiesPage.tsx
      parc-iphone/   ParcIphonePage.tsx
      parametres/    ParametresPage.tsx
    components/
      Layout.tsx     # Sidebar + header + Outlet
      Sidebar.tsx    # Navigation 15 modules
      Stub.tsx       # Page placeholder "Module X - A venir"
    hooks/
      useApi.ts      # TanStack Query wrapper
    lib/
      api.ts         # Client fetch avec auth header
    styles/
      tokens.ts      # Design tokens
      global.css     # Reset + Manrope import + variables CSS
    types/
      persona.ts
      compte.ts
  index.html
  vite.config.ts
  tsconfig.json
```

### src/styles/tokens.ts

```typescript
export const tokens = {
  colors: {
    bg:        '#0b0d16',
    bgCard:    '#12141f',
    bgGlass:   'rgba(18, 20, 31, 0.7)',
    accent1:   '#6d5ef0',
    accent2:   '#4b7bf5',
    gradient:  'linear-gradient(135deg, #6d5ef0, #4b7bf5)',
    text:      '#ffffff',
    textMuted: '#8b8fa3',
    textDim:   '#555872',
    success:   '#22c55e',
    warning:   '#f59e0b',
    error:     '#ef4444',
    border:    'rgba(255,255,255,0.06)',
  },
  font: {
    family: "'Manrope', sans-serif",
    sizes: { xs: '11px', sm: '13px', md: '14px', lg: '16px', xl: '20px', xxl: '28px' },
  },
  radius: { sm: '8px', md: '12px', lg: '16px', xl: '24px' },
} as const
```

### src/styles/global.css

```css
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&display=swap');

:root {
  --bg: #0b0d16;
  --bg-card: #12141f;
  --bg-glass: rgba(18, 20, 31, 0.7);
  --accent-1: #6d5ef0;
  --accent-2: #4b7bf5;
  --text: #ffffff;
  --text-muted: #8b8fa3;
  --text-dim: #555872;
  --success: #22c55e;
  --warning: #f59e0b;
  --error: #ef4444;
  --border: rgba(255,255,255,0.06);
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 24px;
  --blur: 26px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'Manrope', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-width: 1280px;
  -webkit-font-smoothing: antialiased;
}

a { color: inherit; text-decoration: none; }

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--text-dim); border-radius: 3px; }
```

### src/lib/api.ts

```typescript
const API_BASE = import.meta.env.VITE_API_BASE || 'https://api.scalelab.win'
const API_TOKEN = import.meta.env.VITE_API_TOKEN || ''

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_TOKEN}`,
      ...options.headers,
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw new Error(err.error || res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}
```

### src/App.tsx

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import PersonasPage from './modules/personas/PersonasPage'
import Stub from './components/Stub'

const qc = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Stub name="Dashboard" />} />
            <Route path="/comptes" element={<Stub name="Comptes" />} />
            <Route path="/personas" element={<PersonasPage />} />
            <Route path="/posting" element={<Stub name="Posting" />} />
            <Route path="/veille" element={<Stub name="Veille" />} />
            <Route path="/statistiques" element={<Stub name="Statistiques" />} />
            <Route path="/crm" element={<Stub name="CRM" />} />
            <Route path="/liens" element={<Stub name="Liens" />} />
            <Route path="/logs" element={<Stub name="Logs" />} />
            <Route path="/targets" element={<Stub name="Targets" />} />
            <Route path="/scenarios" element={<Stub name="Scenarios" />} />
            <Route path="/comportements" element={<Stub name="Comportements" />} />
            <Route path="/proxies" element={<Stub name="Proxies" />} />
            <Route path="/parc" element={<Stub name="Parc iPhone" />} />
            <Route path="/parametres" element={<Stub name="Parametres" />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
```

### Deploiement Cloudflare Pages

```bash
cd apps/web
npm run build
npx wrangler pages project create scale-lab
npx wrangler pages deploy dist/ --project-name scale-lab
```

Puis dans le dashboard Pages > scale-lab > Custom domains > ajouter `scalelab.win`.

Variables d'environnement dans Pages settings :
```
VITE_API_BASE = https://api.scalelab.win
VITE_API_TOKEN = <API_SECRET>
```

**ATTENTION** : le token dans le front est visible par les utilisateurs du navigateur.
Pour Phase 1 c'est acceptable (app interne, pas d'utilisateurs externes).
En Phase 2 on ajoutera un vrai systeme d'auth (login + JWT).

---

## Etape 6 : DNS recapitulatif

Dashboard Cloudflare > scalelab.win > DNS :

| Type  | Nom  | Contenu                                                | Proxy   |
|-------|------|--------------------------------------------------------|---------|
| CNAME | vps  | `<TUNNEL_ID>.cfargotunnel.com`                         | Proxied |
| CNAME | api  | `scale-lab-gateway.timothee-aubree3.workers.dev`       | Proxied |
| CNAME | @    | `scale-lab.pages.dev`                                  | Proxied |

Note : le record `vps` est cree automatiquement par `cloudflared tunnel route dns`.

---

## Checklist de validation

- [ ] PostgreSQL tourne, `psql -U scalelab -d scalelab -c "SELECT 1;"` OK
- [ ] Tunnel Cloudflare actif, `curl https://vps.scalelab.win/health` retourne `{"ok": true}`
- [ ] FastAPI tourne via systemd, `systemctl status scalelab-api` = active
- [ ] Niches et marches en base (23 niches, 6 marches)
- [ ] Gateway deploye, `curl https://api.scalelab.win/health` retourne `{"ok": true, "layer": "gateway"}`
- [ ] CRUD Personas via gateway : POST, GET, PATCH, DELETE fonctionnent
- [ ] CRUD Comptes via gateway avec filtre par persona_id
- [ ] Front React accessible sur `https://scalelab.win`
- [ ] Front affiche la liste des personas depuis l'API
- [ ] Front cree/modifie une persona via formulaire
- [ ] Sidebar avec les 15 modules (stubs pour les 13 non implementes)
- [ ] Design tokens appliques : fond #0b0d16, Manrope, gradient accent
- [ ] Tunnel stable (pas de deconnexion en 10 min)

---

## Prochaine etape (Phase 2)

Une fois Phase 1 validee :
- Comptes : page complete avec status, workflow, assignation persona
- Logs : WebSocket pour le journal live
- Dashboard : aggregations et widgets
- Design system React : composants partages (modales glass, tables, badges, etc.)
