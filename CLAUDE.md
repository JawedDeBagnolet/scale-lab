# Scale Lab

Application mono-tenant de gestion de comptes sociaux (Instagram, Threads, X) pour l'industrie OFM (OnlyFans Management).

## Architecture

```
scalelab.win              Cloudflare Pages    React + TypeScript (front-end)
api.scalelab.win          Cloudflare Worker   Hono gateway (auth, CORS, cache, proxy)
vps.scalelab.win          Cloudflare Tunnel   FastAPI backend (interne, seul le Worker l'appelle)
VPS 77.42.124.107         PostgreSQL + FastAPI + automation iPhone
```

### Stack

- **Front-end** : React 18 + TypeScript + Vite, deploye sur Cloudflare Pages
- **Gateway** : Cloudflare Worker avec Hono (auth + proxy + cache KV edge)
- **Backend** : Python 3.11+ / FastAPI / SQLAlchemy async / asyncpg
- **Base de donnees** : PostgreSQL 15+ sur le VPS
- **Migrations** : Alembic
- **Real-time** : WebSocket natif FastAPI (logs, telemetrie, alertes)
- **Stockage medias** : Cloudflare R2
- **Cache edge** : Cloudflare KV (donnees lentes : niches, marches, config)

### Versionning

- **Repo** : GitHub prive `scale-lab` (monorepo)
- **Branches** : `main` (production, deploy auto) / `dev` (developpement) / feature branches
- **Deploy front** : automatique via Cloudflare Pages (connecte au repo GitHub)
- **Deploy gateway** : GitHub Actions → `wrangler deploy` sur push dans `apps/gateway/`
- **Deploy backend** : GitHub Actions → SSH VPS → `git pull` + restart service sur push dans `apps/backend/`
- **Le VPS clone le repo** dans `/root/scale-lab/` via SSH (cle ed25519 configuree)

### Monorepo

```
scale-lab/
  apps/
    web/          React + TypeScript (Cloudflare Pages)
    gateway/      Cloudflare Worker Hono
    backend/      FastAPI (VPS)
  packages/
    shared/       Types/constantes partages (si besoin)
  docs/
```

## Conventions

### Backend (Python)

- Async partout : `async def`, `await`, pas de code bloquant
- SQLAlchemy 2.0 style (mapped_column, pas l'ancien Column)
- Pydantic v2 pour les schemas request/response
- Routes dans `app/api/<domaine>.py`
- Modeles dans `app/models/<entite>.py`
- Schemas dans `app/schemas/<entite>.py`
- Services (logique metier) dans `app/services/<domaine>.py`
- Pas de logique metier dans les routes — les routes appellent les services
- UUIDs pour tous les IDs d'entites
- Timestamps avec timezone (`TIMESTAMPTZ`, `datetime.now(UTC)`)
- Les erreurs retournent un JSON `{"error": "message"}` avec le bon code HTTP

### Gateway (TypeScript)

- Hono framework, pas de Express/raw Workers
- Middleware auth sur `/api/*` : verifie `Authorization: Bearer <token>`
- Proxy transparent : forward le body, les headers, le status
- Cache KV pour les donnees lentes (TTL 5 min)
- WebSocket proxy pour `/ws/*`

### Front-end (React + TypeScript)

- 15 modules = 15 routes = 15 dossiers dans `src/modules/`
- Design tokens centralises dans `src/styles/tokens.ts`
- Composants partages dans `src/components/`
- API client dans `src/lib/api.ts`
- WebSocket client dans `src/lib/ws.ts`
- Hooks custom dans `src/hooks/`
- Types TypeScript dans `src/types/`
- TanStack Query pour le data fetching
- Zustand pour le state global
- **Pixel-perfect** avec les maquettes DC (les 15 fichiers `Module *.dc.html`)

### Design tokens (extraits des maquettes)

```
Background:       #0b0d16
Card background:  #12141f
Glass overlay:    rgba(18, 20, 31, 0.7)
Accent gradient:  linear-gradient(135deg, #6d5ef0, #4b7bf5)
Accent 1:         #6d5ef0
Accent 2:         #4b7bf5
Text:             #ffffff
Text muted:       #8b8fa3
Text dim:         #555872
Success:          #22c55e
Warning:          #f59e0b
Error:            #ef4444
Border:           rgba(255,255,255,0.06)
Font:             Manrope
Icons:            Phosphor (regular weight)
Glass blur:       backdrop-filter: blur(26px)
Border radius:    8 / 12 / 16 / 24px
Min width:        1280px (desktop only)
```

### Securite

- Les cles API restent cote serveur, le front n'affiche que les 4 derniers caracteres
- Les identifiants de comptes (mots de passe, 2FA, tokens) sont chiffres en base
- Auth : token unique `Authorization: Bearer <API_SECRET>` sur toutes les requetes
- Le VPS n'expose aucun port — tout passe par le tunnel Cloudflare
- Mono-tenant : un seul workspace par instance (pas d'isolation tenant_id)

## Credentials

Aucun secret dans le repo. Voir `apps/backend/.env.example`, `apps/web/.env.example`,
`apps/gateway/.dev.vars.example` et les secrets GitHub Actions / Cloudflare.

## Entites principales (33+)

Personas, Comptes, Marches, Niches, Collections, Medias, Templates,
Campagnes, Publications, Scenarios, Runs, Plages horaires, Presets,
Targets, Veille (sources/inspirations/favoris/snipes/albums), Regles d'alerte,
Objectifs, Disposition Dashboard, iPhones, Telemetrie, Proxies, Allocations,
Stats quotidiennes (180 jours), Creatrices (OC), Comptes OC, Licences,
Transactions, Fans, Scripts, Medias OC, Credits, Quotas, Liens GMS,
Landings, Domaines GMS, Analytics GMS, Liens trackes, Evenements journal.

Voir `DONNEES-BACKEND.md` pour les champs complets de chaque entite.

## Regles metier transverses

- Un compte en checkpoint, suspendu ou session expiree ne recoit aucun ordre
- Les runs, publications, vagues et stories passent en "Suspendu" et reprennent au retour du compte
- Un iPhone hors ligne met ses comptes en attente
- Une reduction a 0 sur un step payant OC envoie le media gratuitement : bloquer a l'enregistrement

## Modules (15)

1. Dashboard — KPIs, alertes, widgets configurables (mode grille 4 colonnes)
2. Comptes — gestion des comptes IG/Threads/X, Kill mode
3. Personas — profils des modeles, 1 persona = 1 compte OC + 0-5 comptes Telegram
4. Posting — publications, campagnes, templates, collections, Story Builder
5. Veille — surveillance de contenu (IG/Threads/X), albums, snipes
6. Statistiques — KPIs, analytics, graphiques, series temporelles
7. CRM — donnees OnlyChat, scripts, fans, transactions
8. Liens — liens trackes, landings, analytics, GMS
9. Logs — journal live (WebSocket), incidents, alertes Telegram
10. Targets — comptes de reference
11. Scenarios — templates d'automatisation et executions
12. Comportements — presets de comportement (probabilites, pauses, durees)
13. Proxies — gestion des proxies mobiles
14. Parc iPhone — flotte d'iPhones, telemetrie live
15. Parametres — config, integrations (OC, GMS, Telegram)

## Migration depuis le worker monolithique

Le worker actuel (`worker.js`, 10 795 lignes, 426 fonctions, 946 ops KV) est migre
module par module vers le backend FastAPI + PostgreSQL. Le worker Hono remplace
le routing/auth/CORS. Le KV reste uniquement comme cache edge.

Voir `PHASE1_BLUEPRINT.md` pour le plan de migration detaille.
