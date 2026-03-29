"""Analise automatica de websites com Playwright."""

import asyncio
import random
import re

from playwright.async_api import async_playwright

from scraper.utils import setup_logger

logger = setup_logger(__name__)

# Padroes para detectar chat widgets
CHAT_PATTERNS = [
    "tawk", "intercom", "drift", "crisp", "tidio", "zendesk",
    "livechat", "hubspot-messages", "freshchat", "olark", "jivochat",
    "zaask", "chatwoot", "smartsupp", "chatra", "callbell", "landbot",
    "gorgias", "liveperson", "comm100",
    "wa.me", "api.whatsapp.com", "whatsapp",
    "wix chat", "wix-chat",
]

# Padroes para detectar ecommerce
ECOMMERCE_PATTERNS = [
    "cart", "carrinho", "checkout", "shopify", "woocommerce",
    "add-to-cart", "adicionar-ao-carrinho", "loja", "shop",
    "produto", "product", "preco", "price",
    "stripe.com", "paypal.com", "mbway", "multibanco", "sibs",
]

# Padroes para detectar newsletter / email marketing
NEWSLETTER_PATTERNS = [
    "mailchimp", "convertkit", "activecampaign", "sendinblue", "brevo",
    "mailerlite", "getresponse", "constantcontact", "klaviyo",
    "newsletter", "subscrever", "subscribe", "inscreva-se",
]

# Padroes para detectar cookie/GDPR consent
COOKIE_PATTERNS = [
    "cookiebot", "onetrust", "cookieconsent", "cookie-consent",
    "cookie-notice", "cookie-banner", "gdpr", "lgpd",
    "consentimento", "cookies-policy",
]

# Padroes para CMS detection
CMS_SIGNATURES = {
    "wordpress": ["wp-content", "wp-includes", 'content="wordpress'],
    "wix": ["wix.com", "static.wixstatic.com", "wix-warmup-data"],
    "shopify": ["cdn.shopify.com", "shopify.checkout"],
    "squarespace": ["squarespace.com", "static1.squarespace.com"],
    "webflow": ["data-wf-", "webflow.com"],
    "joomla": ['content="joomla'],
    "drupal": ['content="drupal', "drupal.js"],
    "prestashop": ["prestashop", "presta"],
}


