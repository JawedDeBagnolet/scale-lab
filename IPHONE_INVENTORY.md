# Inventaire complet — Infrastructure iPhone Scale Lab

Tout ce qui existe sur le Mac pour l'automatisation iPhone (IG, Threads, touch enrichi,
containerisation, extraction de sessions, outils de debug).

---

## 1. ios-mcp (Serveur MCP)

**Chemin :** `~/ios-mcp-fork/`
**Type :** Tweak Substrate (Theos), charge dans SpringBoard uniquement
**Port :** 8090 (iPhone) → 8190 (VPS via tunnel SSH)
**Protocole :** JSON-RPC sur `POST /mcp`, format `tools/call`

### 47 outils MCP disponibles

**Touch/Gestes :**
`tap_screen`, `tap_element`, `wait_for_element`, `wait_for_disappear`,
`swipe_screen`, `long_press`, `double_tap`, `drag_and_drop`,
`pinch_screen` (fork), `rotate_screen` (fork)

**Ecran :** `get_screen_info`, `screenshot`
**Clipboard :** `get_clipboard`, `set_clipboard`
**Apps :** `launch_app`, `kill_app`, `list_apps`, `list_running_apps`, `get_frontmost_app`
**Accessibilite :** `get_ui_elements`, `get_element_at_point`, `ocr_screen`, `describe_screen`
**Saisie :** `input_text`, `type_text`, `press_key`
**Boutons :** `press_volume_up/down`, `press_power`, `press_home`, `wake_and_home`, `toggle_mute`
**Device :** `get_device_info`, `get_brightness`, `set_brightness`, `get_volume`, `set_volume`
**Apps avance :** `install_app`, `uninstall_app`, `get_app_info`, `open_url`
**Fichiers :** `list_dir`, `read_file`, `write_file`
**Shell :** `run_command`
**Logs :** `get_syslog`, `get_crash_logs`, `read_crash_log`

### IMPORTANT : `perform_action` N'EXISTE PAS

Le backend Python appelle `perform_action` mais le MCP expose `tap_screen`.
C'est un bug du portage VPS → FastAPI. Correction necessaire dans `human_touch.py`.

### Build et deploiement

```bash
cd ~/ios-mcp-fork
export THEOS=~/theos
make THEOS_PACKAGE_SCHEME=rootless

# Dylib pre-compile disponible :
# .theos/_/Library/MobileSubstrate/DynamicLibraries/ios-mcp.dylib (2.2MB)

# Deployer :
scp .theos/_/Library/MobileSubstrate/DynamicLibraries/ios-mcp.dylib \
  root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
scp ios-mcp.plist \
  root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
ssh root@192.168.1.133 'ldid -S /var/jb/Library/MobileSubstrate/DynamicLibraries/ios-mcp.dylib && sbreload'
```

### Fichiers source cles

| Fichier | Lignes | Role |
|---------|--------|------|
| `MCPServer.m` | ~3400 | Serveur HTTP, routage JSON-RPC, execution des outils |
| `HIDManager.m` | ~660 | Injection IOKit : tap, swipe, long press, drag, pinch, rotate |
| `AccessibilityManager.m` | ~1200 | Arbre d'accessibilite |
| `AppManager.m` | ~2000 | Cycle de vie des apps |
| `TextInputManager.m` | ~500 | Saisie clavier |
| `ScreenManager.m` | ~500 | Screenshots |
| `OCRManager.m` | ~300 | OCR |
| `patch_ios_mcp.sh` | ~400 | Patches custom (pinch/rotate) |

---

## 2. RealTouchInject (Enrichissement touch)

**Chemin source :** `~/Downloads/RealTouchInject.m` (v8 finale, 31KB)
**Port :** 8195 (iPhone)
**Filtre :** SpringBoard + Instagram

### Ce qu'il fait

Enrichit AUTOMATIQUEMENT tous les taps MCP avec des donnees 3D Touch realistes :

| Swizzle | Cible | Effet |
|---------|-------|-------|
| `UITouch.force` | Getter public | Force 3D Touch (22 paliers calibres, mean 0.246) |
| `UITouch._pressure` | Getter prive | Idem pour lectures internes |
| `UITouch.majorRadius` | Contact radius | 24.2pt constant (valeur capteur reelle) |
| `CMDeviceMotion.gravity` | Vecteur gravite | Posture spoofee avec micro-tremblements |
| `CMAccelerometerData.acceleration` | Accelerometre | Correlation tap-y <-> mouvement |
| `postHIDEvent:error:` | HID dispatch | Detecte les taps MCP, active l'enrichissement |

