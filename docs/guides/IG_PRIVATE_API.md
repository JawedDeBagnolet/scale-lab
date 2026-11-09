# Guide — API Privee Instagram (Read-Only)

Ce guide documente l'utilisation de l'API privee Instagram pour Scale Lab.
Toutes les donnees sont extraites via ScaleTweak (tweak Substrate natif) —
pas de Frida, pas de scraping web, pas de tokens inventes.

---

## 1. Vue d'ensemble

```
iPhone (ScaleTweak)                Backend (VPS)                    Frontend
  |                                  |                               |
  | Object graph traversal           |                               |
  | + Keychain scan (16 items)       |                               |
  | → /tmp/scale_session.json        |                               |
  |                                  |                               |
  |  SSH cat session.json  ←─────────|                               |
  |                                  |                               |
  |                                  | IGApiClient(session)           |
  |                                  |   → i.instagram.com/api/v1/*  |
  |                                  |                               |
  |                                  | GET /api/ig/search/users?q=   |←── Autocomplete
  |                                  | GET /api/ig/user/{pk}         |←── Profil
  |                                  | GET /api/ig/user/{pk}/feed    |←── Publications
  |                                  | GET /api/ig/music/search?q=   |←── Sons
  |                                  | GET /api/ig/stats/{pk}        |←── Analytics
```

---

## 2. Extraction de session (ScaleTweak)

### Ce qui est extrait

ScaleTweak s'execute dans le process Instagram (tweak Substrate). 15 secondes
apres le lancement, il extrait la session via 3 sources :

| Source | Methode | Donnees |
|--------|---------|---------|
| Object graph | `UIApplication.delegate → _appCoordinator → _userSession` | username, full_name, Bearer token |
| Keychain scan | `SecItemCopyMatching` (bypass hook via orig_) | mid, ig_did, unique_id, logging_claims, nonces, auth headers |
| Bearer parsing | Decode base64 du token IGT:2: | sessionid |

### Fichier de sortie

`/tmp/scale_session.json` sur l'iPhone :

```json
{
  "username": "cassiexgarcia526",
  "full_name": "Cassie Garcia",
  "ds_user_id": "30904964584",
  "authorization": "Bearer IGT:2:eyJ...",
  "sessionid": "30904964584%3AKe759...",
  "mid": "avB-AQAAAAHvyCh6...",
  "ig_did": "BD2C7B11-7F5B-41B9-...",
  "unique_id": "BD2C7B11-7F5B-41B9-...",
  "logging_claims": "{\"30904964584\":\"hmac.AR3a...\"}",
  "container_uuid": "092FB161-3A36-4F4C-...",
  "extracted_at": "2026-11-08 16:08:56 +0000",
  "keychain": {
    "com.instagram.users.authheaders.service": "...",
    "instagram.mid": "...",
    "instagram.deviceid": "...",
    "instagram.activeaccount": "...",
    "unique_id": "...",
    "com.instagram.users.loggingclaims.service": "...",
    "com.instagram.nonce_store": "...",
    "...": "..."
  }
}
```

### 16 entrees keychain par container

| Service | Contenu |
|---------|---------|
| `com.instagram.users.authheaders.service` | Bearer token JSON |
| `instagram.mid` | Machine ID |
| `instagram.deviceid` | Device UUID |
| `instagram.activeaccount` | Bearer du compte actif |
| `instagram.savedaccounts` | Bearer des comptes sauvegardes |
| `instagram.inactiveloggedinaccounts` | Bearers des comptes inactifs |
| `unique_id` | UUID unique |
| `com.instagram.users.loggingclaims.service` | HMAC claims (X-IG-WWW-Claim) |
| `com.instagram.nonce_store` | Nonces vetted device |
| `persistent_accounts.growth` | PK du compte persistent |
| `device_based_login.growth` | PK pour device-based login |
| `com.instagram.device` | Mid header (duplique) |
| `reinstalls` | Timestamp reinstallation |
| `com.facebook.deviceLockedStatusFlag` | Flag device lock |
| `group.com.facebook.family.instagramtokenshare.service` | Token partage famille FB |
| `*.GeckoLight_Default.e2ee.apt.meta.com` | Cle E2EE |

