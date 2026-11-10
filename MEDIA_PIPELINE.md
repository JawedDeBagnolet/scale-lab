# Pipeline Media — Push vers Photos + Spoofing EXIF

Comment les medias (photos, videos) arrivent dans le Camera Roll de l'iPhone
avec des metadata EXIF coherentes, prets a etre publies sur IG/Threads.

---

## Vue d'ensemble

```
Cloudflare R2 (stockage media)
  │
  │  URL du media original
  v
Spoof Server (VPS, port 8502)
  │  Reecrit les metadata EXIF :
  │  - GPS (coordonnees selon le marche)
  │  - Modele d'appareil (iPhone X, etc.)
  │  - Date de prise de vue (recente, realiste)
  │  - Software, orientation, etc.
  │
  │  Retourne le fichier modifie
  v
iPhone (via curl MCP ou SCP)
  │  Le fichier arrive dans /var/mobile/Media/th_media/
  v
Import dans Photos
  │  Via GalleryService (port 8192)
  │  ou MTOUCH /import (port 8091)
  │  ou importmedia CLI
  v
Camera Roll
  │  Le media apparait comme une "vraie photo prise avec l'iPhone"
  v
Instagram / Threads
  │  L'app le voit dans la galerie → selection pour publier
  v
Nettoyage
  │  Suppression du media du Camera Roll apres publication
  │  + suppression du fichier temporaire
```

---

## 1. Spoofing des metadata EXIF

### Pourquoi c'est necessaire

Un media telecharge depuis un CDN n'a pas de metadata EXIF, ou a des metadata
qui trahissent son origine (serveur, date de creation, pas de GPS). Instagram
lit les metadata EXIF pour :
- Geotaguer les publications (si GPS present)
- Verifier la coherence (un media "pris avec un iPhone X" devrait avoir
  les tags EXIF correspondants)
- Detecter les medias synthetiques ou telecharges en masse

### Le Spoof Server

**Localisation :** VPS `77.42.124.107`, port `8502`
**Type :** Service HTTP qui telecharge un media, modifie ses metadata EXIF,
et retourne le fichier modifie.

### API

```
GET http://77.42.124.107:8502/spoof?url=<url_encodee>&market=<geo>&device=<modele>&phone_id=<uuid>
```

| Parametre | Obligatoire | Description | Exemple |
|-----------|-------------|-------------|---------|
| `url` | Oui | URL source du media (R2, CDN) encodee | `https%3A%2F%2Fr2...` |
| `market` | Oui | Marche geo pour les coordonnees GPS | `FR`, `US`, `BR`, `ES`, `IT`, `GB`, `DE` |
| `device` | Non | Modele d'appareil pour les tags EXIF | `iPhone10,6` (iPhone X) |
| `phone_id` | Non | UUID du container pour la coherence | UUID ScaleTweak |

### Ce qui est modifie dans l'EXIF

| Tag EXIF | Valeur injectee |
|----------|----------------|
| **GPS Latitude/Longitude** | Coordonnees realistes dans le pays du `market` |
| **Make** | `Apple` |
| **Model** | Le `device` passe (ex: `iPhone 10,6`) |
| **Software** | Version iOS coherente (ex: `16.7.15`) |
| **DateTime / DateTimeOriginal** | Date recente, quelques heures/jours avant |
| **Orientation** | Aleatoire (1, 3, 6, 8 = normal, 180°, 90° CW, 90° CCW) |
| **ColorSpace** | sRGB |
| **PixelXDimension / PixelYDimension** | Dimensions reelles de l'image |

### Limitation

Le spoofing EXIF fonctionne **uniquement pour les images** (JPEG, PNG, HEIC).
Les videos `.mp4` ne sont pas spoofees par le serveur — leurs metadata sont
differentes (conteneur MP4, pas EXIF).

### Utilisation dans le code

```python
# Dans th_iphone/media.py
SPOOF_BASE = "http://77.42.124.107:8502/spoof"

def _spoof_url(original_url, market="FR", device="iPhone10,6", phone_id=None):
    """Construit l'URL du spoof server."""
    params = {
        "url": original_url,
        "market": market,
        "device": device,
    }
    if phone_id:
        params["phone_id"] = phone_id
    return f"{SPOOF_BASE}?{urlencode(params)}"
```

---

## 2. Push des medias vers l'iPhone

Deux methodes, selon le contexte :

### Methode A : Via MCP (preferee)

