# Gerar PDF — Contabilistas

Guia passo a passo para gerar um PDF de diagnostico para leads do nicho de contabilidade.

---

## Pré-requisitos

- venv activado: `source venv/bin/activate`
- `.env` configurado com: `GOOGLE_MAPS_API_KEY`, `APIFY_API_TOKEN`, `OPENAI_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_SHEETS_ID`
- Playwright instalado: `playwright install chromium`
- Lead ja raspado no Sheets (Fase A concluida)

## Ficheiros envolvidos

| Ficheiro | Papel |
|----------|-------|
| `crm/sheets.py` | Buscar dados do lead no Google Sheets |
| `scraper/website.py` | Analise do site com Playwright (22 campos) |
| `scraper/instagram.py` | Scraping do perfil Instagram via Apify |
| `scraper/google_reviews.py` | Scraping de reviews do Google Maps via Apify |
| `pdf/html_generator.py` | Orquestra a analise do Nuno + injeccao no template + conversao PDF |
| `pdf/templates/contabilidade.html` | Template HTML do PDF (15+ paginas, CSS counters, branding PercepTudo) |
| `analyst-prompt-contabilidade.md` | System prompt do analista "Nuno" (identidade, contexto do sector, instrucoes, formato de output) |
| `ai/prompts/analyst_contabilidade.md` | Copia do prompt do Nuno usada em runtime pelo `html_generator.py` |

---

## Fluxo completo (4 fases)

### Fase 1 — Buscar lead do Sheets

O Sheets tem os dados basicos do lead: Nome, Telefone, Cidade, Sector, Rating, Reviews, Instagram, Website, Estado.

```python
from crm.sheets import _get_worksheet_leads

ws = _get_worksheet_leads()
headers = ws.row_values(1)
row = ws.row_values(NUMERO_DA_LINHA)  # ex: 2 para primeira linha de dados

lead_raw = {}
for h, v in zip(headers, row):
    lead_raw[h] = v
```

**Mapear keys para lowercase** (o `generate_niche_pdf` espera keys em minusculas):

```python
lead = {
    "nome": lead_raw.get("Nome", ""),
    "telefone": lead_raw.get("Telefone", ""),
    "cidade": lead_raw.get("Cidade", ""),
    "sector": lead_raw.get("Sector", ""),
    "rating": lead_raw.get("Rating", ""),
    "reviews": lead_raw.get("Reviews", ""),
    "instagram_url": lead_raw.get("Instagram", ""),
    "website": lead_raw.get("Website", ""),
    "slug": lead_raw.get("Nome", "").lower().replace(" ", "-"),
}
```

### Fase 2 — Obter `place_id` via Google Maps API

O `place_id` e necessario para raspar reviews. Nao esta no Sheets.

```python
import googlemaps
gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))

response = gmaps.places(
    query=f"{lead['nome']} {lead['sector']} {lead['cidade']}",
    language="pt", region="pt"
)
results = response.get("results", [])
if results:
    lead["place_id"] = results[0]["place_id"]
    lead["morada"] = results[0].get("formatted_address", "")
```

### Fase 3 — Enriquecer o lead (3 fontes)

**CRITICO:** Nunca gerar PDF sem enriquecer primeiro. Sem dados, o Nuno gera dores genericas/incorrectas.

#### 3.1 — Website (Playwright)

Extrai 22 campos: redes sociais, contactos, features do site, CMS, design score.

```python
from scraper.website import analyze_websites
import asyncio

enriched = asyncio.run(analyze_websites([lead]))
lead = enriched[0]
```

**Campos extraidos:**
- Redes sociais: `instagram_url`, `facebook_url`, `linkedin_url`, `youtube_url`, `tiktok_url`, `twitter_url`
- Contactos: `phone_on_site`, `whatsapp_phone`, `email_on_site`
- Features: `has_chat`, `has_form`, `has_ecommerce`, `has_blog`, `has_login`, `has_newsletter`, `has_video`, `has_testimonials`, `has_cookie_consent`, `has_https`, `has_multilang`
- Tecnologia: `cms_platform`, `design_score`

#### 3.2 — Instagram (Apify)

Raspa perfil via `apify/instagram-profile-scraper`. Se nao tiver link IG, tenta adivinhar username pelo dominio (ate 5 tentativas).

```python
from scraper.instagram import scrape_instagram_profiles

enriched = scrape_instagram_profiles([lead])
lead = enriched[0]
```

