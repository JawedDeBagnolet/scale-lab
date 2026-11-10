# Guide technique — Infrastructure iPhone Scale Lab

Comment chaque composant fonctionne, pourquoi il existe, et comment ils
s'articulent pour produire une session d'automatisation indistinguable
d'un usage humain reel.

---

## Vue d'ensemble : la chaine complete

```
Backend FastAPI (VPS)
  |
  |  JSON-RPC via tunnel SSH (port 8190 → iPhone 8090)
  v
ios-mcp (SpringBoard)          ← serveur MCP, 47 outils
  |
  |  IOHIDEvent dispatch (postHIDEvent:error:)
  v
RealTouchInject (SpringBoard)  ← enrichit force 3D Touch + radius + motion
  |
  |  IOKit → UIKit
  v
Instagram / Threads (app)      ← recoit des UITouch avec force=0.35, radius=24.2
  |                               + CMDeviceMotion avec posture realiste
  |
  |  Donnees lues par l'app (UITouch.force, CMMotionManager, etc.)
  v
Serveurs Meta                  ← voient un appareil reel, gestes humains, capteurs actifs
```

En parallele :

```
ScaleTweak (dans l'app IG/Threads)
  ├── Isole le filesystem par container (chaque compte = son propre "telephone")
  ├── Spoofe 94+ valeurs d'identite (IDFV, serial, MAC, carrier, etc.)
  ├── Isole le keychain (sessions, tokens, cookies par compte)
  ├── Bypass la detection JB (fishhook + ObjC hooks)
  ├── Simule la batterie (decharge realiste par session)
  ├── Detecte les challenges IG (checkpoint, rate_limit, spam)
  └── Extrait les sessions (cookies + Bearer tokens) pour l'API privee
```

---

## 1. ios-mcp — Le serveur MCP (fondation)

**Quoi :** Fork de `witchan/ios-mcp`, tweak Substrate charge dans SpringBoard.
**Port :** 8090 (iPhone), tunnel vers 8190 (VPS)
**Source :** `~/ios-mcp-fork/`

### Pourquoi il existe

C'est le seul point d'entree pour piloter l'iPhone. Tout passe par lui : taps, swipes,
lecture de l'arbre d'accessibilite, screenshots, lancement d'apps, saisie clavier.

### Comment il marche

1. Demarre un serveur HTTP dans SpringBoard au boot
2. Recoit des requetes JSON-RPC sur `POST /mcp`
3. Format : `{"jsonrpc":"2.0","method":"tools/call","params":{"name":"<outil>","arguments":{...}},"id":1}`
4. Execute l'action demandee via IOKit (touch), Accessibility (UI tree), ou les APIs systeme

### Les outils qu'on utilise dans nos scripts

| Outil MCP | Utilise par | Fonction |
|-----------|------------|----------|
| `tap_screen` | `human_touch.py` → `tap()` | Tap a des coordonnees x,y |
| `drag_and_drop` | `human_touch.py` → `swipe()`, `drag()` | Geste multi-points (scrolls, swipes) |
| `get_ui_elements` | `human_touch.py` → `get_elements()` | Arbre d'accessibilite (detection d'ecrans, elements) |
| `get_screen_info` | `human_touch.py` → `_ensure_screen()` | Dimensions ecran |
| `type_text` | `human_touch.py` → `type_text()` | Saisie clavier caractere par caractere |
| `input_text` | `th_iphone/` | Placer du texte dans un champ (sans animation) |
| `launch_app` | `human_touch.py` → `launch_app()` | Ouvrir une app par bundle ID |
| `kill_app` | `human_touch.py` → `terminate_app()` | Fermer une app |
| `screenshot` | debug, verification | Capture d'ecran base64 PNG |
| `ocr_screen` | `ig_driver.py`, `th_driver.py` | OCR de l'ecran |
| `get_frontmost_app` | `device_session.py` | App au premier plan |
| `run_command` | `session_extract.py` | Commande shell sur iPhone |
| `tap_element` | `device_session.py` (fallback) | Tap un element par son texte |

### Comment le touch fonctionne (HIDManager.m)

