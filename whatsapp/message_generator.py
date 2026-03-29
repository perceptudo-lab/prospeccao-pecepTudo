"""Gerador de mensagens WhatsApp variadas por nicho.

Usa GPT-5 para gerar mensagens unicas por lead (anti-spam).
Cada mensagem segue a estrategia do nicho mas com texto diferente.

Custo estimado: ~$0.008 por mensagem.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

from scraper.utils import setup_logger

load_dotenv()
logger = setup_logger(__name__)

OPENAI_MODEL = os.getenv("OPENAI_MSG_MODEL", "gpt-5")

# Dores fixas por sector — usadas como base para as mensagens
SECTOR_PAINS = {
    "contabilidade": [
        "800h por ano gastas em tarefas repetitivas como lancamentos e reconciliacoes",
        "84% dos gabinetes nao conseguem contratar profissionais qualificados",
        "Multas da AT por erros e documentos perdidos dos clientes",
    ],
    "contabilista": None,  # alias
    "contabilistas": None,  # alias
    "gabinete de contabilidade": None,  # alias
    "escritorio de contabilidade": None,  # alias
}

# Resolver aliases
for _key, _val in list(SECTOR_PAINS.items()):
    if _val is None:
        SECTOR_PAINS[_key] = SECTOR_PAINS["contabilidade"]


def _get_sector_pains(sector: str) -> list[str]:
    """Retorna dores fixas do sector. Fallback vazio se nao existir."""
    return SECTOR_PAINS.get(sector.strip().lower(), [])


# System prompts por touch
TOUCH_PROMPTS = {
    1: """Es um especialista em {sector} em Portugal. Gera UMA mensagem WhatsApp de cold outreach para o negocio "{nome}".

CONTEXTO: Estamos a enviar um PDF de diagnostico gratuito em anexo. A mensagem TEM de criar curiosidade para abrir o PDF.

DORES DO SECTOR (menciona TODAS de forma resumida e directa):
{dores}

ESTRUTURA OBRIGATORIA:
1. Saudacao com o nome do negocio (nao uses "Ola, tudo bem?" — parece bot)
2. Lista as dores do sector de forma curta e directa
3. Frase de identificacao: "Se alguma destas situacoes faz parte da vossa realidade..." ou similar
4. Refere o diagnostico gratuito personalizado — o PDF vai em anexo

REGRAS:
- PT-PT (nunca PT-BR): usa "gabinete" nao "escritorio", "gestao" nao "gerenciamento"
- NAO menciones IA, automacao, tecnologia, site, Instagram, presenca digital
- NAO uses "inovador", "solucao", "oportunidade unica" ou jargao de vendas
- NAO pedir "posso ligar?" ou "tem 5 minutos?"
- Maximo 1 emoji
- Maximo 4-5 linhas curtas
- Tom: especialista que conhece o sector a fundo, NAO vendedor
- VARIA o texto — nunca repitas a mesma estrutura exacta

Responde APENAS com a mensagem, sem explicacoes.""",

    2: """Gera uma mensagem curta de follow-up para o negocio "{nome}" (sector: {sector}).

CONTEXTO: Enviamos um diagnostico gratuito (PDF) ha 3 dias. Queremos saber se viram.

ESTRUTURA: 2-3 linhas no maximo. Curto e directo.
Exemplos de abordagem (varia):
- Perguntar se conseguiram ver o diagnostico
- Mencionar que o diagnostico foi preparado especificamente para eles
- Referir que fica disponivel se tiverem questoes

REGRAS:
- PT-PT, tom profissional mas acessivel
- NAO repitas as dores (ja foram no primeiro contacto)
- NAO uses "Ola, tudo bem?"
- Maximo 1 emoji ou nenhum
- VARIA — cada mensagem deve ser diferente

Responde APENAS com a mensagem.""",

    3: """Gera uma mensagem de follow-up com angulo diferente para o negocio "{nome}" (sector: {sector}).

CONTEXTO: Ja enviamos o diagnostico ha 7 dias e um follow-up ha 4 dias. Sem resposta.

ESTRATEGIA: Destaca UMA dor especifica do sector e liga ao diagnostico.
Escolhe UMA destas dores e constroi a mensagem a volta dela:
{dores}

ESTRUTURA: 2-3 linhas. Foca na dor escolhida + refere o diagnostico.

REGRAS:
- PT-PT, tom de especialista preocupado (nao vendedor)
- NAO repitas o formato dos contactos anteriores
- Maximo 1 emoji ou nenhum
- VARIA — cada mensagem deve ser unica

Responde APENAS com a mensagem.""",

    4: """Gera uma mensagem de despedida respeitosa para o negocio "{nome}" (sector: {sector}).

CONTEXTO: E o ultimo contacto. Ja tentamos 3 vezes sem resposta. Queremos fechar de forma profissional.

ESTRUTURA: 2-3 linhas. Respeitoso, sem pressao.
Transmitir: "Nao quero ser insistente, o diagnostico fica convosco, boa continuacao."

REGRAS:
- PT-PT, tom humano e respeitoso
- NAO menciones quantas vezes tentaste contactar
- NAO uses culpa ou pressao
- Maximo 1 emoji ou nenhum
- VARIA — cada despedida deve ser diferente

Responde APENAS com a mensagem.""",
}

OPT_OUT_FOOTER = "\n\n_Para deixar de receber mensagens, responda PARAR._"


def _get_client() -> OpenAI:
    """Cria cliente OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY nao definida no .env")
    return OpenAI(api_key=api_key)


def generate_message(
    nome: str,
    sector: str,
    touch: int = 1,
) -> str:
    """Gera mensagem WhatsApp variada via GPT-5.

    Args:
        nome: Nome da empresa (ex: 'Contar Mais Lda').
        sector: Sector/nicho (ex: 'contabilidade').
        touch: Numero do toque (1=primeiro contacto, 2-4=follow-ups).

    Returns:
        Mensagem WhatsApp com opt-out no final.
    """
    touch = max(1, min(4, touch))
    dores = _get_sector_pains(sector)
    dores_text = "\n".join(f"- {d}" for d in dores) if dores else "- (sem dores especificas definidas)"

    prompt_template = TOUCH_PROMPTS.get(touch, TOUCH_PROMPTS[1])
    system_prompt = prompt_template.format(
        nome=nome,
        sector=sector,
        dores=dores_text,
    )

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Gera a mensagem para: {nome}"},
            ],
        )

        message = response.choices[0].message.content.strip()

        # Remover aspas se o GPT envolver em aspas
        if message.startswith('"') and message.endswith('"'):
            message = message[1:-1]

        # Adicionar opt-out
        message += OPT_OUT_FOOTER

        logger.info(
            "Mensagem touch %d gerada para '%s' (%d chars)",
            touch, nome, len(message),
        )
        return message

    except Exception as e:
        logger.error("Erro ao gerar mensagem para '%s': %s", nome, e)
        # Fallback generico
        if touch == 1:
            return f"Bom dia, {nome}. Preparamos um diagnostico gratuito para o vosso negocio. Segue em anexo.{OPT_OUT_FOOTER}"
        elif touch == 2:
            return f"Bom dia, {nome}. Enviamos um diagnostico ha alguns dias. Tiveram oportunidade de ver?{OPT_OUT_FOOTER}"
        elif touch == 3:
            return f"{nome}, o diagnostico que vos enviamos tem informacao relevante para o vosso sector. Fica disponivel se quiserem conversar.{OPT_OUT_FOOTER}"
        else:
            return f"{nome}, nao quero ser insistente. O diagnostico fica convosco. Boa continuacao.{OPT_OUT_FOOTER}"