async def analyze_website(url: str) -> dict:
    """Analisa um website e extrai informacao completa.

    Args:
        url: URL do website a analisar.

    Returns:
        Dict com todos os campos de analise do site.
    """
    defaults = _get_defaults()

    if not url or not url.startswith("http"):
        return defaults

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
            )

            # Bloquear recursos desnecessarios para velocidade
            await context.route(
                "**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,eot,ico}",
                lambda route: route.abort(),
            )
            await context.route("**/google-analytics.com/**", lambda route: route.abort())
            await context.route("**/googletagmanager.com/**", lambda route: route.abort())
            await context.route("**/doubleclick.net/**", lambda route: route.abort())

            page = await context.new_page()

            try:
                response = await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                # Esperar para JS carregar widgets
                await page.wait_for_timeout(3000)
            except Exception as e:
                logger.warning("Timeout ou erro ao carregar %s: %s", url, e)
                await browser.close()
                return defaults

            # Extrair todo o HTML
            html = await page.content()
            html_lower = html.lower()

            # URL final (apos redirects)
            final_url = page.url

            # === REDES SOCIAIS ===
            instagram_url = await _extract_social_link(page, html, "instagram.com")
            facebook_url = await _extract_social_link(page, html, "facebook.com", browser)
            linkedin_url = await _extract_social_link(page, html, "linkedin.com", browser)
            youtube_url = await _extract_social_link(page, html, "youtube.com")
            tiktok_url = await _extract_social_link(page, html, "tiktok.com")
            twitter_url = await _extract_social_link(page, html, "twitter.com")
            if not twitter_url:
                twitter_url = await _extract_social_link(page, html, "x.com")

            # === CONTACTOS DIRECTOS ===
            phone_on_site = await _extract_phone(page, html)
            whatsapp_phone = await _extract_whatsapp_phone(page, html)
            email_on_site = await _extract_email(page, html)

            # === FEATURES DO SITE ===
            has_chat = _detect_chat(html_lower)
            if not has_chat:
                has_chat = await _detect_chat_iframes(page)

            has_form = await _detect_form(page, html_lower)
            has_ecommerce = any(p in html_lower for p in ECOMMERCE_PATTERNS)
            has_blog = await _detect_blog(page, html_lower)
            has_login = await _detect_login(page, html_lower)
            has_newsletter = any(p in html_lower for p in NEWSLETTER_PATTERNS)
            has_video = _detect_video(html_lower)
            has_testimonials = _detect_testimonials(html_lower)
            has_cookie_consent = any(p in html_lower for p in COOKIE_PATTERNS)
            has_https = final_url.startswith("https://")
            has_multilang = _detect_multilang(html_lower)

            # === TECNOLOGIA ===
            cms_platform = _detect_cms(html_lower)
            design_score = await _evaluate_design(page, html_lower)

            await browser.close()

            result = {
                # Redes sociais
                "instagram_url": instagram_url,
                "facebook_url": facebook_url,
                "linkedin_url": linkedin_url,
                "youtube_url": youtube_url,
                "tiktok_url": tiktok_url,
                "twitter_url": twitter_url,
                # Contactos
                "has_phone": bool(phone_on_site),
                "phone_on_site": phone_on_site,
                "whatsapp_phone": whatsapp_phone,
                "has_email": bool(email_on_site),
                "email_on_site": email_on_site,
                # Features
                "has_chat": has_chat,
                "has_form": has_form,
                "has_ecommerce": has_ecommerce,
                "has_blog": has_blog,
                "has_login": has_login,
                "has_newsletter": has_newsletter,
                "has_video": has_video,
                "has_testimonials": has_testimonials,
                "has_cookie_consent": has_cookie_consent,
                "has_https": has_https,
                "has_multilang": has_multilang,
                # Tecnologia
                "cms_platform": cms_platform,
                "design_score": design_score,
            }

            logger.info(
                "Analise de %s: IG=%s | FB=%s | LI=%s | YT=%s | Chat=%s | Form=%s | "
                "Blog=%s | Login=%s | Ecom=%s | Newsletter=%s | Video=%s | "
                "Testimonials=%s | HTTPS=%s | CMS=%s | Design=%s",
                url, bool(instagram_url), bool(facebook_url),
                bool(linkedin_url), bool(youtube_url),
                has_chat, has_form, has_blog, has_login, has_ecommerce,
                has_newsletter, has_video, has_testimonials, has_https,
                cms_platform, design_score,
            )

            return result

    except Exception as e:
        logger.error("Erro ao analisar %s: %s", url, e)
        return defaults


def _get_defaults() -> dict:
    """Retorna valores default para quando nao ha website ou ha erro."""
    return {
        "instagram_url": None,
        "facebook_url": None,
        "linkedin_url": None,
        "youtube_url": None,
        "tiktok_url": None,
        "twitter_url": None,
        "has_phone": False,
        "phone_on_site": None,
        "whatsapp_phone": None,
        "has_email": False,
        "email_on_site": None,
        "has_chat": False,
        "has_form": False,
        "has_ecommerce": False,
        "has_blog": False,
        "has_login": False,
        "has_newsletter": False,
        "has_video": False,
        "has_testimonials": False,
        "has_cookie_consent": False,
        "has_https": False,
        "has_multilang": False,
        "cms_platform": "desconhecido",
        "design_score": "desconhecido",
    }


# ========== EXTRACCAO ==========


# Dominios de redes sociais que podem ter redirects de rebranding
_SOCIAL_DOMAINS_RESOLVE = {"linkedin.com", "facebook.com"}


