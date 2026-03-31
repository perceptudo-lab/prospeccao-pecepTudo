# PercepTudo Prospector — Progresso

## Sessao 1: 27-28 Marco 2026

### O que foi construido

Fases 1-5 completas: Scraper, AI, PDF, WhatsApp, Orquestracao.

### Bugs corrigidos (14)

1. Headers duplicados no Sheets
2. GPT-5 nao suporta Assistants API → Chat Completions API
3. GPT-5 nao suporta temperature → removido
4. ROI inflacionado → estimativa de tamanho no prompt
5. Telefone como int no WhatsApp sender → `str(phone)`
6. Telefone nao encontrado no Sheets → fallback 3 formatos
7. PDF base64 rejeitado pela Evolution API → base64 puro
8. Leads gravados sem headers → Sheets com `RAW`
9. **CRITICO:** Scheduler enviava para TODOS os leads → corrigido: so corrida actual
10. **CRITICO:** Paths relativos nos PDFs → paths absolutos
11. Lead sem PDF nao marcado como erro → estado "erro_pdf"
12. Logs duplicados → removido `logging.basicConfig()`
13. Import morto (`search_instagram`) → removido
14. Simbolos unicode feios no PDF → `_clean_text()` + instrucao no prompt

### Termos de teste gastos (Sheets limpo — todos reutilizaveis)

| Termo | Cidade | Leads | Notas |
|-------|--------|-------|-------|
| taxidermistas | Braganca | 0 | Sem resultados |
| papelarias | Beja | 4 | Primeiro teste |
| ferragens | Evora | 4 | Segundo teste |
| talhos | Portalegre | 8 | Primeiro envio WhatsApp real |
| lojas de tapetes | Vila Real | 14 | Teste completo |
| relojoarias | Mirandela | 2 | Primeiro teste pos-bugfix |

---

## Sessao 2: 28 Marco 2026

### Revisao dos PDFs de contabilidade Lisboa

Revisamos visualmente os 3 PDFs gerados na sessao anterior (Contar Mais, Value Advantage, Watchnumber). Problemas encontrados e corrigidos:

### Correcoes no Scraper (website.py)

| Problema | Causa | Correcao |
|----------|-------|----------|
| Chat/WhatsApp nao detectado (Watchnumber) | CHAT_PATTERNS nao tinha "zaask", "wix chat", "whatsapp" | Adicionados 10+ patterns + fallback por iframes de chat |
| Formulario/agendamento nao detectado (Contar Mais) | So detectava `<form>` HTML, nao CTAs de booking | Adicionada deteccao de botoes "Agendar"/"Marcar" + plataformas (Calendly, etc.) |
| Blog nao detectado (Value Advantage) | So procurava "/blog" e "Blog" | Adicionados "Insights", "Recursos", "Novidades", "Conhecimento", etc. |
| Login/portal nao detectado | Nao existia | Nova funcao `_detect_login()` |
| Instagram nao encontrado (Watchnumber) | So procurava link IG no site | Fallback: adivinha username pelo dominio (5 tentativas via Apify) |
| Telefone em texto nao extraido | So procurava `<a href="tel:">` | Regex em texto visivel + links WhatsApp (wa.me) |
| Facebook/LinkedIn do Wix (nao da empresa) | Site Wix tem links do template | Bug do site, nao do scraper |

### Scraper expandido de 8 para 22 campos

**Novos campos:**
- Redes sociais: linkedin_url, youtube_url, tiktok_url, twitter_url
- Contactos: phone_on_site (texto + links), whatsapp_phone (wa.me), email_on_site
- Features: has_blog, has_login, has_newsletter, has_video, has_testimonials, has_cookie_consent, has_https, has_multilang
- Tecnologia: cms_platform (WordPress, Wix, Shopify, etc.)

### Correcoes no Instagram (instagram.py)

- Refactored: `_parse_profile_data()` reutilizavel
- Novo: `_guess_usernames()` — gera ate 5 candidatos por dominio/nome
- Novo: `_try_scrape_username()` — valida candidato via Apify (~$0.001/tentativa)
- Fix: ignora dominios de redes sociais (evita encontrar @linkedin como IG)
- Fix: filtra usernames demasiado curtos/longos