### Donnees de calibration

5 profils de posture calibres sur des captures reelles :

| Posture | Gravity (x, y, z) | Bruit stdev |
|---------|-------------------|-------------|
| assis | (0.06, -0.95, -0.25) | 0.008 |
| dos | (-0.01, -1.0, -0.01) | 0.005 |
| cote | (-0.65, -0.73, 0.10) | 0.012 |
| debout | (0.08, -0.92, -0.32) | 0.015 |
| bureau | (0.05, -0.40, -0.90) | 0.006 |

### API HTTP (port 8195)

- `GET /health` — etat, compteurs, posture active
- `POST /tap {"x","y"}` — tap enrichi auto (force randomisee)
- `POST /tap {"x","y","force":0.3}` — force specifique
- `POST /posture` — changer de posture (random)
- `POST /posture {"id":3}` — forcer une posture

### Fichiers associes

| Fichier | Chemin Mac | Role |
|---------|-----------|------|
| `RealTouchInject.m` | `~/Downloads/RealTouchInject.m` | Source v8 (31KB) |
| `RealTouchInject.plist` | `~/Downloads/RealTouchInject.plist` | Filtre (SpringBoard + IG) |
| `rt_ent.plist` | `~/Downloads/rt_ent.plist` | Entitlements |
| `verify_force.js` | `~/Downloads/verify_force.js` | Script Frida de verification |

### Build et deploiement

```bash
xcrun -sdk iphoneos clang -arch arm64 -shared -fobjc-arc \
  -framework Foundation -framework UIKit -framework IOKit \
  -o /tmp/RealTouchInject.dylib ~/Downloads/RealTouchInject.m

scp /tmp/RealTouchInject.dylib root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
scp ~/Downloads/RealTouchInject.plist root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/

ssh root@192.168.1.133 'ldid -S/tmp/rt_ent.plist \
  /var/jb/Library/MobileSubstrate/DynamicLibraries/RealTouchInject.dylib \
  && sbreload'
```

### Fichiers abandonnes (historique)

| Fichier | Raison abandon |
|---------|---------------|
| `~/Downloads/RealTouch.m` | Ancienne approche (UITouch ivars, port 8194) |
| `~/Downloads/TouchEnrich-3.m` | Port 8194, hook UIWindow sendEvent |
| `~/Downloads/TouchEnrich-7.m` | Version avancee de la meme approche |

---

## 3. TouchCapture (Enregistrement de vrais gestes)

**Chemin source :** `~/Downloads/TouchCapture.m` (14KB)
**Port :** 8193 (iPhone)

### API

- `POST /start` — demarrer la capture
- `POST /stop` — stopper
- `POST /clear` — vider les donnees
- `GET /status` — statut
- `GET /data` — recuperer le JSON (touches + motion + gyro)

### Captures existantes

| Fichier | Taille | Posture |
|---------|--------|---------|
| `~/Downloads/touch_capture.json` | 1.5M | Capture initiale |
| `~/Downloads/capture_assis.json` | 280K | Assis |
| `~/Downloads/capture_dos.json` | 732K | Allonge sur le dos |
| `~/Downloads/capture_cote.json` | 735K | Sur le cote |
| `~/Downloads/capture_debout.json` | 366K | Debout |
| `~/Downloads/capture_bureau.json` | 532K | Au bureau |

---

## 4. MTOUCH (Multi-touch + Media import)

**Chemin source :** `~/mtouch-tweak/`
**Port :** 8091 (iPhone) → 8191 (VPS)
**Type :** Tweak Theos, charge dans SpringBoard
**Package :** `com.ofm.mtouch` v1.0.0

### Endpoints

| Endpoint | Role |
|----------|------|
| `GET /health` | Health check |
| `POST /tap {"x","y"}` | Tap via MCP manager |
| `POST /pinch {"cx","cy","scale","duration"}` | Pinch deux doigts |
| `POST /rotate {"cx","cy","angle","duration"}` | Rotation deux doigts |
| `POST /import {"path"}` | Importer image/video dans Photos |

### Comment ca marche

