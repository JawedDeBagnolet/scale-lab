# Scale Lab — Workflow & Context pour Claude

Ce fichier documente tout ce qu'une session Claude doit savoir pour travailler
efficacement sur le projet Scale Lab : infrastructure, deploiement, workflow Git,
acces au Mac, tests E2E, et lecons apprises.

---

## 1. Architecture reseau

```
Navigateur (Safari)
    |
    v
scalelab.win  ── Cloudflare Pages ── apps/web/public/ (fichiers DC statiques)
    |
    | fetch('/api/...') ou POST('/auth/login')
    v
api.scalelab.win  ── Cloudflare Worker (Hono) ── apps/gateway/src/index.ts
    |
    | proxy transparent (+ cache KV pour /niches, /marches, /settings, /presets)
    v
vps.scalelab.win  ── Cloudflare Tunnel (ID: 5f619bc4-cbf4-442a-a11a-8acb7a8eaf49)
    |
    v
VPS 77.42.124.107  ── FastAPI + PostgreSQL + automation
    |
    | SSH reverse tunnel (iPhone → VPS)
    v
iPhone (jailbreake, ScaleTweak + MCP agent)
```

### Domaines et services

| Domaine | Service | Stack |
|---|---|---|
| `scalelab.win` | Frontend | Cloudflare Pages, fichiers DC statiques |
| `api.scalelab.win` | Gateway | Cloudflare Worker, Hono (TypeScript) |
| `vps.scalelab.win` | Backend | Cloudflare Tunnel → FastAPI (Python 3.12) |
| VPS `77.42.124.107` | BDD + automation | PostgreSQL 15, systemd services |

### Ports du tunnel iPhone (reverse SSH sur le VPS)

| Port VPS local | Port iPhone | Service |
|---|---|---|
| 8190 | 8090 | MCP server (JSON-RPC, UI automation) |
| 8191 | 8091 | MTOUCH |
| 8180 | 8080 | CRANE |
| 2223 | 22 | SSH |

---

## 2. Frontend — CRITIQUE

### Les fichiers DC SONT la production

**Le frontend de production est constitue des 15 fichiers `Module *.dc.html`** dans
`apps/web/public/`. Ce ne sont PAS des maquettes — c'est le code reel servi aux utilisateurs.

```
apps/web/public/
  index.html                          # Redirect vers Module Dashboard
  _headers                            # Cache-Control pour CF Pages
  api-data.js                         # Login gate + helpers API + SCALE_DATA
  support.js                          # DC runtime (React, GENERE — NE PAS MODIFIER)
  Module Dashboard v1.dc.html
  Module Comptes v1.dc.html
  Module Personas v1.dc.html
  Module Posting v1.dc.html
  Module Veille v1.dc.html
  Module Statistiques v1.dc.html
  Module CRM v1.dc.html
  Module Liens v1.dc.html
  Module Logs v1.dc.html
  Module Targets v1.dc.html
  Module Scenarios v1.dc.html
  Module Comportements v1.dc.html
  Module Proxies v1.dc.html
  Module Parc iPhone v1.dc.html
  Module Parametres v1.dc.html
```

**Le React app dans `apps/web/src/` n'est PAS deploye.** Ne jamais remplacer les DC
par le React app. Ne jamais modifier `index.html` pour pointer vers `dist/`.

### Comment fonctionne le systeme DC

1. `support.js` (DC runtime) charge dans le `<head>` — c'est un runtime React compile
2. Le body contient des elements `<x-dc>` que support.js interprete
3. Les scripts dans `<helmet>` a l'interieur de `<x-dc>` sont charges **dynamiquement
   par support.js**, pas par le parser HTML du navigateur
4. Consequence : ces scripts utilisent le **cache HTTP du navigateur** meme apres un
   hard refresh (Cmd+Shift+R)

### Le systeme de login

`api-data.js` gere le login :

1. Au chargement : verifie `localStorage.getItem('sl_api_token')`
2. Si pas de token → affiche l'overlay de login, bloque le chargement des donnees
3. L'utilisateur entre le mot de passe → `POST /auth/login` sur le gateway
4. Le gateway compare le mot de passe (timing-safe) et retourne `{token: API_SECRET}`
5. Le token est stocke dans `localStorage('sl_api_token')` → page reload
6. Au reload : le token existe → `api-data.js` charge les donnees normalement

