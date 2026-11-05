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
iPhone (jailbreake, ScaleTweak + ios-mcp + MTOUCH)
    |
    | Media pipeline
    v
Spoof Server (VPS port 8502) ← R2 (Cloudflare)
```

### Domaines et services

| Domaine | Service | Stack |
|---|---|---|
| `scalelab.win` | Frontend | Cloudflare Pages, fichiers DC statiques |
| `api.scalelab.win` | Gateway | Cloudflare Worker, Hono (TypeScript) |
| `vps.scalelab.win` | Backend | Cloudflare Tunnel → FastAPI (Python 3.12) |
| VPS `77.42.124.107` | BDD + automation | PostgreSQL 15, systemd services |

### Ports du tunnel iPhone (reverse SSH sur le VPS)

Le tunnel SSH part de l'iPhone vers le VPS via le daemon `com.scale.tunnel`.

| Port VPS (localhost) | Port iPhone | Service |
|---|---|---|
| `18090` | `8090` | ios-mcp (JSON-RPC, UI automation) |
| `8191` | `8091` | MTOUCH (touch simulation avancee) |
| `8180` | `8080` | CRANE (reserve) |
| `2223` | `22` | SSH (scalectl, fichiers, commandes) |

> **Note** : Le code Python a deux valeurs par defaut pour le port MCP :
> - `dispatch.py` : `DEFAULT_MCP_PORT = 18090` (utilise pour les appels MCP directs)
> - `ig_driver.py` / `human_touch.py` : `mcp_port = 8190` (defaut constructeur)
>
> En pratique, le port passe toujours via `DeviceSession` qui lit la config du device.
> Les valeurs par defaut des constructeurs sont un fallback.

### iPhone — Daemon tunnel SSH

Fichier : `/var/jb/Library/LaunchDaemons/com.scale.tunnel.plist`

```xml
<plist version="1.0">
<dict>
  <key>Label</key><string>com.scale.tunnel</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/ssh</string>
    <string>-N</string>
    <string>-o</string><string>ServerAliveInterval=30</string>
    <string>-o</string><string>ServerAliveCountMax=3</string>
    <string>-o</string><string>StrictHostKeyChecking=no</string>
    <string>-i</string><string>/var/root/.ssh/id_ed25519</string>
    <string>-R</string><string>2223:127.0.0.1:22</string>
    <string>-R</string><string>18090:127.0.0.1:8090</string>
    <string>root@77.42.124.107</string>
  </array>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardErrorPath</key><string>/var/log/scale-tunnel.err</string>
</dict>
</plist>
```

Cle SSH generee sur l'iPhone : `/var/root/.ssh/id_ed25519`
Pubkey ajoutee sur le VPS dans `/root/.ssh/authorized_keys`

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

### `_headers` — Cache control CF Pages

```
/api-data.js
  Cache-Control: no-cache, must-revalidate

/support.js
  Cache-Control: no-cache, must-revalidate
```

Ce fichier est **essentiel** car `api-data.js` et `support.js` sont charges dynamiquement.

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

### Flux des headers d'auth

```
Navigateur → Gateway : Authorization: Bearer <API_SECRET>
Gateway → Backend :    X-Scale-Token: <API_SECRET>
```

Le gateway remplace le header `Authorization` par `X-Scale-Token` pour le backend.

### Cache KV

Prefixes caches (TTL 5 min) : `/api/niches`, `/api/marches`, `/api/settings`, `/api/presets`
Les mutations (POST/PATCH/PUT/DELETE) invalident automatiquement le cache.

### Variables d'environnement (Cloudflare Worker secrets)

| Variable | Description |
|---|---|
| `API_BASE` | URL du backend via tunnel (`https://vps.scalelab.win`) |
| `API_SECRET` | Token pour l'auth API |
| `LOGIN_PASSWORD` | Mot de passe pour le login frontend |
| `CACHE` | KV namespace binding |
| `MEDIA` | R2 bucket binding |

---

## 4. Backend (FastAPI sur VPS)

