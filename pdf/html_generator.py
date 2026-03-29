"""Gerador de PDF via template HTML + Playwright.

Fluxo simplificado:
1. Carrega template HTML do nicho (ex: contabilidade.html)
2. Substitui {NOME_EMPRESA} pelo nome do lead
3. Playwright converte HTML para PDF
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from scraper.utils import setup_logger

logger = setup_logger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Mapeamento de nichos para templates HTML
NICHE_TEMPLATES = {
    "contabilidade": "contabilidade.html",
    "contabilista": "contabilidade.html",
    "contabilistas": "contabilidade.html",
    "gabinete de contabilidade": "contabilidade.html",
    "gabinetes de contabilidade": "contabilidade.html",
    "escritorio de contabilidade": "contabilidade.html",
    "escritorios de contabilidade": "contabilidade.html",
    "oficinas": "oficinas.html",
    "oficina": "oficinas.html",
    "oficina de automóveis": "oficinas.html",
    "oficina de automoveis": "oficinas.html",
    "oficina de automóveis": "oficinas.html",
    "mecanica": "oficinas.html",
    "auto": "oficinas.html",
}


def _get_template(sector: str) -> str | None:
    """Carrega template HTML do nicho."""
    sector_lower = sector.strip().lower()
    template_file = NICHE_TEMPLATES.get(sector_lower)

    if not template_file:
        # Tentar pelo nome directo
        direct = TEMPLATES_DIR / f"{sector_lower}.html"
        if direct.exists():
            template_file = f"{sector_lower}.html"
        else:
            logger.warning("Sem template HTML para nicho '%s'", sector)
            return None

    filepath = TEMPLATES_DIR / template_file
    if not filepath.exists():
        logger.warning("Template nao encontrado: %s", filepath)
        return None

    logger.info("Template HTML carregado: %s", template_file)
    return filepath.read_text(encoding="utf-8")


async def _html_to_pdf(html_content: str, output_path: str) -> str:
    """Converte HTML para PDF usando Playwright."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.set_content(html_content, wait_until="networkidle")

        # Esperar fonts carregarem
        await page.wait_for_timeout(2000)

        await page.pdf(
            path=output_path,
            format="A4",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )

        await browser.close()

    return str(Path(output_path).resolve())


def generate_niche_pdf(lead: dict, output_path: str | None = None) -> str:
    """Gera PDF a partir de template fixo — so substitui {NOME_EMPRESA}.

    Args:
        lead: Dict com dados do lead (precisa de 'nome' e 'sector').
        output_path: Caminho para o PDF. Se None, gera automaticamente.

    Returns:
        Caminho do PDF gerado, ou string vazia em caso de erro.
    """
    nome = lead.get("nome", "Empresa")
    sector = lead.get("sector", "")
    slug = lead.get("slug", nome.lower().replace(" ", "-"))

    if not output_path:
        output_dir = Path("output/leads") / slug
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(output_dir / "diagnostico.pdf")

    logger.info("A gerar PDF para '%s' (%s)...", nome, sector)

    # 1. Carregar template
    template = _get_template(sector)
    if not template:
        logger.error("Sem template para sector '%s' — PDF nao gerado", sector)
        return ""

    # 2. Substituir placeholders
    website = lead.get("website", "") or ""
    instagram = lead.get("instagram_url", "") or ""
    html_final = template.replace("{NOME_EMPRESA}", nome)
    html_final = html_final.replace("{WEBSITE}", website)
    html_final = html_final.replace("{INSTAGRAM}", instagram)

    # 3. Converter HTML para PDF via Playwright
    try:
        pdf_path = asyncio.run(_html_to_pdf(html_final, output_path))
        logger.info("PDF gerado: %s", pdf_path)
        return pdf_path
    except Exception as e:
        logger.error("Erro ao converter HTML para PDF: %s", e)
        return ""


def has_niche_template(sector: str) -> bool:
    """Verifica se existe template HTML para o sector."""
    sector_lower = sector.strip().lower()
    if sector_lower in NICHE_TEMPLATES:
        return True
    return (TEMPLATES_DIR / f"{sector_lower}.html").exists()