Quand `tap_screen` est appele :
1. Cree 3 `IOHIDEventCreateDigitizerFingerEvent` : began → moved → ended
2. Chaque event a `force=0.0` et `radius=0.04` (valeurs quasi-nulles)
3. Dispatch via `IOHIDEventSystemClientDispatchEvent` → SpringBoard → UIKit → app
4. **C'est ici que RealTouchInject intervient** pour enrichir les valeurs

### IMPORTANT : `perform_action` n'existe pas

Le backend Python (`human_touch.py` ligne 168) appelle `perform_action` mais cet outil
n'existe pas dans ios-mcp. Le vrai nom est `tap_screen`. C'est un bug du portage
VPS → FastAPI. A corriger dans `human_touch.py`.

De meme, `terminate_app` dans le code devrait etre `kill_app`.

---

## 2. RealTouchInject — Enrichissement des touches

**Quoi :** Tweak Substrate v9 "scroll", charge dans SpringBoard + Instagram
**Port :** 8195 (iPhone), HTTP pour API optionnelle
**Source :** `~/Downloads/RealTouchInject.m` (686 lignes, 31KB)

### Pourquoi il existe

Sans lui, chaque tap MCP arrive dans Instagram avec `force=0.006` et `radius=0.0` —
des valeurs impossibles pour un vrai doigt sur un iPhone X avec 3D Touch. Instagram
pourrait detecter que les touches sont synthetiques.

### Comment il marche

#### A. Enrichissement des taps (automatique, transparent)

1. **Interception** : Hook sur `postHIDEvent:error:` dans SpringBoard.
   Quand un event HID passe, RealTouchInject le detecte et active l'enrichissement.

2. **Memoire partagee** : Via `mmap` sur `/tmp/rti_shared_state_v2`, SpringBoard
   ecrit les parametres d'enrichissement, Instagram les lit.

3. **Swizzles dans Instagram** :
   - `UITouch.force` → retourne notre force calibree au lieu de 0.006
   - `UITouch._pressure` → idem pour les lectures internes
   - `UITouch.majorRadius` → retourne 24.2pt (valeur reelle du capteur iPhone X)

4. **Force auto-calibree** :
   - Distribution gaussienne : mean=0.246, stdev=0.087
   - Quantifiee sur les 22 paliers reels du capteur 3D Touch :
     `[0, 0.017, 0.067, 0.117, 0.167, 0.183, 0.217, 0.233, 0.267, 0.283,
      0.300, 0.317, 0.333, 0.350, 0.367, 0.383, 0.400, 0.417, 0.450, 0.467, 0.500, 0.517]`
   - Rampe realiste : began ≈ 40% du peak, moved = peak, ended ≈ 80% du peak
   - Clampe entre 0.067 et 0.517 (range observe)

5. **Radius** : 24.2pt constant — c'est la valeur fixe du capteur de l'iPhone X.
   Sur la phase "ended", le radius passe a 0 (le doigt se leve).

#### B. Enrichissement des scrolls (v9)

Les scrolls (qui durent 600-1800ms) ont un profil de force different des taps :
- Force progressive : 0.117 → 0.383 sur la duree du scroll
- Pas de rampe start/peak/end — c'est une montee continue
- Radius constant a 24.2pt pendant tout le scroll
- La memoire partagee communique le type de geste (`gestureType`: tap vs scroll)
  et la duree du geste (`gestureDurMs`) pour adapter le profil

#### C. Simulation de mouvement (CMMotionManager)

Instagram utilise `AuthenticityAccelerometerPlugin` pour verifier que le telephone
est tenu par un humain (micro-tremblements, orientation). Un telephone pose a plat
et parfaitement immobile pendant l'automatisation serait suspect.

**5 profils de posture** calibres sur des captures reelles :

| Posture | Gravity (x, y, z) | Bruit (stdev) | Quand |
|---------|--------------------|---------------|-------|
| assis | (0.062, -0.952, -0.245) | 0.008 | Tel tenu, assis |
| dos | (-0.01, -1.0, -0.01) | 0.005 | Allonge sur le dos |
| cote | (-0.65, -0.73, 0.10) | 0.012 | Sur le cote |
| debout | (0.08, -0.92, -0.32) | 0.015 | Debout, plus de mouvement |
| bureau | (0.05, -0.40, -0.90) | 0.006 | Pose sur un bureau |

