# CLAUDE.md — PercepTudo Prospector

## O que e este projecto

Sistema de prospeccao automatica para a PercepTudo, uma consultoria de inteligencia aplicada (IA) para PMEs em Portugal. O sistema encontra empresas, analisa o negocio com IA, gera um PDF de diagnostico personalizado, e envia por WhatsApp.

**Fluxo em duas fases (o Victor controla tudo):**

1. **Raspagem** (barata) — Victor corre `python main.py --nicho X --cidade Y` quantas vezes quiser. Raspa Google Maps, enriquece com dados do site e Instagram, grava no Sheets com estado "novo". Sem gastar OpenAI.

2. **Geracao + Envio** (manual) — Victor pede no terminal: "Gera PDFs e envia para os contabilistas de Leiria". Claude Code busca do Sheets, gera analise AI + PDF, envia WhatsApp. Victor decide quando e para quem.

## Stack

- **Python 3.11+** — linguagem principal
- **Google Maps Places API** — pesquisa de empresas
- **Apify** (plano gratis $5/mes) — scraping de Instagram
- **Playwright** — analise automatica de websites + conversao HTML→PDF
- **OpenAI GPT-5** (Chat Completions API) — analise de negocio + diagnostico
- **reportlab** (Python) — geracao de PDF generico (nichos sem template HTML)
- **Evolution API** — envio WhatsApp (VPS Easypanel)
- **Google Sheets API** — CRM (source of truth)

## Estrutura do projecto

```
perceptudo-prospector/
├── CLAUDE.md                    # Este ficheiro
├── PROGRESSO.md                 # Historico de progresso
├── .env                         # API keys (NAO commitar)
├── requirements.txt             # Dependencias Python
├── main.py                      # CLI principal: scrape, gerar, enviar, status
│
├── scraper/
│   ├── __init__.py
│   ├── utils.py                 # Normalizar telefone, validar mobile PT, slug, logger
│   ├── google_maps.py           # Pesquisa empresas por nicho + cidade
│   ├── website.py               # Playwright: analise completa do site (22 campos)
│   ├── instagram.py             # Apify: raspa perfil IG + fallback por nome
│   ├── instagram_search.py      # PAUSADO — pesquisa IG por keywords (nao funcional)
│   └── enrichment.py            # Combina fontes, recupera telefone do site/WhatsApp
│
├── ai/
│   ├── __init__.py
│   ├── assistant.py             # Analise generica com GPT-5
│   └── prompts/
│       ├── base.txt             # Instrucoes base do assistente
│       ├── analyst_contabilidade.md  # Analista "Nuno" — contabilidade
│       └── restauracao.txt      # Benchmarks restauracao
│
├── pdf/
│   ├── __init__.py
│   ├── generator.py             # Template generico Bold A4 (reportlab)
│   ├── html_generator.py        # Templates HTML por nicho (Playwright→PDF)
│   ├── orchestrator.py          # Orquestra: enriquecer + gerar PDF + registar no Sheets
│   └── templates/
│       └── contabilidade.html   # Template contabilidade (15+ paginas)
│
├── whatsapp/
│   ├── __init__.py
│   ├── sender.py                # Envia texto + PDF via Evolution API
│   └── scheduler.py             # Envia em batch com intervalos (2-5 min)
│
├── crm/
│   ├── __init__.py
│   └── sheets.py                # Google Sheets: CRUD leads + termos
│
├── followup/
│   ├── __init__.py
│   └── cron_followup.py         # POR FAZER — follow-ups automaticos
│
└── output/
    └── leads/                   # PDFs e relatorios por lead
        └── {slug}/
            ├── diagnostico.pdf
            └── relatorio_analise.md
```

## Pipeline — como tudo funciona

### Fase A: Raspagem (main.py)

