"""Gera PDFs de diagnostico para as 20 primeiras empresas de contabilidade em Lisboa.

Filtra leads do Sheets com sector: contabilistas, contabilidade, gabinete de contabilidade.
Enriquece cada lead (website + Instagram + Google Reviews) e gera PDF via template contabilidade.
"""

import sys
import os
import asyncio
import time
import traceback

os.chdir('/Users/sirvictoroliveira007/Desktop/Projetos-Gerais/percepTudo/perceptudo-prospector')
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('.env')

import googlemaps
from crm.sheets import _get_worksheet_leads
from scraper.website import analyze_websites
from scraper.instagram import scrape_instagram_profiles
from scraper.google_reviews import enrich_lead_with_reviews
from pdf.html_generator import generate_niche_pdf

# === CONFIG ===
CIDADE = "Lisboa"
MAX_LEADS = 20
SECTORES_CONTABILIDADE = {
    "contabilistas", "contabilista", "contabilidade",
    "gabinete de contabilidade", "gabinetes de contabilidade",
    "escritorio de contabilidade", "escritorios de contabilidade",
}

# === FASE 1: Buscar leads do Sheets ===
print("=" * 60)
print("FASE 1: A buscar leads do Sheets...")
print("=" * 60)

ws = _get_worksheet_leads()
records = ws.get_all_records()

# Filtrar por sector de contabilidade + Lisboa
leads_filtrados = []
for r in records:
    sector = r.get("Sector", "").strip().lower()
    cidade = r.get("Cidade", "").strip().lower()
    if sector in SECTORES_CONTABILIDADE and cidade == CIDADE.lower():
        leads_filtrados.append(r)

print(f"Total de leads contabilidade em {CIDADE}: {len(leads_filtrados)}")

# Limitar a 20
leads_filtrados = leads_filtrados[:MAX_LEADS]
print(f"A processar: {len(leads_filtrados)} leads")

if not leads_filtrados:
    print("ERRO: Nenhum lead encontrado! Verifica o Sheets.")
    sys.exit(1)

# Mapear keys para lowercase (generate_niche_pdf espera keys minusculas)
leads = []
for r in leads_filtrados:
    lead = {
        "nome": r.get("Nome", ""),
        "telefone": r.get("Telefone", ""),
        "cidade": r.get("Cidade", ""),
        "sector": r.get("Sector", ""),
        "rating": r.get("Rating", ""),
        "reviews": r.get("Reviews", ""),
        "instagram_url": r.get("Instagram", ""),
        "website": r.get("Website", ""),
        "slug": r.get("Nome", "").lower().replace(" ", "-"),
    }
    leads.append(lead)
    print(f"  - {lead['nome']} | {lead['sector']} | {lead['cidade']}")

# === FASE 2: Obter place_id para cada lead ===
print("\n" + "=" * 60)
print("FASE 2: A obter place_id via Google Maps API...")
print("=" * 60)

gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))

for i, lead in enumerate(leads):
    try:
        response = gmaps.places(
            query=f"{lead['nome']} {lead['sector']} {lead['cidade']}",
            language="pt", region="pt"
        )
        results = response.get("results", [])
        if results:
            lead["place_id"] = results[0]["place_id"]
            lead["morada"] = results[0].get("formatted_address", "")
            print(f"  [{i+1}/{len(leads)}] {lead['nome']} -> place_id OK")
        else:
            print(f"  [{i+1}/{len(leads)}] {lead['nome']} -> SEM place_id")
    except Exception as e:
        print(f"  [{i+1}/{len(leads)}] {lead['nome']} -> ERRO: {e}")

# === FASE 3.1: Website (Playwright — 22 campos) ===
print("\n" + "=" * 60)
print("FASE 3.1: A analisar websites com Playwright...")
print("=" * 60)

try:
    leads = asyncio.run(analyze_websites(leads))
    print(f"  Websites analisados: {len(leads)}")
except Exception as e:
    print(f"  ERRO no Playwright: {e}")
    traceback.print_exc()

# === FASE 3.2: Instagram (Apify) ===
print("\n" + "=" * 60)
print("FASE 3.2: A raspar Instagram via Apify...")
print("=" * 60)

try:
    leads = scrape_instagram_profiles(leads)
    print(f"  Perfis Instagram processados: {len(leads)}")
except Exception as e:
    print(f"  ERRO no Instagram: {e}")
    traceback.print_exc()

# === FASE 3.3: Google Reviews (Apify) ===
print("\n" + "=" * 60)
print("FASE 3.3: A raspar Google Reviews via Apify...")
print("=" * 60)

for i, lead in enumerate(leads):
    try:
        lead = enrich_lead_with_reviews(lead, max_reviews=30)
        leads[i] = lead
        total = lead.get("total_reviews_scraped", 0)
        neg = len(lead.get("reviews_negativas", []))
        pos = len(lead.get("reviews_positivas", []))
        print(f"  [{i+1}/{len(leads)}] {lead['nome']} -> {total} reviews ({neg} neg, {pos} pos)")
    except Exception as e:
        print(f"  [{i+1}/{len(leads)}] {lead['nome']} -> ERRO reviews: {e}")

# === FASE 4: Gerar PDFs ===
print("\n" + "=" * 60)
print("FASE 4: A gerar PDFs com analista Nuno + template contabilidade...")
print("=" * 60)

sucesso = 0
erros = 0

for i, lead in enumerate(leads):
    print(f"\n  [{i+1}/{len(leads)}] {lead['nome']}...")
    try:
        start = time.time()
        pdf_path = generate_niche_pdf(lead)
        elapsed = time.time() - start
        if pdf_path:
            print(f"    PDF gerado em {elapsed:.1f}s: {pdf_path}")
            sucesso += 1
        else:
            print(f"    FALHOU — sem output")
            erros += 1
    except Exception as e:
        print(f"    ERRO: {e}")
        traceback.print_exc()
        erros += 1

# === RESUMO ===
print("\n" + "=" * 60)
print(f"CONCLUIDO: {sucesso} PDFs gerados | {erros} erros | {len(leads)} total")
print("=" * 60)
print(f"\nPDFs em: output/leads/{{slug}}/diagnostico.pdf")