L'iPhone telecharge directement depuis le spoof server. Pas besoin de passer
par le VPS comme intermediaire.

```
iPhone ──curl──> Spoof Server (VPS:8502) ──> telecharge + modifie EXIF ──> retourne
                                                                              │
                                                                              v
                                                              /var/mobile/Media/th_media/photo.jpg
```

**Etapes :**
1. Construire l'URL spoofee
2. Creer le dossier de staging sur l'iPhone via MCP `run_command`
3. L'iPhone telecharge le media via `curl` (execute par MCP `run_command`)
4. Importer dans Photos via GalleryService

```python
async def push_media_via_mcp(mcp_port, media_url, filename, market="FR",
                              device="iPhone10,6", phone_id=None, spoof=True):
    """Push un media vers le Camera Roll via MCP."""

    # 1. Dossier de staging
    staging_dir = "/var/mobile/Media/th_media"
    await mcp_call(mcp_port, "run_command",
                   {"command": f"mkdir -p {staging_dir}"})

    # 2. URL (spoofee ou originale)
    if spoof and not filename.endswith((".mp4", ".mov")):
        url = _spoof_url(media_url, market, device, phone_id)
    else:
        url = media_url

    # 3. Telecharger sur l'iPhone
    dest = f"{staging_dir}/{filename}"
    await mcp_call(mcp_port, "run_command", {
        "command": f"curl -sL -o '{dest}' '{url}'"
    }, timeout=60)

    # 4. Importer dans Photos
    await _import_to_gallery(dest)

    return dest
```

### Methode B : Via SCP (fallback, gros fichiers)

Le VPS telecharge le media, le spoofe localement, puis l'envoie par SCP.

```
R2 ──> VPS (telecharge) ──> spoof local ──> SCP ──> iPhone
                                                       │
                                                       v
                                          /var/mobile/Media/th_media/video.mp4
```

**Etapes :**
1. Telecharger le media sur le VPS dans `/tmp/th_media_staging/`
2. Spoofer l'EXIF localement (via module Python `spoofer`)
3. SCP vers l'iPhone
4. SSH → `importmedia <path>` pour importer dans Photos
5. Supprimer le fichier local

```python
async def push_media_via_scp(ssh_port, media_url, filename, market="FR"):
    """Push un media via SCP (pour les gros fichiers ou quand MCP ne suffit pas)."""

    # 1. Telecharger localement
    staging = f"/tmp/th_media_staging/{filename}"
    os.makedirs(os.path.dirname(staging), exist_ok=True)
    async with httpx.AsyncClient() as client:
        resp = await client.get(media_url)
        with open(staging, "wb") as f:
            f.write(resp.content)

    # 2. Spoof EXIF localement
    if not filename.endswith((".mp4", ".mov")):
        spoofer.spoof_file(staging, market=market)

    # 3. SCP vers iPhone
    dest = f"/var/mobile/Media/th_media/{filename}"
    await _ssh_exec(ssh_port, f"mkdir -p /var/mobile/Media/th_media")
    proc = await asyncio.create_subprocess_exec(
        "scp", "-P", str(ssh_port),
        "-o", "StrictHostKeyChecking=no",
        staging, f"root@127.0.0.1:{dest}"
    )
    await proc.wait()

    # 4. Import dans Photos
    await _ssh_exec(ssh_port, f"importmedia {dest}")

    # 5. Cleanup local
    os.remove(staging)

    return dest
```

---

## 3. Import dans le Camera Roll (3 methodes)

### Methode 1 : GalleryService (tweak, port 8192) — PREFEREE

Un tweak HTTP sur l'iPhone qui utilise `PHPhotoLibrary` pour importer et
supprimer des photos/videos.

```python
GALLERY_URL = "http://192.168.1.133:8192"

async def _import_via_gallery_service(file_path):
    """Importer un fichier dans Photos via GalleryService."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GALLERY_URL}/import",
            json={"path": file_path},
            timeout=15
        )
    return resp.json().get("ok", False)
```

**Endpoints GalleryService :**

| Endpoint | Methode | Parametres | Description |
|----------|---------|------------|-------------|
| `/import` | POST | `{"path": "/var/mobile/Media/th_media/photo.jpg"}` | Importer dans Photos |
| `/delete` | POST | `{"count": 3}` | Supprimer les N photos les plus recentes |
| `/health` | GET | — | Health check |

### Methode 2 : MTOUCH `/import` (tweak, port 8091)

Meme mecanisme que GalleryService mais integre dans le tweak MTOUCH.

