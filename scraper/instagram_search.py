"""Pesquisa de empresas no Instagram via Apify (segunda fonte de leads)."""

import os
import re
import time

from apify_client import ApifyClient
from dotenv import load_dotenv

from crm.sheets import get_contacted_phones
from scraper.utils import is_portuguese_mobile, normalize_phone, setup_logger

load_dotenv()
logger = setup_logger(__name__)


def _extract_phone_from_bio(bio: str) -> str | None:
    """Extrai telefone portugues da bio do Instagram.

    Procura formatos:
    - +351 9XX XXX XXX
    - 351 9XXXXXXXX
    - 9XX XXX XXX
    - 9XXXXXXXX
    - wa.me/351XXXXXXXXX
    - whatsapp: 9XXXXXXXX
    """
    if not bio:
        return None

    # Limpar bio
    bio_clean = bio.replace("\n", " ")

    # 1. Procurar wa.me links
    wa_match = re.search(r"wa\.me/(\+?351)?(\d{9})", bio_clean)
    if wa_match:
        digits = wa_match.group(2)
        if digits.startswith("9"):
            return normalize_phone(digits)

    # 2. Procurar telefones portugueses
    # Formato internacional: +351 9XX XXX XXX
    intl_match = re.search(r"\+?351[\s.-]?(9\d{2})[\s.-]?(\d{3})[\s.-]?(\d{3})", bio_clean)
    if intl_match:
        phone = f"9{intl_match.group(1)[1:]}{intl_match.group(2)}{intl_match.group(3)}"
        return normalize_phone(phone)

    # Formato local: 9XX XXX XXX ou 9XXXXXXXX
    local_match = re.search(r"(?<!\d)(9\d{2})[\s.-]?(\d{3})[\s.-]?(\d{3})(?!\d)", bio_clean)
    if local_match:
        phone = f"{local_match.group(1)}{local_match.group(2)}{local_match.group(3)}"
        return normalize_phone(phone)

    return None


def _extract_email_from_bio(bio: str) -> str | None:
    """Extrai email da bio do Instagram."""
    if not bio:
        return None
    match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", bio)
    return match.group(0) if match else None


def _extract_website_from_bio(bio: str, external_url: str | None = None) -> str | None:
    """Extrai website da bio ou do external URL do perfil."""
    if external_url and external_url.startswith("http"):
        return external_url

    if not bio:
        return None

    # Procurar URLs na bio
    match = re.search(r"https?://[^\s]+", bio)
    if match:
        return match.group(0)

    # Procurar dominios sem http
    match = re.search(r"(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,}[^\s]*)", bio)
    if match:
        return f"https://{match.group(0)}"

    return None


def _build_hashtags(nicho: str, cidade: str) -> list[str]:
    """Gera lista de hashtags para pesquisa.

    Ex: nicho='contabilidade', cidade='Lisboa'
    → ['contabilidade lisboa', 'contabilidade', 'gabinete contabilidade lisboa']
    """
    nicho_clean = nicho.strip().lower()
    cidade_clean = cidade.strip().lower()

    keywords = [
        f"{nicho_clean} {cidade_clean}",
        nicho_clean,
        f"{nicho_clean} portugal",
    ]

    return keywords


def search_instagram(nicho: str, cidade: str) -> list[dict]:
    """Pesquisa perfis de negocios no Instagram por nicho + cidade.

    Usa o Apify Instagram Search Scraper para encontrar perfis,
    extrai contacto da bio, e filtra por telemovel portugues.

    Args:
        nicho: Sector de negocio (ex: 'contabilidade')
        cidade: Cidade (ex: 'Lisboa')

    Returns:
        Lista de leads com keys: nome, telefone, cidade, sector,
        instagram_url, instagram_followers, instagram_posts,
        instagram_engagement, instagram_bio, website, email
    """
    api_token = os.getenv("APIFY_API_TOKEN")
    if not api_token:
        logger.error("APIFY_API_TOKEN nao definida no .env")
        return []

    # Buscar telefones ja contactados para dedup
    contacted = get_contacted_phones()
    logger.info("Instagram dedup: %d telefones ja registados", len(contacted))

    client = ApifyClient(api_token)
    keywords = _build_hashtags(nicho, cidade)
    logger.info("A pesquisar Instagram com keywords: %s", keywords)

    all_profiles: list[dict] = []
    seen_usernames: set[str] = set()

    for keyword in keywords:
        logger.info("Instagram search: '%s'...", keyword)

        try:
            run_input = {
                "keywords": [keyword],
                "searchType": "user",
                "resultsPerKeyword": 30,
            }

            run = client.actor("apify/instagram-search-scraper").call(
                run_input=run_input
            )
            items = client.dataset(run["defaultDatasetId"]).list_items().items

            for profile in items:
                username = profile.get("username", "")
                if username in seen_usernames:
                    continue
                seen_usernames.add(username)

                # Ignorar perfis privados
                if profile.get("privateAccount"):
                    continue

                all_profiles.append(profile)

            logger.info("'%s': %d perfis encontrados", keyword, len(items))

        except Exception as e:
            logger.error("Erro na pesquisa Instagram '%s': %s", keyword, e)

        time.sleep(2)

    logger.info("Total perfis unicos encontrados: %d", len(all_profiles))

    # Processar perfis e extrair leads
    leads: list[dict] = []

    for profile in all_profiles:
        username = profile.get("username", "")
        full_name = profile.get("fullName", username)
        bio = profile.get("bio", "")
        followers = profile.get("followersCount", 0)
        posts_count = profile.get("postsCount", 0)
        external_url = profile.get("url") or profile.get("externalUrl")

        # Ignorar perfis muito pequenos (provavelmente pessoais)
        if followers and followers < 50:
            logger.info("@%s: %d seguidores (< 50) — a saltar", username, followers)
            continue

        # Extrair contacto da bio
        phone = _extract_phone_from_bio(bio)

        if not phone:
            logger.info("@%s: sem telefone na bio — a saltar", username)
            continue

        if not is_portuguese_mobile(phone):
            logger.info("@%s: telefone %s nao e telemovel PT — a saltar", username, phone)
            continue

        # Dedup com Sheets
        if phone in contacted:
            logger.info("@%s: %s ja contactado — a saltar", username, phone)
            continue

        # Extrair outros dados da bio
        email = _extract_email_from_bio(bio)
        website = _extract_website_from_bio(bio, external_url)

        lead = {
            "nome": full_name or username,
            "telefone": phone,
            "cidade": cidade,
            "sector": nicho,
            "rating": 0,
            "reviews": 0,
            "website": website or "",
            "morada": "",
            "place_id": "",
            "instagram_url": f"https://www.instagram.com/{username}/",
            "instagram_followers": followers,
            "instagram_posts": posts_count,
            "instagram_bio": bio,
            "instagram_last_post": "",
            "instagram_engagement": 0,
            "fonte": "instagram",
        }

        leads.append(lead)
        contacted.add(phone)

        logger.info(
            "Lead IG: @%s (%s) | %s | %d seguidores",
            username, full_name, phone, followers,
        )

    logger.info(
        "Instagram: %d perfis → %d leads com telemovel PT",
        len(all_profiles), len(leads),
    )

    return leads
