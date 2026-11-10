# Guide complet — Tweaks de capture et simulation iPhone

4 tweaks construits pour l'iPhone X jailbreake (iOS 16, palera1n rootless).
3 simulent des donnees realistes, 1 capture des vrais gestes pour calibrer les autres.

---

## Vue d'ensemble

```
                    CAPTURE                              SIMULATION
                    ───────                              ──────────

TouchCapture        ← enregistre de vrais gestes    →    RealTouchInject v9
(port 8193)            force, radius, accelero,          (port 8195)
                       gyro, trajectoires scroll          Force 3D Touch
                                                          Radius contact
                       Les captures calibrent →           Motion/gravite
                       les profils de simulation          Scroll enrichi

                                                         MTOUCH
                                                         (port 8091)
                                                          Pinch 2 doigts
                                                          Rotate 2 doigts
                                                          Import Photos

                                                         MultiTouch (obsolete)
                                                         (port 8091, remplace par MTOUCH)
```

### Pourquoi ces tweaks existent

Quand le serveur MCP (`ios-mcp`) fait un tap sur l'ecran, il cree un event
IOKit avec `force=0.0` et `radius=0.04`. Instagram recoit un `UITouch` avec
ces valeurs quasi-nulles — impossibles pour un vrai doigt sur un iPhone X
avec capteur 3D Touch. Idem pour l'accelerometre : un telephone pose sur un
bureau et pilote a distance est parfaitement immobile, ce qui est suspect.

**RealTouchInject** intercepte ces events et les enrichit avec des valeurs
realistes calibrees sur de vrais gestes humains captures par **TouchCapture**.

**MTOUCH** ajoute les gestes a deux doigts (pinch/rotate) que le MCP ne
supporte pas nativement, plus l'import de medias dans Photos.

---

## 1. TouchCapture — Enregistrement de vrais gestes

**Source :** `~/Downloads/TouchCapture.m` (299 lignes)
**Port :** 8193
**Charge dans :** SpringBoard uniquement
**Role :** Capturer les donnees de vrais gestes humains pour calibrer RealTouchInject

### Ce qu'il enregistre

| Categorie | Donnees capturees | Frequence |
|-----------|-------------------|-----------|
| **Touches** | x, y, force, maximumPossibleForce, majorRadius, radiusTolerance, phase, tapCount | Chaque event UITouch |
| **Scrolls** | point depart/arrivee, dx, dy, duree, velocite, chemin complet (chaque point + force) | Chaque scroll (dy > 15px) |
| **Accelerometre** | ax, ay, az | 20 Hz (toutes les 50ms) |
| **Gyroscope** | rx, ry, rz (vitesse de rotation) | 20 Hz (toutes les 50ms) |

### Comment il marche

1. Hook sur `UIWindow.sendEvent:` — intercepte TOUS les UITouch dans SpringBoard
2. Pour chaque touch : enregistre position, force, radius, phase, timestamp
3. Detecte les scrolls (deplacement > 15px) et enregistre le chemin complet
4. En parallele : `CMMotionManager` echantillonne accelerometre + gyroscope a 20Hz
5. Tout est stocke en memoire (NSMutableArray) pendant la capture
6. `GET /data` retourne le JSON complet

### API HTTP (port 8193)

| Endpoint | Methode | Description |
|----------|---------|-------------|
| `/start` | POST | Demarre la capture (vide le buffer automatiquement) |
| `/stop` | POST | Arrete la capture et le motion manager |
| `/data` | GET | Retourne le JSON complet de toutes les donnees |
| `/status` | GET | Stats : nombre de touches, scrolls, motion, gyro, duree |
| `/clear` | POST | Vide le buffer sans arreter la capture |
| `/health` | GET | Health check |

### Utilisation typique

```bash
# 1. Demarrer la capture
curl -s -X POST http://192.168.1.133:8193/start

# 2. Utiliser l'iPhone normalement pendant 1-2 minutes
#    (scroller le feed IG, taper des boutons, etc.)

# 3. Verifier les stats
curl -s http://192.168.1.133:8193/status
# → {"capturing":true,"duration_s":65.2,"touches":142,"scrolls":8,"motion":1304,"gyro":1304}

# 4. Arreter la capture
curl -s -X POST http://192.168.1.133:8193/stop

# 5. Recuperer les donnees
curl -s http://192.168.1.133:8193/data > capture_assis.json

# 6. Vider pour la prochaine capture
curl -s -X POST http://192.168.1.133:8193/clear
```