**Swizzles motion :**
- `CMDeviceMotion.gravity` → vecteur de gravite spoofed + micro-tremblements gaussiens
- `CMAccelerometerData.acceleration` → correlation tap-y ↔ amplitude mouvement
  (taper en haut de l'ecran = 3x plus de mouvement qu'en bas — observe sur vrais gestes)

**Posture aleatoire** a chaque demarrage de session. Changeable via `POST /posture`.

#### D. API HTTP (port 8195, optionnelle)

| Endpoint | Usage |
|----------|-------|
| `GET /health` | Etat du tweak, compteurs, posture active |
| `POST /tap {"x","y"}` | Tap enrichi (force auto-randomisee) |
| `POST /tap {"x","y","force":0.3}` | Tap avec force specifique |
| `POST /scroll {"duration":1200}` | Signaler un scroll en cours |
| `POST /posture` | Changer de posture (random) |
| `POST /posture {"id":3}` | Forcer une posture |

**En usage normal, l'API n'est pas necessaire.** L'enrichissement est automatique
pour tout ce qui passe par `postHIDEvent` (= tout ce que le MCP fait).

---

## 3. ScaleTweak — Containerisation et anti-fingerprint

**Quoi :** Tweak Substrate v5, charge dans Instagram (et Threads)
**Source :** `~/Desktop/ScaleTweak_v5_antifp_final/ScaleTweak/Tweak.x` (1591 lignes)
**CLI :** `scalectl` (sur iPhone, `/var/jb/usr/local/bin/scalectl`)

### Pourquoi il existe

Un seul iPhone physique doit pouvoir heberger N comptes Instagram/Threads sans que
Meta puisse les relier entre eux. Chaque compte vit dans son propre "container" avec :
- Son propre filesystem (Documents, Library, Caches)
- Son propre keychain (sessions, tokens, cookies)
- Sa propre identite materielle (IDFV, serial, MAC, etc.)
- Son propre operateur, timezone, locale
- Son propre proxy reseau (optionnel)

### Comment il marche

Au lancement d'Instagram, ScaleTweak :

1. **Lit la config** depuis `/var/jb/var/mobile/Library/Preferences/com.scale.tweak.plist`
2. **Identifie le container actif** pour ce bundle (le dernier `scalectl --switch`)
3. **Redirige le filesystem** : NSHomeDirectory, Documents, Library, Caches → dossier du container
4. **Cree les symlinks** si premier lancement du container
5. **Restaure les preferences** (NSUserDefaults, CFPreferences) depuis le cache du container
6. **Genere les valeurs d'identite** de facon deterministe depuis l'UUID du container (SHA256)
7. **Installe les hooks** : fishhook (C) + %init (ObjC)
8. **Restaure les cookies de session** sauvegardees
9. **Synchronise le SSO** IG → Threads si necessaire
10. **Demarre la sauvegarde periodique** (preferences toutes les 30s)
11. **Extrait la session** apres 15s (keychain → `/tmp/scale_session.json`)

### Ce qui est spoofe (par categorie)

#### Identite (deterministe par container UUID)
- **IDFV** — identifiant unique par vendor (le plus important pour Meta)
- **IDFA** — identifiant publicitaire
- **Numero de serie** — 12 caracteres alphanumeriques
- **Platform UUID** — UUID IOKit
- **MACs** — WiFi, Bluetooth, Ethernet (format XX:XX:XX:XX:XX:XX)
- **BSSID/SSID** — nom du reseau WiFi (ex: "Freebox-A7F3E2")
- **Nom d'appareil** — "iPhone de [prenom francais aleatoire]"
- **Hostname**
- **User-Agent** — headers HTTP Instagram

#### Reseau
- **Operateur** — nom + MCC/MNC (ex: Free Mobile, 208/15)
- **Proxy SOCKS** — par container (injecte via CFNetworkCopySystemProxySettings)
- **Interfaces VPN** — masquees (utun/ipsec/ppp filtrees de getifaddrs)