```python
MTOUCH_URL = "http://192.168.1.133:8091"

async def _import_via_mtouch(file_path):
    """Importer via MTOUCH."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{MTOUCH_URL}/import",
            json={"path": file_path},
            timeout=15
        )
    return resp.json().get("ok", False)
```

**Code Objective-C dans MTOUCH (Tweak.x) :**

```objc
// Determine si c'est une video ou une image par l'extension
NSString *ext = [[path pathExtension] lowercaseString];
BOOL isVideo = [ext isEqualToString:@"mp4"]
            || [ext isEqualToString:@"mov"]
            || [ext isEqualToString:@"m4v"];

NSURL *fileURL = [NSURL fileURLWithPath:path];

[[PHPhotoLibrary sharedPhotoLibrary] performChanges:^{
    if (isVideo) {
        [PHAssetCreationRequest creationRequestForAssetFromVideoAtFileURL:fileURL];
    } else {
        [PHAssetCreationRequest creationRequestForAssetFromImageAtFileURL:fileURL];
    }
} completionHandler:^(BOOL ok, NSError *error) {
    // Retourne {"ok": true/false, "error": "..."} en HTTP
}];
```

**Formats supportes :**
- **Images :** JPEG, PNG, HEIC, WEBP, GIF, TIFF, BMP
- **Videos :** MP4, MOV, M4V

**Timeout :** 15 secondes (les grosses videos peuvent prendre plus longtemps)

### Methode 3 : `importmedia` CLI

Outil en ligne de commande installe sur l'iPhone a `/var/jb/usr/bin/importmedia`.

```bash
# Via SSH depuis le VPS
ssh -p 2223 root@127.0.0.1 "importmedia /var/mobile/Media/th_media/photo.jpg"
```

Utilise quand les services HTTP ne sont pas disponibles. Meme mecanisme
`PHPhotoLibrary` sous le capot.

---

## 4. Nettoyage apres publication

Apres la publication, les medias doivent etre supprimes du Camera Roll pour :
- Eviter que les photos d'un compte A apparaissent quand on publie depuis le compte B
- Eviter l'accumulation (l'iPhone a un stockage limite)
- Eviter que les medias de publication restent visibles dans la galerie

### Suppression via GalleryService

```python
async def cleanup_gallery(count=5, delay=30):
    """Supprime les N photos les plus recentes du Camera Roll.

    Attend `delay` secondes avant de supprimer pour laisser le temps
    a l'upload IG/Threads de terminer.
    """
    await asyncio.sleep(delay)  # laisser l'upload finir !

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GALLERY_URL}/delete",
            json={"count": count},
            timeout=10
        )
    return resp.json()
```

**Important :** le delai de 30s avant suppression est crucial. Si on supprime
trop tot, l'upload vers les serveurs Meta peut echouer car le media n'est plus
dans la galerie pendant le transfert.

### Suppression via script SQLite (fallback)

Quand GalleryService n'est pas disponible, un script Python est deploye sur
l'iPhone qui modifie directement la base SQLite de Photos :

```python
async def _deploy_delete_script(ssh_port):
    """Deploie un script de suppression directe via SQLite."""
    script = '''
import sqlite3, os, subprocess

# Arreter assetsd pour debloquer la DB
subprocess.run(["killall", "assetsd"], capture_output=True)

db = sqlite3.connect("/var/mobile/Media/PhotoData/Photos.sqlite")
cursor = db.cursor()

# Trouver les N photos les plus recentes
cursor.execute("""
    SELECT ZASSET.Z_PK, ZASSET.ZDIRECTORY, ZASSET.ZFILENAME
    FROM ZASSET
    ORDER BY ZASSET.ZADDEDDATE DESC
    LIMIT ?
""", (count,))

for pk, directory, filename in cursor.fetchall():
    # Supprimer le fichier physique
    full_path = f"/var/mobile/Media/{directory}/{filename}"
    if os.path.exists(full_path):
        os.remove(full_path)
    # Supprimer de la DB
    cursor.execute("DELETE FROM ZASSET WHERE Z_PK = ?", (pk,))

db.commit()
db.close()

# Relancer assetsd pour qu'il prenne en compte les changements
subprocess.run(["launchctl", "kickstart", "-k", "system/com.apple.assetsd"])
'''
    # SCP le script sur l'iPhone
    await _ssh_exec(ssh_port, f"echo '{script}' > /tmp/delete_photos.py")
```