### Format des donnees JSON

```json
{
  "touches": [
    {"t": 1234, "x": 187, "y": 400, "force": 0.283, "max_force": 6.667,
     "radius_x": 24.2, "radius_tol": 1.5, "phase": "start", "tap_count": 1},
    {"t": 1250, "x": 187, "y": 401, "force": 0.350, ... "phase": "move"},
    {"t": 1334, "x": 187, "y": 400, "force": 0.000, ... "phase": "end"}
  ],
  "scrolls": [
    {"t": 5000, "start_x": 200, "start_y": 600, "end_x": 195, "end_y": 250,
     "dx": -5, "dy": -350, "duration": 900, "velocity": -388,
     "path": [
       {"t": 5000, "x": 200, "y": 600, "f": 0.117},
       {"t": 5030, "x": 200, "y": 590, "f": 0.167},
       ...
       {"t": 5900, "x": 195, "y": 250, "f": 0}
     ]}
  ],
  "motion": [
    {"t": 50, "ax": 0.04, "ay": -0.95, "az": -0.25},
    {"t": 100, "ax": 0.03, "ay": -0.96, "az": -0.24},
    ...
  ],
  "gyro": [
    {"t": 50, "rx": 0.002, "ry": -0.001, "rz": 0.003},
    ...
  ],
  "screen": {"w": 375, "h": 812, "scale": 3}
}
```

### Captures existantes sur le Mac

6 captures multi-posture utilisees pour calibrer RealTouchInject :

| Fichier | Taille | Posture | Utilite |
|---------|--------|---------|---------|
| `~/Downloads/touch_capture.json` | 1.5M | Capture initiale | Premiere calibration |
| `~/Downloads/capture_assis.json` | 280K | Assis | Posture la plus courante |
| `~/Downloads/capture_dos.json` | 732K | Allonge sur le dos | Tel au-dessus du visage |
| `~/Downloads/capture_cote.json` | 735K | Sur le cote | Tel incline |
| `~/Downloads/capture_debout.json` | 366K | Debout | Plus de mouvement |
| `~/Downloads/capture_bureau.json` | 532K | Au bureau | Tel pose, incline |

### Ce qu'on a appris de ces captures

- **Force** : mean=0.246, stdev=0.087, quantifiee sur 22 paliers discrets (capteur 3D Touch)
- **Radius** : constant a 24.2pt sur iPhone X (independant de la pression)
- **Courbe de force** : began ≈ 40% du peak, moved = peak, ended ≈ 80% du peak
- **Scrolls** : force progressive 0.117 → 0.383 (pas de rampe comme les taps)
- **Motion** : amplitude 3x plus forte pour les taps en haut de l'ecran vs le bas
- **Postures** : chaque posture a un vecteur de gravite et un niveau de bruit distincts

### Compilation et deploiement

```bash
# Compiler
xcrun -sdk iphoneos clang -arch arm64 -shared \
  -framework Foundation -framework UIKit -framework CoreMotion \
  -o /tmp/TouchCapture.dylib ~/Downloads/TouchCapture.m

# Creer le plist filtre (SpringBoard uniquement)
cat > /tmp/TouchCapture.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Filter</key>
    <dict>
        <key>Bundles</key>
        <array>
            <string>com.apple.springboard</string>
        </array>
    </dict>
</dict>
</plist>
EOF

# Deployer sur l'iPhone
scp /tmp/TouchCapture.dylib root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
scp /tmp/TouchCapture.plist root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/

# Signer et recharger SpringBoard
ssh root@192.168.1.133 'ldid -S /var/jb/Library/MobileSubstrate/DynamicLibraries/TouchCapture.dylib && sbreload'
```

---

## 2. RealTouchInject v9 — Simulation de touches et mouvement

**Source :** `~/Downloads/RealTouchInject.m` (686 lignes, 31KB)
**Version :** `"9.0-scroll"` (la v8 ajoutait la motion, la v9 ajoute le scroll enrichi)
**Port :** 8195
**Charge dans :** SpringBoard + Instagram (via mmap partage)
**Depend de :** ios-mcp (doit etre charge avant)