#### Systeme
- **Boot time** — offset aleatoire
- **Memoire** — ±2 GB de jitter
- **Coeurs CPU** — 4 a 6 (randomise)
- **Espace disque** — ±3 GB d'offset
- **Timezone, Locale** — par geo-profil (FR, US, BR, ES, IT, GB, DE)

#### Batterie (simulation realiste)
- Charge nocturne : 95-100% au matin
- Decharge en veille : -0.8 à -1.5% par heure
- Decharge en session : -3 à -5% par heure
- Sauvegardee toutes les 60s, persistee entre les sessions

#### Bypass detection JB
- `opendir/access/stat/lstat/fopen` → ENOENT pour tous les chemins JB
- `dlopen` → bloque les librairies JB
- `getenv` → masque DYLD_INSERT_LIBRARIES
- `_dyld_image_count/_dyld_get_image_name` → masque les tweaks charges
- `NSFileManager.fileExistsAtPath` → masque /var/jb, /var/mobile/Library/Preferences, etc.
- `UIApplication.canOpenURL` → bloque cydia:/sileo:/zebra:/filza:

#### Isolation keychain
- Tous les appels `SecItemAdd/CopyMatching/Update/Delete` sont scopes avec le prefix `_sc_{uuid}_`
- Les groupes partages Meta (platformFamily, shared, MachineID, familydeviceid) aussi
- Chaque container a ses propres sessions, tokens, et cookies

### Gestion des containers (scalectl)

```bash
scalectl --list com.burbn.instagram          # Lister
scalectl --create com.burbn.instagram "compte1" FR   # Creer (geo: FR)
scalectl --switch com.burbn.instagram <uuid>         # Activer
scalectl --delete com.burbn.instagram <uuid>         # Supprimer
scalectl --inject com.burbn.instagram <uuid> session.json  # Injecter session
scalectl --status                                    # Vue globale
```

**Geo-profils disponibles** : FR, US, BR, ES, IT, GB, DE — chacun avec timezone,
locale, MCC, et 3-4 operateurs avec MNC.

### Detection de challenges

ScaleTweak monitore les reponses HTTP d'Instagram pour detecter :
- `challenge_required` — verification necessaire
- `checkpoint_required` — checkpoint de securite
- `login_required` — session expiree
- `feedback_required` — feedback necessaire
- `suspicious_activity` — activite suspecte
- `spam` — detection de spam
- `rate_limit` — limite de debit

Chaque detection est loguee dans `/tmp/scale_alerts.log` avec timestamp et URL.

### Extraction de session

15 secondes apres le lancement, ScaleTweak extrait automatiquement :
- **Bearer token** (format IGT:2:) depuis le keychain
- **Mid header** depuis le keychain
- **Cookies** (sessionid, csrftoken, ds_user_id) depuis NSHTTPCookieStorage

Ecrit dans `/tmp/scale_session.json`. Utilise par le backend pour les appels API privee.

### SSO cross-app (IG → Threads)

Quand un container IG se connecte, ScaleTweak :
1. Copie les cles d'auth IG vers le container Threads
2. Ecrit `last_logged_in_user_pk` et `bcn_last_logged_in_threads_igid`
3. Ecrit dans le plist du shared AppGroup pour que Threads reconnaisse la session

---

## 4. MTOUCH — Multi-touch et import media

**Quoi :** Tweak Substrate, charge dans SpringBoard
**Port :** 8091 (iPhone) → 8191 (VPS)
**Source :** `~/mtouch-tweak/Tweak.x` (302 lignes)

### Pourquoi il existe

Le MCP standard ne supporte que les gestes a un doigt. Pour les stories IG
(pinch to zoom, rotation), il faut deux doigts simultanement. MTOUCH ajoute aussi
l'import de medias dans la galerie Photos.

### Comment il marche (multi-touch)

1. Quand un pinch/rotate est demande, MTOUCH met un flag `_addSecondFinger = YES`
2. Il positionne les coordonnees du second doigt
3. Il appelle `performTouchAtPoint:phase:error:` sur le `IOSMCPHIDManager` de ios-mcp
4. Le hook sur `postHIDEvent:error:` detecte le flag et ajoute un second
   `IOHIDEventCreateDigitizerFingerEvent` (finger index 2, identity 5) a l'event parent
