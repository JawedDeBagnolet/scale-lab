# Guide complet — Outils et Tweaks iPhone pour Scale Lab

Ce document explique le fonctionnement de chaque outil, tweak et script
utilise pour l'automatisation iPhone (IG + Threads). Il couvre :
- L'architecture complete et comment les outils interagissent
- L'enrichissement des donnees envoyees a Meta
- Le pipeline media (spoofing EXIF, import galerie)
- L'extraction de sessions pour les APIs privees
- Les anti-patterns comportementaux
- La containerisation multi-comptes

---

## Vue d'ensemble — Architecture

```
                     VPS (77.42.124.107)
                     ┌──────────────────────────────────────────┐
                     │  FastAPI backend                         │
                     │    ├── ig_runner / th_runner   (dispatch) │
                     │    ├── IGDriver / THDriver     (UI haut)  │
                     │    ├── HumanTouch              (MCP wrap) │
                     │    ├── ScrollEngine            (scroll)   │
                     │    └── DeviceSession            (lock)    │
                     │                                          │
                     │  Spoof Server (:8502)                    │
                     │    └── EXIF metadata spoofing            │
                     │                                          │
                     │  Port 8190 ──────────┐                   │
                     │  Port 8191 ────────┐ │                   │
                     │  Port 2223 ──────┐ │ │                   │
                     └──────────────────┼─┼─┼───────────────────┘
                        Tunnel SSH      │ │ │
                     ┌──────────────────┼─┼─┼───────────────────┐
                     │  iPhone X (iOS 16.5, palera1n rootless)  │
                     │                  │ │ │                   │
                     │  :22 ← SSH ──────┘ │ │                   │
                     │  :8090 ← MCP ──────┘ │  ios-mcp.dylib    │
                     │  :8091 ← MTOUCH ─────┘  mtouch.dylib     │
                     │  :8192 ← Gallery        GalleryService   │
                     │  :8193 ← Capture        TouchCapture     │
                     │  :8195 ← Touch          RealTouchInject  │
                     │                                          │
                     │  ScaleTweak    (containers + bypass JB)  │
                     │  Choicy        (bloquer tweaks par app)  │
                     └──────────────────────────────────────────┘
```

### Chaine d'un tap

```
Python: runner → driver → HumanTouch._call("tap_screen", {x, y})
  → dispatch.mcp_call("tools/call", {"name":"tap_screen","arguments":{x,y}})
    → HTTP POST http://127.0.0.1:8190/mcp (tunnel SSH)
      → ios-mcp.dylib reçoit et cree un IOHIDEvent via HIDManager
        → postHIDEvent: dispatch l'event au systeme
          → RealTouchInject intercepte via hook postHIDEvent:
            → Active les swizzles force/radius dans la shared memory
              → Instagram lit UITouch.force → notre valeur (0.246 ± 0.087)
              → Instagram lit UITouch.majorRadius → 24.2pt
              → Instagram lit CMDeviceMotion.gravity → notre posture spoofee
```

---

## 1. ios-mcp — Serveur MCP (fondation)

**Port :** 8090 | **Source :** `~/ios-mcp-fork/` | **Type :** Tweak Substrate dans SpringBoard

Le serveur MCP est la fondation de toute l'automatisation. C'est un fork de
`witchan/ios-mcp` avec des ajouts custom (pinch/rotate). Il expose 47 outils
via JSON-RPC sur `POST /mcp`.

