"""Agente de atendimento WhatsApp — responde a leads por nicho.

Carrega base de conhecimento (.md) do nicho, mantem historico de conversa,
e escala para o Victor quando detecta intencao de agendamento.

Responde 24/7 (sem restricao de horario).
"""

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from crm.sheets import get_leads_by_statuses, update_lead_status
from scraper.utils import setup_logger
from whatsapp.sender import send_text

load_dotenv()
logger = setup_logger(__name__)

AGENTES_DIR = Path(__file__).parent
CONVERSATION_DIR = Path(__file__).parent.parent / "output" / "conversas"
CONVERSATION_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_MODEL = os.getenv("OPENAI_AGENT_MODEL", "gpt-5")
VICTOR_PHONE = os.getenv("VICTOR_PHONE", "351934215049")
MAX_HISTORY = 20  # Maximo de mensagens no historico por conversa

# Keywords que indicam intencao de agendar
ESCALATION_KEYWORDS = [
    "agendar", "marcar", "reuniao", "reunião", "meeting",
    "disponibilidade", "disponivel", "disponível",
    "hora", "horario", "horário", "quando", "calendario", "calendário",
    "cal.com", "agendem", "marcacao", "marcação",
]

# Keywords de opt-out
OPTOUT_KEYWORDS = ["parar", "stop", "remover", "cancelar", "nao quero", "não quero"]


def _get_client() -> OpenAI:
    """Cria cliente OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY nao definida no .env")
    return OpenAI(api_key=api_key)


def _load_knowledge_base(nicho: str) -> str:
    """Carrega ficheiros .md do nicho para usar como contexto.

    Procura em agentes/{nicho}/ pelos ficheiros:
    - personalidade.md
    - conhecimento.md
    - objecoes.md

    Args:
        nicho: Nome do nicho (ex: 'contabilidade').

    Returns:
        Texto concatenado de todos os ficheiros encontrados.
    """
    nicho_dir = AGENTES_DIR / nicho.strip().lower()
    if not nicho_dir.exists():
        logger.warning("Directorio de agente nao encontrado: %s", nicho_dir)
        return ""

    context = ""
    for filename in ["personalidade.md", "conhecimento.md", "objecoes.md"]:
        filepath = nicho_dir / filename
        if filepath.exists():
            content = filepath.read_text(encoding="utf-8")
            section_name = filename.replace(".md", "").upper()
            context += f"\n\n## {section_name}\n\n{content}"
            logger.info("Base de conhecimento carregada: %s/%s", nicho, filename)

    return context


def _load_conversation(phone: str) -> list[dict]:
    """Carrega historico de conversa de um lead.

    Args:
        phone: Telefone normalizado (ex: '351912345678').

    Returns:
        Lista de mensagens [{role, content, timestamp}].
    """
    phone_clean = phone.replace("+", "").replace(" ", "")
    conv_file = CONVERSATION_DIR / f"{phone_clean}.json"
    if conv_file.exists():
        try:
            data = json.loads(conv_file.read_text(encoding="utf-8"))
            return data[-MAX_HISTORY:]  # Limitar historico
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Erro ao carregar conversa de %s: %s", phone, e)
    return []


def _save_conversation(phone: str, history: list[dict]) -> None:
    """Guarda historico de conversa localmente.

    Args:
        phone: Telefone normalizado.
        history: Lista de mensagens.
    """
    phone_clean = phone.replace("+", "").replace(" ", "")
    conv_file = CONVERSATION_DIR / f"{phone_clean}.json"
    try:
        conv_file.write_text(
            json.dumps(history[-MAX_HISTORY:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.error("Erro ao guardar conversa de %s: %s", phone, e)


def _detect_escalation(message: str) -> bool:
    """Detecta intencao de agendamento na mensagem.

    Args:
        message: Texto da mensagem do lead.

    Returns:
        True se contem keywords de agendamento.
    """
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in ESCALATION_KEYWORDS)


def _detect_optout(message: str) -> bool:
    """Detecta pedido de opt-out.

    Args:
        message: Texto da mensagem do lead.

    Returns:
        True se contem keywords de opt-out.
    """
    msg_lower = message.strip().lower()
    return any(kw in msg_lower for kw in OPTOUT_KEYWORDS)


def _find_lead_by_phone(phone: str) -> dict | None:
    """Procura lead no Sheets pelo telefone.

    Args:
        phone: Telefone do lead.

    Returns:
        Dict do lead ou None se nao encontrado.
    """
    # Procurar em todos os estados relevantes
    states = [
        "contactado", "followup_1", "followup_2", "followup_3",
        "respondeu", "agendado",
    ]
    leads = get_leads_by_statuses(states)
    phone_clean = phone.replace("+", "").replace(" ", "")[-9:]

    for lead in leads:
        lead_phone = str(lead.get("Telefone", "")).replace("+", "").replace(" ", "")
        if lead_phone.endswith(phone_clean):
            return lead
    return None


def _notify_victor(phone: str, nome: str, nicho: str, message: str, history_len: int) -> None:
    """Envia alerta ao Victor sobre lead com intencao de agendar.

    Args:
        phone: Telefone do lead.
        nome: Nome do negocio.
        nicho: Sector/nicho.
        message: Ultima mensagem do lead.
        history_len: Numero de mensagens trocadas.
    """
    alert = (
        f"Lead quer agendar!\n\n"
        f"Nome: {nome}\n"
        f"Telefone: +{phone.replace('+', '')}\n"
        f"Nicho: {nicho}\n"
        f"Mensagem: \"{message[:200]}\"\n"
        f"Historico: {history_len} mensagens trocadas"
    )

    try:
        success = send_text(VICTOR_PHONE, alert)
        if success:
            logger.info("Alerta enviado ao Victor sobre '%s'", nome)
        else:
            logger.error("Falha ao enviar alerta ao Victor sobre '%s'", nome)
    except Exception as e:
        logger.error("Erro ao notificar Victor: %s", e)


def handle_incoming_message(phone: str, message: str) -> str | None:
    """Processa mensagem recebida de um lead e gera resposta.

    Fluxo:
    1. Responde 24/7 (sem restricao de horario)
    2. Verifica se lead esta em estado 'agendado' -> NAO responde
    3. Detecta opt-out -> estado 'removido', despedida
    4. Actualiza estado para 'respondeu' (primeira resposta)
    5. Carrega knowledge base + historico
    6. GPT-5 gera resposta
    7. Detecta escalacao -> notifica Victor, estado 'agendado', para
    8. Guarda conversa, envia resposta

    Args:
        phone: Telefone do remetente.
        message: Texto da mensagem recebida.

    Returns:
        Texto da resposta enviada, ou None se nao respondeu.
    """
    logger.info("Mensagem recebida de %s: %s", phone, message[:100])

    # Procurar lead no Sheets
    lead = _find_lead_by_phone(phone)
    nome = lead.get("Nome", "Cliente") if lead else "Cliente"
    nicho = lead.get("Sector", "").strip().lower() if lead else ""
    estado = lead.get("Estado", "").strip().lower() if lead else ""
    telefone = str(lead.get("Telefone", phone)) if lead else str(phone)

    # 1. Se estado = 'agendado' -> nao responder (Victor trata)
    if estado == "agendado":
        logger.info("Lead '%s' ja esta agendado — ignorando", nome)
        return None

    # 2. Se estado = 'removido' -> nao responder
    if estado == "removido":
        logger.info("Lead '%s' esta removido — ignorando", nome)
        return None

    # 3. Detectar opt-out
    if _detect_optout(message):
        logger.info("Opt-out detectado de '%s'", nome)
        resposta = (
            f"Compreendido, {nome}. Deixaremos de enviar mensagens. "
            f"Se no futuro precisar de algo, estamos disponiveis. Boa continuacao."
        )
        send_text(telefone, resposta)
        if lead:
            update_lead_status(telefone, "removido")
        return resposta

    # 4. Actualizar estado para 'respondeu' (se ainda nao esta)
    if lead and estado not in ("respondeu", "agendado"):
        update_lead_status(telefone, "respondeu")
        logger.info("Lead '%s' actualizado para 'respondeu'", nome)

    # 5. Carregar knowledge base + historico
    knowledge = _load_knowledge_base(nicho) if nicho else ""
    history = _load_conversation(phone)

    # Adicionar mensagem do lead ao historico
    history.append({
        "role": "user",
        "content": message,
        "timestamp": datetime.now().isoformat(),
    })

    # 6. Gerar resposta via GPT-5
    system_prompt = f"""Es o assistente da PercepTudo, uma consultoria de inteligencia aplicada (IA) para pequenas e medias empresas em Portugal.

