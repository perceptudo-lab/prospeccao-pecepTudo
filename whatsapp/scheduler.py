"""Scheduler de envio WhatsApp — janela horaria, follow-ups, anti-spam.

Envia mensagens na janela 09:00-13:00 com intervalos aleatorios,
pausas a cada N mensagens, e mix de novos leads + follow-ups.
"""

import os
import random
import time
from datetime import datetime, date, timedelta

from dotenv import load_dotenv

from crm.sheets import (
    get_leads_by_status,
    get_leads_needing_followup,
    update_lead_status,
)
from agentes.atendente import generate_outreach_message, generate_followup_message, has_niche_agent, _resolve_niche, _save_conversation_state, _send_split_messages
from scraper.utils import setup_logger
from whatsapp.message_generator import generate_message
from whatsapp.sender import check_is_whatsapp, send_lead_message, send_pdf, send_text

load_dotenv()
logger = setup_logger(__name__)

# Configuracao via .env
HORARIO_INICIO = os.getenv("HORARIO_INICIO", "09:00")
HORARIO_FIM = os.getenv("HORARIO_FIM", "13:30")
INTERVALO_MIN = int(os.getenv("INTERVALO_MIN_SEG", "90"))
INTERVALO_MAX = int(os.getenv("INTERVALO_MAX_SEG", "150"))
PAUSA_CADA_N = int(os.getenv("PAUSA_CADA_N", "20"))
PAUSA_MIN = int(os.getenv("PAUSA_MIN_SEG", "300"))
PAUSA_MAX = int(os.getenv("PAUSA_MAX_SEG", "480"))
MAX_ENVIOS_DIA = int(os.getenv("MAX_ENVIOS_DIA", "80"))

# Mapeamento base de estados: estado actual -> proximo estado apos envio
NEXT_STATE = {
    "pronto_para_envio": "contactado",
    "contactado": "followup_1",
    "followup_1": "followup_2",
    "followup_2": "followup_3",
    "followup_3": "frio",
}


def _get_next_state(estado_actual: str, nicho: str = "") -> str:
    """Retorna o proximo estado com base no nicho.

    Oficinas (4 toques): followup_2 → frio
    Contabilidade (5 toques): followup_2 → followup_3 → frio
    """
    max_touches = NICHE_MAX_TOUCHES.get(nicho, DEFAULT_MAX_TOUCHES)

    # Para nichos com 4 toques, followup_2 e o ultimo → frio
    if max_touches == 4 and estado_actual == "followup_2":
        return "frio"

    return NEXT_STATE.get(estado_actual, "contactado")

# Mapeamento de estado -> numero do touch que vai ser enviado
STATE_TO_TOUCH = {
    "pronto_para_envio": 1,
    "contactado": 2,
    "followup_1": 3,
    "followup_2": 4,
    "followup_3": 5,
}

# Cadencia de follow-ups por nicho (dias apos cada touch)
# Rui (oficinas): 4 toques — dia 0, 3, 7, 14 → frio
# Marco (contabilidade): 5 toques — dia 0, 3, 7, 14, 30 → frio
NICHE_FOLLOWUP_INTERVALS = {
    "oficinas": {
        1: 3,   # touch 1 -> touch 2 em 3 dias
        2: 4,   # touch 2 -> touch 3 em 4 dias (dia 7)
        3: 7,   # touch 3 -> touch 4 em 7 dias (dia 14)
        # touch 4 = ultimo → frio
    },
    "contabilidade": {
        1: 3,   # touch 1 -> touch 2 em 3 dias
        2: 4,   # touch 2 -> touch 3 em 4 dias (dia 7)
        3: 7,   # touch 3 -> touch 4 em 7 dias (dia 14)
        4: 16,  # touch 4 -> touch 5 em 16 dias (dia 30)
        # touch 5 = ultimo → frio
    },
}

# Fallback para nichos sem cadencia especifica
DEFAULT_FOLLOWUP_INTERVALS = {
    1: 3,
    2: 4,
    3: 7,
}

# Nichos onde touch 4 NAO e o ultimo (tem touch 5)
NICHE_MAX_TOUCHES = {
    "oficinas": 4,
    "contabilidade": 5,
}
DEFAULT_MAX_TOUCHES = 4