5. iOS recoit un vrai geste deux doigts

### Endpoints

| Endpoint | Parametres | Usage |
|----------|-----------|-------|
| `POST /pinch` | `{cx, cy, scale, duration}` | Zoom in/out (scale > 1 = zoom in) |
| `POST /rotate` | `{cx, cy, angle, duration}` | Rotation en degres |
| `POST /tap` | `{x, y}` | Tap simple (passe par le MCP manager) |
| `POST /import` | `{path}` | Importer un fichier dans Photos |
| `GET /health` | — | Health check |

### Import media

`POST /import {"path": "/tmp/photo.jpg"}` utilise `PHPhotoLibrary` pour importer
une image ou video dans le Camera Roll. Supporte : mp4, mov, m4v (video) et tous
les formats image.

---

## 5. Pipeline media — Du cloud a la galerie iPhone

### Le probleme

Pour publier sur IG/Threads, les medias doivent etre dans le Camera Roll de l'iPhone.
Mais les medias sont stockes sur Cloudflare R2 (cloud). Et les metadata EXIF doivent
etre coherentes avec l'identite du container (GPS, modele d'appareil, date).

### La chaine complete

```
R2 (Cloudflare)
  |  HTTP download
  v
Spoof Server (VPS port 8502)
  |  Modifie les metadata EXIF :
  |  - GPS : coordonnees coherentes avec le marche (FR, US, BR...)
  |  - Modele : iPhone X (ou le modele du container)
  |  - Date : recente et realiste
  |  - Orientation, software, etc.
  v
SCP vers iPhone
  |  Le fichier atterrit dans /tmp/ sur l'iPhone
  v
Import dans Photos
  |  Via MTOUCH POST /import
  |  Ou via importmedia CLI (/var/jb/usr/bin/importmedia)
  |  Ou via GalleryService (port 8192)
  v
Camera Roll
  |  Le media apparait comme une "vraie photo"
  v
Instagram/Threads
  |  L'app le voit dans la galerie, l'utilisateur le selectionne pour publier
```

### Trois methodes d'import

| Methode | Comment | Quand |
|---------|---------|-------|
| **MTOUCH** `/import` | `POST http://iPhone:8091/import {"path":"/tmp/photo.jpg"}` | Methode principale |
| **importmedia** CLI | `ssh root@iPhone 'importmedia /tmp/photo.jpg'` | Fallback |
| **GalleryService** | `POST http://iPhone:8192/import` + `/delete` | Version avancee avec suppression |

### Nettoyage apres publication

Apres la publication, les medias importes sont supprimes du Camera Roll :
- Via GalleryService `POST /delete` (supprime les N photos les plus recentes)
- Ou via un script SQLite qui modifie directement `PhotoData/Photos.sqlite`

### Spoof server EXIF

Le serveur tourne sur le VPS (port 8502). Il recoit l'URL du media original et
les parametres du container, et retourne le fichier avec les metadata modifiees :

```
GET http://77.42.124.107:8502/spoof?url=<R2_url>&market=FR&device=iPhone10,6&phone_id=<uuid>
```

---

## 6. Extraction de sessions — API privee IG/Threads

### Pourquoi extraire les sessions

Les sessions (cookies + tokens) permettent d'utiliser l'API privee Instagram/Threads
sans passer par l'UI de l'app. Utile pour :
- Verifier le statut d'un compte (actif, checkpoint, suspendu)
- Lire les stats sans naviguer dans l'app
- Operations en masse (like, follow) via l'API directe

### Methode 1 : ScaleTweak (automatique)

15s apres le lancement d'IG, ScaleTweak extrait automatiquement :
- Bearer token (IGT:2:) depuis le keychain
- Mid header
- Cookies (sessionid, csrftoken, ds_user_id)

Ecrit dans `/tmp/scale_session.json`. Le backend peut lire ce fichier via SSH.

### Methode 2 : session_extract.py (via MCP)

