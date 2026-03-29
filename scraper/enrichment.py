"""Enriquecimento de leads: combina Google Maps + Website + Instagram."""

import asyncio

from scraper.instagram import scrape_instagram_profiles
from scraper.utils import generate_slug, is_portuguese_mobile, setup_logger
from scraper.website import analyze_websites

logger = setup_logger(__name__)


def _dedup_leads(leads: list[dict]) -> list[dict]:
    """Remove leads duplicados por telefone. Mantém a primeira ocorrência."""
    seen: set[str] = set()
    unique: list[dict] = []

    for lead in leads:
        phone = lead.get("telefone", "")
        if phone and phone not in seen:
            seen.add(phone)
            unique.append(lead)
        elif phone in seen:
            logger.info("Duplicado removido: %s (%s)", lead.get("nome"), phone)

    removed = len(leads) - len(unique)
    if removed > 0:
        logger.info("Dedup: %d duplicados removidos", removed)

    return unique


def enrich_leads(leads: list[dict]) -> list[dict]:
    """Enriquece leads com dados de website e Instagram.

    Orquestra a analise de websites (async) e o scraping
    de Instagram (sync), combina tudo, faz dedup final
    e adiciona slugs.

    Args:
        leads: Lista de leads do Google Maps.

    Returns:
        Lista de leads enriquecidos prontos para gravar no Sheets.
    """
    if not leads:
        logger.info("Nenhum lead para enriquecer")
        return []

    initial_count = len(leads)

    # Separar leads COM e SEM telemovel
    leads_com_tel = [l for l in leads if is_portuguese_mobile(l.get("telefone", ""))]
    leads_sem_tel = [l for l in leads if not is_portuguese_mobile(l.get("telefone", ""))]

    # Leads SEM telemovel mas COM website — raspar site para tentar recuperar numero
    leads_para_site = [l for l in leads_sem_tel if l.get("website")]
    if leads_para_site:
        logger.info(
            "%d leads sem telemovel mas com website — a tentar recuperar numero do site...",
            len(leads_para_site),
        )
        leads_para_site = asyncio.run(analyze_websites(leads_para_site))

        recovered = 0
        for lead in leads_para_site:
            # Tentar: WhatsApp > telefone no site
            new_phone = None
            wa_phone = lead.get("whatsapp_phone")
            site_phone = lead.get("phone_on_site")

            if wa_phone:
                # Normalizar: adicionar +351 se necessario
                normalized = normalize_phone(wa_phone)
                if is_portuguese_mobile(normalized):
                    new_phone = normalized
                    logger.info(
                        "Recuperado telemovel WhatsApp para '%s': %s",
                        lead.get("nome"), new_phone,
                    )

            if not new_phone and site_phone:
                normalized = normalize_phone(site_phone)
                if is_portuguese_mobile(normalized):
                    new_phone = normalized
                    logger.info(
                        "Recuperado telemovel do site para '%s': %s",
                        lead.get("nome"), new_phone,
                    )

            if new_phone:
                lead["telefone"] = new_phone
                leads_com_tel.append(lead)
                recovered += 1

        if recovered:
            logger.info("%d leads recuperados com telemovel do site/WhatsApp", recovered)

    # Descartar quem realmente nao tem telemovel
    discarded = initial_count - len(leads_com_tel)
    if discarded:
        logger.info(
            "%d leads descartados — sem telemovel portugues em nenhuma fonte",
            discarded,
        )

    leads = leads_com_tel
    if not leads:
        logger.info("Nenhum lead com telemovel valido para enriquecer")
        return []

    logger.info("A enriquecer %d leads (com telemovel valido)...", len(leads))

    # Passo 1: Dedup por telefone
    leads = _dedup_leads(leads)

    # Passo 2: Analise de websites (para leads que ainda nao foram analisados)
    logger.info("--- Fase: Analise de Websites ---")
    leads_to_analyze = [l for l in leads if "has_chat" not in l]
    leads_already_done = [l for l in leads if "has_chat" in l]

    if leads_to_analyze:
        leads_to_analyze = asyncio.run(analyze_websites(leads_to_analyze))
    leads = leads_already_done + leads_to_analyze

    # Passo 3: Scraping Instagram (sync)
    logger.info("--- Fase: Scraping Instagram ---")
    leads = scrape_instagram_profiles(leads)

    # Passo 4: Gerar slugs
    for lead in leads:
        lead["slug"] = generate_slug(lead.get("nome", "sem-nome"))

    logger.info(
        "Enriquecimento concluido: %d leads finais (de %d iniciais)",
        len(leads), initial_count,
    )

    return leads