### Structure

```
apps/backend/
  app/
    main.py                  # FastAPI app, montage des routers
    auth.py                  # Middleware auth X-Scale-Token
    config.py                # Settings (Pydantic BaseSettings)
    db.py                    # AsyncSession factory (asyncpg)
    crypto.py                # Fernet encrypt/decrypt pour credentials
    api/                     # Routes (routers FastAPI)
      comptes.py             # CRUD comptes + mass login (batch-login, batch-login-all)
      personas.py            # CRUD personas
      iphones.py             # CRUD iPhones + tunnel provisioning + containers
      posting.py             # Collections, medias, templates, campagnes, publications
      scenarios.py           # Scenarios, runs (launch/pause/resume/skip/abort)
      veille.py              # Sources, inspirations, favoris, snipes, albums
      crm.py                 # Fans, transactions, scripts
      liens.py               # Liens trackes, domaines, clicks
      proxies.py             # Gestion des proxies (inclut rotation_url)
      comportements.py       # Presets de comportement
      targets.py             # Comptes de reference
      statistiques.py        # Stats quotidiennes, overview, bulk import
      logs.py                # Evenements, incidents, regles d'alerte
      dashboard.py           # Stats dashboard
      settings.py            # Config workspace, integrations, notifications
      integrations.py        # OC/GMS test/key/status/sync
      telegram.py            # Bot start, linking, groupes, briefs, alertes
      health.py              # Health check
      referentiels.py        # Niches, marches
    models/                  # SQLAlchemy 2.0 models (mapped_column)
    schemas/                 # Pydantic v2 request/response schemas
    services/                # Logique metier
      comptes.py             # CRUD + auto-container sur assign iPhone
      dispatch.py            # Dispatch commandes iPhone (USB + tunnel SSH/MCP)
      engine.py              # Moteur d'execution scenarios
      media_pipeline.py      # Pipeline R2 → spoof EXIF → SCP → import Camera Roll
      mtouch.py              # Wrapper MTOUCH (touch simulation avancee)
      session_extract.py     # Extraction session IG depuis l'iPhone
      logs.py                # Emission d'evenements via WebSocket
      automation/            # Automation sur iPhone
        device_session.py    # Context manager : lock device (FIFO queue), switch container
        ig_driver.py         # Driver Instagram (MCP → UI actions, 13 ecrans detectes)
        ig_runner.py         # Runner IG : login, follow, publish, interact, feed session
        th_driver.py         # Driver Threads
        th_runner.py         # Runner Threads
        scroll_engine.py     # Scrolling naturel
        human_touch.py       # Touches realistes, swipe, type, jitter gaussien
        behavior/            # 14 patterns anti-detection
          __init__.py
          patterns.py        # maybe_pattern(), pick_pattern(), hesitate_before_action()
  alembic/                   # Migrations BDD
  requirements.txt
  seed.sql                   # Donnees initiales
```

### Services systemd sur le VPS

| Service | Description | Commande restart |
|---|---|---|
| `scalelab-api` | FastAPI (uvicorn, port 8000) | `sudo systemctl restart scalelab-api` |
| `telegram-bot` | Bot Telegram | `sudo systemctl restart telegram-bot` |

### Venv Python

`/root/scale-lab/apps/backend/venv` (Python 3.12)

### Alembic (migrations BDD)

```bash
# Depuis le VPS
cd /root/scale-lab/apps/backend
source venv/bin/activate
alembic upgrade heads   # 'heads' (pluriel) si multiple heads existent
alembic history         # voir l'historique des migrations
alembic current         # version actuelle en BDD
```

---

## 5. Pipeline Media

### Flux complet : R2 → iPhone Camera Roll