```python
# Lit les cookies depuis le plist sur l'iPhone via MCP run_command
cookies = await extract_session(mcp_port)
# Verifie le statut via l'API privee
status = await check_account_status(cookies)
# Retourne : sessionid, csrftoken, ds_user_id, mid, ig_did, user_agent
```

Utilise `run_command` pour lire :
- `/var/mobile/Library/Cookies/Cookies.binarycookies`
- Le plist de preferences IG

Puis verifie le compte via `GET https://i.instagram.com/api/v1/feed/timeline/`
avec les cookies extraits.

### Methode 3 : ig_cookie_dump.m (CLI sur iPhone)

Programme standalone qui lit directement le keychain iOS :
- `SecItemCopyMatching` pour les groupes d'acces IG
- Extrait : sessionid, csrftoken, ds_user_id

### Methode 4 : IGCookieDump.m (tweak dans IG)

Tweak charge dans le process Instagram. Traverse l'object graph interne :
`_appCoordinator → _userSession → authHeaderManager → networker → user`
Dump dans `/tmp/ig_cookies.json`.

### Methode 5 : ig_extract.js (Frida)

Script Frida execute dans le process IG :
- Navigate : `session → authHeaderManager → _authHeaderStore → _authHeaders`
- Extrait les Bearer tokens (IGT:2:) et user pk/username

### Methode 6 : ThreadsTokenDump (tweak dans Threads)

Tweak charge dans le process Threads. Traverse :
`UIApplication.delegate → _appCoordinator → _sessionManager → _authenticator`
Dump toutes les proprietes string des objets auth dans `/tmp/threads_dump.json`.

---

## 7. TouchCapture — Enregistrement de vrais gestes

**Quoi :** Tweak de debug/calibration, charge dans SpringBoard
**Port :** 8193 (iPhone)
**Source :** `~/Downloads/TouchCapture.m` (14KB)

### Pourquoi il existe

Pour calibrer RealTouchInject, on a besoin de savoir a quoi ressemblent de VRAIS
gestes humains : quelle force, quel radius, quel profil de mouvement par posture.

### Comment il marche

1. Hook sur `UIWindow sendEvent:` pour intercepter tous les UITouch
2. Enregistre pour chaque touch : position, force, radiusX/Y, phase, timestamp
3. Enregistre en parallele : accelerometre + gyroscope via CMMotionManager
4. Stocke tout en memoire pendant la capture

### API

| Endpoint | Usage |
|----------|-------|
| `POST /start` | Demarrer la capture |
| `POST /stop` | Arreter |
| `POST /clear` | Vider les donnees |
| `GET /status` | Statut (capturing, count) |
| `GET /data` | Recuperer le JSON complet |

### Captures existantes (sur le Mac)

6 fichiers de captures multi-posture dans `~/Downloads/` :
- `touch_capture.json` (1.5M) — capture initiale
- `capture_assis.json` (280K)
- `capture_dos.json` (732K)
- `capture_cote.json` (735K)
- `capture_debout.json` (366K)
- `capture_bureau.json` (532K)

Ces donnees ont servi a calibrer les 22 paliers de force, le radius 24.2pt,
les 5 profils de posture, et la correlation tap-y ↔ amplitude mouvement.

---

## 8. Scripts Frida — Debug et reverse engineering

### SSL Unpinning (`frida_ssl_unpin.js`)

Desactive le SSL pinning dans les apps Meta :
- Hook `SSL_CTX_set_custom_verify` / `SSL_set_custom_verify` → callback retourne 0
- Hook `SSL_CTX_set_verify` → SSL_VERIFY_NONE
- Hook `SecTrustEvaluateWithError` → retourne true

Permet d'intercepter le trafic HTTPS avec mitmproxy.

### Capture de headers (`frida_capture_headers.js`)

Hook 5 couches pour capturer TOUS les headers HTTP sortants :
1. `NSMutableURLRequest.setValue:forHTTPHeaderField:` (ObjC)
2. `CFHTTPMessageSetHeaderFieldValue` (CoreFoundation)
3. Classes Meta internes (Tigon, IGAPIRequest)
4. `NSURLSession.dataTaskWithRequest:` (dump complet)
5. `IGNetworker` + interceptors

