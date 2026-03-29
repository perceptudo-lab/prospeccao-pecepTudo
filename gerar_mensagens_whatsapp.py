"""Gera mensagens WhatsApp personalizadas para os 20 leads de contabilidade Lisboa.

Usa o relatorio_analise.md já gerado + GPT-5 para criar APENAS a mensagem.
Preenche a coluna 'Mensagem WhatsApp' no Sheets.
"""

import sys
import os
import time
import json

os.chdir('/Users/sirvictoroliveira007/Desktop/Projetos-Gerais/percepTudo/perceptudo-prospector')
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv('.env')

from openai import OpenAI
from pathlib import Path
from crm.sheets import _get_worksheet_leads, update_lead_status

# === CONFIG ===
CIDADE = "Lisboa"
MAX_LEADS = 20
SECTORES_CONTABILIDADE = {
    "contabilistas", "contabilista", "contabilidade",
    "gabinete de contabilidade", "gabinetes de contabilidade",
    "escritorio de contabilidade", "escritorios de contabilidade",
}
OUTPUT_DIR = Path("output/leads")

DORES_FIXAS = """- Tarefas repetitivas: 800h/ano gastas em lancamentos manuais e reconciliacoes
- Escassez de talento: 84% dos gabinetes nao conseguem contratar tecnicos qualificados
- Multas da AT e documentos perdidos: risco de coimas por atrasos e extravio de documentacao"""

PROMPT_MENSAGEM = f"""Es um especialista em contabilidade em Portugal. Com base na analise que ja fizeste deste gabinete/negocio, gera APENAS uma mensagem de WhatsApp para cold outreach.

DORES FIXAS DO SECTOR (menciona TODAS de forma resumida):
{DORES_FIXAS}

REGRAS DA MENSAGEM:
1. Saudacao com nome do gabinete/empresa
2. Listar as dores fixas do sector de forma curta e directa (todas elas)
3. Frase de identificacao: "Se isto faz parte da vossa realidade..." ou similar
4. Referir que preparaste um diagnostico gratuito personalizado — o PDF vai em anexo

Tom: Especialista que conhece o sector a fundo, NAO vendedor. Provocar identificacao com as dores. PT-PT (nunca PT-BR).

NAO FAZER:
- Nao usar "Ola, tudo bem?" (parece bot)
- Nao mencionar IA, automacao, ou tecnologia
- Nao falar de site, Instagram, presenca digital
- Nao pedir "posso ligar?" ou "tem 5 minutos?"
- Nao usar emojis excessivos (maximo 1)
- Nao mencionar precos ou investimentos
- Nao usar "inovador", "solucao", "oportunidade unica" ou jargao de vendas
- Maximo 4 linhas

Responde APENAS com a mensagem, sem explicacoes."""

# === Buscar leads ===
print("A buscar leads do Sheets...")
ws = _get_worksheet_leads()
records = ws.get_all_records()

leads = []
for r in records:
    sector = r.get("Sector", "").strip().lower()
    cidade = r.get("Cidade", "").strip().lower()
    if sector in SECTORES_CONTABILIDADE and cidade == CIDADE.lower():
        leads.append(r)

leads = leads[:MAX_LEADS]
print(f"{len(leads)} leads encontrados\n")

# === Gerar mensagens ===
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
sucesso = 0
erros = 0

for i, r in enumerate(leads):
    nome = r.get("Nome", "")
    telefone = r.get("Telefone", "")
    slug = nome.lower().replace(" ", "-")
    report_path = OUTPUT_DIR / slug / "relatorio_analise.md"

    print(f"[{i+1}/{len(leads)}] {nome}...")

    # Ler relatorio
    relatorio = ""
    if report_path.exists():
        relatorio = report_path.read_text(encoding="utf-8")[:3000]  # Limitar tamanho

    try:
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "system", "content": PROMPT_MENSAGEM},
                {"role": "user", "content": f"Nome do gabinete: {nome}\nCidade: {r.get('Cidade', 'Lisboa')}\n\nResumo da analise:\n{relatorio}"},
            ],
        )
        mensagem = response.choices[0].message.content.strip()
        print(f"  Mensagem: {mensagem[:100]}...")

        # Actualizar Sheets
        time.sleep(2)  # Evitar rate limiting
        result = update_lead_status(
            phone=telefone,
            status="pronto_para_envio",
            extra_data={"mensagem_whatsapp": mensagem},
        )
        if result:
            print(f"  Sheets actualizado OK")
            sucesso += 1
        else:
            print(f"  ERRO: telefone {telefone} nao encontrado no Sheets")
            erros += 1

        # Guardar JSON localmente tambem
        json_path = OUTPUT_DIR / slug / "analise.json"
        json_data = {"mensagem_whatsapp": mensagem}
        if json_path.exists():
            try:
                existing = json.loads(json_path.read_text(encoding="utf-8"))
                existing["mensagem_whatsapp"] = mensagem
                json_data = existing
            except Exception:
                pass
        json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")

    except Exception as e:
        print(f"  ERRO GPT-5: {e}")
        erros += 1

print(f"\n{'='*60}")
print(f"CONCLUIDO: {sucesso} mensagens geradas | {erros} erros | {len(leads)} total")
print(f"{'='*60}")
