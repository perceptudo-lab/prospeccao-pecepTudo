# CLAUDE.md — PercepTudo Prospector

## O que e este projecto

Sistema de prospeccao automatica para a PercepTudo, uma consultoria de inteligencia aplicada (IA) para PMEs em Portugal. O sistema encontra empresas, gera um PDF de diagnostico fixo por nicho, envia por WhatsApp com mensagem personalizada, e um agente especialista atende as respostas.

**Fluxo em tres fases:**

1. **Raspagem** (barata) — Victor corre `python main.py scrape --nicho X --cidade Y`. Raspa Google Maps, enriquece com dados do site e Instagram, grava no Sheets com estado "novo". Sem gastar OpenAI.

2. **Geracao de PDF** (barata, sem IA) — `python main.py gerar --nicho X --cidade Y`. Template HTML fixo por nicho, so substitui {NOME_EMPRESA}, {WEBSITE}, {INSTAGRAM}. Playwright converte para PDF.

3. **Envio + Atendimento** (automatico) — `python main.py enviar-dia`. Scheduler envia mensagens (GPT-5 gera variacao) + PDF na janela 9-13h, max 80/dia. Agente especialista (Rui/Nuno) responde 24/7 quando o lead responde.

## Stack

- **Python 3.11+** — linguagem principal
- **Google Maps Places API** — pesquisa de empresas
- **Apify** (plano gratis $5/mes) — scraping de Instagram + Google Reviews
- **Playwright** — analise de websites + conversao HTML→PDF
- **OpenAI GPT-5** — geracao de mensagens WhatsApp + agente atendente
- **Flask** — webhook server para receber mensagens WhatsApp
- **Evolution API** — envio/recepcao WhatsApp (VPS Easypanel)
- **Google Sheets API** — CRM (source of truth)
- **Docker + Easypanel** — deploy na VPS

## Estrutura do projecto

```
perceptudo-prospector/
├── CLAUDE.md                    # Este ficheiro
├── PROGRESSO.md                 # Historico de progresso
├── Dockerfile                   # Build para Easypanel
├── docker-compose.yml           # Agente 24/7 + scheduler cron
├── .env                         # API keys (NAO commitar)
├── requirements.txt             # Dependencias Python
├── main.py                      # CLI: scrape, gerar, enviar, enviar-dia, agente, status
│
├── scraper/
│   ├── utils.py                 # Normalizar telefone, validar mobile PT, slug, logger
│   ├── google_maps.py           # Pesquisa empresas por nicho + cidade
│   ├── website.py               # Playwright: analise completa do site (22 campos)
│   ├── instagram.py             # Apify: raspa perfil IG + fallback por nome
│   ├── google_reviews.py        # Apify: raspa reviews do Google Maps
│   └── enrichment.py            # Combina fontes, recupera telefone do site/WhatsApp
│
├── agentes/
│   ├── atendente.py             # Motor do agente: SPIN, JSON, split msgs, escalacao
│   ├── oficinas/
│   │   └── system_prompt.md     # Agente Rui — especialista oficinas (378+ linhas)
│   └── contabilidade/
│       ├── personalidade.md     # Agente Nuno — tom e vocabulario (formato antigo)
│       ├── conhecimento.md      # Servicos PercepTudo para contabilidade
│       └── objecoes.md          # Objecoes comuns + respostas
│
├── pdf/
│   ├── html_generator.py        # Template fixo → {NOME_EMPRESA} → Playwright → PDF
│   ├── orchestrator.py          # Batch: busca Sheets → gera PDFs → actualiza estado
│   └── templates/
│       └── contabilidade.html   # Template contabilidade (9 paginas)
│
├── whatsapp/
│   ├── sender.py                # Envia texto + PDF via Evolution API
│   ├── message_generator.py     # GPT-5 gera mensagens variadas (fallback generico)
│   ├── scheduler.py             # Envio diario: janela 9-13h, follow-ups, pausas
│   ├── followup.py              # Logica de follow-up (4 toques: dia 0, 3, 7, 14)
│   └── webhook.py               # Flask server: recebe msgs, buffer 15s, agente responde
│
├── crm/
│   └── sheets.py                # Google Sheets: CRUD leads + termos + follow-up queries
│
├── ai/
│   ├── assistant.py             # DEPRECATED — analise generica (substituido por agentes)
│   └── prompts/                 # DEPRECATED — benchmarks por sector
│
└── output/
    ├── leads/{slug}/diagnostico.pdf    # PDFs gerados
    └── conversas/{phone}.json          # Historico de conversas (estado v2)
```

