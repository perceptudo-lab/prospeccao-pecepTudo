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

## Estado actual do Sheets

20 leads de contabilidade em Lisboa com estado `pronto_para_envio`. PDFs gerados, mensagens WhatsApp preenchidas.

---

## O que falta fazer

### Prioridade alta
- [x] ~~Testar pipeline completo: raspar → revisar Sheets → gerar PDFs~~ (feito sessao 3)
- [x] ~~Validar PDFs gerados com a nova ordem (dores antes de oportunidades)~~ (feito sessao 3)
- [ ] Enviar WhatsApp para os 20 leads prontos (quando o Victor decidir)
- [ ] Mais templates HTML por nicho (advocacia, clinicas, imobiliarias, restauracao)

### Prioridade media
- [ ] Follow-ups automaticos (`followup/cron_followup.py`)
- [ ] Git — inicializar repositorio e fazer primeiro commit

### Prioridade baixa
- [ ] Testes automatizados
- [ ] `scraper/instagram_search.py` — pesquisa IG por keywords (pausado)

---

## APIs configuradas (.env)

| Servico | Estado |
|---------|--------|
| Google Maps Places API | OK ($300 credito gratis 90 dias) |
| Apify (Instagram) | OK (plano gratis $5/mes) |
| OpenAI GPT-5 | OK (Chat Completions API) |
| Google Sheets | OK (service account + spreadsheet) |
| Evolution API (WhatsApp) | OK (VPS Easypanel, instancia "PercepTudo") |