```
1. Frontend upload → Gateway → R2 (stockage)
   POST /api/upload/media → R2 bucket "scale-lab-media"

2. Backend telecharge depuis R2
   media_pipeline.download_and_spoof() → GET R2 via signed URL

3. Spoof EXIF (VPS port 8502)
   POST http://localhost:8502/spoof → enleve/modifie les metadonnees EXIF
   (date, GPS, device model, software, etc.)

4. Transfert vers iPhone (SCP via tunnel SSH)
   media_pipeline.transfer_to_iphone() → cat pipe over SSH port 2223

5. Import dans Camera Roll (MTOUCH ou importmedia)
   mtouch.mtouch_import_media() → curl localhost:8091 sur iPhone
   Fallback : MCP run_command → importmedia CLI
```

### Serveur Spoof EXIF

Le serveur spoof tourne sur le VPS port `8502`. Il recoit une image et renvoie
la meme image avec les metadonnees EXIF nettoyees/randomisees.

---

## 6. iPhone — Configuration complete

### Materiel

| Propriete | Valeur |
|---|---|
| Modele | iPhone X (iPhone10,6) |
| iOS | 16.7.15 |
| Jailbreak | palera1n (rootless, `/var/jb/`) |
| UDID | `f3c2322255a21b3cf2c481571e7d21618abb8725` |
| Nom | iPhone de Cassie |
| IP locale (Wi-Fi) | 192.168.1.133 |
| SSH password | alpine |
| DB ID | `c2045215-7f90-44d3-b1e3-df8871ad8cbe` |
| Connection | Tunnel (reverse SSH via Wi-Fi) |

### Tweaks installes

| Tweak | Description | Port |
|---|---|---|
| **ScaleTweak** | Container isolation (multi-compte IG/Threads) | — |
| **ios-mcp** | MCP server (fork witchan/ios-mcp v1.2.2) | 8090 |
| **MTOUCH** | Touch simulation avancee (pinch, rotate, import) | 8091 |

### ios-mcp — Protocole MCP

```bash
# Format d'appel
POST http://127.0.0.1:18090/mcp
Header: MCP-Protocol-Version: 2025-06-18
Body: {
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "<tool_name>",
    "arguments": { ... }
  },
  "id": 1
}
```

#### Outils MCP disponibles (46 au total)

| Outil | Arguments | Description |
|---|---|---|
| `tap_screen` | `{x, y}` | Tap aux coordonnees |
| `tap_element` | `{text, match?}` | Tap element par texte accessibilite |
| `swipe_screen` | `{fromX, fromY, toX, toY, duration, steps}` | Swipe |
| `drag_and_drop` | `{points, hold_duration, move_duration, steps}` | Geste multi-point |
| `long_press` | `{x, y, duration}` | Appui long |
| `get_ui_elements` | `{clickable_only?, max_elements?}` | Arbre d'accessibilite |
| `get_screen_info` | — | Dimensions ecran |
| `type_text` | `{text, interval?}` | Saisie clavier caractere par caractere |
| `input_text` | `{text}` | Remplacer texte du champ focus |
| `launch_app` | `{bundle_id}` | Ouvrir une app |
| `kill_app` | `{bundle_id}` | Fermer une app |
| `screenshot` | — | Capture PNG base64 |
| `ocr_screen` | — | Reconnaissance de texte |
| `run_command` | `{command}` | Commande shell sur iPhone |

> **IMPORTANT** : Ne jamais utiliser `uiopen` (scheme URL) pour lancer une app.
> Toujours utiliser MCP `launch_app` (evite les popups systeme).

### ScaleTweak (gestion des containers)

Via SSH → `scalectl` CLI sur l'iPhone :

```bash
scalectl --list <bundle>                          # lister les containers
scalectl --switch <bundle> <uuid>                 # changer le container actif
scalectl --create <bundle> <name> [country]       # creer un container
scalectl --delete <bundle> <uuid>                 # supprimer
scalectl --inject <bundle> <uuid> <file.json>     # injecter session/fingerprint
scalectl --status                                 # statut global
```

Plist : `/var/jb/var/mobile/Library/Preferences/com.scale.tweak.plist`
Bundle mapping : `ig → com.burbn.instagram`, `th → com.burbn.barcelona`

### Personas

