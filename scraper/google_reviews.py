"""Scraping de reviews do Google Maps via Apify."""

import os

from apify_client import ApifyClient
from dotenv import load_dotenv

from scraper.utils import setup_logger

load_dotenv()
logger = setup_logger(__name__)

# Actor Apify para reviews do Google Maps
ACTOR_ID = "compass/google-maps-reviews-scraper"

# Defaults
DEFAULT_MAX_REVIEWS = 30
DEFAULT_LANGUAGE = "pt-PT"


def scrape_google_reviews(place_id: str, max_reviews: int = DEFAULT_MAX_REVIEWS) -> dict:
    """Raspa reviews do Google Maps para um place_id via Apify.

    Args:
        place_id: Google Maps place_id (ex: 'ChIJ8_JBApXMDUcRDzXcYUPTGUY').
        max_reviews: Numero maximo de reviews a extrair.

    Returns:
        Dict com:
            - reviews_text: lista de dicts com texto, rating, data, autor
            - reviews_negativas: lista de textos de reviews com rating <= 3
            - reviews_positivas: lista de textos de reviews com rating >= 4
            - total_reviews_scraped: numero de reviews extraidas
    """
    api_token = os.getenv("APIFY_API_TOKEN")
    if not api_token:
        logger.error("APIFY_API_TOKEN nao definido no .env")
        return _empty_result()

    if not place_id:
        logger.warning("place_id vazio — sem reviews para raspar")
        return _empty_result()

    logger.info("A raspar reviews do Google Maps (place_id: %s, max: %d)...", place_id, max_reviews)

    try:
        client = ApifyClient(api_token)
        run_input = {
            "placeIds": [f"place_id:{place_id}"],
            "maxReviews": max_reviews,
            "language": DEFAULT_LANGUAGE,
            "personalData": True,
        }

        run = client.actor(ACTOR_ID).call(run_input=run_input)
        items = client.dataset(run["defaultDatasetId"]).list_items().items

        if not items:
            logger.warning("Apify nao retornou reviews para place_id: %s", place_id)
            return _empty_result()

        return _parse_reviews(items)

    except Exception as e:
        logger.error("Erro ao raspar reviews (place_id: %s): %s", place_id, e)
        return _empty_result()


def _parse_reviews(items: list[dict]) -> dict:
    """Processa items do Apify e extrai reviews estruturadas.

    Args:
        items: Lista de reviews retornadas pelo Apify.

    Returns:
        Dict com reviews processadas.
    """
    reviews_text = []
    reviews_negativas = []
    reviews_positivas = []

    for item in items:
        # O actor retorna campos como: text, stars, publishedAtDate, name
        # Tentar varios nomes de campos (diferentes actors usam nomes diferentes)
        texto = (
            item.get("text")
            or item.get("reviewText")
            or item.get("textTranslated")
            or ""
        )
        rating = (
            item.get("stars")
            or item.get("reviewRating")
            or item.get("rating")
            or 0
        )
        data = (
            item.get("publishedAtDate")
            or item.get("publishAt")
            or item.get("date")
            or ""
        )
        autor = (
            item.get("name")
            or item.get("authorName")
            or item.get("reviewer", {}).get("name", "")
            if isinstance(item.get("reviewer"), dict)
            else item.get("name", "")
        )
        resposta_dono = (
            item.get("responseFromOwnerText")
            or item.get("ownerResponse")
            or ""
        )

        # Converter rating para int
        try:
            rating = int(rating)
        except (ValueError, TypeError):
            rating = 0

        review = {
            "texto": texto.strip() if texto else "",
            "rating": rating,
            "data": str(data)[:10] if data else "",
            "autor": autor.strip() if isinstance(autor, str) else "",
            "resposta_dono": resposta_dono.strip() if resposta_dono else "",
        }
        reviews_text.append(review)

        # Classificar por rating
        if texto and texto.strip():
            if rating <= 3:
                reviews_negativas.append(texto.strip())
            elif rating >= 4:
                reviews_positivas.append(texto.strip())

    logger.info(
        "Reviews processadas: %d total | %d negativas (<=3*) | %d positivas (>=4*)",
        len(reviews_text), len(reviews_negativas), len(reviews_positivas),
    )

    return {
        "reviews_text": reviews_text,
        "reviews_negativas": reviews_negativas,
        "reviews_positivas": reviews_positivas,
        "total_reviews_scraped": len(reviews_text),
    }


def _empty_result() -> dict:
    """Retorna resultado vazio padrao."""
    return {
        "reviews_text": [],
        "reviews_negativas": [],
        "reviews_positivas": [],
        "total_reviews_scraped": 0,
    }


def enrich_lead_with_reviews(lead: dict, max_reviews: int = DEFAULT_MAX_REVIEWS) -> dict:
    """Enriquece um lead com reviews do Google Maps.

    Modifica o lead in-place, adicionando campos de reviews.

    Args:
        lead: Dict do lead (deve ter key 'place_id').
        max_reviews: Numero maximo de reviews a extrair.

    Returns:
        O mesmo lead com campos de reviews adicionados.
    """
    place_id = lead.get("place_id", "")
    nome = lead.get("nome", "Empresa")

    if not place_id:
        logger.info("'%s': sem place_id — reviews nao raspadas", nome)
        return lead

    logger.info("A enriquecer '%s' com reviews do Google Maps...", nome)
    reviews_data = scrape_google_reviews(place_id, max_reviews)
    lead.update(reviews_data)

    return lead


def enrich_leads_with_reviews(
    leads: list[dict], max_reviews: int = DEFAULT_MAX_REVIEWS
) -> list[dict]:
    """Enriquece multiplos leads com reviews do Google Maps.

    Args:
        leads: Lista de leads.
        max_reviews: Numero maximo de reviews por lead.

    Returns:
        Lista de leads com reviews adicionadas.
    """
    logger.info("A raspar reviews do Google Maps para %d leads...", len(leads))

    for i, lead in enumerate(leads):
        logger.info("[%d/%d] %s", i + 1, len(leads), lead.get("nome", "?"))
        enrich_lead_with_reviews(lead, max_reviews)

    logger.info("Scraping de reviews concluido")
    return leads