**Campos extraidos:** `instagram_followers`, `instagram_posts`, `instagram_engagement`, `instagram_last_post`

#### 3.3 — Google Reviews (Apify)

Raspa reviews via `compass/google-maps-reviews-scraper`. Precisa de `place_id`.

```python
from scraper.google_reviews import enrich_lead_with_reviews

lead = enrich_lead_with_reviews(lead, max_reviews=30)
```

**Campos extraidos:**
- `reviews_text`: lista de dicts com texto, rating, data, autor, resposta_dono
- `reviews_negativas`: textos de reviews com rating <= 3
- `reviews_positivas`: textos de reviews com rating >= 4
- `total_reviews_scraped`: total

**Nota:** A lingua do actor tem de ser `pt-PT` (nao `pt`).

### Fase 4 — Gerar PDF

```python
from pdf.html_generator import generate_niche_pdf

pdf_path = generate_niche_pdf(lead)
# Output: output/leads/{slug}/diagnostico.pdf
# Relatorio: output/leads/{slug}/relatorio_analise.md
# JSON: output/leads/{slug}/analise.json (dores, mensagem_whatsapp, oportunidades)
# Sheets: actualiza automaticamente Estado -> pronto_para_envio, Link PDF, Mensagem WhatsApp
```

**O que acontece internamente:**

1. **Carrega template** — `pdf/templates/contabilidade.html` (mapeado via `NICHE_TEMPLATES` para termos: contabilidade, contabilista, contabilistas, gabinete de contabilidade, escritorio de contabilidade)

2. **Carrega prompt do Nuno** — `ai/prompts/analyst_contabilidade.md` (mapeado via `ANALYST_PROMPTS`)

3. **Chama GPT-5** com:
   - System: prompt do Nuno + instrucoes JSON (`DORES_JSON_INSTRUCTIONS`)
   - User: todos os dados enriquecidos do lead (via `_build_lead_info`)

4. **GPT-5 retorna:**
   - Relatorio markdown (guardado em `relatorio_analise.md`)
   - JSON entre `%%JSON_START%%` e `%%JSON_END%%` com:
     - `analise_website` (titulo, stats, texto, recomendacao)
     - `analise_instagram` (titulo, seguidores, posts, engagement, texto, reco)
     - `analise_reviews` (titulo, rating, total, texto, reco)
     - `oportunidades` (3-5, com badges "Accao imediata" / "Proximo passo")
     - `dores_cliente` (2-3 dores ESPECIFICAS do negocio, nao do sector)
     - `mensagem_whatsapp` (personalizada, max 4 linhas)

5. **Injecta no template** (`_inject_all`):
   - Substitui `{NOME_EMPRESA}` pelo nome do lead
   - Preenche paginas de analise (website, IG, reviews)
   - Gera HTML das paginas de dor (icone, stat hero, paragrafos, solucao)
   - Injecta badges de oportunidades
   - Adiciona linhas a tabela Mapeamento Dor → Solucao

6. **Playwright converte HTML → PDF** (A4, sem margens, print_background=True)

7. **Guarda JSON** — `output/leads/{slug}/analise.json` (dores, mensagem_whatsapp, oportunidades, blocos de analise)

8. **Actualiza Google Sheets** — Estado → `pronto_para_envio`, Link PDF, Mensagem WhatsApp

---

## Template HTML — contabilidade.html

**Localizacao:** `pdf/templates/contabilidade.html`

### Paginas do template

| # | Pagina | Conteudo |
|---|--------|----------|
| 1 | Capa (dark) | Nome da empresa (com overflow protection) |
| 2 | Contexto do sector | Stats do mercado de contabilidade PT |
| 3 | Dor #1 fixa | Tarefas repetitivas (800h/ano em lancamentos) |
| 4 | Dor #2 fixa | Escassez de talento (84% nao conseguem contratar) |
| 5 | Dor #3 fixa | Multas da AT e documentos perdidos |
| 6 | Analise personalizada | Website + Instagram + Google Reviews (preenchido pelo Nuno) |
| 7 | Google Reviews | Rating, total, barra de progresso (preenchido pelo Nuno) |
| 8-10 | Dores do cliente | 2-3 dores ESPECIFICAS geradas pelo Nuno |
| 11 | Oportunidades | Badges "Accao imediata" / "Proximo passo" |
| 12 | Como funciona | Timeline 4 semanas |
| 13 | Mapeamento | Tabela Dor → Solucao → Resultado |
| 14 | Comparacao | SEM IA vs COM PERCEP TUDO |
| 15 | CTA | Agendar diagnostico gratuito |

