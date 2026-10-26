#!/bin/bash
# Deploy Telegram group management — backend + bot patch + frontend
set -e
cd /root/scale-lab

echo "=== 1/5 Git pull ==="
git pull origin main

echo ""
echo "=== 2/5 Alembic migration ==="
cd apps/backend
source venv/bin/activate
alembic upgrade head
deactivate
cd /root/scale-lab

echo ""
echo "=== 3/5 Restart backend ==="
systemctl restart scalelab-api
sleep 2
curl -sf http://127.0.0.1:8000/health && echo " ✓ Backend healthy" || echo " ✗ Backend unhealthy"

echo ""
echo "=== 4/5 Patch bot for group notifications ==="
python3 scripts/patch_telegram_bot_groups.py
systemctl restart telegram-bot
sleep 2
# Test the bot HTTP is up
curl -sf http://127.0.0.1:8501/health && echo " ✓ Bot healthy" || echo " ✗ Bot may need manual check"

echo ""
echo "=== 5/5 Test new endpoints ==="
TOKEN="${SCALE_API_TOKEN:?Set SCALE_API_TOKEN}"
echo "Testing /api/telegram/groups/pending..."
curl -s -H "X-Scale-Token: $TOKEN" http://127.0.0.1:8000/api/telegram/groups/pending | python3 -m json.tool 2>/dev/null || echo "(no json output)"

echo ""
echo "=== Deploy backend done ==="
echo ""
echo "Now deploy frontend with:"
echo "  npx wrangler pages deploy apps/web/public --project-name=scale-lab --branch=main --commit-dirty=true"
