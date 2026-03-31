#!/usr/bin/env python3
"""
PercepTudo Prospector — CLI principal

Subcomandos:
    scrape  — Raspar leads do Google Maps + enriquecer + gravar no Sheets
    gerar   — Gerar PDFs para leads 'novo' e marcar como 'pronto_para_envio'
    enviar  — Enviar PDFs pendentes por WhatsApp
    status  — Ver contagem de leads por estado

Uso:
    python main.py scrape --nicho "contabilistas" --cidade "Leiria"
    python main.py gerar --nicho "contabilistas" --cidade "Leiria"
    python main.py enviar [--nicho "contabilistas"] [--cidade "Leiria"]
    python main.py status [--nicho "contabilistas"] [--cidade "Leiria"]

    # Backwards compat (assume 'scrape'):
    python main.py --nicho "contabilistas" --cidade "Leiria"
"""

import argparse
import sys
from datetime import datetime

from dotenv import load_dotenv

from crm.sheets import get_leads_by_sector_city, get_leads_by_status
from scraper.enrichment import enrich_leads
from scraper.google_maps import search_businesses
from scraper.utils import setup_logger
from crm.sheets import add_leads

load_dotenv()
logger = setup_logger(__name__)


# =============================================
# Subcomando: scrape
# =============================================


def prospect(nicho: str, cidade: str) -> dict:
    """Raspa leads, enriquece e grava no Sheets.

    Args:
        nicho: Sector de negocio (ex: 'contabilistas').
        cidade: Cidade (ex: 'Leiria').

    Returns:
        Dict com estatisticas.
    """
    stats = {
        "nicho": nicho,
        "cidade": cidade,
        "inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "leads_encontrados": 0,
        "leads_enriquecidos": 0,
        "leads_gravados": 0,
    }

    print(f"\n{'='*60}")
    print(f"  PERCEPTUDO PROSPECTOR")
    print(f"  {nicho.title()} em {cidade}")
    print(f"{'='*60}\n")

    # 1. Google Maps
    print("▸ [1/3] A pesquisar no Google Maps...")
    leads = search_businesses(nicho, cidade)
    stats["leads_encontrados"] = len(leads)

    if not leads:
        print("  ✗ Nenhum lead encontrado ou termo ja utilizado.")
        return stats

    print(f"  ✓ {len(leads)} leads encontrados\n")

    # 2. Enriquecimento (Website + Instagram)
    print("▸ [2/3] A enriquecer (websites + Instagram)...")
    leads = enrich_leads(leads)
    stats["leads_enriquecidos"] = len(leads)

    if not leads:
        print("  ✗ Nenhum lead com telemovel valido apos enriquecimento.")
        return stats

    print(f"  ✓ {len(leads)} leads enriquecidos\n")

    for l in leads:
        ig = "IG" if l.get("instagram_url") else "--"
        chat = "Chat" if l.get("has_chat") else "----"
        blog = "Blog" if l.get("has_blog") else "----"
        cms = l.get("cms_platform", "?")
        print(f"    {l['nome'][:40]:<40} | {l['telefone']} | {ig} | {chat} | {blog} | {cms}")

    print()

    # 3. Gravar no Sheets
    print("▸ [3/3] A gravar no Sheets...")
    added = add_leads(leads)
    stats["leads_gravados"] = added
    print(f"  ✓ {added} leads gravados com estado 'novo'\n")

    # Resumo
    print(f"{'='*60}")
    print(f"  CONCLUIDO")
    print(f"{'='*60}")
    print(f"  Encontrados:    {stats['leads_encontrados']}")
    print(f"  Enriquecidos:   {stats['leads_enriquecidos']}")
    print(f"  No Sheets:      {stats['leads_gravados']}")
    print(f"{'='*60}\n")

    return stats


def cmd_scrape(args: argparse.Namespace) -> None:
    """Handler do subcomando 'scrape'."""
    prospect(args.nicho, args.cidade)


# =============================================
# Subcomando: gerar
# =============================================