### Placeholders do template

**Analise Website:**
`{ANALISE_WEBSITE_TITULO}`, `{ANALISE_WEBSITE_BG}`, `{ANALISE_WEBSITE_COR}`, `{ANALISE_WEBSITE_STAT1}`, `{ANALISE_WEBSITE_LABEL1}`, `{ANALISE_WEBSITE_STAT2}`, `{ANALISE_WEBSITE_LABEL2}`, `{ANALISE_WEBSITE_STAT3}`, `{ANALISE_WEBSITE_LABEL3}`, `{ANALISE_WEBSITE_TEXTO}`, `{ANALISE_WEBSITE_RECO}`

**Analise Instagram:**
`{ANALISE_IG_TITULO}`, `{ANALISE_IG_SEGUIDORES}`, `{ANALISE_IG_POSTS}`, `{ANALISE_IG_ENGAGEMENT}`, `{ANALISE_IG_TEXTO}`, `{ANALISE_IG_RECO}`

**Analise Reviews:**
`{ANALISE_REVIEWS_TITULO}`, `{ANALISE_RATING}`, `{ANALISE_TOTAL_REVIEWS}`, `{ANALISE_RATING_PCT}`, `{ANALISE_REVIEWS_TEXTO}`, `{ANALISE_REVIEWS_RECO}`

**Oportunidades:** `{ANALISE_OPORTUNIDADES}`

**Nome empresa:** `{NOME_EMPRESA}`

**Dores do cliente:** Injectadas antes do marker `<!-- ===== OPORTUNIDADES (apos todas as dores) ===== -->`

**Mapeamento:** Linhas adicionadas ao `<tbody>` da tabela de mapeamento

### CSS

- Numeracao de paginas automatica via CSS counter (`counter-reset: page` no body, `counter-increment: page` por `.page`)
- Cores PercepTudo: `--primary: #7B2FF2`, `--secondary: #F2A900`, `--accent: #00E5A0`, `--dark-bg: #1A1A2E`, `--light-bg: #F5F2ED`
- Fonts: Space Grotesk (titulos) + IBM Plex Sans (corpo)
- Print: `@media print` com margens zero e page-break por secao

---

## Analista Nuno — analyst-prompt-contabilidade.md

**Localizacao:** `analyst-prompt-contabilidade.md` (raiz) e `ai/prompts/analyst_contabilidade.md` (runtime)

### Identidade

O Nuno e um analista de negocios especializado em gabinetes de contabilidade em Portugal. Conhece:
- Ciclos fiscais, obrigacoes declarativas, softwares (PHC, Primavera, Sage, TOConline)
- SNC, SAF-T, calendário fiscal, OCC, RGPD
- Trabalha em parceria com a Percep Tudo (posiciona como parceiro, nunca agressivo)
- Tom serio mas acessivel, PT-PT, linguagem de contabilistas

### O que analisa

1. **Website**: mobile-friendly, proposta de valor, servicos, SEO, maturidade digital (basica/intermedia/avancada)
2. **Instagram**: bio, frequencia, mix de formatos, engagement (benchmark 1.5-3.5%), conteudo educativo
3. **Google Reviews**: rating (alvo >= 4.5), volume, recencia, sentimento, respostas do proprietario
4. **Diagnostico SWOT**: forcas, fraquezas, oportunidades, ameacas
5. **Recomendacoes IA**: priorizadas P1/P2/P3, com ferramentas reais (Luppa IA, PHC CS, etc.)

### Oportunidades de automacao que conhece

| Oportunidade | Ferramentas |
|-------------|-------------|
| OCR + classificacao de documentos | PHC CS, Luppa IA, Dijit.app |
| Reconciliacao bancaria automatica | Luppa IA, Sage, Primavera |
| Validacao fiscal preventiva | Luppa IA, PHC CS |
| Chatbot/assistente para clientes | Tally, Sage Copilot, ChatGPT API |
| Processamento salarial automatico | Primavera HR, PHC CS RH, Sage HR |
| Relatorios e dossiers automaticos | Luppa IA (CFO Virtual), Power BI |
| Descodificador notificacoes AT | Luppa IA |
| Planeamento fiscal assistido por IA | Luppa IA, solucoes customizadas |
| Workflow recolha de documentos | Rauva, TOConline, Make/Zapier |
| Monitorizacao continua e alertas | Power BI, Sage Copilot, Primavera |