### Correcoes no Template PDF (contabilidade.html)

| Problema | Correcao |
|----------|----------|
| Nome da empresa saia fora da pagina | Removido `white-space: nowrap`, adicionado `overflow-wrap: break-word` |
| Numeracao de paginas errada/duplicada | Substituidos numeros hardcoded por CSS counter automatico |
| Caixa "6 servicos" causava pagina vazia | Compactada (font-size, padding, gap reduzidos) |
| Badges "Accao imediata" sem acentos | Corrigido para "Acção imediata" / "Próximo passo" |
| Oportunidades apareciam antes das dores | Movidas para depois de TODAS as dores (fixas + Nuno) |

### Correcoes no html_generator.py

- Acentos nos badges corrigidos no prompt e no default
- Mapeamento de nichos expandido: "contabilista", "gabinete de contabilidade", "escritorio de contabilidade" → template contabilidade
- Dores injectadas antes das oportunidades (novo marker no template)
- Page numbers dinamicos (sem hardcode)

### Correcoes no Pipeline (enrichment.py + main.py)

- **Leads sem telemovel descartados ANTES de gastar APIs** (Playwright, Apify, OpenAI)
- Leads sem telemovel no Google Maps mas COM website → tenta recuperar do site/WhatsApp
- Dedup movido para antes do enriquecimento

### Nova arquitectura: Scrape separado de Geracao

**Antes:** `main.py` fazia tudo (scrape → AI → PDF → WhatsApp) de uma vez.

**Agora:**
- `main.py` so faz **scrape + enriquecer + Sheets** (barato)
- Geracao de PDFs e envio WhatsApp sao **disparados manualmente** pelo Victor no terminal via Claude Code
- Victor controla quando e para quem gera/envia

```bash
# Fase A: Raspar (quantas vezes quiser)
python main.py --nicho "contabilistas" --cidade "Leiria"
python main.py --nicho "restaurantes" --cidade "Porto"

# Fase B: Gerar + Enviar (quando o Victor decidir)
# Victor pede no terminal: "Gera PDFs para os contabilistas de Leiria"
```

### Dados enviados ao AI (assistant.py + html_generator.py)

Os 22 campos do scraper + dados do Google Maps sao enviados ao GPT-5/Nuno:
- Redes sociais (6), contactos (3), features do site (11), tecnologia (2)
- Instagram metricas (4), Google Maps (rating, reviews, morada)

### Testes Leiria (28 Marco 2026)

| Lead | Telemovel | Website | IG | CMS | PDF |
|------|-----------|---------|-----|-----|-----|
| Susana Urbano & Fernandes | +351918467675 | su-f.pt (offline) | Nao | - | Gerado |
| Jonasconta, Lda | +351916399624 | Sem site | Nao | - | Gerado |
| C+R Contabilidade | +351911191191 | cmaisrcontabilidade.pt (offline) | @cmaisrcontabilidade (161 seg) | WordPress | Gerado |

**Nota:** Sites su-f.pt e cmaisrcontabilidade.pt estavam offline durante o teste.

---

---

## Sessao 3: 29 Marco 2026

### Geracao em batch — 20 PDFs contabilidade Lisboa

Primeiro batch de producao real: 20 gabinetes de contabilidade em Lisboa (sectores: contabilistas, gabinete de contabilidade).

**Pipeline executado:**
1. Buscar 20 leads do Sheets (filtro por sector + cidade)
2. Obter `place_id` via Google Maps API (20/20)
3. Enriquecer websites com Playwright — 22 campos (20/20, 4 sem website)
4. Raspar Instagram via Apify (20/20, fallback username ate 5 tentativas)
5. Raspar Google Reviews via Apify (20/20, lingua pt-PT)
6. Gerar PDFs com analista Nuno + template contabilidade (20/20, 0 erros)
7. Actualizar Sheets: estado, link PDF, mensagem WhatsApp (20/20)

**Resultado: 20 PDFs gerados, 0 erros.**

