"""Modulo de analise de leads com OpenAI GPT-5."""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from crm.sheets import update_lead_status
from scraper.utils import setup_logger

load_dotenv()
logger = setup_logger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Modelo OpenAI a usar
OPENAI_MODEL = "gpt-5"

# Mapeamento de nichos para ficheiros de prompt
NICHE_MAP = {
    "restaurantes": "restauracao.txt",
    "restaurante": "restauracao.txt",
    "cafes": "restauracao.txt",
    "café": "restauracao.txt",
    "cafés": "restauracao.txt",
    "padarias": "restauracao.txt",
    "padaria": "restauracao.txt",
    "pastelarias": "restauracao.txt",
    "pastelaria": "restauracao.txt",
    "churrasqueira": "restauracao.txt",
    "churrasqueiras": "restauracao.txt",
    "marisqueira": "restauracao.txt",
    "marisqueiras": "restauracao.txt",
    "pizzaria": "restauracao.txt",
    "pizzarias": "restauracao.txt",
    "bar": "restauracao.txt",
    "bares": "restauracao.txt",
    "construcao": "construcao.txt",
    "construção": "construcao.txt",
    "advocacia": "advocacia.txt",
    "advogados": "advocacia.txt",
}


def _load_prompt(filename: str) -> str:
    """Carrega um ficheiro de prompt."""
    filepath = PROMPTS_DIR / filename
    if not filepath.exists():
        return ""
    return filepath.read_text(encoding="utf-8")


def _get_niche_prompt(sector: str) -> str:
    """Retorna o prompt de nicho para o sector dado.

    Se nao existir ficheiro de benchmarks para o sector,
    gera automaticamente com GPT-5 e guarda para proximas vezes.
    """
    sector_lower = sector.strip().lower()
    niche_file = NICHE_MAP.get(sector_lower)

    # Tentar carregar ficheiro existente via NICHE_MAP
    if niche_file:
        prompt = _load_prompt(niche_file)
        if prompt:
            logger.info("Prompt de nicho carregado: %s", niche_file)
            return prompt

    # Tentar carregar pelo nome do sector directamente
    direct_file = f"{sector_lower}.txt"
    direct_prompt = _load_prompt(direct_file)
    if direct_prompt:
        logger.info("Prompt de nicho carregado: %s", direct_file)
        return direct_prompt

    # Nao existe — gerar automaticamente
    logger.info("Sem benchmarks para '%s' — a gerar automaticamente...", sector)
    return _generate_niche_benchmarks(sector)


def _generate_niche_benchmarks(sector: str) -> str:
    """Gera benchmarks de um sector automaticamente com GPT-5.

    Guarda o ficheiro em ai/prompts/{sector}.txt para reutilizacao.
    """
    try:
        client = _get_client()

        prompt = f"""Gera benchmarks detalhados para o sector de "{sector}" em Portugal,
seguindo EXACTAMENTE este formato:

## Contexto: Sector de {sector.title()} em Portugal

### Benchmarks reais do sector

**Custos operacionais tipicos:**
(lista 4-5 custos tipicos com percentagens reais)

**Tempos operacionais tipicos (PME, 10-50 funcionarios):**
(lista 8-10 tarefas administrativas com horas/semana em ranges)
- Total estimado em tarefas administrativas: XX-XXh/semana

**Custo hora medio:**
(lista 2-3 cargos com custo/hora em EUR)

### Oportunidades tipicas de IA para {sector}

(lista 5-7 oportunidades numeradas com titulo em bold e descricao curta)

### Benchmarks de ROI (conservadores, ja com reducao de 30%)

(lista 4-5 benchmarks com poupanca em horas ou percentagem)

### Dores comuns do sector

(lista 6-8 dores comuns em bullet points)

IMPORTANTE:
- Usa dados realisticos do mercado portugues
- Se conservador nos valores
- Usa SEMPRE ranges (ex: 3-5h, nunca 4h)
- Foca em PMEs (10-200 funcionarios)
- Responde APENAS com o texto formatado, sem JSON, sem markdown code blocks"""

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )

        benchmarks = response.choices[0].message.content.strip()

        # Guardar ficheiro para proximas vezes
        sector_slug = sector.strip().lower().replace(" ", "_")
        filename = f"{sector_slug}.txt"
        filepath = PROMPTS_DIR / filename
        filepath.write_text(benchmarks, encoding="utf-8")

        # Adicionar ao NICHE_MAP para esta sessao
        NICHE_MAP[sector.strip().lower()] = filename

        logger.info(
            "Benchmarks gerados e guardados em ai/prompts/%s", filename
        )
        return benchmarks

    except Exception as e:
        logger.error("Erro ao gerar benchmarks para '%s': %s", sector, e)
        return ""