Estas a conversar com {nome} (sector: {nicho or 'desconhecido'}) via WhatsApp.

REGRAS:
- Responde SEMPRE em PT-PT (nunca PT-BR)
- Tom: profissional mas acessivel, como especialista no cafe
- Respostas curtas (2-4 frases max) — e WhatsApp, nao email
- NAO inventes dados ou precos
- NAO prometas prazos ou resultados especificos
- Se nao sabes a resposta, diz que vais confirmar internamente
- Precos e detalhes de implementacao sao discutidos na reuniao
- NUNCA digas que es uma IA ou bot — tu es parte da equipa PercepTudo
- Se o lead perguntar sobre precos, diz que depende do diagnostico e que e discutido na reuniao
- Se mostrar interesse em agendar, encoraja e diz que o Victor vai entrar em contacto

{knowledge}"""

    # Construir mensagens para o GPT (sem timestamps)
    gpt_messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-MAX_HISTORY:]:
        gpt_messages.append({
            "role": msg["role"],
            "content": msg["content"],
        })

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=gpt_messages,
        )
        resposta = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("Erro ao gerar resposta para '%s': %s", nome, e)
        resposta = f"Obrigado pela mensagem, {nome}. Vou confirmar internamente e volto a contactar brevemente."

    # 7. Detectar escalacao (na mensagem do lead OU na resposta do GPT)
    if _detect_escalation(message) or _detect_escalation(resposta):
        logger.info("Escalacao detectada para '%s' — a notificar Victor", nome)

        # Responder ao lead
        resposta_escalacao = (
            f"Excelente, {nome}! Vou pedir ao Victor para entrar em contacto "
            f"consigo para combinarem a melhor hora. Ate breve!"
        )
        send_text(telefone, resposta_escalacao)

        # Notificar Victor
        _notify_victor(
            phone=telefone,
            nome=nome,
            nicho=nicho,
            message=message,
            history_len=len(history),
        )

        # Actualizar estado
        if lead:
            update_lead_status(telefone, "agendado")

        # Guardar conversa
        history.append({
            "role": "assistant",
            "content": resposta_escalacao,
            "timestamp": datetime.now().isoformat(),
        })
        _save_conversation(phone, history)

        return resposta_escalacao

    # 8. Enviar resposta normal
    send_text(telefone, resposta)

    # Guardar conversa
    history.append({
        "role": "assistant",
        "content": resposta,
        "timestamp": datetime.now().isoformat(),
    })
    _save_conversation(phone, history)

    logger.info("Resposta enviada a '%s': %s", nome, resposta[:100])
    return resposta
