#!/usr/bin/env python3
"""Template PDF para nicho de Contabilidade — PercepTudo."""

import json
import argparse
from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, NextPageTemplate, PageBreak
)

# ─── BRAND COLORS ───
PURPLE = HexColor("#7B2FF2")
PURPLE_DARK = HexColor("#3D1A78")
PURPLE_BG = HexColor("#1E0A3C")
PURPLE_10 = HexColor("#EDE5FF")
AMBER = HexColor("#F2A900")
AMBER_BG = HexColor("#FFF8E8")
GREEN = HexColor("#00E5A0")
GREEN_BG = HexColor("#E6FFF2")
GREEN_DARK = HexColor("#0B8A5E")
RED = HexColor("#E53E3E")
RED_BG = HexColor("#FFF5F5")
CLOUD = HexColor("#F5F2ED")
GRAPHITE = HexColor("#1A1A2E")
DARK2 = HexColor("#222238")
DARK3 = HexColor("#2A2A48")
GRAY = HexColor("#6B7280")
GRAY_LT = HexColor("#E5E2DD")
GRAY_D = HexColor("#999999")
WHITE = HexColor("#FFFFFF")
LIGHT_BG = HexColor("#FAFAF8")

PAGE_W, PAGE_H = A4
M = 2 * cm
W = PAGE_W - 2 * M


# ─── PAGE BACKGROUNDS ───

