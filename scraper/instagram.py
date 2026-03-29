"""Scraping de perfis Instagram via Apify."""

import os
import re
import time
import unicodedata
from urllib.parse import urlparse

from apify_client import ApifyClient
from dotenv import load_dotenv

from scraper.utils import setup_logger

load_dotenv()
logger = setup_logger(__name__)

# Campos default quando nao ha Instagram
NO_INSTAGRAM = {
    "instagram_followers": "Sem perfil",
    "instagram_posts": "Sem perfil",
    "instagram_last_post": "Sem perfil",
    "instagram_engagement": "Sem perfil",
}

ERROR_INSTAGRAM = {
    "instagram_followers": "Erro ao raspar",
    "instagram_posts": "Erro ao raspar",
    "instagram_last_post": "Erro ao raspar",
    "instagram_engagement": "Erro ao raspar",
}


def _extract_username(instagram_url: str) -> str | None:
    """Extrai username do URL do Instagram.

    Aceita formatos como:
    - https://www.instagram.com/username/
    - https://instagram.com/username
    - instagram.com/username
    """
    match = re.search(r"instagram\.com/([a-zA-Z0-9_\.]+)", instagram_url)
    if match:
        username = match.group(1)
        # Ignorar paginas internas do Instagram
        if username in ("p", "explore", "reel", "stories", "accounts", "about"):
            return None
        return username
    return None


def _parse_profile_data(profile: dict) -> dict:
    """Extrai metricas de um perfil Instagram retornado pelo Apify.

    Args:
        profile: Dict retornado pelo Apify instagram-profile-scraper.

    Returns:
        Dict com: instagram_followers, instagram_posts,
        instagram_last_post, instagram_engagement.
    """
    followers = profile.get("followersCount", 0)
    posts_count = profile.get("postsCount", 0)

    # Ultimo post
    latest_posts = profile.get("latestPosts", [])
    last_post = ""
    if latest_posts:
        last_post = latest_posts[0].get("timestamp", "")
        if last_post:
            last_post = last_post[:10] if len(last_post) >= 10 else last_post

    # Engagement rate (media de likes+comments dos ultimos posts / followers)
    engagement = 0.0
    if followers > 0 and latest_posts:
        total_interactions = sum(
            p.get("likesCount", 0) + p.get("commentsCount", 0)
            for p in latest_posts[:12]
        )
        num_posts = min(len(latest_posts), 12)
        if num_posts > 0:
            avg_interactions = total_interactions / num_posts
            engagement = round((avg_interactions / followers) * 100, 2)

    return {
        "instagram_followers": followers,
        "instagram_posts": posts_count,
        "instagram_last_post": last_post,
        "instagram_engagement": engagement,
    }


def _guess_usernames(website: str, nome: str, sector: str = "", cidade: str = "") -> list[str]:
    """Gera ate 5 usernames provaveis para Instagram a partir do dominio/nome.

    Args:
        website: URL do site (ex: "http://www.watchnumber.pt/").
        nome: Nome do negocio (ex: "WATCHNUMBER - Contabilidade e Gestao").
        sector: Nicho do negocio (ex: "contabilidade").
        cidade: Cidade (ex: "Lisboa").

    Returns:
        Lista de ate 5 usernames candidatos, por ordem de probabilidade.
    """
    candidates = []
    base = ""
    tld = ""

    # Dominios de redes sociais/plataformas a ignorar
    ignore_domains = {
        "linkedin", "facebook", "instagram", "twitter", "youtube",
        "tiktok", "pinterest", "google", "wix", "wordpress",
        "squarespace", "shopify", "webflow", "github",
    }

    # Estrategia 1: Extrair do dominio (mais fiavel)
    if website:
        try:
            hostname = urlparse(website).hostname or ""
            domain = hostname.replace("www.", "")
            parts = domain.split(".")
            if len(parts) >= 2:
                base = parts[0]
                tld = parts[-1]

                # Ignorar dominios de redes sociais/plataformas
                if base.lower() in ignore_domains:
                    base = ""
                else:
                    # dominio.tld (ex: watchnumber.pt)
                    if tld in ("pt", "com", "eu", "net", "org"):
                        candidates.append(f"{base}.{tld}")

                    # dominio base (ex: watchnumber)
                    candidates.append(base)

                # dominio + tld colado (ex: watchnumberpt)
                if tld in ("pt", "com"):
                    candidates.append(f"{base}{tld}")
        except Exception:
            pass

    # Estrategia 2: Nome limpo (fallback se dominio nao gerou nada)
    if not base and nome:
        nfkd = unicodedata.normalize("NFKD", nome)
        ascii_name = nfkd.encode("ASCII", "ignore").decode("ASCII").lower()
        clean = ascii_name.split(" - ")[0].split(" | ")[0].strip()
        clean = re.sub(r"[^a-z0-9]", "", clean)
        if clean and len(clean) >= 3:
            base = clean
            candidates.append(clean)

    # Estrategia 3: Combinacoes com sector/cidade
    if base:
        if sector:
            sector_clean = re.sub(r"[^a-z0-9]", "", sector.lower())
            candidates.append(f"{base}.{sector_clean}")
        if cidade:
            cidade_clean = re.sub(r"[^a-z0-9]", "", cidade.lower())
            candidates.append(f"{base}_{cidade_clean}")

    # Deduplicar mantendo ordem, filtrar invalidos
    ignore_usernames = {"com", "pt", "eu", "net", "org", "www"}
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if (c not in seen
                and len(c) >= 3
                and len(c) <= 30
                and c not in ignore_usernames):
            seen.add(c)
            unique.append(c)

    return unique[:5]