Le token persiste dans `localStorage`, donc l'utilisateur ne doit se connecter
qu'une seule fois par navigateur (sauf navigation privee ou clear du storage).

### `_headers` — Cache control CF Pages

```
/api-data.js
  Cache-Control: no-cache, must-revalidate

/support.js
  Cache-Control: no-cache, must-revalidate
```

Ce fichier est **essentiel** car `api-data.js` et `support.js` sont charges dynamiquement.
Sans ces headers, les mises a jour ne se propagent pas aux navigateurs.

---

## 3. Gateway (Cloudflare Worker)

Fichier unique : `apps/gateway/src/index.ts` (Hono)

### Routes du gateway

| Route | Description |
|---|---|
| `POST /auth/login` | Echange mot de passe → token API (hors middleware auth) |
| `GET/POST/PATCH/DELETE /api/*` | Proxy transparent vers le backend VPS |
| `GET /media/*` | Sert les medias depuis R2 (auth par Bearer OU referer) |
| `POST /api/upload/media` | Upload de medias vers R2 (multipart, max 100MB) |
| `GET /ws/*` | Proxy WebSocket vers le backend (auth via query param ?token=) |
| `GET /health` | Health check du gateway |

### Cache KV

Prefixes caches (TTL 5 min) : `/api/niches`, `/api/marches`, `/api/settings`, `/api/presets`

Les mutations (POST/PATCH/PUT/DELETE) invalident automatiquement le cache.

### Variables d'environnement (Cloudflare Worker secrets)

- `API_BASE` — URL du backend via tunnel (ex: `https://vps.scalelab.win`)
- `API_SECRET` — token Bearer pour l'auth
- `LOGIN_PASSWORD` — mot de passe pour le login frontend
- `CACHE` — KV namespace binding
- `MEDIA` — R2 bucket binding

---

## 4. Backend (FastAPI sur VPS)

### Structure

```
apps/backend/
  app/
    main.py                  # FastAPI app, montage des routers
    auth.py                  # Middleware auth X-Scale-Token
    db.py                    # AsyncSession factory (asyncpg)
    crypto.py                # Fernet encrypt/decrypt pour credentials
    api/                     # Routes (routers FastAPI)
      comptes.py             # CRUD comptes IG/Threads/X
      personas.py            # CRUD personas
      iphones.py             # CRUD iPhones + USB/tunnel provisioning + containers
      posting.py             # Collections, medias, templates, campagnes, publications
      scenarios.py           # Scenarios, runs (launch/pause/resume/skip/abort)
      veille.py              # Sources, inspirations, favoris, snipes, albums
      crm.py                 # Fans, transactions, scripts
      liens.py               # Liens trackes, domaines, clicks
      proxies.py             # Gestion des proxies
      comportements.py       # Presets de comportement
      targets.py             # Comptes de reference
      statistiques.py        # Stats quotidiennes, overview, bulk import
      logs.py                # Evenements, incidents, regles d'alerte
      dashboard.py           # Stats dashboard
      settings.py            # Config workspace, integrations, notifications
      integrations.py        # OC/GMS test/key/status/sync, creators, fans
      telegram.py            # Bot start, linking, groupes, briefs, alertes
      health.py              # Health check
      referentiels.py        # Niches, marches
    models/                  # SQLAlchemy 2.0 models (mapped_column)
    schemas/                 # Pydantic v2 request/response schemas
    services/                # Logique metier
      comptes.py             # CRUD + auto-container sur assign iPhone
      dispatch.py            # Dispatch commandes iPhone (USB + tunnel SSH/MCP)
      engine.py              # Moteur d'execution scenarios
      automation/            # Automation sur iPhone
        device_session.py    # Context manager : lock device, switch container
        ig_driver.py         # Driver Instagram (MCP → UI actions)
        ig_runner.py         # Runner IG : login, follow, publish, interact
        th_driver.py         # Driver Threads
        th_runner.py         # Runner Threads
        scroll_engine.py     # Scrolling naturel
        human_touch.py       # Delays humains, jitter
      ...                    # 20+ autres services
  alembic/                   # Migrations BDD
  requirements.txt
  seed.sql                   # Donnees initiales
```

