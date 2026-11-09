"""
th_iphone/interact/publish.py — Publication sur Threads (async).

Flows : post texte, post avec media, reponse.
Les medias doivent etre dans la galerie de l'iPhone.

Usage:
    from ..interact.publish import publish_thread
    await publish_thread(driver, navigator, caption="Hello!", log=print)
"""

import asyncio
import random
import time


async def publish_thread(driver, navigator, caption="", media_index=None, log=print):
    """Publie un thread (texte + optionnel media)."""
    start = time.time()
    stats = {"published": False, "type": "thread", "duration_s": 0, "has_media": media_index is not None}

    log("-> Publication Thread")

    from ..selectors import TAB_CREATE_X, BOTTOM_BAR_Y
    await driver.tap_pos(TAB_CREATE_X, BOTTOM_BAR_Y)
    await driver.wait('transition')
    await asyncio.sleep(2)

    await driver._dismiss_popup()

    els = await driver.get_elements(refresh=True)
    labels = [e.get("text", "").lower() for e in els]
    if not any("champ de texte" in l or "rédigez" in l for l in labels):
        log("   ! ecran de creation non detecte, retry...")
        await driver.tap_pos(TAB_CREATE_X, BOTTOM_BAR_Y)
        await driver.wait('transition')
        await asyncio.sleep(2)
        await driver._dismiss_popup()

    # Ecrire la caption
    if caption:
        text_area = await driver.find_element(contains="Champ de texte", clickable=True, refresh=True)
        if not text_area:
            text_area = await driver.find_element(contains="Rédigez", clickable=True, refresh=True)
        if not text_area:
            text_area = await driver.find_element(contains="Quoi de neuf", clickable=True, refresh=True)

        if text_area and text_area.get("tap"):
            await driver.ht.tap(text_area["tap"]["x"], text_area["tap"]["y"])
            await driver.wait('tap')
            await asyncio.sleep(0.5)

        log("   ecriture caption (%d chars)" % len(caption))
        await driver.type_text(caption, method="slow" if len(caption) < 100 else "normal")
        await asyncio.sleep(1)

    # Ajouter un media (optionnel)
    if media_index is not None:
        indices = media_index if isinstance(media_index, list) else [media_index]
        log("   ajout %d media(s)" % len(indices))

        attach = await driver.find_element(contains="pellicule", clickable=True, refresh=True)
        if not attach:
            attach = await driver.find_element(contains="Ajouter des photos", clickable=True, refresh=True)

        if attach and attach.get("tap"):
            await driver.ht.tap(attach["tap"]["x"], attach["tap"]["y"])
            await driver.wait('transition')
            await asyncio.sleep(2)

            els = await driver.get_elements(refresh=True)
            photos = [e for e in els
                      if e.get("text", "") in ("Photo", "Vidéo")
                      and e.get("tap", {}).get("y", 0) > 150
                      and e.get("clickable")]

            if photos:
                for i, idx in enumerate(indices):
                    actual_idx = min(idx, len(photos) - 1)
                    tap = photos[actual_idx].get("tap", {})
                    if tap:
                        await driver.ht.tap(tap["x"], tap["y"])
                        await driver.wait('tap')
                        await asyncio.sleep(0.8)
                        log("   photo #%d selectionnee" % actual_idx)

                add_btn = await driver.find_element(text="Ajouter", clickable=True, refresh=True)
                if not add_btn:
                    els2 = await driver.get_elements(refresh=True)
                    for e in els2:
                        if "ajouter" in e.get("text", "").lower() and e.get("tap", {}).get("y", 999) < 100:
                            add_btn = e
                            break

                if add_btn and add_btn.get("tap"):
                    await driver.ht.tap(add_btn["tap"]["x"], add_btn["tap"]["y"])
                    await driver.wait('transition')
                    await asyncio.sleep(2)
                    log("   %d media(s) ajoute(s) au thread" % len(indices))
                else:
                    log("   ! bouton Ajouter non trouve")
            else:
                log("   ! aucun media trouve dans la galerie")
        else:
            log("   ! bouton pellicule non trouve")

    # Publier
    await asyncio.sleep(1)
    published = False

    pub_el = await driver.find_element(contains="Publier ce thread", clickable=True, refresh=True)
    if pub_el and pub_el.get("tap"):
        log("   -> Publier")
        await driver.ht.tap(pub_el["tap"]["x"], pub_el["tap"]["y"])
        await driver.wait('transition')
        await asyncio.sleep(3)
        published = True
        log("   thread publie!")
    else:
        log("   ! bouton Publier non trouve")

    stats["published"] = published
    stats["duration_s"] = round(time.time() - start)
    return stats


async def publish_reply(driver, navigator, post, reply_text, log=print):
    """Repond a un thread."""
    start = time.time()
    stats = {"published": False, "type": "reply", "duration_s": 0}

    log("-> Reponse a @%s" % post.get("username", "?"))

    reply_tap = post.get("actions", {}).get("reply")
    if not reply_tap:
        log("   ! pas de bouton reply")
        return stats

    await driver.ht.tap(reply_tap["x"], reply_tap["y"])
    await driver.wait('transition')
    await asyncio.sleep(2)

    reply_input = await driver.find_element(contains="Répondre", clickable=True, refresh=True)
    if not reply_input:
        reply_input = await driver.find_element(contains="réponse", clickable=True, refresh=True)

    if reply_input and reply_input.get("tap"):
        await driver.ht.tap(reply_input["tap"]["x"], reply_input["tap"]["y"])
        await driver.wait('tap')
        await asyncio.sleep(0.5)

    log("   ecriture reponse (%d chars)" % len(reply_text))
    await driver.type_text(reply_text, method="slow")
    await asyncio.sleep(1)

    pub_el = await driver.find_element(contains="Publier ce thread", clickable=True, refresh=True)
    if pub_el and pub_el.get("tap"):
        log("   -> Publier reponse")
        await driver.ht.tap(pub_el["tap"]["x"], pub_el["tap"]["y"])
        await driver.wait('transition')
        await asyncio.sleep(2)
        stats["published"] = True
        log("   reponse publiee!")
    else:
        log("   ! bouton Publier non trouve")

    stats["duration_s"] = round(time.time() - start)
    return stats
