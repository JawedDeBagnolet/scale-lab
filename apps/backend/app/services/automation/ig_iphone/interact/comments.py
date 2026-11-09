"""
ig_iphone/interact/comments.py — Ecriture de commentaires IG.

Usage:
    from app.services.automation.ig_iphone.interact.comments import post_comment, post_emoji_reaction
"""

import asyncio
import time
import random
import json
import requests as _req


async def _get_elements(driver):
    r = await driver.ht._call("get_ui_elements", {"clickable_only": False, "max_elements": 40})
    if not r:
        return []
    for c in r.get("content", []):
        if c.get("type") == "text":
            try:
                return json.loads(c["text"]).get("elements", [])
            except:
                pass
    return []


async def _find_and_tap(driver, elements, text, log=None, max_len=80):
    for el in elements:
        t = (el.get("text") or "")
        if text.lower() in t.lower() and len(t) < max_len:
            tap = el.get("tap", {})
            if tap.get("x") and tap.get("y"):
                if log:
                    log("   tap '%s'" % t[:30])
                await driver.ht.tap(tap["x"], tap["y"])
                return True
    return False


def _has_text(elements, text):
    for el in elements:
        if text.lower() in (el.get("text") or "").lower():
            return True
    return False


async def open_comments(driver, log=print):
    """Ouvre la section commentaires du post visible."""
    els = _get_elements(driver)
    if _find_and_tap(driver, els, "Commenter", log, max_len=20):
        await asyncio.sleep(2)
        return True
    # Fallback: chercher le bouton par icone
    for el in els:
        t = (el.get("text") or "")
        if "comment" in t.lower() and len(t) < 15:
            tap = el.get("tap", {})
            if tap.get("x") and tap.get("y"):
                await driver.ht.tap(tap["x"], tap["y"])
                await asyncio.sleep(2)
                return True
    return False


async def close_comments(driver, log=print):
    """Ferme la section commentaires."""
    # Swipe down pour fermer
    await driver.ht.swipe(187, 200, 187, 700, 300)
    await asyncio.sleep(1)


async def post_comment(driver, text, log=print):
    """Ecrit et publie un commentaire.

    Args:
        text: le commentaire a poster
    Returns:
        True si publie
    """
    log("   comment: '%s'" % text[:40])

    # 1. Taper dans le champ commentaire
    els = _get_elements(driver)
    field_found = False
    for el in els:
        t = (el.get("text") or "")
        if "commentaire" in t.lower() or "conversation" in t.lower():
            tap = el.get("tap", {})
            rect = el.get("rect", {})
            if tap.get("x") and rect.get("y", 0) > 400:
                await driver.ht.tap(tap["x"], tap["y"])
                field_found = True
                break
    if not field_found:
        log("   ! champ commentaire non trouve")
        return False
    await asyncio.sleep(0.5)

    # 2. Taper le commentaire (naturel)
    # Hesitation avant d ecrire
    await asyncio.sleep(random.uniform(0.5, 2.0))
    # Taper caractere par caractere avec delai variable
    for i, char in enumerate(text):
        await driver.ht._call("input_text", {"text": char})
        if char == " ":
            await asyncio.sleep(random.uniform(0.08, 0.25))
        else:
            await asyncio.sleep(random.uniform(0.03, 0.12))
        # Micro-pause entre mots (apres un espace)
        if char == " " and random.random() < 0.3:
            await asyncio.sleep(random.uniform(0.3, 1.0))
    await asyncio.sleep(random.uniform(0.5, 1.5))

    # 3. Tap "Publier"
    els = _get_elements(driver)
    for el in els:
        t = (el.get("text") or "")
        if "publier" in t.lower() and len(t) < 30:
            tap = el.get("tap", {})
            if tap.get("x") and tap.get("y"):
                log("   -> publier")
                await driver.ht.tap(tap["x"], tap["y"])
                await asyncio.sleep(2)
                return True
    log("   ! bouton publier non trouve")
    return False