### Services systemd sur le VPS

- `scalelab-api` — FastAPI (uvicorn)
- `telegram-bot` — Bot Telegram

### Venv Python

`/root/scale-lab/apps/backend/venv` (Python 3.12)

---

## 5. Flux E2E : Compte → iPhone → Container → Login

### Chaine complete

1. **Creer un compte** : Frontend `submitCreate()` → `POST /api/comptes`
   - Body : `{ handle, plateforme, persona_id, device_id, creds_encrypted, ... }`
   - Backend : chiffre les credentials (Fernet), sauvegarde en BDD

2. **Auto-creation du container** : si `device_id` est fourni et que l'iPhone
   est en mode `tunnel` :
   - `_ensure_container_on_assign()` → `_auto_assign_container()`
   - SSH → `scalectl --create <bundle> <name> FR` sur l'iPhone
   - UUID du container stocke dans `compte.env.container_uuid`

3. **Login automation** : declenche **separement** via le moteur de scenarios
   - `DeviceSession(compte_id, bundle)` → lock device + switch container
   - `IGDriver` → `ig_login` handler → MCP UI automation sur l'iPhone
   - Le login n'est PAS auto-declenche apres la creation du compte

### Endpoints iPhone

| Endpoint | Description |
|---|---|
| `GET /api/iphones` | Liste les iPhones |
| `POST /api/iphones/tunnel/provision` | Enregistrer un iPhone via tunnel |
| `GET /api/iphones/:id/tunnel/probe` | Tester la connectivite MCP + SSH |
| `GET /api/iphones/:id/containers` | Lister les containers (via scalectl) |
| `GET /api/iphones/:id/agent` | Verifier l'agent MCP |

### ScaleTweak (gestion des containers)

Via SSH → `scalectl` CLI sur l'iPhone :

```
scalectl --list <bundle>                          # lister les containers
scalectl --switch <bundle> <uuid>                 # changer le container actif
scalectl --create <bundle> <name> [country]       # creer un container
scalectl --delete <bundle> <uuid>                 # supprimer
scalectl --inject <bundle> <uuid> <file.json>     # injecter session/fingerprint
scalectl --status                                 # statut global
```

Plist : `/var/jb/var/mobile/Library/Preferences/com.scale.tweak.plist`

Bundle mapping : `ig → com.burbn.instagram`, `th → com.burbn.barcelona`

---

## 6. Deploiement

### Frontend (Cloudflare Pages)

```bash
npx wrangler pages deploy apps/web/public --project-name=scale-lab --branch=main --commit-dirty=true
```

**Deployer `apps/web/public/`** — jamais `apps/web/dist/`.

L'utilisateur lance cette commande depuis son Mac apres un `git pull`.

### Gateway (Cloudflare Worker)

```bash
cd ~/code/scale-lab/apps/gateway && npm ci && npx wrangler deploy
```

**GitHub Actions pour le gateway NE FONCTIONNE PAS** (secret `CF_API_TOKEN` manquant).
L'utilisateur doit deployer manuellement depuis son Mac.

### Backend (VPS)

GitHub Actions → SSH VPS → `git pull` + restart service. Fonctionne normalement.

En cas de deploy manuel sur le VPS :

```bash
ssh root@77.42.124.107
cd /root/scale-lab
git pull
sudo systemctl restart scalelab-api
```

---

## 7. Workflow Git avec Claude

### Contrainte principale

**`git push` depuis le container cloud Claude est BLOQUE (HTTP 403).**

### Workflow pour modifier des fichiers

1. **Claude** edite les fichiers dans le container cloud (`/home/claude/scale-lab/`)
2. **Claude** copie le fichier modifie vers `/mnt/user-data/outputs/`
3. **Claude** utilise `device_commit_files` pour envoyer le fichier sur le Mac
   - `devicePath` : chemin absolu sur le Mac (ex: `/Users/timotheeaubree/code/scale-lab/apps/web/public/api-data.js`)
   - `stagedPath` : doit etre sous `/mnt/user-data/outputs/` (PAS le chemin uploads)
   - `force: true` si le fichier a change entre-temps
