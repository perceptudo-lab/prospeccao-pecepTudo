"""Agente de atendimento WhatsApp — especialistas por nicho.

Cada nicho tem um agente com personalidade propria (ex: Rui para oficinas).
O agente gera a primeira mensagem de outreach, responde com mensagens
curtas quebradas, segue metodo SPIN, e escala para o Victor quando detecta
intencao de agendamento ou outros gatilhos.

Responde 24/7 (sem restricao de horario).
"""

import json
import os
import random
import time
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
MAX_HISTORY = 20

# Aliases: varios nomes de sector apontam para o mesmo directorio de agente
NICHE_ALIASES = {
    "oficinas": "oficinas",
    "oficina": "oficinas",
    "oficina de automoveis": "oficinas",
    "oficina de automóveis": "oficinas",
    "oficinas de automoveis": "oficinas",
    "oficinas de automóveis": "oficinas",
    "mecanica": "oficinas",
    "auto": "oficinas",
    "contabilidade": "contabilidade",
    "contabilista": "contabilidade",
    "contabilistas": "contabilidade",
    "gabinete de contabilidade": "contabilidade",
    "gabinetes de contabilidade": "contabilidade",
    "escritorio de contabilidade": "contabilidade",
    "escritorios de contabilidade": "contabilidade",
}

# Tipos de escalacao
ESCALATION_TYPES = {
    "price_2x": "Pediu preco pela segunda vez",
    "irritated": "Lead irritado ou frustrado",
    "formal_proposal": "Quer proposta formal",
    "technical_complex": "Questao tecnica complexa",
    "high_value": "Lead de alto valor",
    "complaint": "Reclamacao sobre PercepTudo",
    "wants_schedule": "Quer agendar reuniao",
}

# Keywords de preco (para tracking code-level)
PRICE_KEYWORDS = ["preco", "preço", "custo", "custa", "valor", "investimento", "orcamento", "orçamento", "quanto"]

# Keywords de reclamacao (safety net)
COMPLAINT_KEYWORDS = ["reclamacao", "reclamação", "mau servico", "mau serviço", "fraude", "burla", "enganado"]

# Keywords de opt-out
OPTOUT_KEYWORDS = ["parar", "stop", "remover", "cancelar", "nao quero", "não quero"]

# SPIN stages
VALID_STAGES = {"outreach", "situacao", "problema", "implicacao", "solucao", "fecho", "escalado", "frio"}

# Instrucoes JSON adicionadas ao final de cada system prompt
JSON_FORMAT_INSTRUCTIONS = """

===== FORMATO DE RESPOSTA (OBRIGATORIO) =====

Responde SEMPRE em JSON valido com esta estrutura exacta:
{
  "messages": ["mensagem 1", "mensagem 2"],
  "stage": "situacao",
  "escalation": null,
  "internal_notes": "notas internas opcionais"
}

REGRAS DO JSON:
- "messages" e uma lista de 1 a 3 mensagens curtas (max 3 frases cada)
- "stage" reflecte a fase SPIN actual APOS esta resposta: outreach, situacao, problema, implicacao, solucao, fecho, escalado
- "escalation" e null a menos que um gatilho de escalacao esteja activo
- Se escalacao: {"type": "price_2x|irritated|formal_proposal|technical_complex|high_value|complaint|wants_schedule", "reason": "motivo", "priority": "normal|alta"}
- "internal_notes" sao notas internas para contexto (nao enviadas ao lead)
- Nunca incluas texto fora do JSON
- Nunca incluas markdown code blocks — apenas JSON puro
"""