### Suppression des fichiers temporaires

En plus du Camera Roll, supprimer les fichiers de staging :

```python
async def cleanup_media(mcp_port, file_path):
    """Supprime un fichier temporaire sur l'iPhone."""
    await mcp_call(mcp_port, "run_command", {
        "command": f"rm -f '{file_path}'"
    })

async def cleanup_all_media(mcp_port):
    """Supprime tout le dossier de staging."""
    await mcp_call(mcp_port, "run_command", {
        "command": "rm -rf /var/mobile/Media/th_media"
    })
```

---

## 5. Ce qui manque dans le backend FastAPI

Le portage FastAPI (`ig_runner.py`) a une version **simplifiee** du pipeline media
qui ne fait PAS de spoofing EXIF :

```python
# Version actuelle du backend (ig_runner.py)
async def _transfer_media_to_iphone(ssh_port, local_path):
    # SCP directement dans DCIM (pas de dossier staging)
    dest = f"/var/mobile/Media/DCIM/100APPLE/{os.path.basename(local_path)}"
    # SCP via SSH tunnel
    # Puis ouvre MobileSlideShow (Photos) et le kill pour forcer un scan
    # PAS de spoofing EXIF
    # PAS de GalleryService
    # PAS de cleanup automatique
```

### A ajouter au backend

| Manque | Impact | Reference |
|--------|--------|-----------|
| Integration spoof server EXIF | Les medias publies n'ont pas de GPS, mauvais modele | `th_iphone/media.py` |
| GalleryService / MTOUCH import | L'import via DCIM est fragile (pas de scan garanti) | `th_iphone/media.py` |
| Cleanup automatique post-publication | Les medias s'accumulent dans la galerie | `th_iphone/media.py` |
| Dossier de staging separe | Les medias vont dans DCIM directement | `th_iphone/media.py` |

---

## 6. Deploiement des services media sur l'iPhone

### GalleryService

Pas retrouve comme projet separe — il est possible qu'il soit integre dans
un des tweaks existants ou qu'il faille le creer. L'endpoint `/import` de MTOUCH
(port 8091) fait exactement la meme chose et est deja disponible.

**Recommandation :** utiliser MTOUCH `/import` pour l'import et ajouter un
endpoint `/delete` a MTOUCH si le GalleryService n'est pas retrouve.

### importmedia CLI

A verifier si l'outil est installe apres le re-jailbreak :
```bash
ssh root@192.168.1.133 'which importmedia 2>/dev/null || echo "NOT FOUND"'
```

S'il n'est pas installe, MTOUCH `/import` est le fallback.

### Spoof Server

Le spoof server tourne sur le VPS. Verifier qu'il est actif :
```bash
curl -s "http://77.42.124.107:8502/health" || echo "DOWN"
```

S'il est down, il faut le relancer. Son code source est sur le VPS
(localisation exacte a retrouver dans `/root/` ou comme service systemd).

---

## 7. Flux complet — Exemple concret

Publication d'une photo sur Instagram avec le container "cassie_ig" :

```
1. ig_runner recoit la tache "ig_post" avec media_url + caption

2. Telecharger + spoofer le media :
   URL spoofee = http://77.42.124.107:8502/spoof
     ?url=https://r2.scalelab.win/p/cassie/photo_001.jpg
     &market=FR
     &device=iPhone10,6
     &phone_id=<container_uuid>

3. iPhone telecharge (via MCP run_command → curl) :
   curl -sL -o /var/mobile/Media/th_media/photo_001.jpg "<url_spoofee>"

4. Importer dans Photos :
   POST http://192.168.1.133:8091/import {"path":"/var/mobile/Media/th_media/photo_001.jpg"}

5. Dans Instagram, le flow de publication :
   - Tap "+" (nouveau post)
   - La galerie s'ouvre → le media apparait en premier (le plus recent)
   - Tap sur le media → "Suivant"
   - Ajouter caption, location, tags
   - Tap "Partager"

6. Attendre 30s que l'upload IG termine

7. Cleanup :
   POST http://192.168.1.133:8192/delete {"count": 1}   # supprimer du Camera Roll
   MCP run_command: rm -f /var/mobile/Media/th_media/photo_001.jpg   # supprimer le temp

8. Le media est publie avec :
   - GPS coherent avec le marche FR (coordonnees en France)
   - Model = iPhone X dans l'EXIF
   - Date de prise de vue = quelques heures avant
   - Aucune trace de CDN ou de telechargement
```