### Ce qu'il simule

| Donnee | Valeur simulee | Calibree sur |
|--------|---------------|--------------|
| **Force 3D Touch** | 22 paliers quantifies (0.017 → 0.517), distribution gaussienne mean=0.246 | TouchCapture |
| **Radius contact** | 24.2pt constant (valeur reelle du capteur iPhone X) | TouchCapture |
| **Courbe de force tap** | began=40% peak → moved=peak → ended=80% peak | TouchCapture |
| **Force scroll** | Rampe progressive 0.117 → 0.383 sur la duree du scroll | TouchCapture (captures scroll) |
| **Gravite** | 5 postures reelles avec micro-tremblements gaussiens | Captures multi-posture |
| **Accelerometre** | Pics d'acceleration correles aux taps (3x plus en haut d'ecran) | Correlation tap-y observee |

### Architecture — 2 process, 1 memoire partagee

```
SpringBoard                              Instagram
───────────                              ─────────
ios-mcp fait un tap                      UITouch.force est lu par IG
    │                                         │
    v                                         v
postHIDEvent swizzle                     swizzled_force()
    │ Detecte le tap                          │ Lit la shared memory
    │ Genere force aleatoire                  │ Retourne peakForce
    │ Ecrit dans shared memory                │ au lieu de 0.006
    v                                         │
/tmp/rti_shared_state_v2  ──────────────>     │
    (mmap partage)                            v
                                         swizzled_majorRadius()
                                              │ Retourne 24.2
                                              v
                                         hook_gravity()
                                              │ Retourne posture + bruit
                                              v
                                         hook_userAcceleration()
                                              │ Correle au dernier tap
                                              v
                                         Meta recoit tout ca comme
                                         un vrai telephone
```

### Structure de la memoire partagee

```c
typedef struct {
    volatile int    active;        // 1 = enrichissement en cours
    volatile double peakForce;     // Force peak pour ce tap
    volatile double startForce;    // Force initiale (rampe)
    volatile float  radius;        // Radius contact (24.2)
    volatile int    phaseCounter;  // began=0, puis incremente

    volatile int    postureId;     // 0-4 (choisi au demarrage)
    volatile float  lastTapY;      // Position Y du dernier tap (0-812)
    volatile int    tapCounter;    // Compteur global de taps
    volatile uint64_t tapTime;     // Timestamp du dernier tap

    // v9 scroll
    volatile int    gestureType;   // 0=tap, 1=scroll
    volatile int    gestureDurMs;  // Duree du scroll (pour le profil de force)
} RTISharedState;
```

### Les 22 paliers de force (calibres sur le capteur 3D Touch)

```
[0.000, 0.017, 0.067, 0.117, 0.167, 0.183, 0.217, 0.233,
 0.267, 0.283, 0.300, 0.317, 0.333, 0.350, 0.367, 0.383,
 0.400, 0.417, 0.450, 0.467, 0.500, 0.517]
```

Chaque valeur generee est "snappee" au palier le plus proche — exactement
comme le vrai capteur qui a une resolution finie.

### Les 5 profils de posture

| ID | Nom | Gravite (x, y, z) | Bruit (stdev x, y, z) | Motion haut | Motion bas |
|----|-----|--------------------|-----------------------|-------------|------------|
| 0 | assis | (0.08, -0.94, -0.27) | (0.008, 0.008, 0.005) | 0.95 | 0.25 |
| 1 | dos | (-0.01, -1.0, -0.01) | (0.005, 0.003, 0.005) | 0.61 | 0.23 |
| 2 | cote | (-0.65, -0.73, 0.10) | (0.012, 0.010, 0.008) | 0.60 | 0.22 |
| 3 | debout | (0.08, -0.92, -0.32) | (0.015, 0.012, 0.010) | 1.07 | 0.40 |
| 4 | bureau | (0.05, -0.40, -0.90) | (0.006, 0.004, 0.005) | 0.97 | 0.37 |

"Motion haut" = amplitude du mouvement quand on tape en haut de l'ecran (y < 250).
"Motion bas" = amplitude quand on tape en bas (y > 550).
Le ratio est toujours ~2.5-3.7x — le bras bouge plus pour atteindre le haut.