def _get_client() -> OpenAI:
    """Cria cliente OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY nao definida no .env")
    return OpenAI(api_key=api_key)


def _resolve_niche(sector: str) -> str:
    """Resolve alias de nicho para o nome do directorio."""
    return NICHE_ALIASES.get(sector.strip().lower(), sector.strip().lower())


def _load_system_prompt(nicho: str) -> str:
    """Carrega system prompt do nicho.

    Tenta system_prompt.md primeiro (formato novo).
    Fallback para 3 ficheiros antigos (personalidade + conhecimento + objecoes).
    """
    nicho_resolved = _resolve_niche(nicho)
    nicho_dir = AGENTES_DIR / nicho_resolved

    if not nicho_dir.exists():
        logger.warning("Directorio de agente nao encontrado: %s", nicho_dir)
        return ""

    # Formato novo: ficheiro unico
    single = nicho_dir / "system_prompt.md"
    if single.exists():
        logger.info("System prompt carregado: %s/system_prompt.md", nicho_resolved)
        return single.read_text(encoding="utf-8")

    # Fallback: 3 ficheiros antigos
    context = ""
    for filename in ["personalidade.md", "conhecimento.md", "objecoes.md"]:
        filepath = nicho_dir / filename
        if filepath.exists():
            section = filename.replace(".md", "").upper()
            context += f"\n\n## {section}\n\n{filepath.read_text(encoding='utf-8')}"
    if context:
        logger.info("Knowledge base (3 ficheiros) carregada: %s", nicho_resolved)
    return context


def has_niche_agent(sector: str) -> bool:
    """Verifica se o nicho tem agente especialista (system_prompt.md)."""
    nicho = _resolve_niche(sector)
    return (AGENTES_DIR / nicho / "system_prompt.md").exists()


def _build_system_prompt(nicho: str, nome: str, conv_state: dict) -> str:
    """Monta o system prompt completo: nicho + lead + contexto + JSON."""
    base = _load_system_prompt(nicho)
    if not base:
        base = f"Es o assistente da PercepTudo. Estas a conversar com {nome} via WhatsApp. Responde em PT-PT, max 3 frases por mensagem."

    # Dados do lead
    lead_data = conv_state.get("lead_data", {})
    lead_context = f"""

===== LEAD ACTUAL =====
- Nome: {nome}
- Cidade: {lead_data.get('cidade', 'N/A')}
- Rating Google: {lead_data.get('rating', 'N/A')} ({lead_data.get('reviews', 'N/A')} reviews)
- Website: {lead_data.get('website', 'N/A')}
- Instagram: {lead_data.get('instagram', 'N/A')}
"""

    # Estado da conversa
    stage = conv_state.get("stage", "situacao")
    price_count = conv_state.get("price_ask_count", 0)
    msg_count = len(conv_state.get("messages", []))
    conv_context = f"""
===== ESTADO DA CONVERSA =====
- Fase SPIN actual: {stage}
- Vezes que pediu preco: {price_count}
- Mensagens trocadas: {msg_count}
"""

    return base + lead_context + conv_context + JSON_FORMAT_INSTRUCTIONS


def _load_conversation_state(phone: str) -> dict:
    """Carrega estado de conversa. Migra v1 (lista) para v2 (envelope)."""
    phone_clean = phone.replace("+", "").replace(" ", "")
    conv_file = CONVERSATION_DIR / f"{phone_clean}.json"

    if not conv_file.exists():
        return {
            "version": 2,
            "phone": phone_clean,
            "nome": "",
            "nicho": "",
            "stage": "situacao",
            "price_ask_count": 0,
            "last_activity": datetime.now().isoformat(),
            "lead_data": {},
            "messages": [],
        }

    try:
        data = json.loads(conv_file.read_text(encoding="utf-8"))

        # Migracao v1 → v2
        if isinstance(data, list):
            logger.info("Migrando conversa v1 para v2: %s", phone_clean)
            return {
                "version": 2,
                "phone": phone_clean,
                "nome": "",
                "nicho": "",
                "stage": "situacao",
                "price_ask_count": 0,
                "last_activity": datetime.now().isoformat(),
                "lead_data": {},
                "messages": data[-MAX_HISTORY:],
            }

        # v2
        data["messages"] = data.get("messages", [])[-MAX_HISTORY:]
        return data

    except Exception as e:
        logger.warning("Erro ao carregar conversa %s: %s", phone, e)
        return {
            "version": 2, "phone": phone_clean, "nome": "", "nicho": "",
            "stage": "situacao", "price_ask_count": 0,
            "last_activity": datetime.now().isoformat(),
            "lead_data": {}, "messages": [],
        }


def _save_conversation_state(phone: str, state: dict) -> None:
    """Guarda estado de conversa."""
    phone_clean = phone.replace("+", "").replace(" ", "")
    conv_file = CONVERSATION_DIR / f"{phone_clean}.json"
    state["messages"] = state.get("messages", [])[-MAX_HISTORY:]
    state["last_activity"] = datetime.now().isoformat()
    try:
        conv_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error("Erro ao guardar conversa %s: %s", phone, e)


def _parse_gpt_response(raw: str, current_stage: str) -> dict:
    """Parse JSON do GPT com fallback para texto livre."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
        if "messages" not in data or not isinstance(data["messages"], list):
            raise ValueError("Campo 'messages' invalido")
        data.setdefault("stage", current_stage)
        data.setdefault("escalation", None)
        data.setdefault("internal_notes", "")
        return data
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("GPT nao retornou JSON valido: %s — fallback texto", e)
        return {
            "messages": [raw.strip()],
            "stage": current_stage,
            "escalation": None,
            "internal_notes": "fallback: GPT retornou texto livre",
        }