## Pipeline — como tudo funciona

### Fase A: Raspagem (main.py scrape)

```
python main.py scrape --nicho "oficinas" --cidade "Lisboa"
     |
     v
Google Maps → Enrichment (website 22 campos + IG + reviews) → Sheets (estado "novo")
```

### Fase B: Geracao de PDF (main.py gerar)

```
python main.py gerar --nicho "oficinas" --cidade "Lisboa"
     |
     v
Template HTML fixo → substitui {NOME_EMPRESA}, {WEBSITE}, {INSTAGRAM} → Playwright → PDF
     |
     v
Sheets: estado "pronto_para_envio", link_pdf preenchido
```

### Fase C: Envio + Atendimento

```
python main.py enviar-dia
     |
     v
Scheduler (janela 9-13h, max 80/dia, intervalos 3-7min):
  - Se nicho tem agente especialista → Rui/Nuno gera outreach
  - Se nao → message_generator generico
  - Touch 1: mensagem + PDF
  - Follow-ups: dia 3, 7, 14 (so texto)
     |
     v
python main.py agente --port 80      (corre 24/7 na VPS)
     |
     v
Lead responde no WhatsApp → webhook (buffer 15s) → agente especialista:
  - Mensagens curtas quebradas (2-3 msgs com delay 1-2.5s)
  - Metodo SPIN: situacao → problema → implicacao → solucao
  - Escalacao inteligente: price_2x, irritated, high_value, complaint, etc
  - Notifica Victor (351934215049) quando escalar
  - Estado "agendado" → agente para de responder
```

## Agentes Especialistas

Cada nicho tem um agente com personalidade e conhecimento proprio.
O system prompt COMPLETO esta em `agentes/{nicho}/system_prompt.md`.

### Agente Rui (oficinas) — ACTIVO
- Especialista em oficinas de automoveis
- Conhece: baias, folhas de obra, temparios, PHC, ANECRA
- Metodo SPIN adaptado a oficinas
- Sabe o que esta no PDF (4 dores + solucoes)
- Escalacao com gatilhos especificos (preco 2x, alto valor >3 baias, etc)

### Agente Nuno (contabilidade) — POR MIGRAR
- Tem knowledge base em 3 ficheiros (formato antigo, funcional)
- Precisa de system_prompt.md completo como o Rui

### Aliases de nicho
| Termos no Sheets | Agente | Template PDF |
|-----------------|--------|-------------|
| oficinas, oficina, oficina de automoveis, mecanica, auto | Rui | oficinas.html |
| contabilidade, contabilista, contabilistas, gabinete de contabilidade | Nuno | contabilidade.html |

## Estado de Conversa (v2)

Historico guardado em `output/conversas/{phone}.json`:
```json
{
  "version": 2,
  "phone": "351912345678",
  "nome": "AutoTop Oficina",
  "nicho": "oficinas",
  "stage": "problema",
  "price_ask_count": 1,
  "last_activity": "2026-03-29T17:00:00",
  "lead_data": {"cidade": "Lisboa", "rating": "4.3", "website": "..."},
  "messages": [{"role": "user/assistant", "content": "...", "timestamp": "..."}]
}
```

SPIN stages: outreach → situacao → problema → implicacao → solucao → fecho → escalado | frio

## Google Sheets (CRM)