Sauvegarde chaque requete dans `/tmp/th_request_N.json`.

### Capture GraphQL doc_ids (`frida_graphql_docids.js`)

Hook les constructeurs de requetes GraphQL pour capturer les `persist_ids`
(identifiants des queries internes Meta) :
- `IGGraphQLRequest.initRequestWithQueryId:queryName:`
- `PNPandoGraphQLRequest.initWithPersistID:queryLabel:`

Sauvegarde dans `/tmp/th_graphql_ids.json`.

### Verification force (`verify_force.js`)

Hook `UITouch.force` dans Instagram pour verifier que RealTouchInject fonctionne :
- Sans enrichissement : force ≈ 0.006
- Avec enrichissement : force ≈ 0.35

---

## 9. Scripts Python backend — Le cerveau

### Architecture des couches

```
ig_runner.py / th_runner.py          ← Dispatch des taches (login, feed, post...)
  |
  v
ig_driver.py / th_driver.py         ← Navigation UI haut niveau
  |
  v
scroll_engine.py                    ← Scrolling calibre avec feedback
  |
  v
human_touch.py                      ← Wrapper MCP low-level
  |
  v
dispatch.py                         ← Transport HTTP (httpx → JSON-RPC)
  |
  v
ios-mcp (iPhone)                    ← Execution
```

### human_touch.py — Le realisme des gestes

C'est ici que les gestes deviennent "humains" :

**Taps :**
- Position : jitter gaussien dans les bounds de l'element (sigma = 1/4 de l'etendue)
- Duree : 50-120ms (distribution aleatoire)
- Jamais exactement au centre d'un bouton

**Scrolls :**
- Distance : 40-85% de la hauteur d'ecran (IG feed)
- Duree : 600-1800ms
- Derive laterale : 5-25% de la largeur
- Trajectoire courbe (arc perpendiculaire + bruit gaussien par point)
- Ease-out : deceleration progressive
- 4 points de maintien a la fin (zero-velocity → pas d'inertie iOS)

**Pauses :**
- Lecture : ~250 mots/minute avec jitter
- Entre actions : distribution log-normale

### device_session.py — Orchestration

Context manager async qui gere le cycle de vie d'une session :

1. Lock du device (un seul runner par iPhone physique)
2. Switch du container ScaleTweak via SSH → `scalectl --switch`
3. Kill de l'app (killall)
4. Relaunch (uiopen)
5. Detection de l'ecran de verrouillage (marqueurs FR)
6. Login si necessaire
7. Execution du runner
8. Kill de l'app a la fin
9. Release du lock

---

## 10. Ordre de reinstallation apres restauration

| # | Tweak | Pre-compile ? | Commande |
|---|-------|--------------|----------|
| 1 | **ios-mcp** | Oui (.dylib) | `scp` + `ldid` + `sbreload` |
| 2 | **ScaleTweak** | Oui (.dylib + scalectl) | `scp` × 3 + `chmod` + `ldid` + `sbreload` |
| 3 | **RealTouchInject** | Non (compiler .m) | `xcrun clang` + `scp` + `ldid` + `sbreload` |
| 4 | **MTOUCH** | Oui (.deb) | `scp` + `dpkg -i` + `killall SpringBoard` |
| 5 | **Choicy** | Via Sileo/Cydia | Installer le package |
| 6 | **TouchCapture** | Non (compiler .m) | Optionnel, debug uniquement |
| 7 | **ThreadsTokenDump** | Oui (.deb) | Quand necessaire |
| 8 | **Frida** | Oui (.deb) | Quand necessaire |

### Prerequis sur le Mac

- Xcode CLI tools (`xcrun`, `otool`, `strings`)
- Theos (`~/theos/`)
- Python 3.11+ avec frida-tools
- SSH acces a l'iPhone (root/alpine)

### Prerequis sur l'iPhone

- Jailbreak palera1n rootless actif
- MobileSubstrate/Substitute fonctionnel
- `ldid` installe
- `sbreload` disponible
- SSH (port 22, root/alpine)