def _send_split_messages(phone: str, messages: list[str]) -> bool:
    """Envia multiplas mensagens com delay humano entre elas."""
    for i, msg in enumerate(messages):
        if not msg.strip():
            continue
        success = send_text(phone, msg)
        if not success:
            logger.error("Falha ao enviar msg %d/%d para %s", i + 1, len(messages), phone)
            return False
        if i < len(messages) - 1:
            time.sleep(random.uniform(1.0, 2.5))
    return True


def _detect_optout(message: str) -> bool:
    """Detecta pedido de opt-out."""
    msg_lower = message.strip().lower()
    return any(kw in msg_lower for kw in OPTOUT_KEYWORDS)


def _detect_price_ask(message: str) -> bool:
    """Detecta se o lead perguntou sobre preco."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in PRICE_KEYWORDS)


def _detect_complaint(message: str) -> bool:
    """Detecta reclamacao (safety net)."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in COMPLAINT_KEYWORDS)


def _find_lead_by_phone(phone: str) -> dict | None:
    """Procura lead no Sheets pelo telefone."""
    states = [
        "contactado", "followup_1", "followup_2", "followup_3",
        "respondeu", "agendado", "pronto_para_envio",
    ]
    leads = get_leads_by_statuses(states)
    phone_clean = phone.replace("+", "").replace(" ", "")[-9:]
    for lead in leads:
        lead_phone = str(lead.get("Telefone", "")).replace("+", "").replace(" ", "")
        if lead_phone.endswith(phone_clean):
            return lead
    return None


def _handle_escalation(
    phone: str, nome: str, nicho: str,
    escalation_data: dict, history_len: int,
) -> None:
    """Envia alerta detalhado ao Victor e actualiza estado."""
    esc_type = escalation_data.get("type", "unknown")
    reason = escalation_data.get("reason", "")
    priority = escalation_data.get("priority", "normal")

    priority_label = "URGENTE " if priority == "alta" else ""
    alert = (
        f"{priority_label}Escalacao: {esc_type}\n\n"
        f"Nome: {nome}\n"
        f"Telefone: +{phone.replace('+', '')}\n"
        f"Nicho: {nicho}\n"
        f"Motivo: {reason}\n"
        f"Mensagens trocadas: {history_len}"
    )

    try:
        send_text(VICTOR_PHONE, alert)
        logger.info("Alerta enviado ao Victor: %s (%s)", nome, esc_type)
    except Exception as e:
        logger.error("Erro ao notificar Victor: %s", e)

    # Actualizar Sheets
    telefone_str = str(phone)
    update_lead_status(
        telefone_str, "agendado",
        extra_data={"notas": f"Escalado: {esc_type} - {reason}"},
    )