async def post_emoji_reaction(driver, emoji=None, log=print):
    """Poste un emoji rapide en commentaire.

    Args:
        emoji: emoji specifique ou None pour aleatoire
    Returns:
        True si poste
    """
    EMOJIS = ["heart", "hands", "fire", "clap", "laugh", "love", "wow", "joy"]
    EMOJI_X = [16, 61, 106, 151, 197, 242, 287, 332]

    els = _get_elements(driver)
    # Trouver la rangee d'emojis (y ~ 426 ou 683)
    emoji_y = None
    for el in els:
        t = (el.get("text") or "")
        rect = el.get("rect", {})
        if t in ("❤️", "🙌", "🔥", "👏", "🤣", "😍", "😮", "😂"):
            emoji_y = rect.get("y", 0)
            break

    if emoji_y is None:
        log("   ! emojis rapides non trouves")
        return False

    # Choisir un emoji
    if emoji:
        emoji_map = {"heart": 0, "hands": 1, "fire": 2, "clap": 3,
                     "laugh": 4, "love": 5, "wow": 6, "joy": 7}
        idx = emoji_map.get(emoji, random.randint(0, 7))
    else:
        # Poids: fire et heart plus frequents
        idx = random.choices(range(8), weights=[30, 10, 35, 10, 5, 5, 3, 2])[0]

    x = EMOJI_X[idx] + random.randint(-3, 3)
    y = emoji_y + 20 + random.randint(-3, 3)

    log("   emoji rapide #%d (y=%d)" % (idx, y))
    await driver.ht.tap(x, y)
    await asyncio.sleep(1.5)

    return True



WORKER_URL = "https://ofm-geelark-generator.timothee-aubree3.workers.dev"


def generate_comment(caption, ocr_text="", persona=None, market="FR", log=print):
    """Genere un commentaire IA via le Worker CF.

    Args:
        caption: caption UI du post
        ocr_text: texte OCR du media
        persona: dict persona (name, niche, ai_prompt, etc.)
        market: marche du compte (FR, US, ES...)
    Returns:
        str commentaire ou None
    """
    combined = caption
    if ocr_text:
        combined = caption + " [contenu image: " + ocr_text[:200] + "]"

    body = {
        "caption": combined[:500],
        "lang": market,
    }
    if persona:
        body["persona"] = {
            "name": persona.get("name", ""),
            "niche": persona.get("niche", ""),
            "market": persona.get("market", market),
            "ai_prompt": persona.get("ai_prompt", ""),
            "extra_instructions": persona.get("extra_instructions", ""),
        }

    try:
        from config import WORKER_URL as _wu
        url = _wu
    except Exception:
        url = WORKER_URL

    try:
        r = _req.post(url + "/generate/comment", json=body, timeout=15)
        d = r.json()
        if d.get("ok") and d.get("text"):
            log("   AI comment: '%s'" % d["text"][:50])
            return d["text"]
        else:
            log("   AI comment echoue: %s" % d.get("error", "?"))
            return None
    except Exception as e:
        log("   AI comment erreur: %s" % str(e)[:60])
        return None


async def comment_on_current_post(driver, navigator, text=None, emoji_pct=0.6, caption="", ocr_text="", persona=None, market="FR", log=print):
    """Commente le post actuellement visible dans le feed.

    Args:
        text: texte du commentaire (None = emoji aleatoire)
        emoji_pct: proba de poster un emoji au lieu d'un texte
    Returns:
        True si commente
    """
    # Ouvrir les commentaires
    if not open_comments(driver, log):
        return False

    # Pause lecture des commentaires (comportement naturel)
    read_time = random.uniform(2.0, 6.0)
    log("   lecture commentaires %.1fs" % read_time)
    await asyncio.sleep(read_time)

    # Decider: emoji, texte fourni, ou IA
    if random.random() < emoji_pct:
        result = post_emoji_reaction(driver, log=log)
    elif text:
        result = post_comment(driver, text, log=log)
    else:
        # Generer un commentaire IA si possible
        ai_text = None
        if caption or ocr_text:
            ai_text = generate_comment(
                caption=caption or "", ocr_text=ocr_text or "",
                persona=persona, market=market, log=log)
        if ai_text:
            result = post_comment(driver, ai_text, log=log)
        else:
            result = post_emoji_reaction(driver, log=log)

    # Fermer les commentaires
    await asyncio.sleep(1)
    close_comments(driver, log)

    return result
