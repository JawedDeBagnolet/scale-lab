"""
ig_iphone/selectors.py — Labels accessibility IG iOS (français).

Centralise tous les selecteurs. Si IG change un label, on corrige ici.
Supporte multi-langue via le dict LANG (defaut: fr).
"""

# ── Multi-langue ──────────────────────────────────────────────────────────────

LANG = {
    "fr": {
        # Bottom tabs
        "tab_home":       "Fil principal",
        "tab_reels":      "Reels",
        "tab_explore":    "Explorer",
        "tab_dm":         "messages Direct",
        "tab_profile":    "Profil",

        # Top bar
        "btn_create":     "Créer une publication",          # contient ce texte
        "btn_notifs":     "Notifications",
        "feed_title":     "Fil principal d'Instagram",
        "story_bar":      "Barre des stories",

        # Post actions (feed)
        "like":           "J'aime",
        "comment":        "Commenter",
        "repost":         "Republier",
        "send":           "Envoyer",
        "save":           "Enregistrer",

        # Post info patterns (contient ces textes)
        "post_header":    "Publication de",                 # "Publication de <user>, prise à..."
        "like_count":     "J'aime",                         # "<N> J'aime"
        "comment_count":  "commentaires",                   # "<N> commentaires"
        "share_count":    "partages",                       # "<N> partages"
        "repost_count":   "republications",                 # "Nombre de republications : <N>"
        "time_ago":       "Il y a",                         # "Il y a 4 heures"

        # Reels
        "reels_camera":   "Ouvrez l'appareil photo",
        "reels_for_you":  "Pour vous",
        "reel_header":    "Reel de",                        # "Reel de <user>"
        "follow":         "Suivre",                         # "Suivre <user>"
        "more_actions":   "Plus d'actions",
        "video_progress": "Progression de la vidéo",
        "audio_link":     "Accéder à la page de l'audio",

        # Profile
        "edit_profile":   "Modifier",
        "share_profile":  "Partager le profil",
        "followers":      "abonnés",
        "following":      "abonnements",
        "posts":          "publications",

        # Stories
        "story_reply":    "Envoyer un message",
        "story_like":     "J'aime",
        "story_next":     None,                             # tap droit de l'ecran
        "story_prev":     None,                             # tap gauche de l'ecran

        # Composer
        "share_post":     "Partager",
        "next_btn":       "Suivant",
        "caption_field":  "Écrire une légende",
        "gallery":        "Galerie",
        "photo":          "Photo",
        "video":          "Vidéo",

        # Common
        "back":           "Retour",
        "close":          "Fermer",
        "cancel":         "Annuler",
        "done":           "OK",
        "search":         "Rechercher",
    },
    "en": {
        "tab_home":       "Home",
        "tab_reels":      "Reels",
        "tab_explore":    "Search and Explore",
        "tab_dm":         "Direct",
        "tab_profile":    "Profile",
        "btn_create":     "Create",
        "btn_notifs":     "Notifications",
        "feed_title":     "Instagram Feed",
        "story_bar":      "Stories tray",
        "like":           "Like",
        "comment":        "Comment",
        "repost":         "Reshare",
        "send":           "Send",
        "save":           "Save",
        "post_header":    "Post by",
        "like_count":     "likes",
        "comment_count":  "comments",
        "share_count":    "shares",
        "repost_count":   "reshares",
        "time_ago":       "ago",
        "reels_camera":   "Open camera",
        "reels_for_you":  "For You",
        "reel_header":    "Reel by",
        "follow":         "Follow",
        "more_actions":   "More actions",
        "video_progress": "Video progress",
        "audio_link":     "Go to audio page",
        "edit_profile":   "Edit profile",
        "followers":      "followers",
        "following":      "following",
        "posts":          "posts",
        "story_reply":    "Send message",
        "story_like":     "Like",
        "story_next":     None,
        "story_prev":     None,
        "share_post":     "Share",
        "next_btn":       "Next",
        "caption_field":  "Write a caption",
        "gallery":        "Gallery",
        "photo":          "Photo",
        "video":          "Video",
        "back":           "Back",
        "close":          "Close",
        "cancel":         "Cancel",
        "done":           "Done",
        "search":         "Search",
    },
}


# ── Selecteur actif ───────────────────────────────────────────────────────────

_current_lang = "fr"


def set_lang(lang):
    global _current_lang
    if lang in LANG:
        _current_lang = lang


def sel(key):
    """Retourne le label pour la cle donnee dans la langue active."""
    return LANG[_current_lang].get(key, key)


# ── Bundle IDs ────────────────────────────────────────────────────────────────

IG_BUNDLE      = "com.burbn.instagram"
THREADS_BUNDLE = "com.burbn.barcelona"
SNAP_BUNDLE    = "com.toyopagroup.picaboo"
SAFARI_BUNDLE  = "com.apple.mobilesafari"


# ── Layout constants (iPhone X / 375x812) ─────────────────────────────────────
# Positions en fraction d'ecran pour s'adapter a tous les iPhones

BOTTOM_BAR_Y    = 0.927    # ~753/812 — centre Y de la bottom bar
TAB_HOME_X      = 0.099    # ~37/375
TAB_REELS_X     = 0.299    # ~112/375
TAB_DM_X        = 0.499    # ~187/375
TAB_EXPLORE_X   = 0.699    # ~262/375
TAB_PROFILE_X   = 0.899    # ~337/375

# Story tap zones (gauche = precedent, droite = suivant)
STORY_TAP_PREV_X = 0.15    # 15% gauche
STORY_TAP_NEXT_X = 0.85    # 85% droite
STORY_TAP_Y      = 0.40    # milieu haut de l'ecran