def generate_outreach_message(
    nome: str, sector: str, lead_data: dict,
) -> tuple[list[str], dict]:
    """Gera primeira mensagem de outreach usando o agente especialista.

    Args:
        nome: Nome da empresa.
        sector: Sector/nicho.
        lead_data: Dados do lead (cidade, rating, website, etc).

    Returns:
        Tupla (lista de mensagens, estado de conversa criado).
    """
    nicho = _resolve_niche(sector)
    phone = lead_data.get("telefone", "").replace("+", "").replace(" ", "")

    # Criar estado de conversa
    conv_state = {
        "version": 2,
        "phone": phone,
        "nome": nome,
        "nicho": nicho,
        "stage": "outreach",
        "price_ask_count": 0,
        "last_activity": datetime.now().isoformat(),
        "lead_data": lead_data,
        "messages": [],
    }

    system_prompt = _build_system_prompt(nicho, nome, conv_state)

    user_msg = (
        f"Gera a primeira mensagem de outreach para {nome}. "
        f"E cold outreach — a empresa nunca ouviu falar da PercepTudo. "
        f"O PDF de diagnostico vai em anexo a seguir a esta mensagem. "
        f"Cria curiosidade para abrirem o PDF. "
        f"Menciona as dores do sector de forma directa. "
        f"Max 2-3 mensagens curtas."
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
        )

        parsed = _parse_gpt_response(
            response.choices[0].message.content or "", "outreach"
        )
        messages = parsed["messages"]

    except Exception as e:
        logger.error("Erro ao gerar outreach para '%s': %s", nome, e)
        # Fallback generico — adapta ao nicho
        FALLBACK_LABEL = {
            "oficinas": "oficina",
            "contabilidade": "gabinete",
        }
        label = FALLBACK_LABEL.get(nicho, "empresa")
        messages = [
            f"Bom dia, {nome}!",
            f"Preparamos um diagnostico gratuito para o vosso {label} — com dados concretos do sector e oportunidades de melhoria. Segue em anexo.",
        ]

    # Guardar mensagens no estado
    for msg in messages:
        conv_state["messages"].append({
            "role": "assistant",
            "content": msg,
            "timestamp": datetime.now().isoformat(),
        })

    logger.info("Outreach gerado para '%s': %d mensagens", nome, len(messages))
    return messages, conv_state