### Protocole d'appel

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "tap_screen",
    "arguments": {"x": 187, "y": 400}
  },
  "id": 1
}
```

**IMPORTANT :** Le JSON-RPC method est toujours `tools/call` avec le nom de
l'outil dans `params.name`. Appeler directement `tap_screen` comme method
retourne `"Method not found"`.

### Outils par categorie

**Gestes tactiles :**
- `tap_screen {x, y}` — tap simple aux coordonnees
- `tap_element {text, match?}` — tap sur un element par texte (accessibility tree)
- `swipe_screen {fromX, fromY, toX, toY, duration, steps}` — swipe
- `drag_and_drop {points:[{x,y},...], hold_duration, move_duration, steps}` — geste multi-points
- `long_press {x, y, duration}` — appui long
- `double_tap {x, y}` — double tap
- `pinch_screen {cx, cy, scale, duration}` — pinch deux doigts (fork custom)
- `rotate_screen {cx, cy, angle, duration}` — rotation deux doigts (fork custom)

**Lecture d'ecran :**
- `get_ui_elements {clickable_only?, max_elements?}` — arbre d'accessibilite
- `get_element_at_point {x, y}` — element a une position
- `screenshot {}` — capture PNG en base64
- `ocr_screen {}` — reconnaissance de texte
- `describe_screen {}` — description textuelle de l'ecran
- `get_screen_info {}` — dimensions (375x812 sur iPhone X)

**Saisie :**
- `input_text {text}` — remplacer le texte du champ focus
- `type_text {text, interval?}` — taper caractere par caractere (plus realiste)
- `press_key {key}` — touche specifique (delete, return, etc.)

**Applications :**
- `launch_app {bundle_id}` — lancer une app (reveille l'ecran si verrouille)
- `kill_app {bundle_id}` — forcer la fermeture
- `list_apps {type?}` — lister les apps installees
- `get_frontmost_app {}` — app au premier plan

**Systeme :**
- `run_command {command, timeout?}` — executer une commande shell
- `read_file / write_file` — lire/ecrire des fichiers
- `get_clipboard / set_clipboard` — presse-papiers
- `open_url {url}` — ouvrir une URL

### Comment le MCP gere les touches (HIDManager.m)

Quand `tap_screen` est appele, le HIDManager :
1. Cree un `IOHIDEventCreateDigitizerEvent` (parent, type "Hand")
2. Cree un `IOHIDEventCreateDigitizerFingerEvent` (enfant, un doigt)
3. Definit force=0.0, radius=0.04 (valeurs brutes quasi-nulles)
4. Appelle `postHIDEvent:` pour dispatcher au systeme
5. Enchaine 3 phases : began → moved → ended

**C'est ici que RealTouchInject intervient** — il intercepte le `postHIDEvent:`
pour enrichir ces valeurs avec des donnees realistes.

---

## 2. RealTouchInject — Enrichissement 3D Touch + Motion

**Port :** 8195 | **Source :** `~/Downloads/RealTouchInject.m` (v8) | **Filtre :** SpringBoard + Instagram

### Pourquoi c'est necessaire

Sans RealTouchInject, les taps MCP arrivent dans Instagram avec `force=0.006`
et `radius=0`. Un vrai doigt sur l'ecran 3D Touch de l'iPhone X produit
`force=0.246` et `radius=24.2pt`. Instagram peut potentiellement detecter
cette anomalie via son `AuthenticityAccelerometerPlugin`.

### Comment ca marche — 3 mecanismes

#### A. Hook postHIDEvent (SpringBoard)

Quand le MCP dispatch un event HID, RealTouchInject detecte que c'est un tap
automatise et prepare les valeurs d'enrichissement :

```objc
// Genere une force aleatoire calibree sur des captures reelles
double peakForce = gaussian(mean=0.246, stdev=0.087);
// Quantifiee sur les 22 paliers reels du capteur 3D Touch
peakForce = snapToForceStep(peakForce);
// Ecrit dans la shared memory mmap
_shared->peakForce = peakForce;
_shared->startForce = peakForce * 0.4;  // debut = 40% du peak
_shared->radius = 24.2;                  // valeur constante du capteur
_shared->active = 1;                     // active les swizzles
```

#### B. Swizzles UITouch (Instagram)

Quand Instagram lit les proprietes d'un UITouch, nos swizzles retournent les
valeurs enrichies depuis la shared memory :

```objc
// UITouch.force → notre force au lieu de 0.006
// UITouch._pressure → idem
// UITouch.majorRadius → 24.2pt au lieu de 0

// Courbe de force par phase :
//   began  → startForce (40% du peak)
//   moved  → peakForce
//   ended  → 80% du peak, radius → 0
```

#### C. Swizzles Motion (Instagram)

Instagram utilise un `AuthenticityAccelerometerPlugin` et un pipeline custom
(`LiveAccelerometerMotionProvider → AccelerometerRecorder`) pour verifier
que le telephone est tenu par un humain. Sans motion, le telephone est
parfaitement immobile — suspect.

```objc
// CMDeviceMotion.gravity → vecteur de gravite spoofe par posture
// CMAccelerometerData.acceleration → micro-tremblements correles aux taps

