# Scale Lab

Monorepo : front React (Cloudflare Pages), gateway Hono (Cloudflare Worker), backend FastAPI + PostgreSQL (VPS).
Contexte et conventions : [CLAUDE.md](CLAUDE.md). Plan Phase 1 : [docs/PHASE1_BLUEPRINT.md](docs/PHASE1_BLUEPRINT.md).

```
apps/
  web/        React 18 + TypeScript + Vite + Tailwind   -> scalelab.win
  gateway/    Cloudflare Worker (Hono) : auth + proxy   -> api.scalelab.win
  backend/    FastAPI + SQLAlchemy async + Alembic      -> vps.scalelab.win (tunnel)
docs/
```

## Backend (VPS)

Apres PostgreSQL (etape 1) et cloudflared (etape 2, modele dans `apps/backend/deploy/cloudflared-config.example.yml`) :

```bash
cd /root && git clone git@github.com:<USERNAME>/scale-lab.git
cd scale-lab/apps/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # renseigner DATABASE_URL et API_SECRET (.env n'est pas versionne)
alembic upgrade head            # cree marches, niches, personas, comptes
psql -U scalelab -d scalelab -h localhost -f seed.sql   # 23 niches + 6 marches

cp deploy/scalelab-api.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now scalelab-api
curl https://vps.scalelab.win/health
```

Nouvelle migration : `alembic revision --autogenerate -m "..."` puis `alembic upgrade head`
(l'URL de la base est lue depuis `.env`, pas depuis `alembic.ini`).

## Gateway

```bash
cd apps/gateway
npm install
cp .dev.vars.example .dev.vars        # API_SECRET pour le dev local
npm run dev                           # http://localhost:8787
npm run deploy
npx wrangler secret put API_SECRET    # une seule fois, apres le premier deploy
```

`API_SECRET` est un secret Worker (pas dans `wrangler.toml`) ; il est conserve d'un deploy a l'autre.
Sans lui, le gateway repond 500 sur `/api/*`.

## Front

```bash
cd apps/web
npm install
cp .env.example .env.local   # VITE_API_BASE + VITE_API_TOKEN
npm run dev                  # http://localhost:5173
```

Cloudflare Pages : root directory `apps/web`, build command `npm run build`, output `dist`,
variables `VITE_API_BASE` et `VITE_API_TOKEN`.

## API (Phase 1)

| Methode | Route | |
|---|---|---|
| GET | `/health` | sans auth |
| GET POST | `/api/personas` | |
| GET PATCH DELETE | `/api/personas/{id}` | |
| GET POST | `/api/comptes` | filtres `?persona_id=` `?plateforme=` |
| GET PATCH DELETE | `/api/comptes/{id}` | |
| GET | `/api/niches`, `/api/marches` | referentiels (lecture seule) |

Erreurs : `{"error": "message"}`.

## Deploiement

- `main` : production. Push dans `apps/gateway/**` -> `wrangler deploy` ; push dans `apps/backend/**` -> SSH VPS, `git pull`, `pip install`, `alembic upgrade head`, restart.
- Secrets GitHub Actions : `CF_API_TOKEN`, `CF_ACCOUNT_ID`, `VPS_SSH_KEY`.
- Front : deploy automatique par Cloudflare Pages.