def generate_followup_message(
    nome: str, sector: str, touch: int, lead_data: dict,
) -> list[str]:
    """Gera mensagem de follow-up usando o agente especialista.

    Cada agente tem a sua cadencia e conteudo especifico por touch:
    - Rui (oficinas): dia 1=ANECRA, dia 3=processos, dia 7=chamadas, dia 14=porta aberta
    - Marco (contabilidade): dia 1=OCC, dia 3=classificacao, dia 7=docs, dia 14=porta aberta, dia 30=Tally

    Args:
        nome: Nome da empresa.
        sector: Sector/nicho.
        touch: Numero do touch (2-5).
        lead_data: Dados do lead.

    Returns:
        Lista de mensagens (1-2 msgs curtas).
    """
    nicho = _resolve_niche(sector)

    # Contexto minimo para o system prompt
    conv_state = {
        "version": 2,
        "phone": lead_data.get("telefone", ""),
        "nome": nome,
        "nicho": nicho,
        "stage": "outreach",
        "price_ask_count": 0,
        "last_activity": datetime.now().isoformat(),
        "lead_data": lead_data,
        "messages": [],
    }

    system_prompt = _build_system_prompt(nicho, nome, conv_state)

    # Instrucoes especificas por touch — forca o agente a seguir a SUA cadencia
    TOUCH_INSTRUCTIONS = {
        2: (
            f"Gera a mensagem de follow-up DIA 1 (valor) para {nome}. "
            f"Enviamos o PDF de diagnostico ontem. "
            f"Segue EXACTAMENTE a tua cadencia de follow-up definida para o Dia 1. "
            f"Usa o dado do sector que esta no teu prompt. "
            f"Max 1 mensagem curta (2-3 linhas)."
        ),
        3: (
            f"Gera a mensagem de follow-up DIA 3 (conteudo util) para {nome}. "
            f"Enviamos o PDF ha 7 dias, follow-up ha 4 dias. Sem resposta. "
            f"Segue EXACTAMENTE a tua cadencia de follow-up definida para o Dia 3. "
            f"Max 1 mensagem curta (2-3 linhas)."
        ),
        4: (
            f"Gera a mensagem de follow-up DIA 7 (reframe) para {nome}. "
            f"Ja tentamos contacto 3 vezes sem resposta. "
            f"Segue EXACTAMENTE a tua cadencia de follow-up definida para o Dia 7. "
            f"Aborda um angulo diferente dos contactos anteriores. "
            f"Max 1 mensagem curta (2-3 linhas)."
        ),
        5: (
            f"Gera a mensagem de follow-up DIA 14 ou DIA 30 (porta aberta / reengagement) para {nome}. "
            f"E o ultimo contacto. Sem resposta a todos os anteriores. "
            f"Segue EXACTAMENTE a tua cadencia de follow-up para o ultimo toque. "
            f"Respeitoso, sem pressao, porta aberta. "
            f"Max 1 mensagem curta (2-3 linhas)."
        ),
    }

    user_msg = TOUCH_INSTRUCTIONS.get(touch)
    if not user_msg:
        user_msg = (
            f"Gera uma mensagem de follow-up para {nome}. "
            f"Touch numero {touch}. Max 1 mensagem curta."
        )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
        )

        parsed = _parse_gpt_response(
            response.choices[0].message.content or "", "outreach"
        )
        messages = parsed["messages"]

        # Adicionar opt-out footer a ultima mensagem
        OPT_OUT = "\n\n_Para deixar de receber mensagens, responda PARAR._"
        if messages:
            messages[-1] = messages[-1] + OPT_OUT

        logger.info(
            "Follow-up touch %d gerado por agente para '%s': %d msgs",
            touch, nome, len(messages),
        )
        return messages

    except Exception as e:
        logger.error("Erro ao gerar follow-up agente para '%s': %s", nome, e)
        return [f"{nome}, o diagnostico que preparamos para si continua disponivel. Se tiver questoes, estamos por aqui.\n\n_Para deixar de receber mensagens, responda PARAR._"]


