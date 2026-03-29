"""Pesquisa de empresas via Google Maps Places API."""

import argparse
import os
import time

import googlemaps
from dotenv import load_dotenv

from crm.sheets import (
    get_contacted_phones,
    is_term_used,
    register_term,
)
from scraper.utils import is_portuguese_mobile, normalize_phone, setup_logger

load_dotenv()
logger = setup_logger(__name__)

# Campos a pedir no Place Details
DETAIL_FIELDS = [
    "name",
    "formatted_phone_number",
    "international_phone_number",
    "website",
    "rating",
    "user_ratings_total",
    "formatted_address",
    "place_id",
]


def _create_client() -> googlemaps.Client:
    """Cria cliente Google Maps autenticado."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY nao definida no .env")
    return googlemaps.Client(key=api_key)


def search_businesses(query: str, cidade: str) -> list[dict]:
    """Pesquisa empresas no Google Maps por nicho + cidade.

    Sempre busca as 3 paginas (ate 60 resultados brutos).
    Filtra por telemovel portugues e remove duplicados do Sheets.
    Regista o termo na aba 'Termos' apos pesquisa.

    Args:
        query: Nicho de negocio (ex: 'restaurantes')
        cidade: Cidade (ex: 'Lisboa')

    Returns:
        Lista de leads validos com keys: nome, telefone, cidade,
        sector, rating, reviews, website, morada, place_id
    """
    # Verificar se termo ja foi usado
    if is_term_used(query, cidade):
        logger.warning("Termo '%s' em '%s' ja utilizado — a saltar", query, cidade)
        return []

    # Buscar telefones ja contactados para dedup
    contacted = get_contacted_phones()
    logger.info("Dedup: %d telefones ja registados no Sheets", len(contacted))

    gmaps = _create_client()
    search_text = f"{query} em {cidade}"
    logger.info("A pesquisar: '%s'", search_text)

    all_results: list[dict] = []
    leads: list[dict] = []
    page = 0

    # Primeira pesquisa
    try:
        response = gmaps.places(query=search_text, language="pt", region="pt")
    except Exception as e:
        logger.error("Erro na pesquisa Google Maps: %s", e)
        return []

    while True:
        page += 1
        results = response.get("results", [])
        all_results.extend(results)
        logger.info("Pagina %d: %d resultados", page, len(results))

        # Verificar se ha proxima pagina
        next_token = response.get("next_page_token")
        if not next_token or page >= 3:
            break

        # Google exige 2s antes de usar o next_page_token
        logger.info("A aguardar 2s para proxima pagina...")
        time.sleep(2)

        try:
            response = gmaps.places(
                query=search_text, page_token=next_token, language="pt", region="pt"
            )
        except Exception as e:
            logger.error("Erro na paginacao (pagina %d): %s", page + 1, e)
            break

    logger.info("Total de resultados brutos: %d", len(all_results))

    # Processar cada resultado com Place Details
    for i, result in enumerate(all_results):
        place_id = result.get("place_id")
        name = result.get("name", "Desconhecido")

        if not place_id:
            logger.warning("Resultado sem place_id: %s", name)
            continue

        try:
            details_response = gmaps.place(place_id=place_id, fields=DETAIL_FIELDS)
            details = details_response.get("result", {})
        except Exception as e:
            logger.error("Erro ao obter detalhes de '%s': %s", name, e)
            time.sleep(0.3)
            continue

        # Extrair telefone (preferir internacional)
        phone = details.get("international_phone_number") or details.get(
            "formatted_phone_number", ""
        )

        if not phone:
            logger.info("'%s': sem telefone — a saltar", name)
            time.sleep(0.3)
            continue

        # Normalizar e validar
        phone_normalized = normalize_phone(phone)

        if not is_portuguese_mobile(phone_normalized):
            logger.info("'%s': telefone %s nao e telemovel PT — a saltar", name, phone)
            time.sleep(0.3)
            continue

        # Dedup: ja contactado?
        if phone_normalized in contacted:
            logger.info("'%s': %s ja contactado — a saltar", name, phone_normalized)
            time.sleep(0.3)
            continue

        lead = {
            "nome": details.get("name", name),
            "telefone": phone_normalized,
            "cidade": cidade,
            "sector": query,
            "rating": details.get("rating", 0),
            "reviews": details.get("user_ratings_total", 0),
            "website": details.get("website", ""),
            "morada": details.get("formatted_address", ""),
            "place_id": place_id,
        }

        leads.append(lead)
        # Adicionar ao set de contactados para evitar duplicados dentro da mesma pesquisa
        contacted.add(phone_normalized)
        logger.info(
            "Lead #%d: %s | %s | Rating: %s | Reviews: %s",
            len(leads), lead["nome"], lead["telefone"],
            lead["rating"], lead["reviews"],
        )

        # Rate limiting entre Place Details calls
        time.sleep(0.3)

    logger.info(
        "Pesquisa concluida: %d brutos → %d leads validos", len(all_results), len(leads)
    )

    # Registar termo no Sheets
    register_term(query, cidade, len(all_results), len(leads))

    return leads


def main() -> None:
    """Entry point CLI."""
    parser = argparse.ArgumentParser(
        description="Pesquisa empresas no Google Maps por nicho + cidade"
    )
    parser.add_argument("--query", required=True, help="Nicho (ex: restaurantes)")
    parser.add_argument("--cidade", required=True, help="Cidade (ex: Lisboa)")
    args = parser.parse_args()

    leads = search_businesses(args.query, args.cidade)

    if leads:
        print(f"\n{'='*60}")
        print(f"RESULTADO: {len(leads)} leads validos")
        print(f"{'='*60}")
        for i, lead in enumerate(leads, 1):
            print(
                f"  {i}. {lead['nome']} | {lead['telefone']} | "
                f"Rating: {lead['rating']} | Reviews: {lead['reviews']}"
            )
    else:
        print("\nNenhum lead encontrado ou termo ja utilizado.")


if __name__ == "__main__":
    main()