---

## 3. Headers de requete

### Headers obligatoires

```
Authorization:      Bearer IGT:2:<base64_payload>
User-Agent:         Instagram <version> (iPhone10,6; iOS 16_7_15; fr_FR; fr; scale=3.00; 1125x2436; <build>)
X-IG-App-ID:        124024574287414  (iOS — NE PAS utiliser l'ID Android 936619743392459)
X-IG-Device-ID:     <ig_did UUID>
X-MID:              <mid>
```

### Headers recommandes

```
X-IG-WWW-Claim:     hmac.AR3a...  (extrait de logging_claims)
X-IG-Connection-Type: WiFi
X-IG-App-Locale:    fr_FR
X-IG-Device-Locale: fr_FR
X-IG-Timezone-Offset: 3600
Accept-Language:     fr-FR,fr;q=0.9
```

### Notes importantes

- **App ID iOS vs Android** : 124024574287414 (iOS) vs 936619743392459 (Android).
  Utiliser le mauvais ID peut trigger un challenge.
- **User-Agent** : doit correspondre a la version d'IG installee sur l'iPhone.
  Le format est `Instagram <version> (<model>; iOS <ios_version>; <locale>; ...)`.
  La version se recupere via `plutil -key CFBundleShortVersionString .../Info.plist`.
- **csrftoken** : NON NECESSAIRE pour les requetes GET (lecture seule).
  IG moderne ne le stocke plus localement (ni keychain, ni cookies, ni object graph).
  Il est retourne dans les headers de reponse sur certains endpoints POST.
- **NSHTTPCookieStorage** : VIDE sur IG moderne — les cookies sont geres en interne
  par le stack reseau Tigon/FBNetworking, pas par le systeme iOS.

---

## 4. Endpoints valides

### Recherche de comptes

```
GET /api/v1/users/search/?q=<query>&count=10
```

Reponse : `{ "users": [{ "pk", "username", "full_name", "profile_pic_url", "is_verified", "follower_count" }] }`

Cas d'usage : autocomplete dans les barres de recherche (veille, targets, etc.)

### Profil utilisateur

```
GET /api/v1/users/<pk>/info/
```

Reponse : `{ "user": { "pk", "username", "full_name", "biography", "profile_pic_url",
"follower_count", "following_count", "media_count", "is_private", "is_verified", "external_url" } }`

### Publications d'un profil

```
GET /api/v1/feed/user/<pk>/?count=12&max_id=<cursor>
```

Reponse : `{ "items": [{ "pk", "code", "media_type", "image_versions2", "caption",
"like_count", "comment_count", "taken_at" }], "next_max_id": "...", "more_available": true }`

Pagination : passer `max_id` de la reponse precedente.

### Timeline (feed)

```
POST /api/v1/feed/timeline/
Body: is_pull_to_refresh=0&reason=cold_start_fetch
```

Reponse : `{ "feed_items": [{ "media_or_ad": { ... } }], "next_max_id": "..." }`

**Attention** : cet endpoint est POST, pas GET (retourne 405 en GET).

### Recherche de sons

```
POST /api/v1/music/search/
Body: q=<query>&search_surface=clips_music_search&count=20
```

Reponse : `{ "items": [{ "track": { "id", "title", "subtitle", "cover_artwork_uri",
"progressive_download_url", "duration_in_ms" } }] }`

Le champ `progressive_download_url` contient l'URL de preview du son (jouable directement).

### Sons tendance

Meme endpoint sans query :

```
POST /api/v1/music/search/
Body: q=&search_surface=clips_music_search&count=30
```

### Mon profil (stats)

```
GET /api/v1/accounts/current_user/?edit=true
```

Reponse : `{ "user": { "pk", "username", "follower_count", "following_count", "media_count", ... } }`

### Insights (comptes pro)

```
GET /api/v1/insights/account_organic_insights/?ig_user_id=<pk>&interval=week
```