def handle_incoming_message(phone: str, message: str) -> str | None:
    """Processa mensagem recebida de um lead e gera resposta.

    Fluxo:
    1. Responde 24/7
    2. Verifica estado agendado/removido → nao responde
    3. Detecta opt-out → estado removido
    4. Actualiza estado para respondeu
    5. Carrega conversa + knowledge base
    6. Tracking: price_ask_count
    7. GPT gera resposta JSON
    8. Verifica escalacao (GPT + code safety net)
    9. Envia mensagens quebradas
    10. Guarda estado

    Returns:
        Ultima mensagem enviada, ou None se nao respondeu.
    """
    logger.info("Mensagem recebida de %s: %s", phone, message[:100])

    # Procurar lead no Sheets
    lead = _find_lead_by_phone(phone)
    nome = lead.get("Nome", "Cliente") if lead else "Cliente"
    nicho = lead.get("Sector", "").strip().lower() if lead else ""
    estado = lead.get("Estado", "").strip().lower() if lead else ""
    telefone = str(lead.get("Telefone", phone)) if lead else str(phone)

    # 1. Estado agendado → nao responder
    if estado == "agendado":
        logger.info("Lead '%s' agendado — ignorando", nome)
        return None

    # 2. Estado removido → nao responder
    if estado == "removido":
        logger.info("Lead '%s' removido — ignorando", nome)
        return None

    # 3. Opt-out
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

    # 4. Actualizar estado para respondeu
    if lead and estado not in ("respondeu", "agendado"):
        update_lead_status(telefone, "respondeu")

    # 5. Carregar estado de conversa
    conv_state = _load_conversation_state(phone)

    # Enriquecer estado com dados do lead se nao tinha
    if not conv_state.get("nome") and nome != "Cliente":
        conv_state["nome"] = nome
    if not conv_state.get("nicho") and nicho:
        conv_state["nicho"] = _resolve_niche(nicho)
    if not conv_state.get("lead_data") or not conv_state["lead_data"]:
        if lead:
            conv_state["lead_data"] = {
                "cidade": lead.get("Cidade", ""),
                "rating": str(lead.get("Rating", "")),
                "reviews": str(lead.get("Reviews", "")),
                "website": lead.get("Website", ""),
                "instagram": lead.get("Instagram", ""),
            }

    # Adicionar mensagem do lead ao historico
    conv_state["messages"].append({
        "role": "user",
        "content": message,
        "timestamp": datetime.now().isoformat(),
    })

    # 6. Tracking: price_ask_count
    if _detect_price_ask(message):
        conv_state["price_ask_count"] = conv_state.get("price_ask_count", 0) + 1
        logger.info("Price ask count para '%s': %d", nome, conv_state["price_ask_count"])

    # Se stage era outreach e lead respondeu, avanca para situacao
    if conv_state.get("stage") == "outreach":
        conv_state["stage"] = "situacao"

    # 7. Gerar resposta via GPT
    nicho_resolved = conv_state.get("nicho", "") or _resolve_niche(nicho)
    system_prompt = _build_system_prompt(nicho_resolved, nome, conv_state)

    gpt_messages = [{"role": "system", "content": system_prompt}]
    for msg in conv_state["messages"][-MAX_HISTORY:]:
        gpt_messages.append({"role": msg["role"], "content": msg["content"]})

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=gpt_messages,
        )
        parsed = _parse_gpt_response(
            response.choices[0].message.content or "",
            conv_state.get("stage", "situacao"),
        )
    except Exception as e:
        logger.error("Erro ao gerar resposta para '%s': %s", nome, e)
        parsed = {
            "messages": [f"Obrigado pela mensagem, {nome}. Vou confirmar internamente e volto a contactar brevemente."],
            "stage": conv_state.get("stage", "situacao"),
            "escalation": None,
        }

    # 8. Actualizar stage
    new_stage = parsed.get("stage", conv_state.get("stage", "situacao"))
    if new_stage in VALID_STAGES:
        conv_state["stage"] = new_stage

    # 9. Verificar escalacao — GPT + code safety net
    escalation = parsed.get("escalation")

    # Safety net: price_ask_count >= 2
    if not escalation and conv_state.get("price_ask_count", 0) >= 2:
        escalation = {
            "type": "price_2x",
            "reason": f"Pediu preco {conv_state['price_ask_count']} vezes",
            "priority": "alta",
        }

    # Safety net: complaint
    if not escalation and _detect_complaint(message):
        escalation = {
            "type": "complaint",
            "reason": "Reclamacao detectada na mensagem",
            "priority": "alta",
        }

    if escalation:
        logger.info("Escalacao para '%s': %s", nome, escalation.get("type"))
        conv_state["stage"] = "escalado"

        # Enviar mensagens do GPT (que ja incluem despedida de escalacao)
        _send_split_messages(telefone, parsed["messages"])

        # Notificar Victor
        _handle_escalation(
            phone=telefone,
            nome=nome,
            nicho=nicho_resolved,
            escalation_data=escalation,
            history_len=len(conv_state["messages"]),
        )

        # Guardar mensagens no historico
        for msg in parsed["messages"]:
            conv_state["messages"].append({
                "role": "assistant",
                "content": msg,
                "timestamp": datetime.now().isoformat(),
            })
        _save_conversation_state(phone, conv_state)
        return parsed["messages"][-1] if parsed["messages"] else None

    # 10. Enviar resposta normal (mensagens quebradas)
    _send_split_messages(telefone, parsed["messages"])

    # Guardar no historico
    for msg in parsed["messages"]:
        conv_state["messages"].append({
            "role": "assistant",
            "content": msg,
            "timestamp": datetime.now().isoformat(),
        })
    _save_conversation_state(phone, conv_state)

    logger.info("Resposta enviada a '%s' (%d msgs, stage=%s)",
                nome, len(parsed["messages"]), conv_state["stage"])
    return parsed["messages"][-1] if parsed["messages"] else None