// 5 postures calibrees sur des captures reelles :
//   assis  : gravity(0.06, -0.95, -0.25), bruit stdev=0.008
//   dos    : gravity(-0.01, -1.0, -0.01), bruit stdev=0.005
//   cote   : gravity(-0.65, -0.73, 0.10), bruit stdev=0.012
//   debout : gravity(0.08, -0.92, -0.32), bruit stdev=0.015
//   bureau : gravity(0.05, -0.40, -0.90), bruit stdev=0.006
```

La posture est choisie aleatoirement au lancement de la session.
Les taps en haut de l'ecran generent 3x plus de mouvement (le bras bouge
plus pour atteindre le haut de l'ecran).

### Communication inter-process

La shared memory est un fichier `mmap` (`/tmp/rti_shared_state_v2`) partage
entre SpringBoard (qui ecrit les valeurs) et Instagram (qui les lit).
La struct contient :

```c
typedef struct {
    volatile int    active;       // 1 = override actif
    volatile double peakForce;    // force peak
    volatile double startForce;   // force initiale
    volatile float  radius;       // radius (24.2)
    volatile int    phaseCounter; // compteur de phases
    volatile int    postureId;    // posture active (0-4)
    volatile float  lastTapY;     // position Y du dernier tap
    volatile int    tapCounter;   // compteur de taps
    volatile uint64_t tapTime;    // timestamp du dernier tap
} RTISharedState;
```

### Les 22 paliers de force du capteur 3D Touch

```
0.0, 0.017, 0.067, 0.117, 0.167, 0.183,
0.217, 0.233, 0.267, 0.283, 0.300, 0.317,
0.333, 0.350, 0.367, 0.383, 0.400, 0.417,
0.450, 0.467, 0.500, 0.517
```

Ces valeurs ont ete extraites de captures reelles avec TouchCapture.
Le capteur 3D Touch ne produit pas de valeurs continues — il quantifie
sur ces paliers. Envoyer une force de 0.35 exactement est suspect car
elle correspond a un palier. Notre code "snap" la force generee au palier
le plus proche.

### API HTTP (optionnelle — le mode auto suffit)

- `GET /health` — etat, posture, compteurs
- `POST /tap {"x","y"}` — tap enrichi manuellement
- `POST /posture {"id":3}` — forcer une posture

---

## 3. MTOUCH — Multi-touch (pinch/rotate/import media)

**Port :** 8091 | **Source :** `~/mtouch-tweak/` | **Filtre :** SpringBoard

### Pourquoi c'est necessaire

Le MCP standard ne fait que des gestes a un doigt. Pour les stories Instagram
(zoom, rotation de stickers) et les galleries (pinch to zoom), on a besoin
de gestes a deux doigts.

### Comment ca marche

MTOUCH se branche sur la methode `postHIDEvent:error:` de ios-mcp.
Quand un pinch ou rotate est demande :

1. MTOUCH place les coordonnees du second doigt dans ses variables
2. Active le flag `_addSecondFinger`
3. Appelle `performTouchAtPoint:phase:error:` de ios-mcp (le premier doigt)
4. Le hook `postHIDEvent:` intercepte l'event et ajoute un second
   `IOHIDEventCreateDigitizerFingerEvent` (finger index 2, identity 5)
5. iOS recoit un vrai geste deux doigts

### Endpoints

```
POST /pinch {"cx":187, "cy":400, "scale":1.5, "duration":300}
→ 30 etapes, expansion/contraction radiale depuis le centre

POST /rotate {"cx":187, "cy":400, "angle":45, "duration":300}
→ 30 etapes, mouvement circulaire de deux doigts opposes

POST /import {"path":"/var/mobile/Media/th_media/photo.jpg"}
→ PHPhotoLibrary import dans Camera Roll

