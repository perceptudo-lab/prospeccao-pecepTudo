"""Sistema de follow-up — determina quais leads precisam de contacto.

Modulo de consulta/scheduling. NAO envia mensagens directamente —
fornece dados ao scheduler (send_daily_batch).
"""

from datetime import date, timedelta

from crm.sheets import get_leads_needing_followup, get_leads_by_statuses
from scraper.utils import setup_logger

logger = setup_logger(__name__)

# Dias entre cada touch
TOUCH_INTERVALS = {
    1: 3,   # apos touch 1 -> touch 2 em 3 dias
    2: 4,   # apos touch 2 -> touch 3 em 4 dias (dia 7)
    3: 7,   # apos touch 3 -> touch 4 em 7 dias (dia 14)
}

# Estado actual -> proximo touch a enviar
STATE_TO_NEXT_TOUCH = {
    "contactado": 2,
    "followup_1": 3,
    "followup_2": 4,
}


def get_followup_queue(today: date | None = None) -> list[dict]:
    """Retorna leads que precisam de follow-up hoje ou antes.

    Cada lead recebe key extra 'next_touch' com o numero do proximo touch.

    Args:
        today: Data de referencia. Se None, usa hoje.

    Returns:
        Lista de leads com 'next_touch' adicionado, ordenados por data.
    """
    today = today or date.today()
    today_str = today.isoformat()

    leads = get_leads_needing_followup(today_str)

    # Adicionar next_touch a cada lead
    result = []
    for lead in leads:
        estado = lead.get("Estado", "").strip().lower()
        next_touch = STATE_TO_NEXT_TOUCH.get(estado)
        if next_touch:
            lead["next_touch"] = next_touch
            result.append(lead)
        else:
            logger.warning(
                "Lead '%s' com estado '%s' nao esperado no follow-up",
                lead.get("Nome", "?"), estado,
            )

    logger.info("Follow-ups pendentes para %s: %d leads", today_str, len(result))
    return result


def calculate_next_followup(touch_sent: int, from_date: date | None = None) -> str | None:
    """Calcula data ISO do proximo follow-up.

    Args:
        touch_sent: Touch que acabou de ser enviado (1-4).
        from_date: Data de referencia. Se None, usa hoje.

    Returns:
        Data ISO (YYYY-MM-DD) ou None se foi o ultimo touch.
    """
    interval = TOUCH_INTERVALS.get(touch_sent)
    if not interval:
        return None

    d = (from_date or date.today()) + timedelta(days=interval)
    return d.isoformat()


def get_followup_stats() -> dict:
    """Retorna estatisticas de follow-ups.

    Returns:
        Dict com contagens por estagio e quantos due hoje.
    """
    today_str = date.today().isoformat()

    # Leads em cada estagio de follow-up
    followup_leads = get_leads_by_statuses(["contactado", "followup_1", "followup_2"])

    stats = {
        "contactado": 0,     # aguardam touch 2
        "followup_1": 0,     # aguardam touch 3
        "followup_2": 0,     # aguardam touch 4
        "due_hoje": 0,       # com follow-up para hoje ou antes
        "total_pipeline": 0, # total em pipeline de follow-up
    }

    for lead in followup_leads:
        estado = lead.get("Estado", "").strip().lower()
        if estado in stats:
            stats[estado] += 1
        stats["total_pipeline"] += 1

        proximo = str(lead.get("Proximo Follow-up", "")).strip()
        if proximo and proximo <= today_str:
            stats["due_hoje"] += 1

    return stats