def cmd_gerar(args: argparse.Namespace) -> None:
    """Handler do subcomando 'gerar'."""
    from pdf.orchestrator import batch_generate

    print(f"\n{'='*60}")
    print(f"  PERCEPTUDO — GERAR PDFs")
    print(f"  {args.nicho.title()} em {args.cidade}")
    print(f"{'='*60}")

    stats = batch_generate(args.nicho, args.cidade)

    print(f"\n{'='*60}")
    print(f"  CONCLUIDO")
    print(f"{'='*60}")
    print(f"  Total:    {stats['total']}")
    print(f"  Gerados:  {stats['gerados']}")
    print(f"  Erros:    {stats['erros']}")
    print(f"{'='*60}\n")

    if stats["gerados"] > 0:
        print(f"  Os PDFs ficam com estado 'pronto_para_envio' no Sheets.")
        print(f"  Para enviar: python main.py enviar\n")


# =============================================
# Subcomando: enviar
# =============================================


def cmd_enviar(args: argparse.Namespace) -> None:
    """Handler do subcomando 'enviar'."""
    from whatsapp.scheduler import send_pending_leads

    print(f"\n{'='*60}")
    print(f"  PERCEPTUDO — ENVIAR WhatsApp")
    if args.nicho and args.cidade:
        print(f"  Filtro: {args.nicho.title()} em {args.cidade}")
    else:
        print(f"  Todos os leads pendentes")
    print(f"{'='*60}\n")

    stats = send_pending_leads(sector=args.nicho, cidade=args.cidade)

    print(f"\n{'='*60}")
    print(f"  CONCLUIDO")
    print(f"{'='*60}")
    print(f"  Enviados:  {stats['enviados']}")
    print(f"  Erros:     {stats['erros']}")
    print(f"  Total:     {stats['total']}")
    print(f"{'='*60}\n")


# =============================================
# Subcomando: enviar-dia (novo scheduler)
# =============================================


def cmd_enviar_dia(args: argparse.Namespace) -> None:
    """Handler do subcomando 'enviar-dia' — scheduler diario com follow-ups."""
    from whatsapp.scheduler import send_daily_batch

    # Limites por nicho (se especificados)
    niche_limits = None
    if args.niche_limits:
        niche_limits = {}
        for pair in args.niche_limits:
            nicho, limit = pair.split(":")
            niche_limits[nicho.strip()] = int(limit.strip())

    # Cidades prioritarias
    priority_cities = None
    if args.priority_cities:
        priority_cities = [c.strip() for c in args.priority_cities.split(",")]

    # Instancias Evolution (se especificadas)
    instances = args.instances if args.instances else None

    stats = send_daily_batch(
        dry_run=args.dry_run,
        niche_limits=niche_limits,
        priority_cities=priority_cities,
        instances=instances,
    )

    if stats["total"] == 0:
        print("  Nenhum lead na fila (ou fora da janela horaria).\n")


# =============================================
# Subcomando: agente
# =============================================


def cmd_agente(args: argparse.Namespace) -> None:
    """Handler do subcomando 'agente' — inicia webhook server."""
    from whatsapp.webhook import start_server

    start_server(port=args.port, debug=args.debug)


# =============================================
# Subcomando: status
# =============================================


def cmd_status(args: argparse.Namespace) -> None:
    """Handler do subcomando 'status'."""
    print(f"\n{'='*60}")
    print(f"  PERCEPTUDO — STATUS")
    print(f"{'='*60}\n")

    estados = [
        "novo", "pronto_para_envio", "contactado",
        "followup_1", "followup_2", "followup_3",
        "respondeu", "agendado", "frio", "removido",
    ]

    if args.nicho and args.cidade:
        print(f"  Filtro: {args.nicho.title()} em {args.cidade}\n")
        for estado in estados:
            try:
                leads = get_leads_by_sector_city(args.nicho, args.cidade, estado)
                count = len(leads)
            except Exception:
                count = 0
            if count > 0:
                print(f"    {estado:<22} {count}")
    else:
        for estado in estados:
            try:
                leads = get_leads_by_status(estado)
                count = len(leads)
            except Exception:
                count = 0
            if count > 0:
                print(f"    {estado:<22} {count}")

    print(f"\n{'='*60}\n")