GET /health
→ {"ok":true, "service":"mtouch"}
```

### Cas d'usage concrets

- **Stories IG** : placer un sticker, le redimensionner (pinch) et le tourner (rotate)
- **Galleries** : zoom sur les photos dans le feed
- **Import media** : apres un SCP, importer l'image dans Photos pour que IG la voie

---

## 4. ScaleTweak — Containerisation multi-comptes

**Source :** `~/Desktop/ScaleTweak_v5_antifp_final/ScaleTweak/`
**Filtre :** `com.burbn.instagram` (ajouter `com.burbn.barcelona` pour Threads)

### Le probleme

Un iPhone = une identite. Instagram voit le meme IDFV, serial number, MAC
address, etc. pour tous les comptes. Si un compte est banni, les autres
le sont aussi (ban "device-level").

### La solution

ScaleTweak cree des "containers" — chaque container a sa propre identite
deterministe generee a partir de son UUID via SHA256. Quand on switch de
container, l'iPhone **change d'identite completement** du point de vue d'IG.

### Ce qui est isole par container

**Identite device (deterministe par UUID) :**
- IDFV (identifierForVendor)
- IDFA (advertisingIdentifier)
- Serial number (12 caracteres)
- Platform UUID
- MAC WiFi, Bluetooth, Ethernet
- BSSID, SSID (nom ISP francais aleatoire)
- Nom d'appareil ("iPhone de [prenom francais]")
- Hostname, Timezone, Locale
- User-Agent Instagram
- Boot time (offset aleatoire)
- RAM, coeurs CPU, espace disque (jitter)
- Niveau de batterie (simulation de decharge realiste)

**Filesystem :**
- `NSHomeDirectory` → `/var/mobile/Documents/ScaleContainers/<uuid>/`
- Documents, Library, Caches → rediriges vers le container
- Group containers → scopes

**Keychain :**
- Tous les appels `SecItem*` sont prefixes par `_sc_{uuid}_`
- Les groupes partages Meta (platformFamily, shared, MachineID) → scopes
- Chaque container a ses propres cookies et tokens

**Reseau :**
- Proxy SOCKS per-container (injecte via `CFNetworkCopySystemProxySettings`)
- User-Agent per-container sur les requetes IG
- Interfaces VPN masquees

**NSUserDefaults :**
- Toutes les cles sont prefixees `_sc_{uuid}_`
- Session sauvegardee toutes les 30s
- Restauree au switch de container

### Bypass JB

ScaleTweak masque le jailbreak pour qu'Instagram ne le detecte pas :

- `opendir/access/stat/lstat/fopen` → ENOENT pour `/var/jb/`, `/var/lib/`, etc.
- `dlopen` → bloque les libs JB
- `_dyld_image_count` → ne compte que les dylibs "visibles" (exclut les tweaks)
- `NSFileManager.fileExistsAtPath` → masque les chemins JB
- `UIApplication.canOpenURL` → bloque `cydia://`, `sileo://`, etc.

### Detection de challenges

ScaleTweak surveille les reponses HTTP et ecrit dans `/tmp/scale_alerts.log`
si Instagram retourne :
- `challenge_required`
- `checkpoint_required`
- `login_required`
- `feedback_required`
- `suspicious_activity`
- `spam`
- `rate_limit`

### SSO cross-app (IG → Threads)

Quand on switch de container, ScaleTweak copie le storage auth IG vers
le container Threads correspondant :
- `last_logged_in_user_pk`
- `bcn_last_logged_in_threads_igid`
- Plist AppGroup partage

### scalectl — CLI de gestion

```bash
# Lister les containers Instagram
scalectl --list com.burbn.instagram

# Creer un nouveau container
scalectl --create com.burbn.instagram "cassie_ig" FR

# Switcher (tue l'app, switch, relance)
scalectl --switch com.burbn.instagram <uuid>

# Injecter une session (cookies + fingerprint + proxy)
scalectl --inject com.burbn.instagram <uuid> session.json

# Statut global
scalectl --status
```

Format du fichier d'injection (`session.json`) :
```json
{
  "session": {
    "sessionid": "...",
    "csrftoken": "...",
    "ds_user_id": "...",
    "mid": "...",
    "ig_did": "..."
  },
  "fingerprint": {
    "device_id": "...",
    "family_device_id": "...",
    "user_agent": "..."
  },
  "proxy": "socks5://user:pass@host:port"
}
```

---

## 5. Pipeline Media — Spoofing et import

### Le flow complet

```
R2 (Cloudflare)                    Spoof Server (:8502)
   │ URL du media                     │ spoof EXIF
   └──────────────────────────────────┘
                    │
                    │ curl -sL -o <path> <url>
                    v
              iPhone filesystem
              /var/mobile/Media/th_media/
                    │
                    │ POST /import {"path":"..."}
                    v
              GalleryService (:8192)
              PHPhotoLibrary → Camera Roll
                    │
                    │ IG/Threads ouvre Camera Roll
                    v
              Publication
                    │
                    │ POST /delete {"count":1}
                    v
              Suppression de la galerie (apres upload)
```