def _try_scrape_username(username: str) -> dict | None:
    """Tenta raspar um perfil Instagram por username.

    Usa o mesmo actor Apify que ja funciona. Retorna dados se o
    perfil existir e tiver actividade, ou None se nao existir.

    Args:
        username: Username a tentar (sem @).

    Returns:
        Dict com dados IG + instagram_url se encontrado, ou None.
    """
    api_token = os.getenv("APIFY_API_TOKEN")
    if not api_token:
        return None

    logger.info("A tentar username Instagram: @%s", username)

    try:
        client = ApifyClient(api_token)
        run = client.actor("apify/instagram-profile-scraper").call(
            run_input={"usernames": [username], "resultsType": "details"}
        )
        items = client.dataset(run["defaultDatasetId"]).list_items().items

        if not items:
            logger.info("@%s: perfil nao existe ou vazio", username)
            return None

        profile = items[0]
        followers = profile.get("followersCount", 0)
        posts_count = profile.get("postsCount", 0)

        # Perfil deve ter alguma actividade
        if posts_count == 0 and followers == 0:
            logger.info("@%s: perfil existe mas sem actividade", username)
            return None

        result = _parse_profile_data(profile)
        result["instagram_url"] = f"https://www.instagram.com/{username}/"

        logger.info(
            "@%s encontrado via fallback: %d seguidores | %d posts",
            username, followers, posts_count,
        )

        return result

    except Exception as e:
        logger.warning("Erro ao tentar @%s: %s", username, e)
        return None


def scrape_instagram_profile(instagram_url: str) -> dict:
    """Raspa dados de um perfil Instagram via Apify.

    Args:
        instagram_url: URL do perfil Instagram.

    Returns:
        Dict com: instagram_followers, instagram_posts,
        instagram_last_post, instagram_engagement.
    """
    username = _extract_username(instagram_url)
    if not username:
        logger.warning("Nao foi possivel extrair username de: %s", instagram_url)
        return ERROR_INSTAGRAM

    api_token = os.getenv("APIFY_API_TOKEN")
    if not api_token:
        logger.error("APIFY_API_TOKEN nao definido no .env")
        return ERROR_INSTAGRAM

    logger.info("A raspar perfil Instagram: @%s", username)

    try:
        client = ApifyClient(api_token)

        run = client.actor("apify/instagram-profile-scraper").call(
            run_input={"usernames": [username], "resultsType": "details"}
        )

        items = client.dataset(run["defaultDatasetId"]).list_items().items

        if not items:
            logger.warning("Apify nao retornou dados para @%s", username)
            return ERROR_INSTAGRAM

        result = _parse_profile_data(items[0])

        logger.info(
            "@%s: %d seguidores | %d posts | Engagement: %.2f%%",
            username,
            result["instagram_followers"],
            result["instagram_posts"],
            result["instagram_engagement"],
        )

        return result

    except Exception as e:
        logger.error("Erro ao raspar @%s via Apify: %s", username, e)
        return ERROR_INSTAGRAM


def scrape_instagram_profiles(leads: list[dict]) -> list[dict]:
    """Raspa perfis Instagram de todos os leads.

    Modifica os leads in-place, adicionando campos Instagram.
    Leads sem instagram_url ficam com 'Sem perfil'.

    Args:
        leads: Lista de dicts de leads (deve ter key 'instagram_url').

    Returns:
        A mesma lista com campos Instagram adicionados.
    """
    logger.info("A raspar perfis Instagram de %d leads...", len(leads))

    for i, lead in enumerate(leads):
        instagram_url = lead.get("instagram_url")

        if instagram_url:
            logger.info(
                "[%d/%d] A raspar: %s (%s)",
                i + 1, len(leads), lead.get("nome", "?"), instagram_url,
            )
            ig_data = scrape_instagram_profile(instagram_url)

            # Rate limiting entre calls Apify
            time.sleep(2)
        else:
            # Sem link Instagram no site — tentar adivinhar username
            website = lead.get("website", "")
            business_name = lead.get("nome", "")
            sector = lead.get("sector", "")
            cidade = lead.get("cidade", "")
            candidates = _guess_usernames(website, business_name, sector, cidade)

            ig_data = None
            if candidates:
                logger.info(
                    "[%d/%d] %s: sem IG no site, a tentar fallback (%s)",
                    i + 1, len(leads), lead.get("nome", "?"),
                    ", ".join(f"@{c}" for c in candidates),
                )
                for candidate in candidates:
                    ig_data = _try_scrape_username(candidate)
                    time.sleep(2)
                    if ig_data:
                        # Actualizar instagram_url no lead
                        lead["instagram_url"] = ig_data.pop("instagram_url")
                        logger.info(
                            "[%d/%d] %s: Instagram encontrado via fallback: @%s",
                            i + 1, len(leads), lead.get("nome", "?"), candidate,
                        )
                        break

            if not ig_data:
                logger.info(
                    "[%d/%d] %s: sem Instagram (fallback tambem falhou)",
                    i + 1, len(leads), lead.get("nome", "?"),
                )
                ig_data = NO_INSTAGRAM

        lead.update(ig_data)

    logger.info("Scraping Instagram concluido")
    return leads