Disponible uniquement pour les comptes professionnels/createurs.

---

## 5. Integration backend

### Service : `app/services/ig_api.py`

```python
from app.services.ig_api import IGApiClient

# Depuis un compte_id
client = await IGApiClient.from_compte(db, compte_id)

# Recherche
users = await client.search_users("nike")

# Profil
profile = await client.get_user_info(25025320)

# Publications
feed = await client.get_user_feed(25025320, count=12)

# Sons
tracks = await client.search_music("drake")

# Verification de session
status = await client.verify()
```

### Routes : `app/api/ig_proxy.py`

| Route | Methode | Usage |
|-------|---------|-------|
| `/api/ig/search/users?q=&compte_id=` | GET | Autocomplete comptes |
| `/api/ig/user/{pk}?compte_id=` | GET | Profil utilisateur |
| `/api/ig/user/{pk}/feed?compte_id=` | GET | Publications |
| `/api/ig/feed?compte_id=` | POST | Timeline |
| `/api/ig/music/search?q=&compte_id=` | GET | Recherche sons |
| `/api/ig/music/trending?compte_id=` | GET | Sons tendance |
| `/api/ig/stats/{pk}?compte_id=` | GET | Stats du compte |
| `/api/ig/stats/{pk}/insights?compte_id=` | GET | Insights (pro) |
| `/api/ig/session/verify?compte_id=` | GET | Verification session |

Chaque appel necessite un `compte_id` pour identifier la session IG a utiliser.
La session est mise en cache dans `compte.env.ig_session` apres la premiere extraction.

---

## 6. Ou utiliser quoi dans le frontend

| Module | Endpoint | Usage |
|--------|----------|-------|
| **Veille** | `search/users` | Autocomplete pour cibler un compte |
| **Veille** | `user/{pk}` | Fiche du compte cible |
| **Veille** | `user/{pk}/feed` | Scanner les publications du compte |
| **Targets** | `search/users` | Trouver un compte de reference |
| **Posting** | `music/search` | Mediatheque de sons (recherche) |
| **Posting** | `music/trending` | Sons tendance |
| **Statistiques** | `stats/{pk}` | KPIs de nos comptes |
| **Statistiques** | `stats/{pk}/insights` | Insights detailles |
| **Comptes** | `session/verify` | Verifier qu'un compte est actif |
| **Partout** | `search/users` | Toute barre de recherche IG |

---

## 7. Limites et precautions

- **Rate limits** : IG impose des limites (~200 requetes/heure par session).
  Le backend devrait implementer un throttle par compte_id.
- **Session expiration** : les Bearer tokens expirent apres ~90 jours.
  ScaleTweak re-extrait a chaque lancement d'IG.
- **Comptes prives** : les publications d'un compte prive ne sont pas visibles
  sauf si le compte utilise pour la requete le suit.
- **Insights** : uniquement disponibles pour les comptes pro/createur.
  Les comptes personnels retournent 400/403.
- **Ne pas abuser** : ces endpoints sont pour la lecture. Les actions (follow, like, comment)
  necessitent un csrftoken et sont faites via l'automation UI (MCP + HumanTouch).

---

## 8. Troubleshooting

### Session invalide (401)

Le Bearer token a expire. Solutions :
1. Ouvrir IG sur l'iPhone (ScaleTweak re-extrait apres 15s)
2. Relancer une extraction : `ssh root@<ip> 'cat /tmp/scale_session.json'`
3. Si le compte est deconnecte, relancer un login automation

### Checkpoint (400)

IG demande une verification. Le compte doit passer le challenge manuellement
ou via l'automation (MCP). Pas de solution API pure.

### 429 Too Many Requests

Rate limited. Attendre 1h ou utiliser un autre compte pour les requetes.

### Pas de session disponible

Le compte n'a pas de session extraite. Verifier :
1. L'iPhone est en ligne et le tunnel SSH fonctionne
2. IG a ete lance au moins une fois sur ce container
3. Le fichier `/tmp/scale_session.json` existe sur l'iPhone
