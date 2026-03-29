"""Orquestrador de geracao de PDF — ponte entre PDF e CRM.

Gera PDFs (template fixo + nome) e actualiza o Sheets com estado
'pronto_para_envio' para envio posterior via WhatsApp.
"""

from crm.sheets import get_leads_by_sector_city, update_lead_status
from pdf.html_generator import generate_niche_pdf
from scraper.utils import generate_slug, setup_logger

logger = setup_logger(__name__)


def _map_lead_keys(lead_raw: dict) -> dict:
    """Converte lead do Sheets (keys Title-case) para formato lowercase."""
    nome = lead_raw.get("Nome", "")
    return {
        "nome": nome,
        "telefone": lead_raw.get("Telefone", ""),
        "cidade": lead_raw.get("Cidade", ""),
        "sector": lead_raw.get("Sector", ""),
        "rating": lead_raw.get("Rating", ""),
        "reviews": lead_raw.get("Reviews", ""),
        "instagram_url": lead_raw.get("Instagram", ""),
        "website": lead_raw.get("Website", ""),
        "slug": generate_slug(nome),
    }


def generate_and_register(lead: dict) -> str | None:
    """Gera PDF para 1 lead e actualiza o Sheets.

    Actualiza:
        - estado → 'pronto_para_envio'
        - link_pdf → caminho absoluto do PDF

    Args:
        lead: Lead com keys lowercase.

    Returns:
        Caminho do PDF gerado, ou None se falhar.
    """
    nome = lead.get("nome", "?")
    telefone = lead.get("telefone", "")

    if not telefone:
        logger.warning("Lead '%s' sem telefone — a saltar", nome)
        return None

    logger.info("A gerar PDF para '%s'...", nome)
    pdf_path = generate_niche_pdf(lead)

    if not pdf_path:
        logger.error("Falha ao gerar PDF para '%s'", nome)
        return None

    # Actualizar Sheets: estado + PDF path
    extra_data = {"link_pdf": pdf_path}
    success = update_lead_status(telefone, "pronto_para_envio", extra_data)
    if success:
        logger.info(
            "Lead '%s' actualizado para 'pronto_para_envio' | PDF: %s",
            nome, pdf_path,
        )
    else:
        logger.warning(
            "PDF gerado para '%s' mas falha ao actualizar Sheets", nome
        )

    return pdf_path


def batch_generate(sector: str, cidade: str) -> dict:
    """Gera PDFs para todos os leads 'novo' de um sector+cidade.

    Busca leads do Sheets, gera PDF com template fixo (so nome).
    Actualiza o Sheets com estado 'pronto_para_envio'.

    Args:
        sector: Sector/nicho (ex: 'contabilistas').
        cidade: Cidade (ex: 'Leiria').

    Returns:
        Dict com estatisticas: total, gerados, erros.
    """
    stats = {"total": 0, "gerados": 0, "erros": 0}

    # Buscar leads do Sheets
    leads_raw = get_leads_by_sector_city(sector, cidade, "novo")
    if not leads_raw:
        logger.info("Nenhum lead 'novo' para %s em %s", sector, cidade)
        return stats

    stats["total"] = len(leads_raw)
    logger.info(
        "Encontrados %d leads 'novo' para %s em %s",
        len(leads_raw), sector, cidade,
    )

    for i, lead_raw in enumerate(leads_raw):
        nome = lead_raw.get("Nome", "?")
        print(f"\n [{i + 1}/{len(leads_raw)}] {nome}")

        try:
            # Mapear keys
            lead = _map_lead_keys(lead_raw)

            # Gerar PDF + registar no Sheets
            pdf_path = generate_and_register(lead)

            if pdf_path:
                stats["gerados"] += 1
                print(f"  + PDF gerado: {pdf_path}")
            else:
                stats["erros"] += 1
                print(f"  x Falha ao gerar PDF")
        except Exception as e:
            stats["erros"] += 1
            logger.error("Erro ao processar '%s': %s", nome, e)
            print(f"  x Erro: {e}")

    logger.info(
        "Batch concluido: %d gerados, %d erros, %d total",
        stats["gerados"], stats["erros"], stats["total"],
    )

    return stats