# =============================================
# CLI principal
# =============================================


def main() -> None:
    """Entry point CLI com subcomandos."""
    parser = argparse.ArgumentParser(
        description="PercepTudo Prospector — Raspar, gerar PDFs e enviar por WhatsApp"
    )
    subparsers = parser.add_subparsers(dest="comando")

    # Subcomando: scrape
    sp_scrape = subparsers.add_parser(
        "scrape", help="Raspar leads do Google Maps + enriquecer + gravar no Sheets"
    )
    sp_scrape.add_argument("--nicho", required=True, help="Sector (ex: contabilistas)")
    sp_scrape.add_argument("--cidade", required=True, help="Cidade (ex: Leiria)")
    sp_scrape.set_defaults(func=cmd_scrape)

    # Subcomando: gerar
    sp_gerar = subparsers.add_parser(
        "gerar", help="Gerar PDFs para leads 'novo' e marcar como 'pronto_para_envio'"
    )
    sp_gerar.add_argument("--nicho", required=True, help="Sector (ex: contabilistas)")
    sp_gerar.add_argument("--cidade", required=True, help="Cidade (ex: Leiria)")
    sp_gerar.set_defaults(func=cmd_gerar)

    # Subcomando: enviar
    sp_enviar = subparsers.add_parser(
        "enviar", help="Enviar PDFs pendentes por WhatsApp"
    )
    sp_enviar.add_argument("--nicho", help="Filtrar por sector (opcional)")
    sp_enviar.add_argument("--cidade", help="Filtrar por cidade (opcional)")
    sp_enviar.set_defaults(func=cmd_enviar)

    # Subcomando: enviar-dia (novo scheduler com follow-ups)
    sp_enviar_dia = subparsers.add_parser(
        "enviar-dia", help="Envio diario: novos + follow-ups na janela 9-13h"
    )
    sp_enviar_dia.add_argument("--dry-run", action="store_true", help="Simular sem enviar")
    sp_enviar_dia.add_argument(
        "--niche-limits", nargs="+", metavar="NICHO:N",
        help="Limite por nicho (ex: oficinas:40 contabilidade:40)",
    )
    sp_enviar_dia.add_argument(
        "--priority-cities", type=str,
        help="Cidades prioritarias separadas por virgula (ex: Lisboa,Porto)",
    )
    sp_enviar_dia.add_argument(
        "--instances", nargs="+", metavar="INSTANCE",
        help="Instancias Evolution para round-robin (ex: 'Percep Tudo AI' 'Percep Tudo - AI')",
    )
    sp_enviar_dia.set_defaults(func=cmd_enviar_dia)

    # Subcomando: agente (webhook server)
    sp_agente = subparsers.add_parser(
        "agente", help="Iniciar agente atendente WhatsApp (webhook server)"
    )
    sp_agente.add_argument("--port", type=int, default=5001, help="Porta (default: 5001)")
    sp_agente.add_argument("--debug", action="store_true", help="Modo debug com hot reload")
    sp_agente.set_defaults(func=cmd_agente)

    # Subcomando: status
    sp_status = subparsers.add_parser(
        "status", help="Ver contagem de leads por estado"
    )
    sp_status.add_argument("--nicho", help="Filtrar por sector (opcional)")
    sp_status.add_argument("--cidade", help="Filtrar por cidade (opcional)")
    sp_status.set_defaults(func=cmd_status)

    # Backwards compat: se nao houver subcomando mas --nicho e --cidade existirem
    # assume 'scrape'
    parser.add_argument("--nicho", help=argparse.SUPPRESS)
    parser.add_argument("--cidade", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.comando:
        args.func(args)
    elif args.nicho and args.cidade:
        # Backwards compat
        prospect(args.nicho, args.cidade)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
