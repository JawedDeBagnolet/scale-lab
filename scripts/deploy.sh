#!/bin/bash
set -euo pipefail

# ─── Scale Lab Deploy ───────────────────────────────────────────
# Usage :
#   ./scripts/deploy.sh                          → commit + build + deploy (changements locaux)
#   ./scripts/deploy.sh archive.tar.gz           → extract + commit + build + deploy
#   ./scripts/deploy.sh archive.tar.gz "message"  → idem avec message de commit custom
#
# Workflow : extract → git commit → npm build → wrangler deploy → git tag
# Le commit est AVANT le deploy : en cas de problème, git revert est propre.
# ────────────────────────────────────────────────────────────────

REPO="/root/scale-lab"
WEB="$REPO/apps/web"
ENV_FILE="$REPO/.env.deploy"
ARCHIVE="${1:-}"
MSG="${2:-}"

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
echo "║       Scale Lab — Deploy             ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. Extract archive (si fournie) ──────────────────────────
if [[ -n "$ARCHIVE" ]]; then
  if [[ ! -f "$ARCHIVE" ]]; then
    echo "❌ Archive introuvable : $ARCHIVE"
    exit 1
  fi
  echo "📦 Extraction de $ARCHIVE..."
  tar xzf "$ARCHIVE" -C "$WEB/public"
  echo "   ✓ Fichiers extraits"
  echo ""
fi

# ── 2. Vérifier qu'il y a des changements ────────────────────
if git diff --quiet && git diff --cached --quiet && [[ -z "$(git ls-files --others --exclude-standard)" ]]; then
  echo "ℹ️  Aucun changement détecté. Rien à déployer."
  exit 0
fi

# ── 3. Afficher les changements ──────────────────────────────
echo "📝 Changements détectés :"
git status --short
echo ""

# ── 4. Commit ────────────────────────────────────────────────
git add -A

if [[ -z "$MSG" ]]; then
  # Générer un message auto à partir des fichiers modifiés
  CHANGED=$(git diff --cached --name-only | head -5)
  COUNT=$(git diff --cached --name-only | wc -l)
  MSG="deploy: update ${COUNT} file(s)"$'\n\n'"Files:"$'\n'"${CHANGED}"
  if [[ "$COUNT" -gt 5 ]]; then
    MSG="${MSG}"$'\n'"... and $((COUNT - 5)) more"
  fi
fi

echo "💾 Commit..."
git commit -m "$MSG"
COMMIT_HASH=$(git rev-parse --short HEAD)
echo "   ✓ Commit $COMMIT_HASH"
echo ""

# ── 5. Push (sauvegarder avant de déployer) ──────────────────
echo "⬆️  Push vers GitHub..."
git push origin main
echo "   ✓ Code sauvegardé sur GitHub"
echo ""

# ── 6. Build frontend ───────────────────────────────────────
echo "🔨 Build frontend..."
cd "$WEB"
npm run build 2>&1 | tail -3
echo "   ✓ Build terminé"
echo ""

# ── 7. Deploy Cloudflare Pages ───────────────────────────────
echo "🚀 Deploy Cloudflare Pages..."
CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN" npx wrangler pages deploy dist \
  --project-name=scale-lab --branch=main 2>&1 | tail -5
echo "   ✓ Déployé sur Cloudflare"
echo ""

# ── 8. Tag le deploy ────────────────────────────────────────
cd "$REPO"
TAG="deploy-$(date +%Y%m%d-%H%M%S)"
git tag "$TAG"
git push origin "$TAG" 2>/dev/null || true
echo "🏷️  Tag : $TAG ($COMMIT_HASH)"

echo ""
echo "══════════════════════════════════════"
echo "✅ Deploy terminé avec succès !"
echo "   Commit : $COMMIT_HASH"
echo "   Tag    : $TAG"
echo "   Rollback : ./scripts/rollback.sh"
echo "══════════════════════════════════════"
echo ""
