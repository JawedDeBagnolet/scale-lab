"""
ig_iphone/interact/consent_flow.py — Parcours de consentement publicitaire Meta.

Ce n'est pas une popup isolee mais un ENCHAINEMENT de 4 ecrans, qui apparait
en usage automatise (compte frais, container vierge, nouvelle IP) et rarement
en usage manuel. Tant qu'il n'est pas franchi, il recouvre le feed :
run_feed_session ne trouve aucun post, part en recovery, et finit par lever
(AttributeError sur post=None).

Chaque etape est identifiee par un REPERE (texte discriminant de l'ecran) et
resolue par une CIBLE (bouton a taper). On ne tape jamais une cible sans avoir
vu son repere : deux ecrans portent des libelles proches ("Continuer",
"Accepter"), et un tap a l'aveugle enverrait vers l'abonnement payant.

Ordre observe :
  1. "Autorisez ou non le traitement de vos donnees..."  -> Demarrer
  2. "S'abonner pour une utilisation sans publicites"    -> choisir la version
     gratuite avec publicites, PUIS Continuer
  3. "Pour utiliser nos produits sans frais..."          -> Accepter
  4. "Vous pouvez gerer votre experience publicitaire"   -> OK
"""

import asyncio
import time

# (nom, repere, cible, pre_tap)
# pre_tap : option a selectionner AVANT la cible (etape 2 : choisir l'offre
# gratuite, sinon "Continuer" mene vers l'abonnement payant).
CONSENT_STEPS = [
    ("autorisation",
     "Autorisez ou non le traitement de vos données",
     "Démarrer",
     None),

    ("abonnement_ou_pub",
     "S’abonner pour une utilisation sans publicités",
     "Continuer",
     "Utiliser sans paiement avec des publicités"),

    ("acceptation",
     "Pour utiliser nos produits sans frais",
     "Accepter",
     None),

    ("experience_pub",
     "Vous pouvez gérer votre expérience publicitaire",
     "OK",
     None),
]

# Les apostrophes typographiques d'iOS (’) different de l'ASCII (') : on
# normalise avant comparaison, sinon les repères ne matchent jamais.
async def _norm(s):
    return (s or "").replace("\u2019", "'").replace("\u2018", "'").lower()


async def _texts(driver):
    try:
        els = await driver.get_elements(refresh=True)
    except Exception:
        return [], []
    return els, [_norm(e.get("text", "")) for e in els]


def _has(all_texts, needle):
    n = _norm(needle)
    return any(n in t for t in all_texts)


async def _tap(driver, label, log):
    ok = await driver.tap_element(contains=label)
    if not ok:
        log("   [consent] cible '%s' introuvable" % label)
    return ok


async def handle_consent_flow(driver, log=print, max_rounds=8):
    """Franchit le parcours de consentement s'il est present.

    Renvoie le nombre d'ecrans franchis (0 = rien a faire). Ne leve jamais :
    un consentement non reconnu ne doit pas faire echouer la tache, le feed
    signalera de lui-meme qu'il ne trouve pas de post.
    """
    done = 0
    for _ in range(max_rounds):
        els, texts = _texts(driver)
        if not texts:
            break

        step = None
        for name, marker, target, pre_tap in CONSENT_STEPS:
            if _has(texts, marker):
                step = (name, marker, target, pre_tap)
                break
        if not step:
            break   # plus aucun ecran de consentement -> on sort

        name, marker, target, pre_tap = step
        log("   [consent] ecran '%s' detecte" % name)

        if pre_tap:
            # Selection explicite de l'offre gratuite avant de valider.
            if _tap(driver, pre_tap, log):
                log("   [consent] option choisie : %s" % pre_tap[:45])
                await driver.wait("tap")
                await asyncio.sleep(1)

        if not _tap(driver, target, log):
            break
        await driver.wait("transition")
        await asyncio.sleep(2)
        done += 1

    if done:
        log("   [consent] parcours franchi (%d ecran(s))" % done)
    return done