### Hook 1 — Force 3D Touch (UITouch.force)

**Quand IG lit `touch.force`**, notre swizzle retourne :

Pour un **tap** :
- Phase `began` : `startForce` = ~40% du peak (simule le doigt qui se pose)
- Phase `moved` : `peakForce` = valeur aleatoire (mean 0.246)
- Phase `ended` : 80% du peak (le doigt se leve progressivement)

Pour un **scroll** (v9) :
- Force progressive qui monte de 0.117 a 0.383 sur la duree du scroll
- Calculee par `scrollForceNow()` : interpole lineairement selon le temps ecoule
- Dans les derniers 10% : la force redescend legerement (le doigt relache)

### Hook 2 — Radius (UITouch.majorRadius)

Retourne **24.2pt** quand l'enrichissement est actif, **0.0** sur la phase `ended`.
C'est la valeur constante mesuree sur l'iPhone X — le capteur ne varie pas le radius
avec la pression (contrairement a certains appareils Android).

### Hook 3 — Gravite (CMDeviceMotion.gravity)

Quand IG lit `deviceMotion.gravity`, notre hook retourne :

```
gravite_simulee = posture_gravity + bruit_gaussien + derive_sinusoidale
```

- `posture_gravity` : vecteur fixe selon la posture (ex: assis = 0.08, -0.94, -0.27)
- `bruit_gaussien` : par axe, stdev 0.003-0.015 selon la posture (micro-tremblements)
- `derive_sinusoidale` : oscillation lente (~0.02 d'amplitude, periode ~10s) qui simule
  les micro-ajustements du poignet

### Hook 4 — Acceleration (CMDeviceMotion.userAcceleration)

Quand IG lit `deviceMotion.userAcceleration`, notre hook retourne :

**Si un tap a eu lieu dans les 500ms precedentes :**
```
acceleration = amplitude * (1 - elapsed/500ms) * bruit_gaussien
```

Ou `amplitude` depend de la position Y du tap :
- Tap en haut (y < 250) : amplitude = `tapHighMotion` (0.60-1.07 selon posture)
- Tap en bas (y > 550) : amplitude = `tapLowMotion` (0.22-0.40)
- Entre les deux : interpolation lineaire

Le pic decroit lineairement sur 500ms — le telephone bouge quand on tape
puis se stabilise.

**Si aucun tap recent :** retourne ~0 + bruit tres faible (telephone au repos).

### Hook 5 — postHIDEvent (SpringBoard)

Intercepte `IOSMCPHIDManager.postHIDEvent:error:` dans SpringBoard.
A chaque event HID qui passe :

1. Genere une force aleatoire (Box-Muller, snappee aux 22 paliers)
2. Calcule startForce = ~40% du peak
3. Lit la position Y du tap depuis l'event HID
4. Ecrit tout dans la shared memory
5. Active l'enrichissement pour 500ms (taps) ou duree_scroll + 250ms (scrolls)
6. Appelle l'original `postHIDEvent` — ios-mcp envoie l'event normalement

### Hook 6 — CMMotionManager.deviceMotion getter

Fallback : si IG interroge `motionManager.deviceMotion` et que le manager
n'a pas de donnees (IG ne demarre pas toujours les motion updates), notre
hook retourne les donnees de notre propre CMMotionManager interne (demarre
a 10Hz 5 secondes apres le chargement).

### API HTTP (port 8195)

| Endpoint | Methode | Parametres | Description |
|----------|---------|------------|-------------|
| `/health` | GET | — | Version, posture, compteurs, etat du geste |
| `/tap` | POST | `{"x":187, "y":400}` | Tap enrichi via MCP (force auto-randomisee) |
| `/tap` | POST | `{"x":187, "y":400, "force":0.3, "radius":24}` | Tap avec force/radius specifiques |
| `/scroll` | POST | `{"duration_ms": 900}` | Signaler un scroll en cours (active le profil scroll) |
| `/posture` | POST | `{}` | Changer de posture (aleatoire) |
| `/posture` | POST | `{"id": 3}` | Forcer une posture (0=assis, 1=dos, 2=cote, 3=debout, 4=bureau) |

**Note importante :** en usage normal, l'API `/tap` n'est pas utilisee.
L'enrichissement est **automatique** — tout tap venant du MCP est intercepte
par le hook `postHIDEvent`. L'API sert uniquement pour :
- Tester manuellement (`curl -X POST .../tap`)
- Forcer une force specifique pour du debug
- Signaler un scroll (`/scroll`) avant de l'envoyer via MCP

### Comment le backend Python doit l'utiliser

**Pour les taps** : rien a faire. Le backend appelle `tap_screen` via MCP,
RealTouchInject enrichit automatiquement.

**Pour les scrolls** : le backend devrait appeler `/scroll` AVANT d'envoyer
le `drag_and_drop` au MCP pour que le profil de force soit adapte :

```python
# Dans human_touch.py, avant un scroll :
async def scroll_down(self):
    duration = random.randint(600, 1800)

    # Signaler le scroll a RealTouchInject (optionnel mais recommande)
    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"http://{self.host}:8195/scroll",
                              json={"duration_ms": duration}, timeout=2)
    except Exception:
        pass  # pas critique, le tap enrichment marche quand meme

    # Envoyer le scroll via MCP
    await self._call("drag_and_drop", {..., "move_duration": duration})
```

### Fichiers necessaires pour le deploiement

| Fichier | Chemin Mac | Deployer vers |
|---------|-----------|---------------|
| Source | `~/Downloads/RealTouchInject.m` | Compiler sur le Mac |
| Filtre plist | `~/Downloads/RealTouchInject.plist` | `/var/jb/Library/MobileSubstrate/DynamicLibraries/` |
| Entitlements | `~/Downloads/rt_ent.plist` | Utilise par `ldid` pour signer |

**Contenu de `RealTouchInject.plist`** (charge dans SpringBoard + Instagram) :
```xml
<plist version="1.0">
<dict>
    <key>Filter</key>
    <dict>
        <key>Bundles</key>
        <array>
            <string>com.apple.springboard</string>
            <string>com.burbn.instagram</string>
        </array>
    </dict>
</dict>
</plist>
```

**Contenu de `rt_ent.plist`** (entitlements pour l'injection IOKit) :
```xml
<dict>
    <key>platform-application</key><true/>
    <key>com.apple.private.security.container-required</key><false/>
    <key>com.apple.private.hid.client.event-dispatch</key><true/>
    <key>com.apple.private.hid.manager.user-access-protected</key><true/>
</dict>
```

### Compilation et deploiement

```bash
# 1. Compiler
xcrun -sdk iphoneos clang -arch arm64 -shared -fobjc-arc \
  -framework Foundation -framework UIKit -framework IOKit \
  -o /tmp/RealTouchInject.dylib ~/Downloads/RealTouchInject.m

# 2. Copier les 3 fichiers sur l'iPhone
scp /tmp/RealTouchInject.dylib root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
scp ~/Downloads/RealTouchInject.plist root@192.168.1.133:/var/jb/Library/MobileSubstrate/DynamicLibraries/
scp ~/Downloads/rt_ent.plist root@192.168.1.133:/tmp/

# 3. Signer avec les entitlements + recharger SpringBoard
ssh root@192.168.1.133 'ldid -S/tmp/rt_ent.plist \
  /var/jb/Library/MobileSubstrate/DynamicLibraries/RealTouchInject.dylib \
  && sbreload'

# 4. Verifier (attendre ~25s que SpringBoard redemarres)
curl -s http://192.168.1.133:8195/health
# → {"ok":true,"version":"9.0-scroll","posture":"assis",...}
```

### Pour ajouter le support Threads

Modifier `RealTouchInject.plist` pour ajouter le bundle Threads :

```xml
<array>
    <string>com.apple.springboard</string>
    <string>com.burbn.instagram</string>
    <string>com.burbn.barcelona</string>
</array>
```

---

## 3. MTOUCH — Multi-touch et import media

**Source :** `~/mtouch-tweak/Tweak.x` (302 lignes)
**Port :** 8091
**Charge dans :** SpringBoard uniquement
**Package :** `com.ofm.mtouch` v1.0.0
**Depend de :** ios-mcp (doit etre charge avant — attend 5s au demarrage)

### Ce qu'il fait

2 choses distinctes :

**A. Gestes a 2 doigts (pinch/rotate)** — pour les stories IG (zoom, rotation)
**B. Import de medias dans Photos** — pour pousser des photos/videos avant publication

### Comment le multi-touch marche

Le MCP (`ios-mcp`) ne supporte nativement qu'un seul doigt. MTOUCH ajoute
un second doigt en hookant le dispatch HID :

1. Quand un pinch/rotate est demande, MTOUCH positionne les coordonnees du 2e doigt
2. Il appelle `performTouchAtPoint:phase:error:` sur le `IOSMCPHIDManager` de ios-mcp
3. Le hook sur `postHIDEvent:error:` detecte le flag `_addSecondFinger`
4. Il cree un 2e `IOHIDEventCreateDigitizerFingerEvent` (finger index 2, identity 5)
5. Il l'ajoute a l'event parent via `IOHIDEventAppendEvent`
6. iOS recoit un vrai geste a 2 doigts

### API HTTP (port 8091)

| Endpoint | Methode | Parametres | Description |
|----------|---------|------------|-------------|
| `/health` | GET | — | Health check |
| `/tap` | POST | `{"x": 187, "y": 400}` | Tap simple via le MCP manager |
| `/pinch` | POST | `{"cx": 187, "cy": 400, "scale": 1.5, "duration": 300}` | Zoom in/out (30 etapes) |
| `/rotate` | POST | `{"cx": 187, "cy": 400, "angle": 45, "duration": 300}` | Rotation en degres (30 etapes) |
| `/import` | POST | `{"path": "/var/mobile/Media/th_media/photo.jpg"}` | Importer dans Photos |

### Parametres pinch

- `cx, cy` : centre du geste (coordonnees ecran en points)
- `scale` : facteur de zoom (> 1 = zoom in, < 1 = zoom out)
- `duration` : duree en ms (defaut 300)
- Le geste fait 30 etapes : les 2 doigts s'ecartent/se rapprochent depuis le centre

### Parametres rotate

- `cx, cy` : centre de rotation
- `angle` : angle en degres (positif = sens horaire)
- `duration` : duree en ms (defaut 300)
- Le geste fait 30 etapes : les 2 doigts tournent autour du centre a distance fixe (60pt)

### Import media

Utilise `PHPhotoLibrary` pour importer un fichier local dans le Camera Roll :

```objc
[[PHPhotoLibrary sharedPhotoLibrary] performChanges:^{
    if (isVideo) {
        [PHAssetCreationRequest creationRequestForAssetFromVideoAtFileURL:fileURL];
    } else {
        [PHAssetCreationRequest creationRequestForAssetFromImageAtFileURL:fileURL];
    }
} completionHandler:^(BOOL ok, NSError *error) { ... }];
```

**Formats supportes :**
- Images : JPEG, PNG, HEIC, WEBP, GIF, TIFF, BMP
- Videos : MP4, MOV, M4V
- Timeout : 15 secondes

### Utilisation depuis le backend

```python
# Pinch zoom in sur une story
async with httpx.AsyncClient() as client:
    await client.post("http://192.168.1.133:8091/pinch",
                      json={"cx": 187, "cy": 406, "scale": 2.0, "duration": 400})

# Rotation
    await client.post("http://192.168.1.133:8091/rotate",
                      json={"cx": 187, "cy": 406, "angle": 30, "duration": 300})

# Import d'un media dans Photos
    await client.post("http://192.168.1.133:8091/import",
                      json={"path": "/var/mobile/Media/th_media/photo.jpg"})
```

### Compilation et deploiement

```bash
# Methode 1 : via Theos (recommandee)
cd ~/mtouch-tweak
export THEOS=~/theos
make package
# Resultat : packages/com.ofm.mtouch_1.0.0-XX+debug_iphoneos-arm64.deb

# Deployer
scp packages/com.ofm.mtouch_*.deb root@192.168.1.133:/tmp/
ssh root@192.168.1.133 'dpkg -i /tmp/com.ofm.mtouch_*.deb && killall SpringBoard'

# Methode 2 : deb pre-compile (deja disponible)
scp ~/mtouch-tweak/packages/com.ofm.mtouch_1.0.0-13+debug_iphoneos-arm64.deb root@192.168.1.133:/tmp/
ssh root@192.168.1.133 'dpkg -i /tmp/com.ofm.mtouch_*.deb && killall SpringBoard'
```

**Note :** le Makefile a `THEOS_DEVICE_IP = 192.168.1.134` (ancienne IP).
Si tu utilises `make install`, mettre a jour vers `192.168.1.133`.

---

## 4. MultiTouch — Version obsolete (remplacee par MTOUCH)

**Source :** `~/Downloads/MultiTouch.m` (263 lignes)
**Port :** 8091 (meme port que MTOUCH — ne peuvent pas coexister)
**Statut :** OBSOLETE — remplace par MTOUCH

### Pourquoi il a ete remplace

MultiTouch dispatche les events HID **directement** via `BKSHIDEventRouteToFocusedApplication`
(BackBoardServices). Cette approche est moins fiable que celle de MTOUCH qui **hook ios-mcp** :
- Des events peuvent etre perdus
- Le sender ID n'est pas toujours correct
- Pas d'import media

### Differences avec MTOUCH

| | MultiTouch (ancien) | MTOUCH (actuel) |
|---|---|---|
| Dispatch | Direct via BackBoardServices | Hook ios-mcp postHIDEvent |
| Etapes par geste | 20 | 30 (plus fluide) |
| `/import` | Non | Oui (PHPhotoLibrary) |
| `/tap` | Non | Oui |
| Fiabilite | Events parfois perdus | Fiable (meme chemin que ios-mcp) |
| Build | `xcrun clang` | Theos (.deb) |

**Recommandation :** utiliser MTOUCH. Garder MultiTouch.m uniquement comme reference historique.

---

## 5. Script de verification — verify_force.js (Frida)

**Source :** `~/Downloads/verify_force.js` (30 lignes)
**Outil :** Frida (doit etre installe sur l'iPhone + Mac)

### Ce qu'il fait

Hook `UITouch.force` **dans le process Instagram** pour verifier en temps reel
que RealTouchInject fonctionne.

### Utilisation

```bash
# Terminal 1 : lancer le hook dans Instagram
frida -U -n Instagram -l ~/Downloads/verify_force.js

# Terminal 2 : faire un tap via RealTouchInject
curl -X POST http://192.168.1.133:8195/tap -d '{"x":187,"y":400}'

# Terminal 1 affiche :
# [IG] force=0.283 phase=began radius=24.2
# [IG] force=0.350 phase=moved radius=24.2
# [IG] force=0.280 phase=ended radius=0.0
```

**Sans RealTouchInject** : force ≈ 0.006 (quasi-zero)
**Avec RealTouchInject** : force ≈ 0.25-0.40 (realiste)

---

## 6. Ordre d'installation et dependances

```
ios-mcp                    ← FONDATION (doit etre charge en premier)
    │
    ├── RealTouchInject    ← hook postHIDEvent de ios-mcp
    │                         (attend que ios-mcp soit charge)
    │
    └── MTOUCH             ← hook postHIDEvent de ios-mcp
                              (attend 5s que ios-mcp soit charge)

TouchCapture               ← INDEPENDANT (hook UIWindow, pas ios-mcp)
```

**Ordre d'installation :**

1. **ios-mcp** — le serveur MCP (sans lui, rien ne marche)
2. **ScaleTweak** — containerisation (independant mais necessaire pour multi-comptes)
3. **RealTouchInject** — enrichissement touches + motion
4. **MTOUCH** — multi-touch + import media
5. **TouchCapture** — uniquement si recalibration necessaire
6. **Choicy** — pour bloquer les tweaks par app si besoin

Apres installation, un seul `sbreload` ou `killall SpringBoard` suffit
pour tout charger. Verifier avec :

```bash
# ios-mcp
curl -s -X POST http://192.168.1.133:8090/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 -c "
import sys,json
d=json.load(sys.stdin)
tools=d.get('result',{}).get('tools',[])
print(f'{len(tools)} outils MCP charges')
"

# RealTouchInject
curl -s http://192.168.1.133:8195/health

# MTOUCH
curl -s http://192.168.1.133:8091/health

# TouchCapture
curl -s http://192.168.1.133:8193/health
```