```
python main.py --nicho "contabilistas" --cidade "Leiria"
     |
     v
[scraper/google_maps.py]
  - Pesquisa na Places API
  - Extrai: nome, telefone, rating, reviews, website, morada
  - Filtra: so telemoveis portugueses (9xx)
  - Remove leads ja no Sheets (dedup)
     |
     v
[scraper/enrichment.py]
  - Leads SEM telemovel mas COM website → tenta recuperar do site/WhatsApp
  - Sem telemovel em nenhuma fonte → DESCARTADO (nao gasta APIs)
     |
     v
[scraper/website.py] — Analise completa (22 campos)
  - Redes sociais: Instagram, Facebook, LinkedIn, YouTube, TikTok, Twitter/X
  - Contactos: telefone (links + texto visivel), email, WhatsApp (wa.me)
  - Features: chat, formulario/booking, ecommerce, blog, login/portal,
    newsletter, video, testemunhos, cookie consent, HTTPS, multi-idioma
  - Tecnologia: CMS (WordPress, Wix, Shopify, etc.), design score
     |
     v
[scraper/instagram.py]
  - Se tem link IG no site → raspa via Apify
  - Se NAO tem → fallback: adivinha username pelo dominio (ate 5 tentativas)
    Ex: watchnumber.pt → @watchnumber.pt, @watchnumber, @watchnumberpt
  - Custo fallback: ~$0.001 por tentativa
     |
     v
[crm/sheets.py]
  - Grava leads com estado "novo"
  - PARA AQUI — sem gastar OpenAI
```

### Fase B: Geracao + Envio (disparado pelo Victor no terminal)

```
Victor: "Gera PDFs e envia para os contabilistas de Leiria"
     |
     v
[Busca leads do Sheets] (nicho + cidade, estado "novo")
     |
     v
[ai/assistant.py] ou [pdf/html_generator.py]
  - Template HTML existe (ex: contabilidade) → analista Nuno + template rico
  - Template nao existe → GPT-5 generico + template reportlab
     |
     v
[pdf/] — Gera PDF A4
  - Guarda em output/leads/{slug}/diagnostico.pdf
  - Relatorio do Nuno guardado em relatorio_analise.md
     |
     v
[whatsapp/sender.py]
  - Envia mensagem + PDF via Evolution API
  - Intervalo 2-5 min entre envios
  - Actualiza Sheets: estado "contactado"
```

## Google Sheets (CRM)

### Colunas
Nome | Telefone | Cidade | Sector | Rating | Reviews | Instagram | Website | Score | Estado | Data Contacto | Link PDF | Follow-up 1 | Follow-up 2 | Notas | Mensagem WhatsApp

### Estados possiveis
novo → pronto_para_envio → contactado → followup_1 → followup_2 → frio
                                      → respondeu (Victor trata)
                                      → removido (pediu para parar)

## Scraper de Website — 22 campos

O scraper analisa cada site com Playwright e extrai:

| Categoria | Campos |
|-----------|--------|
| Redes sociais | instagram_url, facebook_url, linkedin_url, youtube_url, tiktok_url, twitter_url |
| Contactos | phone_on_site, whatsapp_phone, email_on_site |
| Features | has_chat, has_form, has_ecommerce, has_blog, has_login, has_newsletter, has_video, has_testimonials, has_cookie_consent, has_https, has_multilang |
| Tecnologia | cms_platform, design_score |

### Deteccao de telefone (3 fontes)
1. Links `<a href="tel:...">` (clicaveis)
2. Texto visivel na pagina (regex: +351 9xx, 9xx xxx xxx)
3. Links WhatsApp (`wa.me/NUMERO`, `api.whatsapp.com/send?phone=NUMERO`)

### Fallback Instagram (5 tentativas)
Quando nao ha link IG no site, tenta adivinhar pelo dominio:
1. `dominio.tld` (ex: watchnumber.pt)
2. `dominio` (ex: watchnumber)
3. `dominiotld` (ex: watchnumberpt)
4. `dominio.sector` (ex: watchnumber.contabilidade)
5. `dominio_cidade` (ex: watchnumber_lisboa)

Ignora dominios de redes sociais (linkedin, facebook, etc.) para evitar falsos positivos.