| Persona | UUID |
|---|---|
| Cassie | `fb40b74e-4ae5-4400-9cf7-c8af9a8176bd` |
| Maeva | `476cb11f-feb5-4a82-b513-fbc4e138a763` |

---

## 7. Deploiement — Guide complet

### Frontend (Cloudflare Pages)

**Deploiement** : automatique via Cloudflare Pages, connecte au repo GitHub.
A chaque push sur `main` qui modifie `apps/web/public/`, Cloudflare Pages re-deploie.

**Deploy manuel** (si le deploy auto ne suffit pas) :

```bash
cd ~/code/scale-lab
npx wrangler pages deploy apps/web/public --project-name=scale-lab --branch=main --commit-dirty=true
```

**TOUJOURS deployer `apps/web/public/`** — JAMAIS `apps/web/dist/`.

**Verification post-deploy** :
1. Aller sur `https://scalelab.win`
2. Ouvrir la console (F12 / Cmd+Option+I)
3. Verifier qu'il n'y a pas d'erreur JS
4. Si changement ne prend pas : vider le cache Safari (Cmd+Option+E) puis recharger

### Gateway (Cloudflare Worker)

**GitHub Actions** : configure dans `.github/workflows/deploy-gateway.yml`
- Declenche sur push dans `apps/gateway/`
- **ATTENTION** : le secret `CF_API_TOKEN` n'est peut-etre pas configure → deploy
  automatique peut echouer.

**Deploy manuel** (recommande) :

```bash
cd ~/code/scale-lab/apps/gateway
npm ci
npx wrangler deploy
```

**Pour mettre a jour un secret Worker** :

```bash
cd ~/code/scale-lab/apps/gateway
npx wrangler secret put API_SECRET     # coller la valeur quand demande
npx wrangler secret put LOGIN_PASSWORD
```

### Backend (FastAPI sur VPS)

**GitHub Actions** : configure dans `.github/workflows/deploy-backend.yml`
- Declenche sur push dans `apps/backend/`
- Se connecte en SSH au VPS et execute :
  1. `git pull origin main`
  2. `pip install -r requirements.txt`
  3. `alembic upgrade heads`
  4. `systemctl restart scalelab-api`

**Deploy manuel** (si GitHub Actions ne fonctionne pas) :

```bash
ssh root@77.42.124.107
cd /root/scale-lab
git pull origin main
cd apps/backend
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade heads
sudo systemctl restart scalelab-api
```

**Verifier les logs du backend** :

```bash
ssh root@77.42.124.107
journalctl -u scalelab-api -f       # logs en direct
journalctl -u scalelab-api --since "5 min ago"  # 5 dernieres minutes
```

### iPhone — Deploy de tweaks

Les tweaks (ScaleTweak, ios-mcp, MTOUCH) se compilent sur le Mac via `theos` :

```bash
# Depuis le Mac
cd ~/Desktop/ScaleTweak_v5_threads   # ou autre tweak
make clean && make package
# Installer sur l'iPhone
scp packages/*.deb root@192.168.1.133:/tmp/
ssh root@192.168.1.133 "dpkg -i /tmp/*.deb && ldrestart"
```

> L'iPhone est accessible en SSH directement via Wi-Fi (port 22, mdp: alpine)
> pour l'installation de tweaks. Le tunnel reverse SSH (port 2223) est pour le
> VPS qui ne peut pas atteindre l'iPhone directement.

### iPhone — Verifier le tunnel

```bash
# Depuis le VPS
ssh -p 2223 -o StrictHostKeyChecking=no root@127.0.0.1 "echo OK"

# Tester le MCP
curl -s -X POST http://127.0.0.1:18090/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_screen_info","arguments":{}},"id":1}'

# Lister les containers IG
ssh -p 2223 root@127.0.0.1 "scalectl --list com.burbn.instagram"
```

### iPhone — Relancer le tunnel si coupe

