"""
th_iphone/selectors.py — Labels accessibility Threads iOS (français).

Centralise tous les selecteurs. Si Threads change un label, on corrige ici.
Basé sur le mapping accessibility du 2026-08-26.
"""

# ── App info ──────────────────────────────────────────────────────────────────

TH_BUNDLE = "com.burbn.barcelona"

# ── Screen dimensions (iPhone X/11/12/13/14) ─────────────────────────────────
# Points, pas pixels

SCREEN_W = 375
SCREEN_H = 812

# ── Bottom bar tab positions (Y ~756) ─────────────────────────────────────────

BOTTOM_BAR_Y = 0.932  # 756 / 812
TAB_HOME_X = 0.143    # 53.5 / 375
TAB_MESSAGES_X = 0.321  # 120.5 / 375
TAB_CREATE_X = 0.500  # 187.5 / 375
TAB_ACTIVITY_X = 0.679  # 254.5 / 375
TAB_PROFILE_X = 0.857  # 321.5 / 375

# ── Multi-langue ──────────────────────────────────────────────────────────────

_lang = "fr"

LANG = {
    "fr": {
        # Bottom tabs
        "tab_home":       "Fil principal",
        "tab_messages":   "Messages",
        "tab_create":     "Créer une publication",
        "tab_activity":   "Activité",
        "tab_profile":    "Profil",

        # Top bar
        "menu_lateral":   "Menu latéral",
        "rechercher":     "Rechercher",

        # Post info
        "quoi_de_neuf":   "Quoi de neuf",
        "options_pub":    "Options de publication",

        # Post actions (contient ces textes)
        "like":           "J'aime",
        "reply":          "Répondre",
        "repost":         "Republier",
        "share":          "Partager",

        # Like patterns
        "like_count":     "personnes ont aimé",
        "reply_count":    "personnes ont répondu",
        "repost_count":   "personnes ont republié",
        "share_count":    "personnes ont partagé",

        # Post header patterns
        "post_header":    "Il y a",  # "username Il y a X heures"

        # Create flow
        "suivant":        "Suivant",
        "publier":        "Publier ce thread",
        "ajouter_photo":  "Ajouter des photos",
        "ajouter_video":  "Ajouter des vidéos",
        "joindre_media":  "Joindre un fichier",
        "galerie":        "Pellicule",

        # Profile
        "modifier":       "Modifier le profil",
        "abonnes":        "abonnés",
        "publications":   "publications",

        # Navigation
        "retour":         "Retour",
        "fermer":         "Fermer",
        "annuler":        "Annuler",

        # Search
        "rechercher":     "Rechercher",
        "recherche_bar":  "Rechercher sur Threads",

        # Interactions
        "suivre":         "Suivre",
        "ne_plus_suivre": "Abonné(e)",
        "repondre":       "Répondre",
    },
}


def set_lang(l):
    global _lang
    _lang = l


def sel(key):
    """Get a selector label for the current language."""
    return LANG.get(_lang, LANG["fr"]).get(key, key)