def _is_within_window() -> bool:
    """Verifica se estamos dentro da janela de envio."""
    now = datetime.now().strftime("%H:%M")
    return HORARIO_INICIO <= now <= HORARIO_FIM


def _parse_time(time_str: str) -> datetime:
    """Converte string HH:MM para datetime de hoje."""
    h, m = time_str.split(":")
    return datetime.now().replace(hour=int(h), minute=int(m), second=0, microsecond=0)


def _next_followup_date(touch_sent: int, nicho: str = "") -> str | None:
    """Calcula data ISO do proximo follow-up apos enviar um touch.

    Args:
        touch_sent: Touch que acabou de ser enviado.
        nicho: Nicho resolvido (ex: 'oficinas', 'contabilidade').

    Returns:
        Data ISO (YYYY-MM-DD) ou None se foi o ultimo touch.
    """
    intervals = NICHE_FOLLOWUP_INTERVALS.get(nicho, DEFAULT_FOLLOWUP_INTERVALS)
    interval = intervals.get(touch_sent)
    if not interval:
        return None
    return (date.today() + timedelta(days=interval)).isoformat()


def _prioritize_by_city(leads: list[dict], priority_cities: list[str] | None = None) -> list[dict]:
    """Ordena leads por cidade — cidades prioritarias primeiro."""
    if not priority_cities:
        return leads
    priority_set = {c.strip().lower() for c in priority_cities}

    def sort_key(lead):
        cidade = lead.get("Cidade", "").strip().lower()
        return 0 if cidade in priority_set else 1

    return sorted(leads, key=sort_key)


def _get_daily_queue(
    niche_limits: dict[str, int] | None = None,
    priority_cities: list[str] | None = None,
) -> list[dict]:
    """Constroi a fila de envio do dia.

    Prioridade: follow-ups primeiro (leads mais quentes), depois novos.
    Total limitado a MAX_ENVIOS_DIA.

    Args:
        niche_limits: Limite por nicho (ex: {"oficinas": 40, "contabilidade": 40}).
                      Se None, sem limite por nicho (comportamento original).
        priority_cities: Cidades prioritarias (ex: ["Lisboa", "Porto"]).

    Cada item recebe keys extra: '_touch' e '_type'.
    """
    queue = []

    # 1. Follow-ups (prioridade — leads mais quentes)
    today_str = date.today().isoformat()
    followups = get_leads_needing_followup(today_str)
    for lead in followups:
        estado = lead.get("Estado", "").strip().lower()
        touch = STATE_TO_TOUCH.get(estado)
        if touch:
            lead["_touch"] = touch
            lead["_type"] = "followup"
            queue.append(lead)

    # 2. Novos leads — filtrados por nicho + cidade prioritaria
    novos = get_leads_by_status("pronto_para_envio")

    if niche_limits:
        # Separar por nicho
        niche_buckets: dict[str, list[dict]] = {}
        for lead in novos:
            sector = lead.get("Sector", "").strip().lower()
            nicho = _resolve_niche(sector)
            if nicho not in niche_buckets:
                niche_buckets[nicho] = []
            niche_buckets[nicho].append(lead)

        # Priorizar cidades e aplicar limite por nicho
        for nicho, limit in niche_limits.items():
            bucket = niche_buckets.get(nicho, [])
            bucket = _prioritize_by_city(bucket, priority_cities)
            for lead in bucket[:limit]:
                lead["_touch"] = 1
                lead["_type"] = "novo"
                queue.append(lead)
    else:
        # Sem limites por nicho — comportamento original
        novos = _prioritize_by_city(novos, priority_cities)
        for lead in novos:
            lead["_touch"] = 1
            lead["_type"] = "novo"
            queue.append(lead)

    # Limitar ao maximo diario
    if len(queue) > MAX_ENVIOS_DIA:
        queue = queue[:MAX_ENVIOS_DIA]

    logger.info(
        "Fila do dia: %d follow-ups + %d novos = %d total (max %d)",
        sum(1 for q in queue if q["_type"] == "followup"),
        sum(1 for q in queue if q["_type"] == "novo"),
        len(queue),
        MAX_ENVIOS_DIA,
    )

    return queue