### Restricoes do Nuno

1. NUNCA inventa dados
2. NUNCA usa PT-BR (usa "gabinete" nao "escritorio", "gestao" nao "gerenciamento")
3. NUNCA inclui precos ou valores de investimento
4. NUNCA da aconselhamento juridico/fiscal directo
5. NUNCA deprecia software que o gabinete ja usa
6. NUNCA inventa cases ficticios
7. Posiciona Percep Tudo como parceiro, nunca obrigacao
8. Contacto: WhatsApp 910 104 835 | perceptudo@gmail.com

---

## Script completo (copiar e colar)

```python
import sys, asyncio, os
os.chdir('/Users/sirvictoroliveira007/Desktop/Projetos-Gerais/percepTudo/perceptudo-prospector')
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('.env')

import googlemaps
from crm.sheets import _get_worksheet_leads
from scraper.website import analyze_websites
from scraper.instagram import scrape_instagram_profiles
from scraper.google_reviews import enrich_lead_with_reviews
from pdf.html_generator import generate_niche_pdf

# === CONFIG ===
LINHA_SHEETS = 2  # Linha do lead no Sheets (2 = primeira linha de dados)

# === FASE 1: Buscar lead do Sheets ===
ws = _get_worksheet_leads()
headers = ws.row_values(1)
row = ws.row_values(LINHA_SHEETS)
lead_raw = dict(zip(headers, row))

lead = {
    "nome": lead_raw.get("Nome", ""),
    "telefone": lead_raw.get("Telefone", ""),
    "cidade": lead_raw.get("Cidade", ""),
    "sector": lead_raw.get("Sector", ""),
    "rating": lead_raw.get("Rating", ""),
    "reviews": lead_raw.get("Reviews", ""),
    "instagram_url": lead_raw.get("Instagram", ""),
    "website": lead_raw.get("Website", ""),
    "slug": lead_raw.get("Nome", "").lower().replace(" ", "-"),
}

print(f"Lead: {lead['nome']} | {lead['cidade']} | {lead['sector']}")

# === FASE 2: Obter place_id ===
gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
response = gmaps.places(
    query=f"{lead['nome']} {lead['sector']} {lead['cidade']}",
    language="pt", region="pt"
)
results = response.get("results", [])
if results:
    lead["place_id"] = results[0]["place_id"]
    lead["morada"] = results[0].get("formatted_address", "")
    print(f"Place ID: {lead['place_id']}")

# === FASE 3.1: Website (Playwright — 22 campos) ===
print("Fase 3.1: Website...")
lead = asyncio.run(analyze_websites([lead]))[0]

# === FASE 3.2: Instagram (Apify) ===
print("Fase 3.2: Instagram...")
lead = scrape_instagram_profiles([lead])[0]

# === FASE 3.3: Google Reviews (Apify) ===
print("Fase 3.3: Google Reviews...")
lead = enrich_lead_with_reviews(lead, max_reviews=30)
print(f"Reviews: {lead['total_reviews_scraped']} | Neg: {len(lead['reviews_negativas'])} | Pos: {len(lead['reviews_positivas'])}")

# === FASE 4: Gerar PDF ===
print("Fase 4: Gerar PDF...")
pdf_path = generate_niche_pdf(lead)
print(f"PDF gerado: {pdf_path}")
```

---

## Troubleshooting

| Problema | Causa | Solucao |
|----------|-------|---------|
| `ModuleNotFoundError` | venv nao activado | `source venv/bin/activate` |
| `AssertionError` no dotenv | Usar heredoc/stdin | Usar `load_dotenv('.env')` explicito |
| Reviews vazias | Lingua `pt` em vez de `pt-PT` | Ja corrigido em `google_reviews.py` |
| Dores genericas no PDF | Lead nao enriquecido | Correr Fases 3.1-3.3 antes da Fase 4 |
| LinkedIn "desalinhado" | Slug antigo no site | Nota no `_build_lead_info` previne isto |
| Template nao encontrado | Sector nao mapeado | Verificar `NICHE_TEMPLATES` em `html_generator.py` |
| PDF vazio/erro Playwright | Chromium nao instalado | `playwright install chromium` |
