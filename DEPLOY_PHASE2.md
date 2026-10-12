# Scale Lab — Deploy Phase 2

## Fichiers modifies / ajoutes

### Backend (apps/backend/)

**Nouveaux :**
```
app/models/settings.py
app/models/target.py
app/models/log.py
app/models/comportement.py
app/schemas/dashboard.py
app/schemas/settings.py
app/schemas/target.py
app/schemas/log.py
app/schemas/comportement.py
app/services/dashboard.py
app/services/settings.py
app/services/targets.py
app/services/logs.py
app/services/comportements.py
app/api/dashboard.py
app/api/settings.py
app/api/targets.py
app/api/logs.py
app/api/comportements.py
app/ws.py
alembic/versions/002_phase2_settings_targets_presets_logs.py
```

**Modifies :**
```
app/main.py              (import des nouveaux routers + WebSocket)
app/models/__init__.py   (import des nouveaux modeles)
```

### Frontend (apps/web/src/)

**Nouveaux :**
```
types/settings.ts
types/target.ts
types/preset.ts
types/log.ts
types/dashboard.ts
hooks/useLogStream.ts
modules/parametres/ParametresPage.tsx
modules/targets/TargetsPage.tsx
modules/targets/TargetForm.tsx
modules/targets/BulkImportModal.tsx
modules/comportements/ComportementsPage.tsx
modules/comportements/PresetForm.tsx
modules/logs/LogsPage.tsx
modules/dashboard/DashboardPage.tsx
```

**Modifies :**
```
hooks/useApi.ts          (hooks Phase 2 : settings, targets, presets, logs, dashboard)
App.tsx                  (imports + routes des nouveaux modules)
```

---

## Deploiement

### 1. Push sur GitHub

```bash
cd /root/scale-lab          # ou ton repo local
git add -A
git commit -m "Phase 2 : Parametres, Targets, Comportements, Logs, Dashboard"
git push origin main
```

### 2. Frontend (automatique)

Le push sur `main` declenche le deploy Cloudflare Pages automatiquement.
Verifier sur https://dash.cloudflare.com → Pages → scale-lab.

### 3. Backend (VPS)

```bash
# Se connecter au VPS
ssh root@77.42.124.107

# Pull les changements
cd /root/scale-lab
git pull origin main

# Installer les eventuelles nouvelles deps
cd apps/backend
source venv/bin/activate
pip install -r requirements.txt

# Lancer la migration (cree les 6 nouvelles tables)
alembic upgrade head

# Redemarrer le service
systemctl restart scalelab-api

# Verifier
systemctl status scalelab-api
curl -s http://localhost:8000/health | python3 -m json.tool
```

### 4. Verification

```bash
# Tester le dashboard stats
curl -s -H "Authorization: Bearer 75640332d36f253e8debecbcc6dba4d0eebfd9fafaeac96812b67593d77886b7" \
  https://api.scalelab.win/api/dashboard/stats | python3 -m json.tool

# Tester les settings (auto-cree la ligne id=1)
curl -s -H "Authorization: Bearer 75640332d36f253e8debecbcc6dba4d0eebfd9fafaeac96812b67593d77886b7" \
  https://api.scalelab.win/api/settings | python3 -m json.tool

# Tester les targets (liste vide au debut)
curl -s -H "Authorization: Bearer 75640332d36f253e8debecbcc6dba4d0eebfd9fafaeac96812b67593d77886b7" \
  https://api.scalelab.win/api/targets | python3 -m json.tool
```

---

## Tables creees par la migration 002

| Table | Description |
|---|---|
| `workspace_settings` | Config workspace (nom, devise, timezone, integrations OC/GMS/TG) |
| `targets` | Comptes de reference (handle, plateforme, market, niche, status) |
| `presets` | Presets de comportement (probabilites, pauses, durees) |
| `events` | Journal d'evenements (module, level, message, meta) |
| `incidents` | Incidents groupes (module, event_type, count, status) |
| `alert_rules` | Regles d'alerte (seuils, Telegram on/off) |

## Rollback

```bash
# Annuler la migration
cd /root/scale-lab/apps/backend
source venv/bin/activate
alembic downgrade 001

# Redemarrer
systemctl restart scalelab-api
```