async def _resolve_social_redirect(browser, url: str) -> str:
    """Resolve o URL real de redes sociais usando Playwright.

    LinkedIn nao faz HTTP redirect quando uma empresa muda de nome —
    serve o conteudo na URL antiga. Para resolver, navega com Playwright
    e extrai o URL canonico (og:url ou link[rel=canonical] ou URL final).
    Se falhar, retorna o URL original.
    """
    # Limpar parametros de template (ex: ?viewAsMember=true do Wix)
    clean_url = re.sub(r'\?viewAsMember=true', '', url)

    try:
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            ignore_https_errors=True,
        )
        page = await context.new_page()
        await page.goto(clean_url, timeout=15000, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # 1. Tentar og:url (LinkedIn usa isto para o URL canonico)
        canonical = None
        try:
            canonical = await page.get_attribute('meta[property="og:url"]', 'content')
        except Exception:
            pass

        # 2. Fallback: link[rel=canonical]
        if not canonical:
            try:
                canonical = await page.get_attribute('link[rel="canonical"]', 'content')
            except Exception:
                pass
            if not canonical:
                try:
                    canonical = await page.get_attribute('link[rel="canonical"]', 'href')
                except Exception:
                    pass

        # 3. Fallback: URL final da pagina
        final_url = canonical or page.url

        await context.close()

        # Limpar parametros de tracking
        final_url = re.sub(r'\?.*$', '', final_url).rstrip('/')
        clean_original = re.sub(r'\?.*$', '', url).rstrip('/')

        if final_url != clean_original:
            logger.info("URL social resolvido: %s -> %s", url, final_url)

        return final_url
    except Exception as e:
        logger.warning("Erro ao resolver URL social de %s: %s", url, e)
        return clean_url


async def _extract_social_link(page, html: str, domain: str, browser=None) -> str | None:
    """Extrai link de rede social da pagina.

    Procura primeiro em <a href>, depois com regex no HTML.
    Para LinkedIn e Facebook, segue redirects via Playwright para obter
    o URL final (empresas que mudaram de nome mantêm URLs antigos).
    """
    raw_url = None

    # Metodo 1: procurar em links <a>
    try:
        links = await page.eval_on_selector_all(
            f"a[href*='{domain}']",
            "elements => elements.map(e => e.href)",
        )
        if links:
            for link in links:
                if f"{domain}/" in link and "sharer" not in link and "share" not in link:
                    raw_url = link
                    break
    except Exception:
        pass

    # Metodo 2: regex fallback no HTML
    if not raw_url:
        pattern = rf'https?://(?:www\.)?{re.escape(domain)}/[\w\.\-]+'
        match = re.search(pattern, html)
        if match:
            url = match.group(0)
            if "sharer" not in url and "share" not in url:
                raw_url = url

    if not raw_url:
        return None

    # Resolver redirects para dominios que costumam ter rebranding
    if browser and any(d in domain for d in _SOCIAL_DOMAINS_RESOLVE):
        raw_url = await _resolve_social_redirect(browser, raw_url)

    return raw_url


async def _extract_phone(page, html: str) -> str | None:
    """Extrai telefone do site — primeiro de links, depois de texto visivel.

    Procura em <a href="tel:..."> e depois faz regex no texto
    visivel da pagina para numeros portugueses.
    """
    # 1. Links tel:
    try:
        links = await page.eval_on_selector_all(
            "a[href^='tel:']",
            "elements => elements.map(e => e.href)",
        )
        if links:
            value = links[0].replace("tel:", "").strip()
            if value:
                return value
    except Exception:
        pass

    # 2. Regex em texto visivel — numeros portugueses
    try:
        text = await page.inner_text("body")
        # Padroes: +351 xxx xxx xxx, 9xx xxx xxx, 2xx xxx xxx, Tel. 9xxxxxxxx
        patterns = [
            r'\+351[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{3}',  # +351 912 345 678
            r'(?<!\d)9\d{2}[\s\-]?\d{3}[\s\-]?\d{3}(?!\d)',  # 912 345 678
            r'(?<!\d)2\d{2}[\s\-]?\d{3}[\s\-]?\d{3}(?!\d)',  # 222 468 303
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
    except Exception:
        pass

    return None


async def _extract_whatsapp_phone(page, html: str) -> str | None:
    """Extrai numero de telefone de links/botoes WhatsApp no site.

    Procura em links wa.me/NUMERO e api.whatsapp.com/send?phone=NUMERO.
    """
    # 1. Links wa.me
    try:
        links = await page.eval_on_selector_all(
            "a[href*='wa.me'], a[href*='whatsapp.com']",
            "elements => elements.map(e => e.href)",
        )
        for link in links:
            # wa.me/351912345678 ou wa.me/+351912345678
            match = re.search(r'wa\.me/\+?(\d{9,15})', link)
            if match:
                return match.group(1)
            # api.whatsapp.com/send?phone=351912345678
            match = re.search(r'phone=\+?(\d{9,15})', link)
            if match:
                return match.group(1)
    except Exception:
        pass

    # 2. Fallback: regex no HTML para links wa.me
    match = re.search(r'wa\.me/\+?(\d{9,15})', html)
    if match:
        return match.group(1)

    match = re.search(r'whatsapp\.com/send\?phone=\+?(\d{9,15})', html)
    if match:
        return match.group(1)

    return None


async def _extract_email(page, html: str) -> str | None:
    """Extrai email do site — primeiro de links, depois de texto visivel.

    Procura em <a href="mailto:..."> e depois faz regex no texto
    visivel da pagina.
    """
    # 1. Links mailto:
    try:
        links = await page.eval_on_selector_all(
            "a[href^='mailto:']",
            "elements => elements.map(e => e.href)",
        )
        if links:
            value = links[0].replace("mailto:", "").strip()
            if value:
                return value
    except Exception:
        pass

    # 2. Regex em texto visivel
    try:
        text = await page.inner_text("body")
        match = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
        if match:
            email = match.group(0)
            # Filtrar emails genericos de plataformas
            ignore = ["wix.com", "wordpress.com", "example.com", "sentry.io"]
            if not any(d in email for d in ignore):
                return email
    except Exception:
        pass

    return None


# ========== DETECCAO DE FEATURES ==========


def _detect_chat(html_lower: str) -> bool:
    """Detecta chat widgets via pattern matching no HTML."""
    return any(pattern in html_lower for pattern in CHAT_PATTERNS)


async def _detect_chat_iframes(page) -> bool:
    """Fallback: detectar iframes de chat (Wix Chat, etc.)."""
    try:
        chat_iframes = await page.locator(
            "iframe[title*='chat' i], "
            "iframe[aria-label*='chat' i], "
            "iframe[src*='chat']"
        ).count()
        return chat_iframes > 0
    except Exception:
        return False


async def _detect_form(page, html_lower: str) -> bool:
    """Detecta formularios de contacto, CTAs de agendamento ou plataformas de booking."""
    # 1. Forms tradicionais
    try:
        form_count = await page.locator(
            "form:has(input[type='email']), "
            "form:has(textarea), "
            "form:has(input[name*='email']), "
            "form:has(input[name*='contact']), "
            "form:has(input[name*='mensagem'])"
        ).count()
        if form_count > 0:
            return True
    except Exception:
        pass

    # 2. CTAs de agendamento/booking
    try:
        booking_count = await page.locator(
            "a:has-text('agendar'), a:has-text('Agendar'), a:has-text('AGENDAR'), "
            "a:has-text('marcar'), a:has-text('Marcar'), "
            "a:has-text('reunião'), a:has-text('Reunião'), a:has-text('REUNIÃO'), "
            "a:has-text('schedule'), a:has-text('Schedule'), "
            "a:has-text('booking'), a:has-text('Booking'), "
            "a:has-text('Book'), a:has-text('Contacte'), a:has-text('contacte'), "
            "a:has-text('Pedir proposta'), a:has-text('pedir proposta'), "
            "a:has-text('Pedir orçamento'), a:has-text('orçamento'), "
            "button:has-text('agendar'), button:has-text('Agendar'), "
            "button:has-text('marcar'), button:has-text('reunião'), "
            "button:has-text('Contacte'), button:has-text('enviar')"
        ).count()
        if booking_count > 0:
            return True
    except Exception:
        pass

    # 3. Plataformas de agendamento conhecidas
    booking_platforms = [
        "calendly.com", "cal.com", "tidycal.com",
        "hubspot.com/meetings", "acuityscheduling.com",
        "zcal.co", "savvycal.com", "setmore.com",
        "bookly", "mindbody", "opentable.com",
    ]
    if any(p in html_lower for p in booking_platforms):
        return True

    return False


async def _detect_blog(page, html_lower: str) -> bool:
    """Detecta se o site tem blog ou seccao de conteudo."""
    try:
        blog_links = await page.locator(
            "a[href*='/blog'], a[href*='/artigos'], a[href*='/noticias'], "
            "a[href*='/insights'], a[href*='/recursos'], a[href*='/news'], "
            "a:has-text('Blog'), a:has-text('Artigos'), "
            "a:has-text('Notícias'), a:has-text('Noticias'), "
            "a:has-text('Publicações'), a:has-text('Publicacoes'), "
            "a:has-text('Insights'), a:has-text('Recursos'), "
            "a:has-text('Novidades'), a:has-text('Conhecimento'), "
            "a:has-text('Academy'), a:has-text('Learning')"
        ).count()
        if blog_links > 0:
            return True
    except Exception:
        pass
    blog_urls = ["/blog", "/artigos", "/noticias", "/insights", "/recursos", "/news"]
    return any(u in html_lower for u in blog_urls)


async def _detect_login(page, html_lower: str) -> bool:
    """Detecta se o site tem login ou painel de cliente."""
    try:
        login_links = await page.locator(
            "a:has-text('Login'), a:has-text('Entrar'), "
            "a:has-text('Área de Cliente'), a:has-text('Area de Cliente'), "
            "a:has-text('Painel'), a:has-text('Portal'), "
            "a:has-text('Minha Conta'), a:has-text('My Account'), "
            "a:has-text('Registo'), a:has-text('Sign in'), "
            "a[href*='login'], a[href*='signin'], "
            "a[href*='portal'], a[href*='cliente'], "
            "a[href*='account'], a[href*='dashboard']"
        ).count()
        if login_links > 0:
            return True
    except Exception:
        pass
    return False


def _detect_video(html_lower: str) -> bool:
    """Detecta presenca de video embebido no site."""
    video_patterns = [
        "youtube.com/embed", "player.vimeo.com", "<video",
        "wistia.com", "vidyard.com", "loom.com/embed",
    ]
    return any(p in html_lower for p in video_patterns)


def _detect_testimonials(html_lower: str) -> bool:
    """Detecta presenca de testemunhos ou reviews no site."""
    testimonial_patterns = [
        "testemunho", "testimonial", "opiniao", "opinião",
        "clientes dizem", "o que dizem", "what our clients",
        "reviews", "avaliacao", "avaliação", "depoimento",
        "caso de sucesso", "case study", "case-study",
    ]
    return any(p in html_lower for p in testimonial_patterns)


def _detect_multilang(html_lower: str) -> bool:
    """Detecta se o site suporta multiplos idiomas."""
    multilang_patterns = [
        "hreflang=", "lang-switcher", "language-switcher",
        "wpml", "polylang", "translatepress",
        'href="/en"', 'href="/en/"', 'href="/es"', 'href="/fr"',
        "google_translate", "gtranslate",
    ]
    return any(p in html_lower for p in multilang_patterns)


def _detect_cms(html_lower: str) -> str:
    """Detecta a plataforma/CMS do site."""
    for cms_name, signatures in CMS_SIGNATURES.items():
        if any(sig in html_lower for sig in signatures):
            return cms_name
    return "custom"


# ========== AVALIACAO ==========


async def _evaluate_design(page, html_lower: str) -> str:
    """Avalia se o design do site e moderno ou desatualizado.

    Criterios modernos: viewport meta, responsive CSS, HTTPS, frameworks modernos.
    Criterios antigos: tabelas para layout, font tags, Flash.
    """
    modern_score = 0
    outdated_score = 0

    # Indicadores modernos
    if '<meta name="viewport"' in html_lower:
        modern_score += 2
    if "@media" in html_lower:
        modern_score += 1
    if "tailwind" in html_lower or "bootstrap" in html_lower:
        modern_score += 2

    # Detectar frameworks modernos
    try:
        has_framework = await page.evaluate(
            "() => !!(window.__NUXT__ || window.__NEXT_DATA__ || "
            "window.__vue__ || window.React || window.__remixContext)"
        )
        if has_framework:
            modern_score += 2
    except Exception:
        pass

    # Indicadores desatualizados
    if "<table" in html_lower and "width=" in html_lower:
        outdated_score += 2
    if "<font" in html_lower:
        outdated_score += 2
    if "flash" in html_lower and "swf" in html_lower:
        outdated_score += 3
    if "<marquee" in html_lower or "<blink" in html_lower:
        outdated_score += 2
    if "<center>" in html_lower:
        outdated_score += 1

    if modern_score > outdated_score:
        return "moderno"
    elif outdated_score > modern_score:
        return "desatualizado"
    else:
        return "moderno"  # Em caso de duvida, assumir moderno


# ========== BATCH PROCESSING ==========


async def analyze_websites(leads: list[dict]) -> list[dict]:
    """Analisa websites de todos os leads.

    Modifica os leads in-place, adicionando campos de analise web.
    Leads sem website ficam com valores default.

    Args:
        leads: Lista de dicts de leads (deve ter key 'website').

    Returns:
        A mesma lista com campos de analise adicionados.
    """
    logger.info("A analisar websites de %d leads...", len(leads))

    for i, lead in enumerate(leads):
        website = lead.get("website", "")

        if website:
            logger.info(
                "[%d/%d] A analisar: %s (%s)",
                i + 1, len(leads), lead.get("nome", "?"), website,
            )
            analysis = await analyze_website(website)

            # Sleep aleatorio entre sites (1-2s)
            delay = random.uniform(1.0, 2.0)
            await asyncio.sleep(delay)
        else:
            logger.info(
                "[%d/%d] %s: sem website — a saltar analise",
                i + 1, len(leads), lead.get("nome", "?"),
            )
            analysis = _get_defaults()

        # Adicionar campos ao lead
        lead.update(analysis)

    logger.info("Analise de websites concluida")
    return leads