4. **L'utilisateur** fait depuis son terminal Mac :
   ```bash
   cd ~/code/scale-lab
   git add <fichiers>
   git commit -m "description"
   git push
   ```
5. **L'utilisateur** deploie si necessaire (cf. section Deploiement)

### Acces au Mac (device bridge)

- `device_bash` : shell sur le Mac (scope aux dossiers connectes)
  - Utiliser `$HOME/mnt/scale-lab` (PAS `~/code/scale-lab` — `~` resout vers le home de la session)
- `device_list_dir` : lister les fichiers d'un dossier
- `device_stage_files` : copier des fichiers du Mac vers le container cloud
- `device_commit_files` : copier des fichiers du container cloud vers le Mac
- Dossier connecte : `/Users/timotheeaubree/code/scale-lab`
- Permission de suppression : peut etre demandee via `device_request_delete_permission`

### Verifier le contenu deploye

Apres un push + deploy frontend, toujours verifier que le code deploye est bien
celui attendu, surtout pour `api-data.js` et les fichiers charges dynamiquement.

---

## 8. iPhone connecte

| Propriete | Valeur |
|---|---|
| Modele | iPhone X (iPhone10,6) |
| iOS | 16.7.15 (jailbreak) |
| UDID | `f3c2322255a21b3cf2c481571e7d21618abb8725` |
| Nom | iPhone de Cassie |
| IP locale | 192.168.1.133 |
| SSH password | alpine |
| DB ID | `c2045215-7f90-44d3-b1e3-df8871ad8cbe` |
| Connection | Tunnel (reverse SSH) |

### Personas

| Persona | UUID |
|---|---|
| Cassie | `fb40b74e-4ae5-4400-9cf7-c8af9a8176bd` |
| Maeva | `476cb11f-feb5-4a82-b513-fbc4e138a763` |

---

## 9. Credentials (references)

Les vrais secrets sont dans les fichiers `.env` sur le VPS et les secrets Cloudflare.
Voir les `.env.example` pour la structure.

| Secret | Localisation |
|---|---|
| PostgreSQL | VPS `.env` : user `scalelab`, db `scalelab` |
| API token | Cloudflare Worker secrets + VPS `.env` |
| FERNET_KEY | VPS `.env` (chiffrement des credentials comptes) |
| Login password | Cloudflare Worker secret `LOGIN_PASSWORD` |
| OC API key | VPS `.env` |
| Telegram bot token | VPS `.env` |
| CF Account ID | `a1f6e652bdb299f6a1ab4da85bb64311` |
| KV Namespace ID | `15ea593d7838454dabd796d8e34669f4` |
| Tunnel ID | `5f619bc4-cbf4-442a-a11a-8acb7a8eaf49` |
| GitHub repo | `JawedDeBagnolet/scale-lab` (prive) |

---

## 10. Lecons apprises (pieges a eviter)

### 1. Le cache des scripts DC

Les scripts dans `<helmet>` (comme `api-data.js`) sont charges dynamiquement par
`support.js`. Le navigateur utilise son cache HTTP normal pour ces requetes — un
hard refresh (Cmd+Shift+R) ne les recharge PAS.

**Solution** : le fichier `_headers` avec `Cache-Control: no-cache, must-revalidate`.
Si malgre ca le cache pose probleme, l'utilisateur doit :
- Safari : `Cmd+Option+E` (vider le cache) puis recharger
- Ou ouvrir en navigation privee pour tester

### 2. Ne jamais toucher a support.js

`support.js` est un fichier **genere** par le DC runtime. La premiere ligne dit :
```
// GENERATED from dc-runtime/src/*.ts — do not edit.
```
Ne jamais le modifier. C'est le moteur qui interprete tous les fichiers DC.

### 3. device_commit_files : stagedPath

Le `stagedPath` doit etre sous `/mnt/user-data/outputs/`, pas sous le chemin
retourne par `device_stage_files` (qui est sous `/mnt/user-data/uploads/`).