| # | Empresa | Website | IG | Reviews | PDF |
|---|---------|---------|-----|---------|-----|
| 1 | Fiscal360 | fiscal360.pt | @fiscal360.pt (196 seg) | 27 | OK |
| 2 | Contar Mais | contarmais.pt | @contarmaispt | 15 | OK |
| 3 | Eugest | eugest.pt | @eugest (fallback) | sim | OK |
| 4 | Joao Luis de Deus | sem site | @joaoluisdedeus (fallback) | sim | OK |
| 5 | Value Advantage | valueadvantage.pt | sem IG | sim | OK |
| 6 | Deeper Contabilidade | deeper.pt | @deeper.pt (fallback) | sim | OK |
| 7 | BMGEST | bmgest.pt | @bmgest (57 seg) | sim | OK |
| 8 | Assoc. Portuguesa Contabilistas | apc.pt | @apc (fallback, 3417 seg) | sim | OK |
| 9 | RB Contabilidade | sites.google.com | @sites (fallback) | sim | OK |
| 10 | HVR Business Consulting | hvrbusinessconsulting.com | @hvrbusinessconsulting | sim | OK |
| 11 | Three Stars Consulting | sem site | sem IG | sim | OK |
| 12 | PRC Gestao Global | prcgestaoglobal.pt | @prcgestaoglobal.pt (fallback) | sim | OK |
| 13 | ROY&CO Business Consultant | sem site | sem IG | sim | OK |
| 14 | VM Gabinete de Contabilidade | sem site | sem IG | sim | OK |
| 15 | 464 Contabilidade | facebook.com | @464contabilidade (fallback) | sim | OK |
| 16 | EPGest | facebook.com | @epgest (fallback) | sim | OK |
| 17 | Gesticonta | welinkaccountants.pt (offline) | sem IG | sim | OK |
| 18 | Nymalis | nymalis.com | sem IG | sim | OK |
| 19 | Isabel Ayala | facebook.com | sem IG | sim | OK |
| 20 | Liliana Machado | lm-contabilidade.pt | sem IG | sim | OK |

**Tempo total:** ~60 min (websites ~8 min, Instagram ~11 min, reviews ~5 min, PDFs ~37 min)

**Nota:** A API do GPT-5 ficou lenta num lead (Value Advantage demorou ~11 min em vez de ~1 min), mas respondeu e o script continuou sem erros.

### Correcoes no html_generator.py

| Problema | Correcao |
|----------|----------|
| JSON da analise (dores, mensagem WhatsApp, oportunidades) nao era guardado em disco | Adicionado: guarda `analise.json` em `output/leads/{slug}/` apos gerar |
| Sheets nao era actualizado apos gerar PDF | Adicionado: `generate_niche_pdf` actualiza automaticamente Estado → `pronto_para_envio`, Link PDF, Mensagem WhatsApp |
| Mensagem WhatsApp perdia-se (so existia em memoria) | Corrigido: guardada no `analise.json` + preenchida no Sheets |

### Formatacao do Google Sheets