### Colunas (19)
Nome | Telefone | Cidade | Sector | Rating | Reviews | Instagram | Website | Score | Estado | Data Contacto | Link PDF | Follow-up 1 | Follow-up 2 | Notas | Mensagem WhatsApp | Follow-up 3 | Proximo Follow-up | Touch Actual

### Estados possiveis
novo → pronto_para_envio → contactado → followup_1 → followup_2 → followup_3 → frio
                                       → respondeu (agente atende)
                                       → agendado (Victor trata, agente para)
                                       → removido (opt-out)

## Scheduler — Envio diario

- Janela: 09:00-13:00 (configuravel via .env)
- Limite: 80 msgs/dia
- Intervalos: 3-7 min aleatorios entre mensagens
- Pausa: 15-30 min a cada 10 mensagens
- Prioridade: follow-ups primeiro, depois novos leads
- Validacao WhatsApp antes de enviar (check_is_whatsapp)
- Follow-ups: touch 2 (dia 3), touch 3 (dia 7), touch 4 (dia 14) → frio
- PDF so no touch 1; touches 2-4 so texto

## Deploy (Easypanel)

### VPS: 64.227.125.178
- **Servico agente**: Docker, porta 80, always running (24/7)
- **Dominio**: https://perceptudo-agente.6mfvzj.easypanel.host
- **Webhook Evolution API**: https://perceptudo-agente.6mfvzj.easypanel.host/webhook/messages
- **Health check**: https://perceptudo-agente.6mfvzj.easypanel.host/health
- **GitHub**: https://github.com/perceptudo-lab/prospeccao-pecepTudo (privado)
- **Scheduler**: corre localmente (`python main.py enviar-dia`) ou via cron na VPS

### Variaveis de ambiente na VPS
Todas as do .env + GOOGLE_SERVICE_ACCOUNT_DATA (JSON inline em vez de ficheiro)

## Comandos uteis

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && playwright install chromium

# Fase A — Raspagem
python main.py scrape --nicho "oficinas" --cidade "Lisboa"

# Fase B — Gerar PDFs
python main.py gerar --nicho "oficinas" --cidade "Lisboa"

# Fase C — Enviar (producao)
python main.py enviar-dia              # envia novos + follow-ups na janela 9-13h
python main.py enviar-dia --dry-run    # simula sem enviar (max 3-5 leads!)

# Agente atendente (local)
python main.py agente --debug          # hot reload
python main.py agente --port 5001      # producao local

# Status
python main.py status
python main.py status --nicho "oficinas" --cidade "Lisboa"

# Envio legacy (backwards compat)
python main.py enviar [--nicho X] [--cidade Y]
```

## Regras para o Claude Code

- Escreve codigo limpo com docstrings e type hints
- Trata TODOS os erros com try/except (especialmente APIs externas)
- Loga tudo (cada lead processado, cada envio, cada erro)
- Nunca hardcoda API keys — usa .env
- Se uma API falhar, nao crash — loga o erro e passa ao proximo lead
- Sem telemovel = lead descartado ANTES de gastar APIs
- O Sheets e a source of truth — tudo actualiza la
- O PDF usa template fixo — so {NOME_EMPRESA}, {WEBSITE}, {INSTAGRAM}
- Dry-runs e testes: MAXIMO 3-5 leads (nunca batch inteiro!)
- System prompt do agente = ficheiro unico `system_prompt.md` por nicho
- Mensagens WhatsApp do agente: max 3 frases por msg, quebradas com delay

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

## Contexto adicional

- O Victor esta em Portugal (Lisboa)
- A PercepTudo foca em PMEs (10-200 funcionarios)
- NAO vende chatbots — vende consultoria de IA (diagnostico + implementacao)
- O Victor trata pessoalmente todas as reunioes (agente escala para ele)
- Contacto: perceptudo@gmail.com | +351 910 104 835 | perceptudo.vercel.app
- Victor WhatsApp pessoal (alertas): +351 934 215 049
