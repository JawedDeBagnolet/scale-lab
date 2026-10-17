#!/bin/bash
set -euo pipefail

# ─── Scale Lab Rollback ─────────────────────────────────────────
# Usage :
#   ./scripts/rollback.sh              → rollback au deploy précédent
#   ./scripts/rollback.sh list         → voir les 10 derniers deploys
#   ./scripts/rollback.sh <tag>        → rollback à un tag spécifique
#   ./scripts/rollback.sh <commit>     → rollback à un commit spécifique
#
# Ce script remet le code frontend à l'état d'un commit/tag antérieur,
# rebuild et redéploie. Le rollback est lui-même un nouveau commit
# (pas de rewrite d'historique, pas de perte).
# ────────────────────────────────────────────────────────────────

REPO="/root/scale-lab"
WEB="$REPO/apps/web"
ENV_FILE="$REPO/.env.deploy"
TARGET="${1:-}"

# Charger le token Cloudflare
if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ Fichier $ENV_FILE introuvable."
  echo "   Créez-le avec : echo 'CLOUDFLARE_API_TOKEN=votre_token' > $ENV_FILE"
  exit 1
fi
source "$ENV_FILE"
if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  echo "❌ CLOUDFLARE_API_TOKEN non défini dans $ENV_FILE"
  exit 1
fi

cd "$REPO"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║       Scale Lab — Rollback           ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Mode "list" : afficher les derniers deploys ──────────────
if [[ "$TARGET" == "list" ]]; then
  echo "📋 Derniers deploys (tags) :"
  echo ""
  git tag -l 'deploy-*' --sort=-creatordate | head -10 | while read -r tag; do
    HASH=$(git rev-parse --short "$tag")
    DATE=$(git log -1 --format="%ci" "$tag" 2>/dev/null | cut -d' ' -f1,2)
    MSG=$(git log -1 --format="%s" "$tag" 2>/dev/null)
    echo "  🏷️  $tag  ($HASH)  $DATE"
    echo "      $MSG"
    echo ""
  done

  echo "📋 Derniers commits :"
  echo ""
  git log --oneline -10
  echo ""
  echo "Usage : ./scripts/rollback.sh <tag-ou-commit>"
  exit 0
fi

# ── Déterminer la cible du rollback ──────────────────────────
if [[ -z "$TARGET" ]]; then
  # Par défaut : dernier tag deploy-* (= deploy précédent)
  # On prend l'avant-dernier tag puisque le dernier = l'état actuel
  TAGS=$(git tag -l 'deploy-*' --sort=-creatordate)
  TAG_COUNT=$(echo "$TAGS" | wc -l)

  if [[ "$TAG_COUNT" -lt 2 ]]; then
    # Pas assez de tags, on revient au commit précédent
    TARGET="HEAD~1"
    echo "⚠️  Pas assez de tags deploy. Rollback au commit précédent."
  else
    TARGET=$(echo "$TAGS" | sed -n '2p')
    echo "🎯 Rollback au deploy précédent : $TARGET"
  fi
else
  echo "🎯 Rollback vers : $TARGET"
fi

# Vérifier que la cible existe
if ! git rev-parse "$TARGET" &>/dev/null; then
  echo "❌ Cible introuvable : $TARGET"
  echo "   Utilisez './scripts/rollback.sh list' pour voir les options."
  exit 1
fi

TARGET_HASH=$(git rev-parse --short "$TARGET")
TARGET_MSG=$(git log -1 --format="%s" "$TARGET" 2>/dev/null)
echo "   Commit : $TARGET_HASH — $TARGET_MSG"
echo ""

# ── Confirmation ─────────────────────────────────────────────
CURRENT_HASH=$(git rev-parse --short HEAD)
CURRENT_MSG=$(git log -1 --format="%s" HEAD)
echo "📌 État actuel : $CURRENT_HASH — $CURRENT_MSG"
echo "🔙 Retour vers : $TARGET_HASH — $TARGET_MSG"
echo ""
read -rp "Confirmer le rollback ? (o/N) " CONFIRM
if [[ "$CONFIRM" != "o" && "$CONFIRM" != "O" && "$CONFIRM" != "oui" ]]; then
  echo "Annulé."
  exit 0
fi
echo ""

# ── 1. Restaurer les fichiers frontend ───────────────────────
echo "🔄 Restauration des fichiers frontend..."
git checkout "$TARGET" -- apps/web/public/
echo "   ✓ Fichiers restaurés depuis $TARGET_HASH"
echo ""

# ── 2. Commit le rollback ────────────────────────────────────
echo "💾 Commit du rollback..."
git add -A
git commit -m "rollback: revert frontend to $TARGET_HASH ($TARGET_MSG)"
ROLLBACK_HASH=$(git rev-parse --short HEAD)
echo "   ✓ Commit $ROLLBACK_HASH"
echo ""

# ── 3. Push ──────────────────────────────────────────────────
echo "⬆️  Push..."
git push origin main
echo "   ✓ Sauvegardé sur GitHub"
echo ""

# ── 4. Build ─────────────────────────────────────────────────
echo "🔨 Build frontend..."
cd "$WEB"
npm run build 2>&1 | tail -3
echo "   ✓ Build terminé"
echo ""

# ── 5. Deploy ────────────────────────────────────────────────
echo "🚀 Deploy Cloudflare Pages..."
CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN" npx wrangler pages deploy dist \
  --project-name=scale-lab --branch=main 2>&1 | tail -5
echo "   ✓ Redéployé"
echo ""

# ── 6. Tag ───────────────────────────────────────────────────
cd "$REPO"
TAG="rollback-$(date +%Y%m%d-%H%M%S)"
git tag "$TAG"
git push origin "$TAG" 2>/dev/null || true

echo ""
echo "══════════════════════════════════════"
echo "✅ Rollback terminé !"
echo "   Depuis : $CURRENT_HASH"
echo "   Vers   : $TARGET_HASH"
echo "   Commit : $ROLLBACK_HASH"
echo "   Tag    : $TAG"
echo "══════════════════════════════════════"
echo ""