def send_daily_batch(
    dry_run: bool = False,
    niche_limits: dict[str, int] | None = None,
    priority_cities: list[str] | None = None,
) -> dict:
    """Processa a fila diaria de envios dentro da janela horaria.

    Args:
        dry_run: Se True, simula tudo sem enviar nem alterar Sheets.
        niche_limits: Limite por nicho (ex: {"oficinas": 40, "contabilidade": 40}).
        priority_cities: Cidades prioritarias (ex: ["Lisboa", "Porto"]).

    Para cada lead:
    1. Verifica janela horaria
    2. Verifica limite diario
    3. Valida numero no WhatsApp
    4. Gera mensagem variada (GPT-5)
    5. Envia texto + PDF (touch 1) ou so texto (follow-ups)
    6. Actualiza Sheets: estado + data proximo follow-up + touch
    7. Espera intervalo aleatorio
    8. Pausa a cada N mensagens

    Returns:
        Dict com estatisticas: enviados, erros, saltados, total.
    """
    stats = {"enviados": 0, "erros": 0, "saltados": 0, "total": 0}

    if not dry_run and not _is_within_window():
        logger.info(
            "Fora da janela de envio (%s-%s). Agora: %s",
            HORARIO_INICIO, HORARIO_FIM, datetime.now().strftime("%H:%M"),
        )
        return stats

    queue = _get_daily_queue(niche_limits=niche_limits, priority_cities=priority_cities)
    if not queue:
        logger.info("Nenhum lead na fila de envio")
        return stats

    stats["total"] = len(queue)
    count_enviados = 0

    mode_label = "SIMULACAO (dry-run)" if dry_run else "ENVIO DIARIO"
    print(f"\n{'='*60}")
    print(f"  PERCEPTUDO — {mode_label}")
    print(f"  Janela: {HORARIO_INICIO} - {HORARIO_FIM}")
    print(f"  Fila: {len(queue)} leads (max {MAX_ENVIOS_DIA})")
    print(f"{'='*60}\n")

    for i, lead in enumerate(queue):
        # Verificar janela (ignorar em dry-run)
        if not dry_run and not _is_within_window():
            logger.info("Janela de envio terminou — a parar")
            print(f"\n  Janela terminou as {datetime.now().strftime('%H:%M')}.")
            stats["saltados"] += len(queue) - i
            break

        # Verificar limite
        if count_enviados >= MAX_ENVIOS_DIA:
            logger.info("Limite diario atingido (%d)", MAX_ENVIOS_DIA)
            stats["saltados"] += len(queue) - i
            break

        nome = lead.get("Nome", "?")
        telefone = str(lead.get("Telefone", ""))
        sector = lead.get("Sector", "")
        touch = lead["_touch"]
        tipo = lead["_type"]
        pdf_link = lead.get("Link PDF", "")

        if not telefone:
            logger.warning("Lead '%s' sem telefone — a saltar", nome)
            stats["saltados"] += 1
            continue

        print(f"  [{i + 1}/{len(queue)}] {nome} (touch {touch}, {tipo})")

        # Validar WhatsApp (skip rapido antes de gastar GPT)
        if not dry_run and not check_is_whatsapp(telefone):
            logger.warning("'%s' (%s) nao esta no WhatsApp — a saltar", nome, telefone)
            stats["saltados"] += 1
            print(f"    x Nao esta no WhatsApp")
            continue

        # PDF so no touch 1
        pdf_path = pdf_link if touch == 1 else None
        if touch == 1 and not pdf_path:
            logger.warning("Lead '%s' sem PDF para touch 1 — a saltar", nome)
            stats["saltados"] += 1
            continue

        # Agente especialista gera TODOS os toques (outreach + follow-ups)
        use_agent = has_niche_agent(sector)

        lead_data = {
            "telefone": str(telefone),
            "cidade": str(lead.get("Cidade", "")),
            "rating": str(lead.get("Rating", "")),
            "reviews": str(lead.get("Reviews", "")),
            "website": str(lead.get("Website", "")),
            "instagram": str(lead.get("Instagram", "")),
        }

        if use_agent and touch == 1:
            # Touch 1: outreach + PDF
            try:
                msgs, conv_state = generate_outreach_message(nome, sector, lead_data)
                mensagem = " | ".join(msgs)
            except Exception as e:
                logger.error("Erro ao gerar outreach agente para '%s': %s", nome, e)
                stats["erros"] += 1
                continue
        elif use_agent and touch >= 2:
            # Follow-ups: agente segue a SUA cadencia especifica
            try:
                msgs = generate_followup_message(nome, sector, touch, lead_data)
                mensagem = " | ".join(msgs)
                conv_state = None
            except Exception as e:
                logger.error("Erro ao gerar follow-up agente para '%s': %s", nome, e)
                stats["erros"] += 1
                continue
        else:
            # Nichos sem agente: gerador generico
            try:
                mensagem = generate_message(nome, sector, touch=touch)
                msgs = [mensagem]
                conv_state = None
            except Exception as e:
                logger.error("Erro ao gerar mensagem para '%s': %s", nome, e)
                stats["erros"] += 1
                continue

        # Resolver nicho para cadencia de follow-up
        nicho = _resolve_niche(sector)

        if dry_run:
            count_enviados += 1
            stats["enviados"] += 1
            estado_actual = lead.get("Estado", "").strip().lower()
            novo_estado = _get_next_state(estado_actual, nicho)
            proximo_followup = _next_followup_date(touch, nicho)
            agent_label = " [AGENTE]" if use_agent else ""
            print(f"    [DRY-RUN]{agent_label} {len(msgs)} msg(s):")
            for m in msgs:
                print(f"    > {m[:100]}...")
            print(f"    -> {novo_estado} | follow-up: {proximo_followup or 'nenhum'}")
        else:
            # Enviar mensagens
            if use_agent:
                success = _send_split_messages(telefone, msgs)
                if success and pdf_path:
                    time.sleep(random.uniform(2, 5))
                    success = send_pdf(telefone, pdf_path)
            else:
                success = send_lead_message(
                    phone=telefone,
                    message=mensagem,
                    pdf_path=pdf_path,
                )

            if success:
                count_enviados += 1
                stats["enviados"] += 1

                # Calcular proximo estado e follow-up (por nicho)
                estado_actual = lead.get("Estado", "").strip().lower()
                novo_estado = _get_next_state(estado_actual, nicho)
                proximo_followup = _next_followup_date(touch, nicho)

                extra_data = {
                    "data_contacto": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "touch_actual": str(touch),

                }
                if proximo_followup:
                    extra_data["data_followup_proximo"] = proximo_followup

                # Guardar data do follow-up na coluna correcta
                followup_col_map = {2: "followup_1", 3: "followup_2", 4: "followup_3"}
                followup_key = followup_col_map.get(touch)
                if followup_key:
                    extra_data[followup_key] = datetime.now().strftime("%Y-%m-%d %H:%M")

                update_lead_status(telefone, novo_estado, extra_data)

                # Guardar estado de conversa (se agente especialista)
                if conv_state:
                    _save_conversation_state(telefone, conv_state)

                logger.info(
                    "'%s' enviado (touch %d) -> estado '%s'%s",
                    nome, touch, novo_estado,
                    " [AGENTE]" if use_agent else "",
                )
                print(f"    + Enviado (-> {novo_estado}{'  [AGENTE]' if use_agent else ''})")
            else:
                stats["erros"] += 1
                logger.error("Falha ao enviar para '%s'", nome)
                print(f"    x Falha no envio")

        # Intervalo aleatorio antes do proximo (skip em dry-run)
        if not dry_run and i < len(queue) - 1:
            # Pausa longa a cada N mensagens
            if count_enviados > 0 and count_enviados % PAUSA_CADA_N == 0:
                pausa = random.randint(PAUSA_MIN, PAUSA_MAX)
                logger.info("Pausa longa: %d segundos (a cada %d msgs)...", pausa, PAUSA_CADA_N)
                print(f"    ... pausa longa: {pausa // 60} min")
                time.sleep(pausa)
            else:
                delay = random.randint(INTERVALO_MIN, INTERVALO_MAX)
                logger.info("A aguardar %ds...", delay)
                time.sleep(delay)

    print(f"\n{'='*60}")
    print(f"  CONCLUIDO")
    print(f"{'='*60}")
    print(f"  Enviados:  {stats['enviados']}")
    print(f"  Erros:     {stats['erros']}")
    print(f"  Saltados:  {stats['saltados']}")
    print(f"  Total:     {stats['total']}")
    print(f"{'='*60}\n")

    logger.info(
        "Envio diario concluido: %d enviados, %d erros, %d saltados, %d total",
        stats["enviados"], stats["erros"], stats["saltados"], stats["total"],
    )

    return stats
