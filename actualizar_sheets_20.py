"""Actualiza o Google Sheets para os 20 leads de contabilidade Lisboa.

Preenche: Estado -> pronto_para_envio, Link PDF, Mensagem WhatsApp.
Extrai a mensagem WhatsApp do JSON nos relatorios gerados.
"""

import sys
import os
import json
import re

os.chdir('/Users/sirvictoroliveira007/Desktop/Projetos-Gerais/percepTudo/perceptudo-prospector')
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('.env')

from crm.sheets import _get_worksheet_leads, update_lead_status
from pathlib import Path

# === CONFIG ===
CIDADE = "Lisboa"
SECTORES_CONTABILIDADE = {
    "contabilistas", "contabilista", "contabilidade",
    "gabinete de contabilidade", "gabinetes de contabilidade",
    "escritorio de contabilidade", "escritorios de contabilidade",
}
MAX_LEADS = 20
OUTPUT_DIR = Path("output/leads")

# === Buscar leads do Sheets ===
print("A buscar leads do Sheets...")
ws = _get_worksheet_leads()
records = ws.get_all_records()

leads_filtrados = []
for r in records:
    sector = r.get("Sector", "").strip().lower()
    cidade = r.get("Cidade", "").strip().lower()
    if sector in SECTORES_CONTABILIDADE and cidade == CIDADE.lower():
        leads_filtrados.append(r)

leads_filtrados = leads_filtrados[:MAX_LEADS]
print(f"Encontrados {len(leads_filtrados)} leads para actualizar")

# === Para cada lead, extrair mensagem WhatsApp e actualizar Sheets ===
sucesso = 0
erros = 0

for i, r in enumerate(leads_filtrados):
    nome = r.get("Nome", "")
    telefone = r.get("Telefone", "")
    slug = nome.lower().replace(" ", "-")

    lead_dir = OUTPUT_DIR / slug
    pdf_path = lead_dir / "diagnostico.pdf"
    report_path = lead_dir / "relatorio_analise.md"

    print(f"\n[{i+1}/{len(leads_filtrados)}] {nome}")

    # Verificar se o PDF existe
    if not pdf_path.exists():
        print(f"  AVISO: PDF nao encontrado em {pdf_path}")
        erros += 1
        continue

    # Extrair mensagem WhatsApp do relatorio (esta no JSON entre %%JSON_START%% e %%JSON_END%%)
    mensagem_whatsapp = ""

    # Tentar ler o HTML gerado que tem o JSON inline, ou procurar ficheiros de output
    # A mensagem foi guardada pelo generate_niche_pdf no lead dict, mas nao persistida
    # Vamos tentar extrair do relatorio markdown original (antes do split JSON)

    # Alternativa: procurar nos ficheiros de output por algum JSON guardado
    json_path = lead_dir / "analise.json"
    if json_path.exists():
        try:
            with open(json_path, "r") as f:
                data = json.load(f)
                mensagem_whatsapp = data.get("mensagem_whatsapp", "")
        except Exception:
            pass

    # Se nao temos JSON separado, tentar extrair do relatorio
    if not mensagem_whatsapp and report_path.exists():
        try:
            content = report_path.read_text(encoding="utf-8")
            # O relatorio e a parte ANTES do JSON, entao o JSON nao esta la
            # Mas vamos tentar caso esteja
            if "%%JSON_START%%" in content:
                json_str = content.split("%%JSON_START%%")[1].split("%%JSON_END%%")[0].strip()
                data = json.loads(json_str)
                mensagem_whatsapp = data.get("mensagem_whatsapp", "")
        except Exception:
            pass

    # Actualizar Sheets
    pdf_abs_path = str(pdf_path.resolve())

    extra_data = {
        "link_pdf": pdf_abs_path,
    }
    if mensagem_whatsapp:
        extra_data["mensagem_whatsapp"] = mensagem_whatsapp

    try:
        result = update_lead_status(
            phone=telefone,
            status="pronto_para_envio",
            extra_data=extra_data,
        )
        if result:
            print(f"  OK: Estado -> pronto_para_envio | Link PDF preenchido")
            if mensagem_whatsapp:
                print(f"  Mensagem WhatsApp: {mensagem_whatsapp[:80]}...")
            else:
                print(f"  AVISO: Mensagem WhatsApp nao encontrada (preencher manualmente)")
            sucesso += 1
        else:
            print(f"  ERRO: Telefone {telefone} nao encontrado no Sheets")
            erros += 1
    except Exception as e:
        print(f"  ERRO: {e}")
        erros += 1

# === RESUMO ===
print(f"\n{'='*60}")
print(f"CONCLUIDO: {sucesso} actualizados | {erros} erros | {len(leads_filtrados)} total")
print(f"{'='*60}")