Hook dans `IOSMCPHIDManager.postHIDEvent:error:` de ios-mcp. Quand un pinch/rotate
est declenche, injecte un second `IOHIDEventCreateDigitizerFingerEvent` (finger index 2)
dans l'event parent avant d'appeler l'original. iOS recoit un vrai geste deux doigts.

### Build

```bash
cd ~/mtouch-tweak && export THEOS=~/theos && make package
scp packages/com.ofm.mtouch_*.deb root@192.168.1.133:/tmp/
ssh root@192.168.1.133 'dpkg -i /tmp/com.ofm.mtouch_*.deb && killall SpringBoard'
```

**Deb pre-compile :** `packages/com.ofm.mtouch_1.0.0-13+debug_iphoneos-arm64.deb`

---

## 5. ScaleTweak v5 (Containerisation + Anti-fingerprint)

**Chemin source :** `~/Desktop/ScaleTweak_v5_antifp_final/ScaleTweak/`
(attention : `~/ScaleTweak/` est VIDE)
**Filtre :** `com.burbn.instagram` (version Threads : ajouter `com.burbn.barcelona`)

### Ce que ScaleTweak spoofe

**Identite (deterministe par container UUID via SHA256) :**
- IDFV, IDFA
- Numero de serie, Platform UUID
- MAC WiFi, Bluetooth, Ethernet
- BSSID, SSID (nom d'ISP francais aleatoire)
- Nom d'appareil (prenom francais aleatoire, "iPhone de X")
- Hostname, Timezone, Locale
- User-Agent Instagram
- Boot time, taille memoire, nombre de coeurs CPU
- Espace disque, niveau de batterie (avec simulation de decharge realiste)

**Bypass JB (fishhook + ObjC) :**
- `opendir/access/stat/lstat/fopen` → ENOENT pour chemins JB
- `dlopen` → bloque les libs JB
- `getenv` → masque DYLD_*, redirige HOME
- `_dyld_image_count/_dyld_get_image_name` → masque les tweaks
- `NSFileManager.fileExistsAtPath` → masque chemins JB
- `UIApplication.canOpenURL` → bloque cydia:/sileo:/zebra:/filza:
- `NSString.writeToFile` → bloque tests JB via /tmp/

**Containerisation filesystem :**
- `NSHomeDirectory` → chemin du container
- `NSSearchPathForDirectoriesInDomains` → redirige
- `getenv("HOME")` → chemin du container
- Symlinks Documents/Library/Caches → container
- Group containers → scopes

**Isolation keychain :**
- `SecItemAdd/CopyMatching/Update/Delete` → prefix `_sc_{uuid}_`
- Groupes Meta partages (platformFamily, shared, MachineID) → scopes

**Reseau :**
- `getifaddrs` → masque interfaces VPN
- `CNCopyCurrentNetworkInfo` → spoofe BSSID/SSID
- `CFNetworkCopySystemProxySettings` → proxy SOCKS par container
- `NSMutableURLRequest` → User-Agent per-container

**Session :**
- NSUserDefaults scopes par prefix `_sc_{uuid}_`
- Sauvegarde periodique (30s)
- Detection de challenges (checkpoint, login_required, spam, rate_limit) → `/tmp/scale_alerts.log`

**Extraction de session :**
- Cookies → `Library/session.json` via NSHTTPCookieStorage
- Auth headers (Bearer IGT:2:) → `/tmp/scale_session.json`
- Mid header depuis le keychain

**SSO cross-app (IG → Threads) :**
- Copie le storage auth IG vers le container Threads
- Ecrit dans le AppGroup plist partage

### scalectl CLI

```
scalectl --list [bundle]                           # Lister les containers
scalectl --create <bundle> <name> [country]        # Creer (FR,US,BR,ES,IT,GB,DE)
scalectl --switch <bundle> <uuid|name:N|default>   # Changer le container actif
scalectl --delete <bundle> <uuid>                  # Supprimer
scalectl --inject <bundle> <uuid> <file.json>      # Injecter session + fingerprint + proxy
scalectl --status                                  # Statut global
```

### Build

```bash
cd ~/Desktop/ScaleTweak_v5_antifp_final/ScaleTweak
export THEOS=~/theos
make clean && make FINALPACKAGE=1

# Binaires pre-compiles disponibles :
# .theos/obj/arm64/ScaleTweak.dylib
# .theos/obj/arm64/scalectl

scp .theos/obj/arm64/ScaleTweak.dylib root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
scp ScaleTweak.plist root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
scp .theos/obj/arm64/scalectl root@192.168.1.133:/var/jb/usr/local/bin/
ssh root@192.168.1.133 'chmod 755 /var/jb/usr/local/bin/scalectl && \
  ldid -S /var/jb/Library/MobileSubstrate/DynamicLibraries/ScaleTweak.dylib && sbreload'
```

### Config plist

Chemin : `/var/jb/var/mobile/Library/Preferences/com.scale.tweak.plist`

```json
{
  "com.burbn.instagram": {
    "active": "<container-uuid>",
    "containers": {
      "<uuid>": {
        "name": "account_name_ig",
        "country": "FR",
        "device_name": "iPhone de Lea",
        "timezone": "Europe/Paris",
        "locale": "fr_FR",
        "carrier": "Free",
        "mcc": "208", "mnc": "15",
        "proxy_host": "...", "proxy_port": 5014
      }
    }
  }
}
```

---

## 6. ThreadsTokenDump (Extraction de sessions Threads)

**Chemin source :** `~/ThreadsTokenDump/`
**Type :** Tweak Substrate, charge dans Threads (`com.burbn.barcelona`)

### Comment ca marche

1. Se charge dans le process Threads via MobileSubstrate
2. Attend 10s apres le lancement
3. Traverse l'object graph interne : `UIApplication.delegate → _appCoordinator → _userSession`
4. Dump toutes les proprietes string des objets auth (cookies, tokens, device IDs)
5. Ecrit le JSON dans `/tmp/threads_dump.json`

### Build

```bash
cd ~/ThreadsTokenDump && make package
scp packages/com.ofm.threadstokendump_1.0-7+debug_iphoneos-arm64.deb root@192.168.1.133:/tmp/
ssh root@192.168.1.133 'dpkg -i /tmp/com.ofm.threadstokendump_*.deb && killall Barcelona'
```

**Deb pre-compile :** 7 versions disponibles dans `packages/`

---

## 7. Extracteurs de sessions IG

### Tweaks Objective-C (sur le Mac)

| Fichier | Taille | Methode |
|---------|--------|---------|
| `~/Downloads/ig_cookie_dump.m` | 6.7K | Dump cookies NSHTTPCookieStorage |
| `~/Downloads/ig_cookie_dump2.m` | 2.7K | Version simplifiee |
| `~/Downloads/IGCookieDump.m` | 4.9K | Version avec plus de donnees |

### Script Frida

| Fichier | Taille | Methode |
|---------|--------|---------|
| `~/Downloads/IG/API_IG/ig_extract.js` | 3.4K | Extraction via Frida |

### Via les scripts Python

`~/th_iphone/interact/session_extract.py` — extraction via MCP `run_command`
(lit les plists directement + verifie le statut du compte via l'API privee IG)

---

## 8. Scripts Threads iPhone (VPS standalone)

**Chemin :** `~/th_iphone/`
**Type :** Scripts Python (version originale VPS, avant le portage FastAPI)

### Fichiers

| Fichier | Lignes | Role |
|---------|--------|------|
| `driver.py` | 454 | UI driver : elements, ecrans, scroll, tap, type |
| `navigator.py` | 173 | Navigation : onglets, popups, recherche |
| `selectors.py` | 126 | Labels UI francais, zones safe, positions onglets |
| `media.py` | 370 | Pipeline media : R2 → spoof EXIF → SCP → import gallery |
| `interact/account_login.py` | 255 | Login Threads via creds IG, 2FA (TOTP) |
| `interact/account_create.py` | 295 | Creation de compte Threads depuis IG |
| `interact/feed_session.py` | 274 | Navigation feed naturelle : scroll, like, reply, repost |
| `interact/profile_session.py` | 233 | Visite de profils : recherche, scroll, like, follow |
| `interact/profile_config.py` | 498 | Config profil : nom, bio, photo, liens, privacy |
| `interact/publish.py` | 199 | Publication de threads (texte/media) |
| `interact/session_extract.py` | 188 | Extraction cookies + verification statut via API privee |
| `behavior/patterns.py` | 127 | Anti-patterns : scroll-back, hesitation, lecture lente, typos |
| `behavior/presets.py` | 42 | Resolveur de presets |

### Services references

- **GalleryService** (port 8192) — tweak pour importer/supprimer des photos
- **Spoof server** (`http://77.42.124.107:8502`) — service VPS qui spoofe les metadata EXIF
- **importmedia** (`/var/jb/usr/bin/importmedia`) — CLI pour import media dans Camera Roll

---

## 9. Outils de debug et reverse engineering

### Frida

| Fichier | Role |
|---------|------|
| `~/Downloads/verify_force.js` | Verifier force/radius dans IG |
| `~/Downloads/frida_ssl_unpin.js` | SSL unpinning |
| `~/Downloads/frida_graphql_docids.js` | Capturer les doc_ids GraphQL |
| `~/Downloads/frida_capture_headers.js` | Capturer les headers HTTP |
| `~/Downloads/frida_boring_hook.js` | Hook generique |
| `~/Downloads/frida-server.deb` | Frida server pour iPhone |

### Hooks IG compiles

| Fichier | Role |
|---------|------|
| `~/Downloads/IGHook4.dylib` + `.plist` | Hook IG generique |
| `~/Downloads/IGNetLogger.dylib` | Logger reseau IG |
| `~/Downloads/IGInsightHook.plist` | Hook insights |
| `~/Downloads/SSLKillSwitch.dylib` | SSL kill switch |

### Snapchat

| Fichier | Role |
|---------|------|
| `~/Downloads/SnapV1.m` | Hook Snapchat v1 |
| `~/Downloads/SnapHook-2.m` | Hook Snapchat v2 |

### Binaires (pour analyse otool/strings/Ghidra)

| Fichier | Taille |
|---------|--------|
| `~/Downloads/IG/Instagram` | 310M |
| `~/Downloads/IG/Threads` | 139M |
| `~/Downloads/IG/Snapchat` | 300M |
| `~/Downloads/IG/IG_Frameworks.zip` | 29M |

---

## 10. Specs et documentation

| Fichier | Contenu |
|---------|---------|
| `~/Downloads/IG/ScaleTweak_spoofing_spec.md` | 94 valeurs a spoofer par container |
| `~/Downloads/IG/ScaleTweak_Snapchat_spec.md` | 7 niveaux de defense Snap + procedure Ghidra |
| `~/Downloads/IG/ScaleTweak_Spec.md` | Spec ScaleTweak generale |
| `~/Downloads/IG/SPEC_IG_SCROLL.md` | Spec scrolling IG calibre |
| `~/Downloads/IG/ROADMAP.md` | Roadmap V1-V3 |
| `~/Downloads/ScaleTweak_MGCopyAnswer_Brief.md` | Brief sur MGCopyAnswer spoofing |
| `~/Downloads/TODO_OFM.md` | Todo list OFM |

---

## 11. Archives

| Fichier | Contenu |
|---------|---------|
| `~/Downloads/ig_iphone.tar` | Scripts IG iPhone (version VPS) |
| `~/Downloads/ig_runner.tar` | Runner IG (version VPS) |
| `~/Downloads/ScaleTweak.zip` | ScaleTweak archive |

---

## 12. Ordre de reinstallation sur l'iPhone

Apres restauration, reinstaller dans cet ordre :

1. **ios-mcp** — serveur MCP (fondation, tout le reste en depend)
2. **ScaleTweak** — containerisation + scalectl (prerequis pour multi-comptes)
3. **RealTouchInject** — enrichissement 3D Touch + motion (anti-detection)
4. **MTOUCH** — multi-touch, pinch, rotate, import media (optionnel mais utile pour stories)
5. **Choicy** — bloquer les tweaks par app (via Cydia/Sileo)
6. **TouchCapture** — uniquement pour debug/recalibration (optionnel)
7. **ThreadsTokenDump** — extraction de sessions Threads (quand necessaire)
8. **Frida** — debug et reverse engineering (quand necessaire)

### Correction du backend apres reinstallation

Dans `apps/backend/app/services/automation/human_touch.py`, changer :
```python
# Ligne 168 : perform_action → tap_screen
await self._call("tap_screen", {
    "x": round(x, 1),
    "y": round(y, 1),
})

# Ligne 274 : terminate_app → kill_app
await self._call("kill_app", {"bundle_id": bundle})
```

Et dans le docstring (lignes 8-13), mettre a jour les vrais noms d'outils MCP.