### Spoofing EXIF (VPS port 8502)

Le spoof server tourne sur le VPS et modifie les metadata EXIF des images
avant qu'elles n'arrivent sur l'iPhone :

- **GPS** : coordonnees coherentes avec le marche (FR, US, BR, etc.)
- **Device** : modele d'appareil photo coherent (iPhone, Samsung, etc.)
- **Date** : timestamp realiste (pas exactement "maintenant")
- **Software** : version d'app coherente

Appel : `GET /spoof?url=<url_media>&market=FR&device=<model>&phone_id=<id>`

Le `phone_id` permet de garder la coherence : le meme "telephone" produit
toujours les memes metadata EXIF (meme modele d'appareil, memes parametres).

### GalleryService (port 8192)

Tweak SpringBoard qui expose deux endpoints :

```
POST /import {"path":"/var/mobile/Media/th_media/photo.jpg"}
→ Importe dans la galerie via PHPhotoLibrary

POST /delete {"count": 1}
→ Supprime les N photos les plus recentes
```

La suppression apres publication est critique : sinon la galerie s'accumule
et IG pourrait voir des photos "identiques" a celles publiees par d'autres
comptes sur le meme appareil.

### Deux methodes de push

**Via MCP (recommande) :**
L'iPhone telecharge directement depuis le spoof server. Pas besoin de SCP.

```python
# iPhone telecharge directement (curl via MCP run_command)
driver.ht._call("run_command", {
    "command": 'curl -sL -o "/var/mobile/Media/th_media/photo.jpg" "http://spoof:8502/spoof?url=..."'
})
# Import dans la galerie
requests.post("http://192.168.1.133:8192/import", json={"path": "..."})
```

**Via SCP (pour les gros fichiers/videos) :**
Le VPS telecharge, spoofe, SCP vers l'iPhone, puis importe.

```python
# VPS telecharge et spoofe localement
# SCP vers iPhone
subprocess.run(["scp", local_path, "root@192.168.1.133:/var/mobile/Media/th_media/"])
# Import via importmedia CLI
ssh_exec("importmedia /var/mobile/Media/th_media/video.mp4")
```

---

## 6. Extraction de sessions — APIs privees IG/Threads

### Pourquoi extraire les sessions

Les sessions IG/Threads (cookies, tokens) permettent d'utiliser les APIs
privees Meta sans passer par l'interface graphique :
- Verifier le statut d'un compte (checkpoint, ban, rate limit)
- Lire les DMs
- Scraper des donnees (followers, engagement)
- Actions en masse (follow, unfollow, like)

### 3 methodes d'extraction

#### A. Via ScaleTweak (automatique)

ScaleTweak capture automatiquement les sessions :

1. **Cookies** : hook `NSHTTPCookieStorage` → ecrit dans `Library/session.json`
   du container actif
2. **Auth headers** : hook keychain → extrait le Bearer token `IGT:2:*`
   → ecrit dans `/tmp/scale_session.json`
3. **Mid header** : extrait du keychain → inclus dans le JSON

Format de sortie :
```json
{
  "sessionid": "123456789:abc...",
  "csrftoken": "xyz...",
  "ds_user_id": "123456789",
  "mid": "...",
  "ig_did": "...",
  "authorization": "Bearer IGT:2:..."
}
```

#### B. Via session_extract.py (MCP run_command)

Le script Python `session_extract.py` extrait les cookies en lisant
directement les plists du container Threads via MCP :

```python
# Trouve le container data de Threads
driver.ht._call("run_command", {
    "command": "find /var/mobile/Containers/Data/Application -maxdepth 1 ..."
})

# Lit le plist pour extraire les cles session/device/csrf
driver.ht._call("run_command", {
    "command": 'python3 -c "import plistlib,json;..."'
})
```

Puis verifie le statut du compte via l'API privee IG :

```python
headers = {
    "Cookie": "sessionid=%s" % sessionid,
    "User-Agent": "Barcelona 341.0.0.36.109 Android",
    "X-IG-App-ID": "238260118697367",
}
r = requests.get("https://i.instagram.com/api/v1/feed/timeline/", headers=headers)
# 200 = actif, 401 = expire, 400 = checkpoint
```

#### C. Via ThreadsTokenDump (tweak runtime)

Le tweak `ThreadsTokenDump` va plus loin que les plists — il traverse
l'object graph interne de Threads pour trouver les auth headers :

```
UIApplication.delegate
  → _appCoordinator
    → _userSession / _sessionManager / _authenticator
      → properties string (sessionid, csrftoken, Bearer token, etc.)
```

Ecrit dans `/tmp/threads_dump.json` apres 10s de lancement.

#### D. Via IGCookieDump (tweak runtime pour IG)

Meme approche pour Instagram :

```
UIApplication.delegate
  → _appCoordinator
    → _userSession
      → authHeaderManager, networker, user, pk, csrfToken, etc.
```

Ecrit dans `/tmp/ig_cookies.json` apres 12s. Inclut le deep scan
des ivars avec protection crash (signal handler pour SIGSEGV).

#### E. Via ig_cookie_dump (CLI keychain)

Executable standalone qui lit directement le keychain iOS :

```bash
./ig_cookie_dump
# Dump les GenericPassword pour les access groups :
#   MH9GU9K5PX.com.burbn.instagram
#   group.com.burbn.instagram
# + tous les InternetPassword pour instagram.com/facebook.com
```

---

## 7. TouchCapture — Calibration des donnees tactiles

**Port :** 8193 | **Source :** `~/Downloads/TouchCapture.m`

### A quoi ca sert

TouchCapture enregistre les VRAIS gestes d'un humain sur l'iPhone pour
calibrer RealTouchInject. On l'utilise pour :
- Mesurer la distribution reelle de force 3D Touch
- Mesurer le radius reel du capteur
- Capturer les mouvements accelerometre/gyroscope par posture
- Analyser les scrolls reels (trajectoire, vitesse, drift)

### Donnees capturees

- **Touches** : position, force, max_force, radius, phase, tap_count
- **Scrolls** : start/end, dx/dy, duree, vitesse, trajectoire complete
- **Accelerometre** : ax, ay, az (20 Hz)
- **Gyroscope** : rx, ry, rz (20 Hz)

### Captures existantes

6 sessions de capture multi-posture sont stockees sur le Mac :
- `capture_assis.json` (393 touches, 1358 motion)
- `capture_dos.json` (1123 touches, 3488 motion)
- `capture_cote.json` (1168 touches, 3162 motion)
- `capture_debout.json` (543 touches, 1651 motion)
- `capture_bureau.json` (992 touches, 2084 motion)
- `touch_capture.json` (capture initiale, 3730 touches)

---

## 8. Anti-patterns comportementaux

### Pourquoi

Instagram et Threads analysent les patterns d'usage. Un bot qui scrolle
regulierement, like systematiquement et ne fait jamais d'erreur est detecte.

### Patterns implementes (behavior/patterns.py)

| Pattern | Description | Frequence |
|---------|-------------|-----------|
| `scroll_back` | Remonte pour revoir un post | ~10% des scrolls |
| `pause_distraction` | Longue pause (8-20s) | Aleatoire |
| `hesitate_before_action` | Pause avant like/comment | Avant chaque action |
| `slow_read_caption` | Pause de lecture (~250 wpm) | Chaque post |
| `browse_replies_slow` | Lit les reponses lentement | Parfois |
| `imprecise_scroll` | Scroll trop/pas assez + correction | ~15% |
| `double_tap_miss` | Double-tap imprecis | Rare |
| `random_profile_peek` | Visite rapide d'un profil | Aleatoire |
| `typing_corrections` | Ecrit, efface, re-ecrit | Sur les commentaires |

### Realisme tactile (HumanTouch)

| Technique | Implementation |
|-----------|---------------|
| Position gaussienne | `x += gauss(0, w/4)` dans les bounds de l'element |
| Duree de tap aleatoire | 50-120ms (gauss centree 85ms) |
| Trajectoire courbee | Arc perpendiculaire + ease-out + bruit |
| Hold points (anti-inertie) | 4 points dupliques en fin de swipe |
| Drift lateral calibre | 5-25% de la largeur sur les scrolls |
| Vitesse de frappe humaine | 30-80ms entre chaque touche |
| Pauses de lecture | ~250 mots/minute avec jitter |

---

## 9. Outils de debug et reverse engineering

### Frida

| Script | Usage |
|--------|-------|
| `verify_force.js` | Hooker UITouch.force dans IG pour verifier l'enrichissement |
| `frida_ssl_unpin.js` | Desactiver le SSL pinning pour intercepter le trafic |
| `frida_graphql_docids.js` | Capturer les doc_ids des requetes GraphQL |
| `frida_capture_headers.js` | Logger tous les headers HTTP |

```bash
# Verifier que RealTouchInject fonctionne dans Instagram
frida -U -n Instagram -l verify_force.js
# Puis faire un tap via MCP ou RealTouchInject
# → force=0.350, radius=24.2 (au lieu de 0.006, 0.0)
```

### Hooks IG compiles

| Fichier | Role |
|---------|------|
| `IGHook4.dylib` | Hook generique IG |
| `IGNetLogger.dylib` | Logger reseau IG |
| `SSLKillSwitch.dylib` | Kill switch SSL |

### Binaires pour analyse (Ghidra/otool/strings)

```
~/Downloads/IG/Instagram    310MB  — binaire IG pour reverse
~/Downloads/IG/Threads      139MB  — binaire Threads
~/Downloads/IG/Snapchat     300MB  — binaire Snap (futur)
```

---

## 10. Ordre de reinstallation apres restauration

1. **ios-mcp** — sans lui, rien ne marche
   ```bash
   scp ~/ios-mcp-fork/.theos/_/Library/MobileSubstrate/DynamicLibraries/ios-mcp.dylib root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
   scp ~/ios-mcp-fork/ios-mcp.plist root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
   ```

2. **ScaleTweak** — containerisation (prerequis multi-comptes)
   ```bash
   scp ~/Desktop/ScaleTweak_v5_antifp_final/ScaleTweak/.theos/obj/arm64/ScaleTweak.dylib root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
   scp ~/Desktop/ScaleTweak_v5_antifp_final/ScaleTweak/ScaleTweak.plist root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
   scp ~/Desktop/ScaleTweak_v5_antifp_final/ScaleTweak/.theos/obj/arm64/scalectl root@192.168.1.133:/var/jb/usr/local/bin/
   ssh root@192.168.1.133 'chmod 755 /var/jb/usr/local/bin/scalectl'
   ```

3. **RealTouchInject** — enrichissement touch + motion
   ```bash
   xcrun -sdk iphoneos clang -arch arm64 -shared -fobjc-arc -framework Foundation -framework UIKit -framework IOKit -o /tmp/RealTouchInject.dylib ~/Downloads/RealTouchInject.m
   scp /tmp/RealTouchInject.dylib root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
   scp ~/Downloads/RealTouchInject.plist root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
   ```

4. **MTOUCH** — multi-touch + import media
   ```bash
   scp ~/mtouch-tweak/packages/com.ofm.mtouch_1.0.0-13+debug_iphoneos-arm64.deb root@192.168.1.133:/tmp/
   ssh root@192.168.1.133 'dpkg -i /tmp/com.ofm.mtouch_*.deb'
   ```

5. **Signer + recharger tout**
   ```bash
   ssh root@192.168.1.133 'ldid -S /var/jb/Library/MobileSubstrate/DynamicLibraries/ios-mcp.dylib && ldid -S /var/jb/Library/MobileSubstrate/DynamicLibraries/ScaleTweak.dylib && ldid -S/tmp/rt_ent.plist /var/jb/Library/MobileSubstrate/DynamicLibraries/RealTouchInject.dylib && sbreload'
   ```

6. **Verifier**
   ```bash
   curl -s http://192.168.1.133:8090/mcp -X POST -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python3 -c "import sys,json;print(len(json.load(sys.stdin)['result']['tools']),'tools')"
   curl -s http://192.168.1.133:8195/health
   curl -s http://192.168.1.133:8091/health
   ```

---

## 11. Correction backend necessaire

Dans `apps/backend/app/services/automation/human_touch.py`, le portage
VPS → FastAPI a introduit des noms d'outils incorrects :

```python
# AVANT (bug) :
await self._call("perform_action", {"action": "tap", ...})
await self._call("terminate_app", {"bundle_id": ...})

# APRES (correct — vrais noms MCP) :
await self._call("tap_screen", {"x": ..., "y": ...})
await self._call("kill_app", {"bundle_id": ...})
```

Le docstring en haut du fichier doit aussi etre corrige pour refleter
les vrais noms d'outils MCP.