def _cover_bg(c, doc):
    c.saveState()
    # Dark purple gradient background
    c.setFillColor(PURPLE_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Subtle gradient overlay
    c.setFillColor(PURPLE)
    c.setFillAlpha(0.15)
    c.circle(PAGE_W - 2*cm, PAGE_H - 3*cm, 6*cm, fill=1, stroke=0)
    c.setFillAlpha(0.08)
    c.circle(1*cm, 4*cm, 3*cm, fill=1, stroke=0)
    c.setFillAlpha(1)
    c.restoreState()


def _light_bg(c, doc):
    c.saveState()
    c.setFillColor(LIGHT_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Footer
    c.setFont('Helvetica', 7)
    c.setFillColor(GRAY)
    c.drawRightString(PAGE_W - M, 0.7*cm, f"{doc.page}")
    c.restoreState()


def _dark_bg(c, doc):
    c.saveState()
    c.setFillColor(PURPLE_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(PURPLE)
    c.setFillAlpha(0.08)
    c.circle(PAGE_W - 3*cm, PAGE_H - 4*cm, 5*cm, fill=1, stroke=0)
    c.setFillAlpha(1)
    c.setFont('Helvetica', 7)
    c.setFillColor(GRAY)
    c.drawRightString(PAGE_W - M, 0.7*cm, f"{doc.page}")
    c.restoreState()


def generate_contabilidade_pdf(data: dict, output_path: str) -> str:
    """Gera PDF de diagnostico para nicho de Contabilidade."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    D = data
    nome = D.get('nome', 'Empresa')
    sector = D.get('sector', 'contabilidade')

    doc = BaseDocTemplate(output_path, pagesize=A4,
        leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=1.5*cm)

    doc.addPageTemplates([
        PageTemplate('cover', frames=Frame(M, M, W, PAGE_H-2*M, id='fc'), onPage=_cover_bg),
        PageTemplate('light', frames=Frame(M, 1.5*cm, W, PAGE_H-3*cm, id='fl'), onPage=_light_bg),
        PageTemplate('dark', frames=Frame(M, 1.5*cm, W, PAGE_H-3*cm, id='fd'), onPage=_dark_bg),
    ])

    story = []

    # ══════════════════════════════════════════
    # P1: CAPA (dark purple)
    # ══════════════════════════════════════════
    # Logo
    story.append(Spacer(1, 1*cm))
    logo_badge = Table([
        [Paragraph(
            '<font name="Helvetica" color="#F5F2ED" size="18">Percep </font>'
            '<font name="Helvetica-Bold" color="#7B2FF2" size="18">Tudo</font>',
            ParagraphStyle('logo', fontSize=18, leading=22)),
         Paragraph(
            '<font color="#00E5A0" size="7">DIAGNOSTICO EXCLUSIVO</font>',
            ParagraphStyle('badge', fontSize=7, alignment=TA_RIGHT, borderColor=GREEN,
                          textColor=GREEN))]
    ], colWidths=[W*0.5, W*0.5])
    logo_badge.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(logo_badge)

    story.append(Spacer(1, 4*cm))

    # Headline
    story.append(Paragraph(
        f"O gabinete da<br/>"
        f"<font color='#F2A900'><b>{nome}</b></font> gasta<br/>"
        f"60% do tempo em tarefas<br/>que a IA resolve sozinha.",
        ParagraphStyle('h_cover', fontName='Helvetica-Bold', fontSize=28,
                      textColor=WHITE, leading=38, spaceAfter=16)))

    story.append(Paragraph(
        f"Diagnostico exclusivo para gabinetes de <font color='#00E5A0'><b>{sector}</b></font> que "
        f"querem crescer sem contratar.",
        ParagraphStyle('sub_cover', fontName='Helvetica', fontSize=12,
                      textColor=GRAY_D, leading=18, spaceAfter=24)))

    # Box "PREPARADO PARA"
    prep_box = Table([[
        Paragraph(
            f"<font color='#999999' size='8'>PREPARADO PARA</font><br/><br/>"
            f"<font color='#F2A900' size='16'><b>{nome}</b></font>",
            ParagraphStyle('prep', fontSize=16, leading=22))
    ]], colWidths=[W])
    prep_box.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, AMBER),
        ('TOPPADDING', (0,0), (-1,-1), 14),
        ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
    ]))
    story.append(prep_box)

    story.append(NextPageTemplate('light'))

    # ══════════════════════════════════════════
    # P2: CONTEXTO DO SECTOR (light)
    # ══════════════════════════════════════════
    story.append(PageBreak())

    story.append(Paragraph(
        "O sector esta a mudar. A questao e:<br/>o seu gabinete esta a acompanhar?",
        ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=22,
                      textColor=GRAPHITE, leading=28, spaceAfter=16)))

    # Stats row
    stats = Table([[
        Paragraph(
            f"<font color='#F2A900' size='36'><b>60-70</b></font>"
            f"<font color='#F2A900' size='18'>%</font><br/>"
            f"<font color='#6B7280' size='8'>TEMPO EM TAREFAS<br/>REPETITIVAS</font>",
            ParagraphStyle('s1', fontSize=10, alignment=TA_CENTER, leading=16)),
        Paragraph(
            f"<font color='#6B7280' size='20'>+</font>",
            ParagraphStyle('plus', fontSize=20, alignment=TA_CENTER, textColor=GRAY)),
        Paragraph(
            f"<font color='#7B2FF2' size='36'><b>84</b></font>"
            f"<font color='#7B2FF2' size='18'>%</font><br/>"
            f"<font color='#6B7280' size='8'>NAO CONSEGUEM<br/>CONTRATAR</font>",
            ParagraphStyle('s2', fontSize=10, alignment=TA_CENTER, leading=16)),
    ]], colWidths=[W*0.4, W*0.2, W*0.4])
    stats.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 16),
        ('BOTTOMPADDING', (0,0), (-1,-1), 16),
        ('BACKGROUND', (0,0), (-1,-1), CLOUD),
    ]))
    story.append(stats)
    story.append(Spacer(1, 12))

    # Carta directa (sem nome do decisor)
    carta = Table([
        [Paragraph(
            f"Gerir um gabinete de <font color='#00E5A0'><b>{sector}</b></font> nunca exigiu tanto. "
            f"Prazos da AT cada vez mais apertados. Legislacao que muda a cada Orcamento de Estado. "
            f"Clientes que enviam documentos pelo WhatsApp as 23h.<br/><br/>"
            f"E no meio disto tudo, a sua equipa passa o dia a lancar faturas, reconciliar contas e "
            f"perseguir clientes por recibos em falta.<br/><br/>"
            f"Este documento foi preparado com base em <b>dados reais do sector da contabilidade "
            f"em Portugal</b> — e mostra exactamente onde o seu gabinete esta a perder tempo e dinheiro.",
            ParagraphStyle('carta', fontName='Helvetica', fontSize=11,
                          textColor=GRAPHITE, leading=17, alignment=TA_JUSTIFY))]
    ], colWidths=[W])
    carta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), WHITE),
        ('TOPPADDING', (0,0), (-1,-1), 20),
        ('BOTTOMPADDING', (0,0), (-1,-1), 20),
        ('LEFTPADDING', (0,0), (-1,-1), 20),
        ('RIGHTPADDING', (0,0), (-1,-1), 20),
    ]))
    story.append(carta)
    story.append(Spacer(1, 12))

    # Barra adopcao IA
    adopt = Table([[
        Paragraph("<font color='#F2A900' size='9'><b>Portugal: 30%</b></font>",
                  ParagraphStyle('apt', fontSize=9)),
        Paragraph("<font color='#00E5A0' size='9'><b>Europa: 74%</b></font>",
                  ParagraphStyle('aeu', fontSize=9, alignment=TA_CENTER)),
        Paragraph("<font color='#F2A900' size='9'><b>Adopcao de IA</b></font><br/>"
                  "<font color='#6B7280' size='7'>na contabilidade</font><br/>"
                  "<font color='#6B7280' size='7'>Fed Finance / IDC, 2026</font>",
                  ParagraphStyle('asrc', fontSize=9, alignment=TA_RIGHT)),
    ]], colWidths=[W*0.3, W*0.4, W*0.3])
    adopt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRAPHITE),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('LEFTPADDING', (0,0), (-1,-1), 14),
        ('RIGHTPADDING', (0,0), (-1,-1), 14),
    ]))
    story.append(adopt)

    # ══════════════════════════════════════════
    # P3: DOR #1 — Tarefas repetitivas (light)
    # ══════════════════════════════════════════
    story.append(PageBreak())

    story.append(Paragraph(
        "<font color='#F2A900' size='9'><b>DOR #1</b></font>",
        ParagraphStyle('d1l', fontSize=9, spaceAfter=4)))
    story.append(Paragraph(
        "O peso das tarefas repetitivas",
        ParagraphStyle('d1h', fontName='Helvetica-Bold', fontSize=22,
                      textColor=GRAPHITE, leading=28, spaceAfter=14)))

    # Big stat
    stat1 = Table([[
        Paragraph(
            "<font color='#1A1A2E' size='56'><b>800h</b></font><br/><br/>"
            "<font color='#6B7280' size='10'>por ano, por profissional — gastas em lancamentos, "
            "reconciliacoes e classificacao</font>",
            ParagraphStyle('st1', fontSize=10, alignment=TA_CENTER, leading=16))
    ]], colWidths=[W])
    stat1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GREEN_BG),
        ('TOPPADDING', (0,0), (-1,-1), 24),
        ('BOTTOMPADDING', (0,0), (-1,-1), 20),
        ('LEFTPADDING', (0,0), (-1,-1), 20),
        ('RIGHTPADDING', (0,0), (-1,-1), 20),
    ]))
    story.append(stat1)
    story.append(Spacer(1, 14))

    story.append(Paragraph(
        "Horas que nao geram valor. Horas que nao pode faturar como consultoria. "
        "Horas que os seus concorrentes mais ageis ja eliminaram.",
        ParagraphStyle('d1p', fontName='Helvetica', fontSize=11,
                      textColor=GRAPHITE, leading=17, spaceAfter=10)))

    story.append(Paragraph(
        "<b>Os gabinetes que nao automatizaram gastam 35% mais em custos operacionais. "
        "A cada mes que passa, a diferenca cresce.</b>",
        ParagraphStyle('d1q', fontName='Helvetica', fontSize=10,
                      textColor=PURPLE, leading=15, leftIndent=12,
                      borderLeftWidth=3, borderLeftColor=PURPLE, spaceAfter=14,
                      borderPadding=8)))

    # Solucao card
    sol1 = Table([
        [Paragraph(
            "<font color='#00E5A0' size='8'><b>SOLUCAO</b></font>  "
            "<font size='12'><b>Automacao Inteligente — Percep Tudo</b></font>",
            ParagraphStyle('sol1h', fontName='Helvetica-Bold', fontSize=12,
                          textColor=GRAPHITE, leading=18))],
        [Paragraph(
            "Pipeline de automacao documental — OCR inteligente, classificacao automatica e "
            "lancamento directo no Sage, PHC ou Primavera que ja utiliza.",
            ParagraphStyle('sol1d', fontName='Helvetica', fontSize=10,
                          textColor=GRAY, leading=15))],
        [Paragraph(
            "<font color='#FFFFFF'><b>-50-60% tempo transacional  •  "
            "Fecho mensal ate 56% mais rapido</b></font>",
            ParagraphStyle('sol1r', fontName='Helvetica-Bold', fontSize=9,
                          textColor=WHITE, alignment=TA_LEFT))],
    ], colWidths=[W])
    sol1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,1), GREEN_BG),
        ('BACKGROUND', (0,2), (-1,2), GREEN_DARK),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
        ('RIGHTPADDING', (0,0), (-1,-1), 16),
    ]))
    story.append(sol1)
    story.append(Spacer(1, 10))

    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_LT, spaceAfter=6))
    story.append(Paragraph(
        "<font color='#999999' size='7'>Fontes: Fed Finance 2026 • McKinsey • IDC Portugal "
        "— reducao de erros em 20%, aumento de eficiencia em 25%</font>",
        ParagraphStyle('src1', fontSize=7, textColor=GRAY_D)))

    # ══════════════════════════════════════════
    # P4: DOR #2 — Escassez de talento (light)
    # ══════════════════════════════════════════
    story.append(PageBreak())

    story.append(Paragraph(
        "<font color='#E53E3E' size='9'><b>DOR #2</b></font>",
        ParagraphStyle('d2l', fontSize=9, spaceAfter=4)))
    story.append(Paragraph(
        "Nao ha gente para contratar",
        ParagraphStyle('d2h', fontName='Helvetica-Bold', fontSize=22,
                      textColor=GRAPHITE, leading=28, spaceAfter=14)))

    # Big stat
    stat2 = Table([[
        Paragraph(
            "<font color='#E53E3E' size='56'><b>84%</b></font><br/><br/>"
            "<font color='#6B7280' size='10'>dos gabinetes reportam dificuldades extremas em recrutar</font>",
            ParagraphStyle('st2', fontSize=10, alignment=TA_CENTER, leading=16))
    ]], colWidths=[W])
    stat2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), RED_BG),
        ('TOPPADDING', (0,0), (-1,-1), 24),
        ('BOTTOMPADDING', (0,0), (-1,-1), 20),
    ]))
    story.append(stat2)
    story.append(Spacer(1, 8))

    # Two stats side by side
    stats2 = Table([[
        Paragraph(
            "<font color='#F2A900' size='32'><b>53</b></font><br/>"
            "<font color='#6B7280' size='9'>dias para recrutar</font>",
            ParagraphStyle('s2a', fontSize=10, alignment=TA_CENTER, leading=16)),
        Paragraph(
            "<font color='#7B2FF2' size='32'><b>31%</b></font><br/>"
            "<font color='#6B7280' size='9'>ofertas rejeitadas</font>",
            ParagraphStyle('s2b', fontSize=10, alignment=TA_CENTER, leading=16)),
    ]], colWidths=[W/2, W/2])
    stats2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), CLOUD),
        ('BACKGROUND', (1,0), (1,0), CLOUD),
        ('TOPPADDING', (0,0), (-1,-1), 16),
        ('BOTTOMPADDING', (0,0), (-1,-1), 16),
        ('LINEBEFORE', (1,0), (1,0), 8, LIGHT_BG),
    ]))
    story.append(stats2)
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        "Enquanto procura quem nao existe, a equipa actual acumula horas extra. "
        "A qualidade baixa. Os clientes notam.",
        ParagraphStyle('d2p', fontName='Helvetica', fontSize=11,
                      textColor=GRAPHITE, leading=17, spaceAfter=10)))

    story.append(Paragraph(
        "<b>A pergunta nao e onde encontrar mais pessoas. E como fazer mais com as que ja tem.</b>",
        ParagraphStyle('d2q', fontName='Helvetica', fontSize=10,
                      textColor=PURPLE, leading=15, leftIndent=12,
                      borderLeftWidth=3, borderLeftColor=PURPLE, spaceAfter=14,
                      borderPadding=8)))

    # Solucao
    sol2 = Table([
        [Paragraph(
            "<font color='#00E5A0' size='8'><b>SOLUCAO</b></font>  "
            "<font size='12'><b>Automacao + Capacitacao de Equipa — Percep Tudo</b></font>",
            ParagraphStyle('sol2h', fontName='Helvetica-Bold', fontSize=12,
                          textColor=GRAPHITE, leading=18))],
        [Paragraph(
            "Eliminamos 60-70% das tarefas mecanicas e formamos a sua equipa para usar IA no dia-a-dia.",
            ParagraphStyle('sol2d', fontName='Helvetica', fontSize=10,
                          textColor=GRAY, leading=15))],
        [Paragraph(
            "<font color='#FFFFFF'><b>1 pessoa = 1,3-1,5 profissionais  •  Sem horas extra</b></font>",
            ParagraphStyle('sol2r', fontName='Helvetica-Bold', fontSize=9, textColor=WHITE))],
    ], colWidths=[W])
    sol2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,1), GREEN_BG),
        ('BACKGROUND', (0,2), (-1,2), GREEN_DARK),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
        ('RIGHTPADDING', (0,0), (-1,-1), 16),
    ]))
    story.append(sol2)
    story.append(Spacer(1, 10))

    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_LT, spaceAfter=6))
    story.append(Paragraph(
        "<font color='#999999' size='7'>Fontes: Fed Finance 2026 • Hays "
        "— rotatividade de 20% no sector</font>",
        ParagraphStyle('src2', fontSize=7, textColor=GRAY_D)))

    # ══════════════════════════════════════════
    # P5: DOR #3 — Multas AT (light)
    # ══════════════════════════════════════════
    story.append(PageBreak())

    story.append(Paragraph(
        "<font color='#F2A900' size='9'><b>DOR #3</b></font>",
        ParagraphStyle('d3l', fontSize=9, spaceAfter=4)))
    story.append(Paragraph(
        "Multas da AT e documentos perdidos",
        ParagraphStyle('d3h', fontName='Helvetica-Bold', fontSize=22,
                      textColor=GRAPHITE, leading=28, spaceAfter=14)))

    # Three fine cards
    fines = Table([[
        Paragraph(
            "<font color='#F2A900' size='8'><b>Atraso IVA</b></font><br/>"
            "<font color='#1A1A2E' size='28'><b>150EUR</b></font><br/>"
            "<font color='#6B7280' size='8'>minimo</font>",
            ParagraphStyle('f1', fontSize=10, alignment=TA_CENTER, leading=14)),
        Paragraph(
            "<font color='#E53E3E' size='8'><b>Omissao</b></font><br/>"
            "<font color='#1A1A2E' size='28'><b>22.500EUR</b></font><br/>"
            "<font color='#6B7280' size='8'>maximo</font>",
            ParagraphStyle('f2', fontSize=10, alignment=TA_CENTER, leading=14)),
        Paragraph(
            "<font color='#7B2FF2' size='8'><b>Falta SAF-T</b></font><br/>"
            "<font color='#1A1A2E' size='28'><b>450EUR</b></font><br/>"
            "<font color='#6B7280' size='8'>minimo</font>",
            ParagraphStyle('f3', fontSize=10, alignment=TA_CENTER, leading=14)),
    ]], colWidths=[W/3, W/3, W/3])
    fines.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), CLOUD),
        ('TOPPADDING', (0,0), (-1,-1), 16),
        ('BOTTOMPADDING', (0,0), (-1,-1), 16),
        ('LINEBEFORE', (1,0), (1,0), 0.5, GRAY_LT),
        ('LINEBEFORE', (2,0), (2,0), 0.5, GRAY_LT),
    ]))
    story.append(fines)
    story.append(Spacer(1, 14))

    story.append(Paragraph(
        "Com a fiscalizacao digital cada vez mais apertada, o erro que antes passava "
        "despercebido agora gera notificacao automatica.",
        ParagraphStyle('d3p', fontName='Helvetica', fontSize=11,
                      textColor=GRAPHITE, leading=17, spaceAfter=10)))

    story.append(Paragraph(
        "<b>E enquanto o gabinete lida com prazos, os clientes continuam a enviar documentos "
        "tarde, incompletos e por cinco canais diferentes.</b>",
        ParagraphStyle('d3q', fontName='Helvetica', fontSize=10,
                      textColor=PURPLE, leading=15, leftIndent=12,
                      borderLeftWidth=3, borderLeftColor=PURPLE, spaceAfter=14,
                      borderPadding=8)))

    # Solucao
    sol3 = Table([
        [Paragraph(
            "<font color='#00E5A0' size='8'><b>SOLUCAO</b></font>  "
            "<font size='12'><b>Agentes de IA Personalizados — Percep Tudo</b></font>",
            ParagraphStyle('sol3h', fontName='Helvetica-Bold', fontSize=12,
                          textColor=GRAPHITE, leading=18))],
        [Paragraph(
            "Calendario fiscal inteligente com alertas, validacao automatica de declaracoes "
            "antes da submissao, e portal de cliente com lembretes automaticos para recolha de documentos.",
            ParagraphStyle('sol3d', fontName='Helvetica', fontSize=10,
                          textColor=GRAY, leading=15))],
        [Paragraph(
            "<font color='#FFFFFF'><b>Zero multas por descuido  •  Documentos organizados</b></font>",
            ParagraphStyle('sol3r', fontName='Helvetica-Bold', fontSize=9, textColor=WHITE))],
    ], colWidths=[W])
    sol3.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,1), GREEN_BG),
        ('BACKGROUND', (0,2), (-1,2), GREEN_DARK),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
        ('RIGHTPADDING', (0,0), (-1,-1), 16),
    ]))
    story.append(sol3)
    story.append(Spacer(1, 10))

    # Fluxo
    fluxo = Table([[
        Paragraph(
            "<font size='9'><b>Fluxo de Recolha Automatizada</b></font><br/><br/>"
            "<font color='#6B7280' size='9'>Portal Cliente  →  OCR  →  Classificacao  →  Lancamento</font>",
            ParagraphStyle('flx', fontSize=9, textColor=GRAPHITE, leading=14))
    ]], colWidths=[W])
    fluxo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), CLOUD),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
    ]))
    story.append(fluxo)
    story.append(Spacer(1, 8))

    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_LT, spaceAfter=6))
    story.append(Paragraph(
        "<font color='#999999' size='7'>Fontes: RGIT • Neves &amp; Freitas "
        "• 40-60% dos gabinetes micro com infracoes anuais</font>",
        ParagraphStyle('src3', fontSize=7, textColor=GRAY_D)))

    # ══════════════════════════════════════════
    # P6: COMO FUNCIONA (light)
    # ══════════════════════════════════════════
    story.append(PageBreak())

    story.append(Paragraph(
        "Como funciona",
        ParagraphStyle('h6', fontName='Helvetica-Bold', fontSize=22,
                      textColor=GRAPHITE, leading=28, spaceAfter=6)))
    story.append(Paragraph(
        "A Percep Tudo nao substitui o que ja funciona. <b>Complementa.</b><br/>"
        "Integramo-nos com o software que ja utiliza e automatizamos o que consome tempo sem gerar valor.",
        ParagraphStyle('h6d', fontName='Helvetica', fontSize=11,
                      textColor=GRAPHITE, leading=17, spaceAfter=16)))

    # Timeline
    for week, title, desc, color in [
        ("SEMANA 1", "Diagnostico gratuito dos fluxos do gabinete",
         "Mapeamos processos, identificamos bottlenecks, calculamos o retorno esperado.", PURPLE),
        ("SEMANAS 2-3", "Configuracao e integracao com os seus sistemas",
         "Ligamos a automacao ao software que ja utiliza — sem interrupcoes.", GRAPHITE),
        ("SEMANA 4", "Teste paralelo com dados reais",
         "Corremos em paralelo para validar resultados antes de activar.", AMBER),
        ("MES 2", "Operacao em pleno com acompanhamento",
         "Monitorizacao continua e ajustes para maximizar resultados.", GREEN),
    ]:
        step = Table([[
            Paragraph(
                f"<font color='{color.hexval()}' size='8'><b>{week}</b></font><br/>"
                f"<font size='12'><b>{title}</b></font><br/>"
                f"<font color='#6B7280' size='9'>{desc}</font>",
                ParagraphStyle(f'tw_{week}', fontName='Helvetica', fontSize=12,
                              textColor=GRAPHITE, leading=16))
        ]], colWidths=[W])
        step.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), CLOUD),
            ('LINEBEFORE', (0,0), (0,0), 3, color),
            ('TOPPADDING', (0,0), (-1,-1), 12),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
            ('LEFTPADDING', (0,0), (-1,-1), 16),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ]))
        story.append(step)
        story.append(Spacer(1, 6))

    # Compativel com
    compat = Table([[
        Paragraph("<font size='8'><b>COMPATIVEL COM</b></font>",
                  ParagraphStyle('cmp', fontSize=8, textColor=GRAY)),
        Paragraph("<font size='9'><b>Sage</b></font>",
                  ParagraphStyle('c1', fontSize=9, alignment=TA_CENTER, textColor=GRAPHITE)),
        Paragraph("<font size='9'><b>PHC</b></font>",
                  ParagraphStyle('c2', fontSize=9, alignment=TA_CENTER, textColor=GRAPHITE)),
        Paragraph("<font size='9'><b>Primavera</b></font>",
                  ParagraphStyle('c3', fontSize=9, alignment=TA_CENTER, textColor=GRAPHITE)),
        Paragraph("<font size='9'><b>Moloni</b></font>",
                  ParagraphStyle('c4', fontSize=9, alignment=TA_CENTER, textColor=GRAPHITE)),
        Paragraph("<font size='9'><b>+ outros</b></font>",
                  ParagraphStyle('c5', fontSize=9, alignment=TA_CENTER, textColor=GRAY)),
    ]], colWidths=[W*0.22, W*0.15, W*0.15, W*0.18, W*0.15, W*0.15])
    compat.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), CLOUD),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LINEBEFORE', (1,0), (-1,0), 0.5, GRAY_LT),
    ]))
    story.append(Spacer(1, 6))
    story.append(compat)
    story.append(Spacer(1, 8))

    # Banner
    banner = Table([[
        Paragraph(
            "<font color='#1A1A2E'><b>Sem disrupcao. Sem paragens. Sem curvas de aprendizagem dolorosas.</b></font>",
            ParagraphStyle('bn', fontName='Helvetica-Bold', fontSize=10,
                          alignment=TA_CENTER, textColor=GRAPHITE))
    ]], colWidths=[W])
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GREEN_BG),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(banner)

    # ══════════════════════════════════════════
    # P7: MAPEAMENTO DOR → SOLUCAO (light)
    # ══════════════════════════════════════════
    story.append(PageBreak())

    story.append(Paragraph(
        "Mapeamento Dor → Solucao",
        ParagraphStyle('h7', fontName='Helvetica-Bold', fontSize=22,
                      textColor=GRAPHITE, leading=28, spaceAfter=6)))
    story.append(Paragraph(
        "Cada solucao resolve uma dor especifica. Sem promessas vagas. Sem jargao tecnico.",
        ParagraphStyle('h7d', fontName='Helvetica', fontSize=11,
                      textColor=GRAY, leading=17, spaceAfter=14)))

    # Header row
    map_header = Table([[
        Paragraph("<font size='8'><b>DOR DO GABINETE</b></font>",
                  ParagraphStyle('mh1', fontSize=8, textColor=GRAY)),
        Paragraph("", ParagraphStyle('mha', fontSize=8)),
        Paragraph("<font size='8'><b>SOLUCAO PERCEP TUDO</b></font>",
                  ParagraphStyle('mh2', fontSize=8, textColor=GRAY)),
        Paragraph("<font size='8'><b>RESULTADO</b></font>",
                  ParagraphStyle('mh3', fontSize=8, textColor=GRAY)),
    ]], colWidths=[W*0.30, W*0.08, W*0.32, W*0.30])
    map_header.setStyle(TableStyle([
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(map_header)

    # Mapping rows
    for dor, sol, resultado in [
        ("Tarefas manuais repetitivas", "Automacao Inteligente", "-60% tempo transacional"),
        ("Escassez de talento", "Automacao + Capacitacao", "1 pessoa = 1,5 pessoas"),
        ("Fecho mensal demorado", "Automacao + Analise", "Ate 56% mais rapido"),
        ("Risco de multas AT", "Agentes IA", "Zero infracoes"),
        ("Recolha de documentos", "Agentes IA + Automacao", "Documentos organizados"),
    ]:
        row = Table([[
            Paragraph(f"<font size='10'>{dor}</font>",
                      ParagraphStyle(f'md_{dor[:8]}', fontSize=10, textColor=GRAPHITE)),
            Paragraph("<font size='10' color='#6B7280'>→</font>",
                      ParagraphStyle(f'ma_{dor[:8]}', fontSize=10, alignment=TA_CENTER, textColor=GRAY)),
            Paragraph(f"<font size='10' color='#7B2FF2'><b>{sol}</b></font>",
                      ParagraphStyle(f'ms_{dor[:8]}', fontSize=10, textColor=PURPLE)),
            Paragraph(f"<font size='9'><b>{resultado}</b></font>",
                      ParagraphStyle(f'mr_{dor[:8]}', fontSize=9, textColor=GRAPHITE)),
        ]], colWidths=[W*0.30, W*0.08, W*0.32, W*0.30])
        row.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), WHITE),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 12),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('LINEBELOW', (0,0), (-1,0), 0.5, GRAY_LT),
        ]))
        story.append(row)

    story.append(Spacer(1, 16))

    # 6 servicos
    servicos = Table([
        [Paragraph("<font size='10'><b>Os 6 servicos da Percep Tudo</b></font>",
                   ParagraphStyle('sv_h', fontSize=10, textColor=GRAPHITE))],
        [Table([[
            Paragraph("<font size='9'>● Automacao Inteligente</font>", ParagraphStyle('sv1', fontSize=9, textColor=GRAPHITE)),
            Paragraph("<font size='9'>● Analise de Dados</font>", ParagraphStyle('sv2', fontSize=9, textColor=GRAPHITE)),
        ]], colWidths=[W/2, W/2])],
        [Table([[
            Paragraph("<font size='9'>● Marketing com IA</font>", ParagraphStyle('sv3', fontSize=9, textColor=GRAPHITE)),
            Paragraph("<font size='9'>● Agentes de IA Personalizados</font>", ParagraphStyle('sv4', fontSize=9, textColor=GRAPHITE)),
        ]], colWidths=[W/2, W/2])],
        [Table([[
            Paragraph("<font size='9'>● Capacitacao de Equipa</font>", ParagraphStyle('sv5', fontSize=9, textColor=GRAPHITE)),
            Paragraph("<font size='9'>● Diagnostico Estrategico</font>", ParagraphStyle('sv6', fontSize=9, textColor=GRAPHITE)),
        ]], colWidths=[W/2, W/2])],
    ], colWidths=[W])
    servicos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), CLOUD),
        ('TOPPADDING', (0,0), (0,0), 14),
        ('TOPPADDING', (0,1), (-1,-1), 4),
        ('BOTTOMPADDING', (0,-1), (-1,-1), 14),
        ('LEFTPADDING', (0,0), (-1,-1), 16),
    ]))
    story.append(servicos)

    # ══════════════════════════════════════════
    # P8: CUSTO DE NAO AGIR (light)
    # ══════════════════════════════════════════
    story.append(PageBreak())

    story.append(Paragraph(
        "O custo de nao agir e maior do que o custo de agir.",
        ParagraphStyle('h8', fontName='Helvetica-Bold', fontSize=22,
                      textColor=GRAPHITE, leading=28, spaceAfter=16)))

    # Comparison table
    comp = Table([
        [Paragraph("<font color='#E53E3E' size='9'><b>✗  SEM IA</b></font>",
                   ParagraphStyle('ch1', fontSize=9)),
         Paragraph("<font color='#00E5A0' size='9'><b>✓  COM PERCEP TUDO</b></font>",
                   ParagraphStyle('ch2', fontSize=9))],
        [Paragraph("Tempo em tarefas repetitivas  <font color='#E53E3E'><b>60-70%</b></font>",
                   ParagraphStyle('cr1', fontSize=10, textColor=GRAPHITE)),
         Paragraph("Tempo em tarefas repetitivas  <font color='#00E5A0'><b>25-30%</b></font>",
                   ParagraphStyle('cr1b', fontSize=10, textColor=GRAPHITE))],
        [Paragraph("Fecho mensal  <font color='#E53E3E'><b>9 dias</b></font>",
                   ParagraphStyle('cr2', fontSize=10, textColor=GRAPHITE)),
         Paragraph("Fecho mensal  <font color='#00E5A0'><b>4 dias</b></font>",
                   ParagraphStyle('cr2b', fontSize=10, textColor=GRAPHITE))],
        [Paragraph("Multas AT/ano  <font color='#E53E3E'><b>2-4</b></font>",
                   ParagraphStyle('cr3', fontSize=10, textColor=GRAPHITE)),
         Paragraph("Multas AT/ano  <font color='#00E5A0'><b>Zero</b></font>",
                   ParagraphStyle('cr3b', fontSize=10, textColor=GRAPHITE))],
        [Paragraph("Capacidade/colaborador  <font color='#E53E3E'><b>1x</b></font>",
                   ParagraphStyle('cr4', fontSize=10, textColor=GRAPHITE)),
         Paragraph("Capacidade/colaborador  <font color='#00E5A0'><b>1,3-1,5x</b></font>",
                   ParagraphStyle('cr4b', fontSize=10, textColor=GRAPHITE))],
    ], colWidths=[W/2, W/2])
    comp.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), RED_BG),
        ('BACKGROUND', (1,0), (1,-1), GREEN_BG),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 14),
        ('LINEBELOW', (0,1), (-1,-2), 0.5, GRAY_LT),
    ]))
    story.append(comp)
    story.append(Spacer(1, 14))

    # Big numbers
    big_nums = Table([[
        Paragraph(
            "<font color='#F2A900' size='28'><b>28-74K EUR</b></font><br/>"
            "<font color='#FFFFFF' size='8'>POUPANCA ANUAL<br/>DOCUMENTADA</font>",
            ParagraphStyle('bn1', fontSize=10, alignment=TA_CENTER, leading=14)),
        Paragraph(
            "<font color='#00E5A0' size='28'><b>3-6</b></font><br/>"
            "<font color='#FFFFFF' size='8'>MESES DE PAYBACK</font>",
            ParagraphStyle('bn2', fontSize=10, alignment=TA_CENTER, leading=14)),
        Paragraph(
            "<font color='#7B2FF2' size='28'><b>96%</b></font><br/>"
            "<font color='#FFFFFF' size='8'>CLIENTES ESCALAM<br/>APOS PILOTO</font>",
            ParagraphStyle('bn3', fontSize=10, alignment=TA_CENTER, leading=14)),
    ]], colWidths=[W/3, W/3, W/3])
    big_nums.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRAPHITE),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 18),
        ('BOTTOMPADDING', (0,0), (-1,-1), 18),
    ]))
    story.append(big_nums)
    story.append(Spacer(1, 12))

    # Nota
    nota = Table([[
        Paragraph(
            f"<i>No diagnostico gratuito, calculamos os numeros exactos para a "
            f"<font color='#F2A900'><b>{nome}</b></font>.</i>",
            ParagraphStyle('nota', fontName='Helvetica', fontSize=10,
                          textColor=GRAY, alignment=TA_CENTER))
    ]], colWidths=[W])
    nota.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), CLOUD),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(nota)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_LT, spaceAfter=6))
    story.append(Paragraph(
        "<font color='#999999' size='7'>Fontes: IDC Portugal • Fed Finance 2026 • McKinsey "
        "• Dados internos Percep Tudo</font>",
        ParagraphStyle('src8', fontSize=7, textColor=GRAY_D)))

    story.append(NextPageTemplate('dark'))

    # ══════════════════════════════════════════
    # P9: CTA (dark)
    # ══════════════════════════════════════════
    story.append(PageBreak())

    story.append(Spacer(1, 2*cm))

    story.append(Paragraph(
        "Os gabinetes que comecaram a automatizar ha 6 meses ja estao a fechar "
        "contas em 4 dias e a aceitar mais clientes sem contratar.",
        ParagraphStyle('cta1', fontName='Helvetica', fontSize=12,
                      textColor=GRAY_D, leading=18, spaceAfter=16)))

    story.append(Paragraph(
        "<font color='#F2A900'><b>O seu concorrente ja comecou.</b></font>",
        ParagraphStyle('cta2', fontName='Helvetica-Bold', fontSize=22,
                      textColor=AMBER, leading=28, spaceAfter=20)))

    # Botao agendar
    cta_btn = Table([[
        Paragraph(
            "<font color='#1A1A2E'><b>Agendar Diagnostico Gratuito — 30 min</b></font>",
            ParagraphStyle('btn', fontName='Helvetica-Bold', fontSize=12,
                          alignment=TA_CENTER, textColor=GRAPHITE))
    ]], colWidths=[W*0.6])
    cta_btn.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), AMBER),
        ('TOPPADDING', (0,0), (-1,-1), 14),
        ('BOTTOMPADDING', (0,0), (-1,-1), 14),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(cta_btn)
    story.append(Spacer(1, 16))

    story.append(Paragraph(
        f"Sem compromisso. Sem jargao. Analisamos os processos da "
        f"<font color='#F2A900'><b>{nome}</b></font> e mostramos exactamente "
        f"onde pode poupar — com numeros.",
        ParagraphStyle('cta3', fontName='Helvetica', fontSize=11,
                      textColor=GRAY_D, leading=17, spaceAfter=24)))

    # Contactos
    story.append(Paragraph(
        "<font color='#00E5A0'>WhatsApp:</font> <font color='#D0D0D0'>+351 910 104 835</font>"
        "     <font color='#00E5A0'>Email:</font> <font color='#D0D0D0'>perceptudo@gmail.com</font>",
        ParagraphStyle('ct1', fontName='Helvetica', fontSize=10, leading=16, spaceAfter=6)))
    story.append(Paragraph(
        "<font color='#00E5A0'>Web:</font> <font color='#D0D0D0'>perceptudo.vercel.app</font>",
        ParagraphStyle('ct2', fontName='Helvetica', fontSize=10, leading=16, spaceAfter=24)))

    # Logo footer
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph(
        '<font name="Helvetica" size="16" color="#F5F2ED">Percep </font>'
        '<font name="Helvetica-Bold" size="16" color="#7B2FF2">Tudo</font>'
        '     <font name="Helvetica" size="8" color="#6B7280">perceptudo.vercel.app</font>',
        ParagraphStyle('logo_ft', fontSize=16, leading=20)))

    doc.build(story)
    return str(Path(output_path).resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nome", default="Gabinete Exemplo")
    parser.add_argument("--output", "-o", default="output/teste-contabilidade.pdf")
    args = parser.parse_args()
    data = {"nome": args.nome, "sector": "contabilidade"}
    print(f"PDF gerado: {generate_contabilidade_pdf(data, args.output)}")