```bash
# Depuis l'iPhone (SSH direct via Wi-Fi)
ssh root@192.168.1.133
launchctl unload /var/jb/Library/LaunchDaemons/com.scale.tunnel.plist
launchctl load /var/jb/Library/LaunchDaemons/com.scale.tunnel.plist
```

Ou simplement attendre — le daemon a `KeepAlive: true` donc il redemarrera
automatiquement (delai max ~10 secondes via `ThrottleInterval`).

---

## 8. Workflow Git avec Claude

### Contrainte principale

**`git push` depuis le container cloud Claude est BLOQUE (HTTP 403 — pas d'acces GitHub App).**
**`git push` depuis le `device_bash` du Mac est BLOQUE (pas de reseau dans le sandbox).**

L'utilisateur doit toujours faire le `git push` depuis son terminal Mac.

### Workflow pour modifier des fichiers

```
1. Claude edite les fichiers dans /home/claude/scale-lab/
2. Claude copie le fichier → /mnt/user-data/outputs/<nom>
3. Claude envoie via device_commit_files :
   - stagedPath: /mnt/user-data/outputs/<nom>  (PAS /mnt/user-data/uploads/)
   - devicePath: /Users/timotheeaubree/code/scale-lab/...
   - force: true si necessaire
4. Claude commit via device_bash :
   cd $HOME/mnt/scale-lab && git add <fichier> && git commit -m "..."
5. L'UTILISATEUR push depuis son terminal Mac :
   cd ~/code/scale-lab && git push origin main
```

**Alternative plus fiable** : utiliser `SendUserFile` puis `device_commit_files`
avec le `fileUuid` retourne (bypasse le probleme de stagedPath).

### Acces au Mac (device bridge)

| Outil | Usage |
|---|---|
| `device_bash` | Shell sur le Mac (scope aux dossiers connectes) |
| `device_list_dir` | Lister les fichiers d'un dossier |
| `device_stage_files` | Copier fichiers du Mac → container cloud |
| `device_commit_files` | Copier fichiers du container cloud → Mac |
| `device_request_delete_permission` | Demander le droit de supprimer |

**Chemins dans device_bash** :
- Utiliser `$HOME/mnt/scale-lab` (PAS `~/code/scale-lab`)
- `$HOME/mnt/` liste les dossiers connectes

**Dossiers connectes** :
- `/Users/timotheeaubree/code/scale-lab`
- `/Users/timotheeaubree/Desktop/ScaleTweak_v5_threads`
- `/Users/timotheeaubree/Desktop/ScaleTweak_v5_antifp_final`
- `/Users/timotheeaubree/ios-mcp-fork`
- `/Users/timotheeaubree/mtouch-tweak`
- `/Users/timotheeaubree/theos`

### Commandes Git pour l'utilisateur

Apres que Claude a commit :

```bash
# Push simple
cd ~/code/scale-lab && git push origin main

# Si le push echoue (commits en avance sur le remote)
cd ~/code/scale-lab && git pull --rebase origin main && git push origin main
```

---

## 9. Automation iPhone — Details techniques

### FIFO Device Queue

Chaque iPhone a un `asyncio.Lock` pour garantir qu'un seul task s'execute a la fois.
Les tasks sont servies en FIFO (premier arrive, premier servi).

Entre deux sessions sur le meme device, le proxy IP est tourne automatiquement
si le proxy a un `rotation_url` configure.

### Detection d'ecran IG (ig_driver.py)

13 ecrans detectes, verifies dans cet ordre (auth en premier) :

```
login, onboarding, save_login, 2fa_choice, 2fa_notif, notif_popup,
2fa_code, checkpoint, login_error, welcome, feed, reels, own_profile,
post_view, explore, story
```

La detection utilise du **substring matching** : `any(marker.lower() in text for text in texts)`

### Boucle post-login (device_session.py)

15 etapes gerees automatiquement apres la saisie des identifiants :
`save_login → notif_popup → 2fa_notif → 2fa_choice → 2fa_code →
checkpoint → login_error → welcome → feed`

Regles :
- Ne PAS taper sur la case a cocher "Faire confiance" (deja cochee par defaut)
- 2FA : `tap_screen(169, 511)` pour le champ code (pas `tap_element("Code")`)
- Utiliser `input_text` pour le code TOTP, pas `type_text`

### 14 Patterns anti-detection (behavior/)

| Pattern | Description |
|---|---|
| `scroll_back` | Remonter legerement apres un scroll |
| `pause_distraction` | Pause aleatoire (simule distraction) |
| `hesitate` | Hesitation avant une action |
| `slow_read_caption` | Lecture lente d'une legende |
| `browse_replies_slow` | Parcourir les reponses lentement |
| `imprecise_scroll` | Scroll avec derive laterale |
| `double_tap_miss` | Double tap rate puis reussi |
| `random_profile_peek` | Visite aleatoire de profil |
| `typing_corrections` | Fautes de frappe corrigees |
| `watch_video_variable` | Regarder une video duree variable |
| `change_scroll_speed` | Varier la vitesse de scroll |
| `behavior_glance` | Coup d'oeil rapide |
| `behavior_browse` | Navigation exploratoire |
| `behavior_deep_read` | Lecture approfondie |

Utilisation : `maybe_pattern(drv, log, probability=0.15)` apres chaque scroll.

---

## 10. Flux E2E : Compte → iPhone → Container → Login

### Chaine complete

1. **Creer un compte** : Frontend `submitCreate()` → `POST /api/comptes`
   - Body : `{ handle, plateforme, persona_id, device_id, creds_encrypted, ... }`
   - Backend : chiffre les credentials (Fernet), sauvegarde en BDD

2. **Auto-creation du container** : si `device_id` fourni et iPhone en mode tunnel
   - `_ensure_container_on_assign()` → `_auto_assign_container()`
   - SSH → `scalectl --create <bundle> <name> FR` sur l'iPhone
   - UUID du container stocke dans `compte.env.container_uuid`

3. **Login automation** : declenche **separement** via masse login ou scenario
   - `POST /api/comptes/batch-login` (IDs specifiques) ou `batch-login-all`
   - `DeviceSession(compte_id, bundle)` → lock device + switch container
   - `IGDriver` → `ig_login` handler → MCP UI automation

### Verification via l'API

```bash
TOKEN="<api_token>"

# Probe tunnel iPhone
curl -H "X-Scale-Token: $TOKEN" https://vps.scalelab.win/api/iphones/$ID/tunnel/probe

# Lister containers
curl -H "X-Scale-Token: $TOKEN" https://vps.scalelab.win/api/iphones/$ID/containers

# Agent MCP status
curl -H "X-Scale-Token: $TOKEN" https://vps.scalelab.win/api/iphones/$ID/agent
```

> Note : depuis le navigateur, les appels passent par le gateway avec
> `Authorization: Bearer $TOKEN`. Depuis le VPS, utiliser `X-Scale-Token`.

---

## 11. Credentials (references)

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

## 12. Lecons apprises (pieges a eviter)

### Frontend

1. **Cache des scripts DC** : les scripts dans `<helmet>` sont charges dynamiquement.
   Hard refresh ne suffit pas. Vider le cache Safari (`Cmd+Option+E`) puis recharger.
   Le fichier `_headers` force `no-cache` pour `api-data.js` et `support.js`.

2. **Ne jamais toucher a support.js** : fichier genere par le DC runtime.

3. **Fallbacks dans les modules DC** : toujours mettre des fallbacks sur les lookups
   (`this.LV[x] || this.LV.info`, `(this.CAT[x] || [])`, etc.) car le backend peut
   renvoyer des valeurs inattendues.

4. **Deployer le bon dossier** : `apps/web/public/`, jamais `apps/web/dist/`.

### device_commit_files

5. **stagedPath** : doit etre sous `/mnt/user-data/outputs/`. Copier d'abord :
   ```bash
   cp /home/claude/scale-lab/.../fichier /mnt/user-data/outputs/fichier
   ```
   Puis `device_commit_files(stagedPath="/mnt/user-data/outputs/fichier", ...)`.
   Ou utiliser `SendUserFile` + `fileUuid` (plus fiable).

### device_bash

6. **Chemins** : utiliser `$HOME/mnt/scale-lab`, pas `~/code/scale-lab`.

7. **Pas de reseau** : `device_bash` n'a pas d'acces internet. Impossible de faire
   `git push`, `npm install`, `pip install` etc. depuis ce shell.

### iPhone / MCP

8. **Noms d'outils MCP** : `tap_screen` (pas `perform_action`), `kill_app`
   (pas `terminate_app`). Toujours verifier les noms exacts.

9. **Ne pas utiliser uiopen** : cause des popups systeme. Toujours `launch_app`.

10. **Detection d'ecran** : utiliser du substring matching, pas du exact match.
    Les textes d'accessibilite sont souvent plus longs que les marqueurs.

11. **Port MCP** : eviter le port 8090 en local sur le VPS (conflit avec le backend
    qui tourne sur 8000 mais d'autres services peuvent occuper 8090).

### Backend / Alembic

12. **Multiple heads Alembic** : utiliser `alembic upgrade heads` (pluriel).
    Si erreur, creer une migration merge : `alembic merge heads -m "merge"`

13. **FERNET_KEY** : doit etre une cle Fernet valide (base64, 44 chars).
    Generer avec : `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

### GitHub Actions

14. **Deploy gateway** : le secret `CF_API_TOKEN` peut ne pas etre configure.
    L'utilisateur doit deployer manuellement avec `wrangler deploy`.

---

## 13. Tests

### Approche

Pas de framework de test automatise. Les tests sont lances manuellement.

### Tester via le frontend

1. Ouvrir `https://scalelab.win` → se connecter
2. Module Comptes : creer un compte, assigner un iPhone
3. Module Comptes : bouton "Mass login" pour declencher les logins
4. Module Logs : verifier les evenements en temps reel (WebSocket)
5. Module Scenarios : lancer un scenario et suivre l'execution

### Tester via l'API (depuis le VPS)

```bash
# Health check
curl http://localhost:8000/health

# Lister les comptes
curl -H "X-Scale-Token: $TOKEN" http://localhost:8000/api/comptes

# Probe iPhone
curl -H "X-Scale-Token: $TOKEN" http://localhost:8000/api/iphones/$ID/tunnel/probe

# Lancer un login
curl -X POST -H "X-Scale-Token: $TOKEN" -H "Content-Type: application/json" \
  http://localhost:8000/api/comptes/batch-login \
  -d '{"account_ids": ["<uuid>"]}'
```

### Verification de la connectivite iPhone

```bash
# Depuis le VPS
ssh -p 2223 -o StrictHostKeyChecking=no root@127.0.0.1 "echo OK"

# MCP
curl -s -X POST http://127.0.0.1:18090/mcp \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_screen_info","arguments":{}},"id":1}'
```

---

## 14. WebSocket (Logs live)

### URL de connexion

```
wss://api.scalelab.win/ws/logs?token=<API_SECRET>
```

> **Bug connu** : l'URL se construit parfois avec un double domaine :
> `wss://scalelab.win/.scalelab.win/api/ws/logs`. Verifier `api-data.js`
> si ce probleme reapparait.

Le gateway proxy le WebSocket vers le backend VPS.
Le backend emet les evenements via `ws_logs` (pas d'auth sur le WS cote backend).

---

## 15. Checklist avant de tester

- [ ] VPS backend en marche : `ssh root@77.42.124.107 "systemctl is-active scalelab-api"`
- [ ] Tunnel iPhone actif : `ssh -p 2223 root@127.0.0.1 "echo OK"` (depuis VPS)
- [ ] MCP repond : tester avec `get_screen_info` (depuis VPS)
- [ ] Au moins 1 proxy configure (Module Proxies)
- [ ] Au moins 1 compte IG avec iPhone et container assignes (Module Comptes)
- [ ] Frontend deploye et accessible (pas d'erreur console)
