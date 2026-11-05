# AI Agent — Design Document

## Contexte

Le script de feed IG actuel (ig_runner.py) utilise des regex, des coordonnées
en dur et de la détection d'écran fragile. Chaque mise à jour d'Instagram casse
potentiellement le script. L'idée : remplacer (ou assister) le script par un
agent IA qui voit l'écran et décide en temps réel.

## Architecture retenue

```
Boucle agent (~3s par action) :

  iPhone (ios-mcp)
      │
      │ get_ui_elements → arbre accessibilité (texte, ~5-15KB)
      │
      ▼
  VPS (FastAPI)
      │
      │ POST https://api.scalelab.win/ai/agent-step
      │   body: { ui_tree, mission, history[] }
      │
      ▼
  Cloudflare Worker AI  (Workers AI binding)
      │
      │ Llama 3.2 3B ou Qwen3 30B-A3B
      │ Input: prompt système + arbre UI + historique des 5 dernières actions
      │ Output: { "action": "tap_screen", "args": { "x": 187, "y": 650 }, "reason": "like button" }
      │
      ▼
  VPS exécute l'action via MCP
      │
      └── Retour en haut de la boucle
```

### Pourquoi Cloudflare Workers AI

- Déjà sur notre infra (même compte, même réseau edge)
- Modèles petits et rapides (1-3B), pas besoin de vision
- Quasi gratuit : ~$0.001 par session de 120s (~40 appels)
- 10 000 neurons/jour en free tier
- Pas de clé API externe à gérer

### Pourquoi l'arbre d'accessibilité (pas screenshot)

- Texte pur → pas besoin de modèle vision (10x moins cher, 3x plus rapide)
- Contient labels, positions, types d'éléments → plus riche qu'un OCR
- ~5-15KB vs ~200-400KB pour un screenshot
- Un modèle 3B peut traiter du texte structuré efficacement

## Perception (input)

```
get_ui_elements via MCP → arbre JSON :
[
  { "text": "Photo de username", "type": "image", "x": 187, "y": 320, "w": 375, "h": 400 },
  { "text": "J'aime", "type": "button", "x": 30, "y": 650 },
  { "text": "Commenter", "type": "button", "x": 90, "y": 650 },
  { "text": "Accueil", "type": "tab", "x": 37, "y": 780 },
  ...
]
```

On simplifie avant d'envoyer au LLM (filtrer les éléments non pertinents,
tronquer à ~50 éléments max).

## Cerveau (prompt)

Deux niveaux possibles :

### Option A : Agent unique (simple)

```
Système : Tu contrôles un iPhone sur Instagram. Ta mission : {mission}.
Tu reçois l'arbre d'accessibilité de l'écran.
Réponds UNIQUEMENT en JSON : { "action": "...", "args": {...}, "reason": "..." }

Actions possibles :
- tap_screen {x, y} — taper à une position
- tap_element {text} — taper sur un élément par son label
- swipe_screen {fromX, fromY, toX, toY} — swipe/scroll
- type_text {text} — saisir du texte
- wait {seconds} — attendre
- done {} — mission terminée

Historique des 5 dernières actions : [...]
Arbre UI actuel : [...]
```

### Option B : Planner + Actor (plus robuste, inspiré ESP32 agent)

- **Planner** : reçoit la mission + l'état actuel → décide l'étape haut niveau
  ("liker ce post", "scroller au prochain", "revenir au feed")
- **Actor** : traduit l'étape en geste concret avec coordonnées
  ({ action: "tap_screen", args: { x: 30, y: 650 } })

Le planner est appelé moins souvent (quand l'état change significativement).
L'actor est appelé à chaque cycle.

## Mains (output → MCP)

Le VPS traduit la réponse JSON en appel MCP :

```python
action = llm_response["action"]
args = llm_response["args"]
await mcp_call(mcp_port, action, args)
```

## Recovery

- Si l'agent détecte un écran inconnu → il essaie de revenir (retour, home)
- Si 3 actions échouent d'affilée → abort la session
- Si le LLM renvoie un JSON invalide → retry une fois, puis skip

## Modèles candidats (Cloudflare Workers AI)

| Modèle | Params | Input/1M | Output/1M | Notes |
|---|---|---|---|---|
| Llama 3.2 1B | 1B | $0.027 | $0.201 | Ultra rapide, peut suffire |
| Llama 3.2 3B | 3B | $0.051 | $0.335 | Bon compromis vitesse/qualité |
| Qwen3 30B-A3B | 3B actifs | $0.051 | $0.335 | MoE, potentiellement meilleur |
| Llama 3.1 8B | 8B | $0.152 | $0.287 | Si les petits ne suffisent pas |

## Coût estimé

- Session feed 120s : ~40 actions × ~500 tokens input + ~50 tokens output
- Total : ~22K tokens/session
- Llama 3.2 3B : ~$0.001/session → ~$0.05/jour pour 50 sessions
- Free tier : 10K neurons/jour couvre plusieurs sessions

## Latence estimée par cycle

| Étape | Durée |
|---|---|
| get_ui_elements (MCP) | ~0.8-1.5s |
| Worker AI inference (3B) | ~0.5-1.5s |
| Exécution action (MCP) | ~0.3-0.5s |
| **Total** | **~2-3.5s** |

Acceptable — un humain fait 1-3s/action mais avec des pauses de 2-5s pour lire.

## Avantages vs scripts

- ✅ Pas de regex ni coordonnées en dur
- ✅ S'adapte aux mises à jour d'Instagram automatiquement
- ✅ Recovery naturelle (l'IA sait revenir en arrière)
- ✅ Comportement plus naturel (décisions contextuelles)
- ✅ Moins de maintenance

## Risques

- ⚠️ Latence ~3s/action vs ~0.5s pour un script
- ⚠️ Le modèle 3B peut se tromper sur des cas edge
- ⚠️ Dépendance à Cloudflare Workers AI (disponibilité)
- ⚠️ Coût résiduel (même faible)

## Approche hybride (recommandée pour la v1)

Script pour les actions rapides (scroll, timing) + Agent IA en recovery :

```
Script (rapide, 0.5-2s/action)
    ↓ écran inconnu
Agent IA (3-5s, screenshot ou UI tree → LLM → recovery)
    ↓ résolu
Script reprend
```

Migration progressive : commencer par le recovery, puis étendre l'agent
à plus de décisions quand la fiabilité est prouvée.

## Implémentation future

1. Worker Cloudflare `apps/gateway/src/agent.ts` — endpoint `/ai/agent-step`
2. Binding Workers AI dans `wrangler.toml`
3. Service backend `app/services/ai_agent.py` — boucle agent
4. Intégration dans `ig_runner.py` — fallback vers l'agent
5. Prompts dans `apps/backend/prompts/` — planner.txt, actor.txt

## Références

- ESP32 iPhone Agent : https://github.com/onehumanbeing/esp32-iphone-agent
- Cloudflare Workers AI : https://developers.cloudflare.com/workers-ai/
- ios-mcp tools : voir WORKFLOW.md section 6
