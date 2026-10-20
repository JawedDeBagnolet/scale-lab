#!/bin/bash
set -euo pipefail

# ─── Scale Lab — Deploy Telegram Integration ────────────────────
# Usage (sur le VPS) :
#   cd /root/scale-lab && bash scripts/deploy-telegram.sh
#
# Etapes :
#   1. git pull (recuperer les fichiers)
#   2. Alembic migration 005 (table telegram_pending)
#   3. Redemarrer le backend FastAPI
#   4. Patcher le bot Telegram
#   5. Installer + demarrer le service systemd du bot
#   6. Verifier que tout tourne
# ────────────────────────────────────────────────────────────────

REPO="/root/scale-lab"
BACKEND="$REPO/apps/backend"
VENV="$BACKEND/venv"
PYTHON="$VENV/bin/python3"
ALEMBIC="$VENV/bin/alembic"

cd "$REPO"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Scale Lab — Deploy Telegram            ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Pull ──────────────────────────────────────────────────
echo "⬇️  git pull..."
git pull origin main
echo "   ✓ Code a jour"
echo ""

# ── 2. Migration Alembic ─────────────────────────────────────
echo "🗃️  Migration Alembic (005_telegram_pending)..."
cd "$BACKEND"

# Verifier si la migration est deja appliquee
CURRENT=$($ALEMBIC current 2>/dev/null | grep -oP '^\S+' || echo "none")
echo "   Version actuelle : $CURRENT"

if [[ "$CURRENT" == *"005"* ]]; then
  echo "   ✓ Migration 005 deja appliquee, skip"
else
  $ALEMBIC upgrade head
  echo "   ✓ Migration appliquee"
fi
echo ""

# ── 3. Redemarrer le backend ─────────────────────────────────
echo "🔄 Redemarrage du backend FastAPI..."
systemctl restart scalelab-api
sleep 2

if systemctl is-active --quiet scalelab-api; then
  echo "   ✓ Backend actif"
else
  echo "   ❌ Backend ne demarre pas !"
  journalctl -u scalelab-api --no-pager -n 15
  exit 1
fi
echo ""

# ── 4. Verifier endpoint Telegram ────────────────────────────
echo "🧪 Test endpoint /api/telegram/pending..."
# Lire le token API depuis le .env du backend
API_SECRET=""
if [[ -f "$BACKEND/.env" ]]; then
  API_SECRET=$(grep -oP '^API_SECRET=\K.*' "$BACKEND/.env" | tr -d '"' | tr -d "'")
fi

if [[ -z "$API_SECRET" ]]; then
  echo "   ⚠️  API_SECRET non trouve dans .env, skip test"
else
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "X-Scale-Token: $API_SECRET" \
    "http://127.0.0.1:8000/api/telegram/pending")
  if [[ "$HTTP_CODE" == "200" ]]; then
    echo "   ✓ Endpoint repond (HTTP $HTTP_CODE)"
  else
    echo "   ⚠️  Endpoint repond HTTP $HTTP_CODE (verifier les logs)"
  fi
fi
echo ""

# ── 5. Patcher le bot Telegram ───────────────────────────────
echo "🤖 Patch du bot Telegram..."
$PYTHON "$REPO/scripts/patch_telegram_bot.py"
echo ""

# ── 6. Installer le service systemd ──────────────────────────
echo "⚙️  Installation du service systemd telegram-bot..."

# Copier le fichier service
cp "$REPO/scripts/telegram-bot.service" /etc/systemd/system/telegram-bot.service

# Recharger systemd
systemctl daemon-reload

# Activer au demarrage
systemctl enable telegram-bot

# (Re)demarrer le bot
systemctl restart telegram-bot
sleep 2

if systemctl is-active --quiet telegram-bot; then
  echo "   ✓ Bot Telegram actif"
else
  echo "   ❌ Bot ne demarre pas !"
  journalctl -u telegram-bot --no-pager -n 15
  exit 1
fi
echo ""

# ── 7. Verification finale ──────────────────────────────────
echo "══════════════════════════════════════════"
echo ""
echo "✅ Deploy Telegram termine !"
echo ""
echo "Services actifs :"
echo "   • scalelab-api   : $(systemctl is-active scalelab-api)"
echo "   • telegram-bot   : $(systemctl is-active telegram-bot)"
echo ""
echo "Endpoints disponibles :"
echo "   POST /api/telegram/bot/start     (appele par le bot)"
echo "   GET  /api/telegram/pending       (liste des inscriptions)"
echo "   GET  /api/telegram/status/{id}   (statut d'une persona)"
echo "   POST /api/telegram/link/{id}     (lier une modele)"
echo "   DELETE /api/telegram/link/{id}   (delier)"
echo ""
echo "Deep link :"
echo "   https://t.me/ScaleCrewBot?start=<persona_id>"
echo ""
echo "══════════════════════════════════════════"
echo ""