## PDF — Sistema hibrido

### Template HTML por nicho (Playwright)
- Contabilidade: `pdf/templates/contabilidade.html` + analista "Nuno"
- Outros nichos: por criar

### Template generico (reportlab)
- `pdf/generator.py` — 7 paginas Bold A4
- Usado quando nao ha template HTML para o nicho

### Paginas do template contabilidade
1. Capa (dark) — nome empresa (com overflow protection)
2. Contexto do sector — stats do mercado
3. Dor #1 fixa — Tarefas repetitivas (800h/ano)
4. Dor #2 fixa — Escassez de talento (84%)
5. Dor #3 fixa — Multas AT e documentos perdidos
6. Analise personalizada — Website + Instagram
7. Google Reviews
8-10. Dores do cliente (geradas pelo Nuno)
11. Oportunidades identificadas (badges "Acção imediata" / "Próximo passo")
12. Como funciona — timeline 4 semanas
13. Mapeamento Dor → Solução
14. Comparação SEM IA vs COM PERCEP TUDO
15. CTA — agendar diagnóstico

Numeracao de paginas automatica via CSS counter.

## Mapeamento de nichos

Varios termos podem apontar para o mesmo template/analista:

| Termos aceites | Template | Analista |
|----------------|----------|----------|
| contabilidade, contabilista, contabilistas, gabinete de contabilidade, escritorio de contabilidade | contabilidade.html | analyst_contabilidade.md |

## Branding PercepTudo

### Cores
- Percep Purple: #7B2FF2 (primary)
- Spark Amber: #F2A900 (secondary)
- Signal Green: #00E5A0 (accent)
- Cloud Warm: #F5F2ED (background)
- Deep Graphite: #1A1A2E (text)

### Tom de voz
- Provocador Confiante — fala como especialista no cafe, nao em palestra
- USAR: inteligencia aplicada, resultado mensuravel, processo otimizado
- EVITAR: solucoes inovadoras, machine learning, cutting-edge, jargao tech

## Comandos uteis

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Fase A — Raspagem
python main.py scrape --nicho "contabilistas" --cidade "Leiria"
python main.py scrape --nicho "restaurantes" --cidade "Porto"

# Fase B.1 — Gerar PDFs (ficam com estado 'pronto_para_envio')
python main.py gerar --nicho "contabilistas" --cidade "Leiria"

# Fase B.2 — Enviar por WhatsApp (dias depois, quando quiser)
python main.py enviar                                              # todos os pendentes
python main.py enviar --nicho "contabilistas" --cidade "Leiria"    # so os de Leiria

# Ver estado dos leads
python main.py status
python main.py status --nicho "contabilistas" --cidade "Leiria"

# Backwards compat (assume 'scrape')
python main.py --nicho "contabilistas" --cidade "Leiria"
```

## Regras para o Claude Code

- Escreve codigo limpo com docstrings e type hints
- Trata TODOS os erros com try/except (especialmente APIs externas)
- Loga tudo (cada lead processado, cada envio, cada erro)
- Nunca hardcoda API keys — usa .env
- Se uma API falhar, nao crash — loga o erro e passa ao proximo lead
- Sem telemovel = lead descartado ANTES de gastar APIs (OpenAI, Apify)
- O Sheets e a source of truth — tudo actualiza la
- Os valores de ROI no JSON nunca devem conter "EUR" ou "€"
- O PDF usa Helvetica/Helvetica-Bold (nao instalar fontes custom)

## Contexto adicional

- O Victor esta em Portugal (Lisboa)
- A PercepTudo foca em PMEs (10-200 funcionarios)
- NAO vende chatbots — vende consultoria de IA (diagnostico + implementacao)
- O PDF tem simulacao de ROI (nao prova social / casos de uso)
- O Victor trata pessoalmente todas as respostas (sem bot de atendimento)
- Contacto PDF: perceptudo@gmail.com | +351 910 104 835 | perceptudo.vercel.app