def _get_client() -> OpenAI:
    """Cria cliente OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY nao definida no .env")
    return OpenAI(api_key=api_key)


def analyze_lead(lead: dict) -> dict | None:
    """Analisa um lead com GPT-5 via Chat Completions.

    Envia os dados do lead com prompt base + benchmarks do sector.
    Recebe analise JSON estruturada.

    Args:
        lead: Dict com dados do lead (nome, sector, cidade, rating, etc.)

    Returns:
        Dict com analise JSON ou None em caso de erro.
    """
    nome = lead.get("nome", "Desconhecido")
    sector = lead.get("sector", "")
    logger.info("A analisar lead: %s (%s)", nome, sector)

    try:
        client = _get_client()

        # Carregar prompts
        base_prompt = _load_prompt("base.txt")
        niche_prompt = _get_niche_prompt(sector)

        # System prompt = base + nicho
        system_content = base_prompt
        if niche_prompt:
            system_content += f"\n\n{niche_prompt}"

        # User message = dados do lead
        lead_data = _format_lead_data(lead)
        user_content = f"""Analisa este negocio e produz o JSON de diagnostico.

## Dados do negocio

{lead_data}

Responde APENAS com JSON valido, sem texto adicional."""

        # Chamar GPT-5
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )

        result = response.choices[0].message.content

        if not result:
            logger.error("Analise falhou para '%s' — resposta vazia", nome)
            return None

        # Extrair e validar JSON
        analysis = _parse_analysis(result)

        if analysis:
            logger.info(
                "Analise concluida para '%s': score=%s",
                nome, analysis.get("score", "?"),
            )

            # Actualizar score no Sheets
            phone = lead.get("telefone", "")
            if phone:
                update_lead_status(
                    phone, "novo",
                    extra_data={"score": str(analysis.get("score", ""))},
                )

        return analysis

    except Exception as e:
        logger.error("Erro ao analisar '%s': %s", nome, e)
        return None


def analyze_leads(leads: list[dict]) -> list[dict]:
    """Analisa multiplos leads com GPT-5.

    Args:
        leads: Lista de dicts de leads.

    Returns:
        Lista de leads com campo 'analise' adicionado (dict ou None).
    """
    logger.info("A analisar %d leads com OpenAI (%s)...", len(leads), OPENAI_MODEL)

    for i, lead in enumerate(leads):
        logger.info(
            "[%d/%d] A analisar: %s",
            i + 1, len(leads), lead.get("nome", "?"),
        )

        analysis = analyze_lead(lead)
        lead["analise"] = analysis

        if analysis:
            logger.info(
                "[%d/%d] %s: score=%s, %d oportunidades, %d solucoes",
                i + 1, len(leads), lead.get("nome", "?"),
                analysis.get("score", "?"),
                len(analysis.get("oportunidades", [])),
                len(analysis.get("solucoes", [])),
            )
        else:
            logger.warning(
                "[%d/%d] %s: analise falhou", i + 1, len(leads), lead.get("nome", "?")
            )

        # Pausa entre analises para nao sobrecarregar a API
        if i < len(leads) - 1:
            time.sleep(1)

    successful = sum(1 for l in leads if l.get("analise"))
    logger.info(
        "Analise OpenAI concluida: %d/%d leads analisados com sucesso",
        successful, len(leads),
    )

    return leads


def _format_lead_data(lead: dict) -> str:
    """Formata dados do lead para enviar ao GPT-5."""
    lines = [
        f"- Nome: {lead.get('nome', 'N/A')}",
        f"- Sector: {lead.get('sector', 'N/A')}",
        f"- Cidade: {lead.get('cidade', 'N/A')}",
        f"- Rating Google: {lead.get('rating', 'N/A')}",
        f"- Reviews Google: {lead.get('reviews', 'N/A')}",
        f"- Website: {lead.get('website', 'Sem website')}",
        # Redes sociais
        f"- Instagram: {lead.get('instagram_url') or 'Sem perfil'}",
        f"- Facebook: {lead.get('facebook_url') or 'Sem perfil'}",
        f"- LinkedIn: {lead.get('linkedin_url') or 'Sem perfil'}",
        f"- YouTube: {lead.get('youtube_url') or 'Sem perfil'}",
        f"- TikTok: {lead.get('tiktok_url') or 'Sem perfil'}",
        f"- Twitter/X: {lead.get('twitter_url') or 'Sem perfil'}",
        # Instagram metricas
        f"- Seguidores Instagram: {lead.get('instagram_followers', 'N/A')}",
        f"- Posts Instagram: {lead.get('instagram_posts', 'N/A')}",
        f"- Ultimo post Instagram: {lead.get('instagram_last_post', 'N/A')}",
        f"- Engagement Instagram: {lead.get('instagram_engagement', 'N/A')}",
        # Contactos no site
        f"- Telefone no site: {lead.get('phone_on_site') or 'Nao encontrado'}",
        f"- Email no site: {lead.get('email_on_site') or 'Nao encontrado'}",
        # Features do site
        f"- Tem chat no site: {'Sim' if lead.get('has_chat') else 'Nao'}",
        f"- Tem formulario/agendamento: {'Sim' if lead.get('has_form') else 'Nao'}",
        f"- Tem ecommerce: {'Sim' if lead.get('has_ecommerce') else 'Nao'}",
        f"- Tem blog: {'Sim' if lead.get('has_blog') else 'Nao'}",
        f"- Tem login/painel de cliente: {'Sim' if lead.get('has_login') else 'Nao'}",
        f"- Tem newsletter: {'Sim' if lead.get('has_newsletter') else 'Nao'}",
        f"- Tem video no site: {'Sim' if lead.get('has_video') else 'Nao'}",
        f"- Tem testemunhos no site: {'Sim' if lead.get('has_testimonials') else 'Nao'}",
        f"- Tem HTTPS: {'Sim' if lead.get('has_https') else 'Nao'}",
        f"- Tem cookie consent/GDPR: {'Sim' if lead.get('has_cookie_consent') else 'Nao'}",
        f"- Tem multi-idioma: {'Sim' if lead.get('has_multilang') else 'Nao'}",
        # Tecnologia
        f"- Plataforma/CMS: {lead.get('cms_platform', 'desconhecido')}",
        f"- Design do site: {lead.get('design_score', 'N/A')}",
        f"- Morada: {lead.get('morada', 'N/A')}",
    ]
    return "\n".join(lines)


def _parse_analysis(text: str) -> dict | None:
    """Faz parse e validacao basica do JSON de analise."""
    # Remover markdown code blocks se presentes
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("JSON invalido na resposta: %s", e)
        logger.debug("Texto recebido: %s", text[:500])
        return None

    # Validacao basica
    required_keys = ["resumo", "score", "oportunidades", "solucoes", "roi", "mensagem_whatsapp"]
    missing = [k for k in required_keys if k not in data]
    if missing:
        logger.warning("JSON incompleto — faltam keys: %s", missing)

    # Garantir que score esta dentro dos limites
    if "score" in data:
        data["score"] = max(5, min(95, int(data["score"])))

    # Garantir que resumo nao excede 200 chars
    if "resumo" in data and len(data["resumo"]) > 200:
        data["resumo"] = data["resumo"][:197] + "..."

    # Limitar oportunidades a 4
    if "oportunidades" in data and len(data["oportunidades"]) > 4:
        data["oportunidades"] = data["oportunidades"][:4]

    # Limitar solucoes a 3
    if "solucoes" in data and len(data["solucoes"]) > 3:
        data["solucoes"] = data["solucoes"][:3]

    return data