Workflow correct :
```
1. Editer le fichier dans /home/claude/scale-lab/...
2. cp /home/claude/scale-lab/.../fichier /mnt/user-data/outputs/fichier
3. device_commit_files(stagedPath="/mnt/user-data/outputs/fichier", devicePath="...")
```

### 4. device_bash : les chemins

Dans `device_bash`, utiliser `$HOME/mnt/scale-lab` pour acceder au repo.
Le `~` resout vers le home de la session, pas vers `/Users/timotheeaubree`.

### 5. GitHub Actions gateway

Le deploy automatique du gateway via GitHub Actions echoue (secret `CF_API_TOKEN`
non configure). L'utilisateur doit deployer manuellement :
```bash
cd ~/code/scale-lab/apps/gateway && npm ci && npx wrangler deploy
```

### 6. Deployer le bon dossier

Toujours deployer `apps/web/public/` sur Cloudflare Pages.
Ne JAMAIS deployer `apps/web/dist/` (le build React).

### 7. Diagnostiquer les problemes frontend

Quand un changement frontend ne prend pas effet :
1. Verifier que le deploy a bien uploade des fichiers (`Uploaded X files`)
2. Verifier le contenu servi : `fetch('/api-data.js').then(r=>r.text()).then(console.log)`
3. Si le contenu est ancien : c'est un probleme de cache → vider le cache navigateur
4. Si le contenu est bon mais ne fonctionne pas : inspecter la console pour les erreurs

---

## 11. Tests E2E

### Approche

Pas de framework de test automatise pour l'instant. Les tests sont manuels :

1. **Creer un compte IG** depuis le Module Comptes de l'app
2. **Assigner un iPhone** (dropdown dans le formulaire)
3. **Verifier la creation du container** : `GET /api/iphones/:id/containers`
4. **Verifier la connectivite** : `GET /api/iphones/:id/tunnel/probe`
5. **Declencher un scenario de login** via le Module Scenarios
6. **Verifier les logs** dans le Module Logs (WebSocket live)

### Verification de la connectivite iPhone

```bash
# Depuis le VPS (SSH)
ssh -p 2223 -o StrictHostKeyChecking=no root@127.0.0.1 "echo ok"

# MCP health check
curl -s http://127.0.0.1:8190/mcp -d '{"jsonrpc":"2.0","method":"get_ui_elements","params":{},"id":1}'

# Lister les containers
ssh -p 2223 -o StrictHostKeyChecking=no root@127.0.0.1 "scalectl --list com.burbn.instagram"
```

### Verification via l'API

```bash
# Probe tunnel
curl -H "Authorization: Bearer $TOKEN" https://api.scalelab.win/api/iphones/$IPHONE_ID/tunnel/probe

# Lister containers
curl -H "Authorization: Bearer $TOKEN" https://api.scalelab.win/api/iphones/$IPHONE_ID/containers

# Agent status
curl -H "Authorization: Bearer $TOKEN" https://api.scalelab.win/api/iphones/$IPHONE_ID/agent
```

---

## 12. Commits recents (contexte)

```
d0520a7 fix(web): restore index.html redirect + wire creds_encrypted in DC comptes
79fbc0b fix(web): wire React app entry point in index.html
7593bba feat(comptes): add credentials fields + iPhone dropdown in form
536d76e feat(automation): implement E2E publish flows + auto container + login
a08725d chore: clean repo — remove venv/ and stray files from tracking
a983933 feat(dispatch): replace crane-controller with ScaleTweak SSH scalectl
b369f46 feat: port VPS automation stack into backend as async services
ff1e936 feat(dispatch): support dual USB + reverse SSH tunnel connections
```

---

## 13. Prochaines etapes potentielles

1. **Test E2E complet** : creer un compte IG → assigner iPhone → auto container →
   declencher login → verifier que le login IG fonctionne
2. **Migration des modules restants** du worker monolithique vers FastAPI
3. **Pipeline CI/CD** : corriger le deploy gateway automatique (ajouter CF_API_TOKEN)
4. **Monitoring** : alertes Telegram pour les incidents, telemetrie iPhone
