"""IG Private API proxy — expose read-only IG data to the frontend.

Provides:
- User search with autocomplete (profile pics, verification badge)
- User profiles and publications
- Music search and trending (with preview URLs)
- Account insights/stats
- Session verification

Every call requires a `compte_id` query param to identify which IG session to use.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.ig_api import IGApiClient

router = APIRouter(prefix="/ig", tags=["ig-proxy"])


async def _get_client(compte_id: str, db: AsyncSession) -> IGApiClient:
    """Helper — build an IGApiClient from a compte_id or raise 400."""
    client = await IGApiClient.from_compte(db, compte_id)
    if not client:
        raise HTTPException(400, "Session IG indisponible pour ce compte")
    return client


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Recherche de comptes (autocomplete)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/search/users")
async def search_users(
    q: str = Query(..., min_length=1, description="Recherche @username"),
    compte_id: str = Query(..., description="UUID du compte IG à utiliser"),
    count: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Recherche de comptes IG — retourne username, photo de profil, badge vérifié.

    Utilisé pour l'autocomplete dans la veille, les targets, et toute barre
    de recherche IG de l'application.
    """
    client = await _get_client(compte_id, db)
    try:
        return await client.search_users(q, count)
    except Exception as e:
        raise HTTPException(502, f"Erreur API IG: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Profil utilisateur
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/user/{user_pk}")
async def get_user(
    user_pk: str,
    compte_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Profil complet d'un utilisateur IG — bio, stats, photo HD."""
    client = await _get_client(compte_id, db)
    try:
        info = await client.get_user_info(user_pk)
        if not info:
            raise HTTPException(404, "Utilisateur non trouvé")
        return info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Erreur API IG: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Publications d'un utilisateur
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/user/{user_pk}/feed")
async def get_user_feed(
    user_pk: str,
    compte_id: str = Query(...),
    count: int = Query(12, ge=1, le=50),
    max_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Publications d'un profil IG — images, vidéos, carousel, stats d'engagement.

    Supporte la pagination via max_id (retourné dans la réponse).
    Utilisé dans la veille pour scanner les publications d'un compte cible.
    """
    client = await _get_client(compte_id, db)
    try:
        return await client.get_user_feed(user_pk, count, max_id)
    except Exception as e:
        raise HTTPException(502, f"Erreur API IG: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Timeline (feed)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/feed")
async def get_feed(
    compte_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Feed timeline du compte — publications des comptes suivis."""
    client = await _get_client(compte_id, db)
    try:
        return await client.get_timeline()
    except Exception as e:
        raise HTTPException(502, f"Erreur API IG: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Musique — recherche et trending
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/music/search")
async def search_music(
    q: str = Query(..., min_length=1),
    compte_id: str = Query(...),
    count: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Recherche de sons — retourne titre, artiste, pochette, URL de preview.

    Utilisé dans le module Posting pour la médiathèque de sons.
    La preview_url permet d'écouter un extrait directement dans le frontend.
    """
    client = await _get_client(compte_id, db)
    try:
        return await client.search_music(q, count)
    except Exception as e:
        raise HTTPException(502, f"Erreur API IG: {e}")


@router.get("/music/trending")
async def get_trending_music(
    compte_id: str = Query(...),
    count: int = Query(30, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Sons tendance — les tracks les plus utilisées sur les Reels."""
    client = await _get_client(compte_id, db)
    try:
        return await client.get_trending_music(count)
    except Exception as e:
        raise HTTPException(502, f"Erreur API IG: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Stats / Analytics
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/stats/{user_pk}")
async def get_user_stats(
    user_pk: str,
    compte_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Stats complètes d'un compte — followers, following, posts, bio.

    Utilisé dans le module Statistiques pour les KPIs de nos comptes.
    """
    client = await _get_client(compte_id, db)
    try:
        info = await client.get_user_info(user_pk)
        if not info:
            raise HTTPException(404, "Utilisateur non trouvé")
        return info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Erreur API IG: {e}")


@router.get("/stats/{user_pk}/insights")
async def get_account_insights(
    user_pk: str,
    compte_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Insights du compte (nécessite un compte professionnel/créateur).

    Reach, impressions, engagement sur la dernière semaine.
    """
    client = await _get_client(compte_id, db)
    try:
        insights = await client.get_account_insights(user_pk)
        if insights is None:
            raise HTTPException(403, "Insights non disponibles (compte personnel ?)")
        return insights
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Erreur API IG: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Vérification de session
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/session/verify")
async def verify_session(
    compte_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Vérifie que la session IG du compte est toujours valide."""
    client = await _get_client(compte_id, db)
    try:
        return await client.verify()
    except Exception as e:
        raise HTTPException(502, f"Erreur vérification: {e}")