Aplicada formatacao visual ao Sheets:
- Header: fundo escuro (#1A1A2E), texto branco bold, congelado
- Linhas alternadas (branco / bege #F5F2ED)
- Borda roxa (#7B2FF2) no header
- Colunas com larguras ajustadas ao conteudo
- Nome em bold, Rating/Reviews/Score centrados, Estado centrado e bold

---

---

## Sessao 4: 29 Marco 2026 (tarde)

### Overhaul completo do sistema

Reestruturacao major do sistema inteiro. Objectivo: simplificar PDF (sem IA), scheduler com follow-ups, agente atendente especialista por nicho.

### Decisoes de negocio tomadas nesta sessao

- **PDF simplificado**: templates fixos por nicho, so {NOME_EMPRESA}/{WEBSITE}/{INSTAGRAM}. Zero GPT-5 na geracao.
- **Meta diaria**: ~80 mensagens/dia, janela 9:00-13:00
- **Follow-ups**: 4 toques (dia 0, 3, 7, 14) → frio
- **3 numeros WhatsApp** para chegar a 100/dia (futuro, nao implementado ainda)
- **Agentes especialistas**: cada nicho tem agente proprio (Rui para oficinas, Nuno para contabilidade)
- **Agente gera outreach**: o mesmo agente que atende e quem faz a primeira mensagem
- **Escalacao para Victor**: 7 gatilhos (preco 2x, irritado, proposta formal, alto valor, etc)

### O que foi construido

#### 1. PDF simplificado
- `pdf/html_generator.py` reescrito de ~750 para ~110 linhas
- `pdf/orchestrator.py` simplificado — sem enrichment, so template + nome
- Templates so substituem {NOME_EMPRESA}, {WEBSITE}, {INSTAGRAM}
- **60 PDFs de contabilidade gerados** (linhas 2-61 do Sheets, 0 erros, ~4s cada)

#### 2. Gerador de mensagens WhatsApp
- `whatsapp/message_generator.py` — GPT-5 gera mensagens variadas (anti-spam)
- 4 variantes de touch (outreach, follow-up curto, angulo diferente, despedida)
- Dores fixas por sector em dict SECTOR_PAINS
- Opt-out automatico em todas as mensagens
- Custo: ~$0.008/mensagem

#### 3. Scheduler com follow-ups
- `whatsapp/scheduler.py` reescrito — janela 9-13h, intervalos 3-7min, pausas a cada 10 msgs
- Mix: follow-ups primeiro (mais quentes), depois novos leads
- `whatsapp/followup.py` — logica de follow-up (4 toques com intervalos)
- Modo --dry-run para simulacao

#### 4. Agente atendente avancado
- `agentes/atendente.py` reescrito completo (~400 linhas)
- Respostas GPT em JSON estruturado: messages[], stage, escalation
- Mensagens quebradas com delay 1-2.5s (parece humano)
- Metodo SPIN: outreach → situacao → problema → implicacao → solucao → fecho
- Escalacao inteligente: GPT classifica + code safety net (price_ask_count, complaint)
- Estado de conversa v2: envelope JSON com lead_data, stage, price tracking
- Buffer de 15s no webhook: junta mensagens rapidas antes de processar

#### 5. Agente Rui (oficinas)
- `agentes/oficinas/system_prompt.md` — 400+ linhas
- Personalidade: directo, pratico, especialista em oficinas
- Vocabulario: baias, folha de obra, tempario, ANECRA, PHC
- Metodo SPIN adaptado a oficinas
- Sabe o que esta no PDF (4 dores + solucoes concretas)
- Objecoes: "e caro", "nao percebo de tecnologia", "ja tentei", etc
- Exemplos de conversa completos
- Escalacao com gatilhos proprios

#### 6. Novos estados no Sheets
- Colunas adicionadas: Follow-up 3, Proximo Follow-up, Touch Actual
- Estados: followup_1, followup_2, followup_3, agendado
- Funcoes: get_leads_needing_followup(), get_leads_by_statuses()
- Suporte a credenciais Google via env var (Docker)

#### 7. Deploy na VPS (Easypanel)
- Dockerfile + docker-compose.yml
- Servico "agente" online 24/7 em https://perceptudo-agente.6mfvzj.easypanel.host
- Webhook Evolution API configurado
- GitHub: https://github.com/perceptudo-lab/prospeccao-pecepTudo

#### 8. Template contabilidade actualizado
- Copiado novo template de /Desktop/prospecting-contabilidade.html
- Removidos placeholders antigos ({SETOR}, {NOME_DECISOR}, {CARGO}, {DATA})
- Adicionados {WEBSITE} e {INSTAGRAM} na capa com badges visuais
- Nome empresa responsivo (clamp + word-break)
- 60 PDFs regenerados com novo template

### Testes realizados

| Teste | Resultado |
|-------|----------|
| PDF com nome gigante | OK — responsivo |
| 60 PDFs batch contabilidade | 60/60 OK, 0 erros |
| Mensagem GPT-5 (4 touches) | OK — todas diferentes |
| Envio real mensagem + PDF | OK — chegou no WhatsApp |
| Agente responde (VPS) | OK — mensagens quebradas |
| Agente com contexto oficinas | OK — vocabulario correcto |
| Escalacao (agendar) | OK — Victor recebe alerta |
| Opt-out (PARAR) | OK — estado removido |
| Health check VPS | OK — https://...6mfvzj.easypanel.host/health |

### Metricas de custo (estimadas)

| Item | Custo |
|------|-------|
| Dry-run 60 leads (teste) | ~$2 OpenAI |
| Mensagem outreach (por lead) | ~$0.008 |
| Resposta agente (por msg) | ~$0.01-0.02 |
| 80 msgs/dia + respostas | ~$0.80-1.00/dia |
| Meta mensal OpenAI | ~$19-25 |

### Directrizes WhatsApp (anti-spam)

| Parametro | Valor |
|-----------|-------|
| Limite diario (numero aquecido) | 80 msgs |
| Janela de envio | 09:00-13:00 |
| Intervalo entre msgs | 3-7 min aleatorio |
| Pausa a cada 10 msgs | 15-30 min |
| Follow-ups | 4 toques (dia 0, 3, 7, 14) |
| Buffer resposta | 15s (junta msgs rapidas) |
| Opt-out | Obrigatorio em todas as msgs |

### Funil de conversao esperado (conservador)

| Metrica | Mensal (~1.760 msgs) |
|---------|---------------------|
| Respostas positivas | 55-90 |
| Reunioes marcadas | 25-45 |
| Clientes fechados | 5-13 |

---

## Sessao 5: 30-31 Marco 2026

### O que foi construido

#### 1. Template oficinas + PDFs
- Template `pdf/templates/oficinas.html` copiado e adaptado (badges website/IG na capa)
- Aliases de nicho com acentos (oficina de automóveis) corrigidos
- 60 PDFs de oficinas gerados em batch (0 erros)
- Coluna "Mensagem WhatsApp" removida do Sheets e codigo (19→18 colunas)

#### 2. Agente Marco (contabilidade) — COMPLETO
- `agentes/contabilidade/system_prompt.md` — 456+ linhas
- SPIN adaptado a contabilidade (IVA, IRC, IES, SNC, SAF-T)
- Seccao "PDF ENVIADO AO LEAD" com 3 dores do template
- Escalacao: 8 gatilhos (imediata + comercial + tecnica)
- Follow-up: 5 toques (dia 0, 3, 7, 14, 30 com reengagement Tally)
- Testado end-to-end: outreach + conversa + SPIN stages

#### 3. Follow-ups especificos por agente
- Cada agente gera follow-ups conforme a SUA cadencia no system_prompt.md
- Rui: ANECRA (dia 1), 3 processos (dia 3), chamadas (dia 7), porta aberta (dia 14)
- Marco: OCC (dia 1), classificacao (dia 3), documentos (dia 7), porta aberta (dia 14), Tally (dia 30)
- Nova funcao `generate_followup_message()` no atendente.py
- Opt-out footer em todos os follow-ups

#### 4. Safety nets (redes de seguranca no codigo)
- **irritated**: detecta "chato", "farto", "bloquear" → escala Victor
- **wants_schedule**: detecta "agendar", "vamos marcar" → escala Victor
- **high_value**: detecta >3 baias (oficinas), >200 clientes (contabilidade) → escala Victor
- **SPIN blocking**: impede saltos de stage (situacao→solucao forcado a problema)
- **Opt-out expandido**: 6→14 keywords (+sair, chega, desinscrever, unsubscribe)

#### 5. Scheduler avancado
- `--niche-limits oficinas:40 contabilidade:40` — limite por nicho
- `--priority-cities "Lisboa,Porto"` — cidades prioritarias primeiro
- `--instances "Percep Tudo AI" "Percep Tudo - AI"` — multi-numero round-robin
- Fix: telefone/rating/reviews como int do Sheets → str()
- Intervalos e janela configuraveis via .env

#### 6. Multi-instancia Evolution API
- `sender.py`: param `instance` em send_text, send_pdf, check_is_whatsapp
- `atendente.py`: instance propagado em cascata, guardado no conv_state
- `webhook.py`: extrai instance do payload, agente responde pela mesma
- `scheduler.py`: round-robin de instancias
- Webhooks configurados: Percep Tudo AI + Percep Tudo - AI → VPS

#### 7. Primeiro disparo real — 30 Marco 2026
- 44 leads contactados (30 oficinas + 14 contabilidade)
- Conta comercial PercepTudo restringida ~24h (intervalos muito curtos + numero novo)
- Teste com numero pessoal: 44 msgs enviadas, 2+ respostas em <2h (vs 0 visualizacoes no business)
- Descoberta: numeros business desconhecidos sao ignorados, numeros pessoais sao vistos
- 2 numeros novos (normais) adquiridos e configurados para prospeccao

### Testes realizados

| Teste | Resultado |
|-------|----------|
| 60 PDFs oficinas | 60/60 OK, 0 erros |
| Marco outreach contabilidade | OK — referencias OCC, 800h, multas AT |
| Marco follow-up dia 30 (Tally) | OK — menciona Tally 60€/mes |
| Rui follow-up dia 1 (ANECRA) | OK — menciona 7000 mecanicos |
| Safety net irritated | OK — detecta e escala |
| Safety net wants_schedule | OK — detecta e escala |
| Safety net high_value | OK — detecta >3 baias, >200 clientes |
| SPIN blocking | OK — impede saltos |
| Envio via Percep Tudo AI | OK — chegou |
| Envio via Percep Tudo - AI | OK — chegou |
| Webhook multi-instancia | OK — agente respondeu pela mesma instancia |
| Envio real 44 leads (comercial) | 44 enviados, conta restringida |
| Envio real 44 leads (pessoal) | 44 enviados, 0 erros, 2+ respostas |

---

## Estado actual

### Sheets
- 44 leads oficinas+contabilidade com estado `contactado`
- 70 leads oficinas+contabilidade com estado `pronto_para_envio`
- 6 leads com outros estados

### VPS (Easypanel)
- Servico agente: ONLINE 24/7
- Webhook Evolution API: CONFIGURADO (3 instancias)
- Deploy automatico via GitHub push
- Codigo actualizado: multi-instancia + safety nets + Marco

### Instancias Evolution API
- PercepTudo (business): restringida ate 31/03 ~12:10
- Percep Tudo AI (normal): activa, webhook configurado
- Percep Tudo - AI (normal): activa, webhook configurado
- Pessoal - Joaozin (normal): numero pessoal Victor

### GitHub
- Repo: perceptudo-lab/prospeccao-pecepTudo
- Ultimo commit: multi-instancia + disparo_amanha.py

---

## O que falta fazer

### Prioridade alta (31 Marco)
- [ ] Disparar 70 leads restantes via 2 numeros novos (`python disparo_amanha.py`)
- [ ] Monitorizar respostas e ajustar tom se necessario
- [ ] Aquecimento gradual dos numeros (25→40→60→80 por semana)

### Prioridade media
- [ ] Mais nichos (restauracao, advocacia, clinicas)
- [ ] Cron job na VPS para scheduler automatico
- [ ] Follow-up mid-conversa (leads que pararam de responder ao agente)
- [ ] Volume persistente no Easypanel para conversas
- [ ] Perfil WhatsApp dos numeros novos (nome, foto)

### Prioridade baixa
- [ ] Testes automatizados
- [ ] Monitoramento de block rate / report rate
- [ ] Dashboard de metricas (visualizacoes, respostas, agendamentos)

---

## APIs configuradas (.env)

| Servico | Estado |
|---------|--------|
| Google Maps Places API | OK ($300 credito gratis 90 dias) |
| Apify (Instagram + Reviews) | OK (plano gratis $5/mes) |
| OpenAI GPT-5 | OK (Chat Completions API) |
| Google Sheets | OK (service account + env var inline para Docker) |
| Evolution API (WhatsApp) | OK (VPS Easypanel, 4 instancias) |
| Flask webhook (VPS) | OK (https://perceptudo-agente.6mfvzj.easypanel.host) |
