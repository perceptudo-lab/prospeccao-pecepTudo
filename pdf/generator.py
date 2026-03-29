#!/usr/bin/env python3
"""
PercepTudo — PDF Diagnostic Generator (Bold A4 Template)

TEMPLATE OFICIAL. Nao recriar — usar este ficheiro.

Uso como modulo:
    from pdf.generator import generate_pdf
    generate_pdf(data_dict, "output/diagnostico.pdf")

Uso via CLI:
    python -m pdf.generator --input data.json --output diagnostico.pdf
"""

import json
import re
import sys
import argparse
from pathlib import Path

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
PURPLE_10 = HexColor("#EDE5FF")
AMBER = HexColor("#F2A900")
GREEN = HexColor("#00E5A0")
GREEN_BG = HexColor("#E6FFF2")
CLOUD = HexColor("#F5F2ED")
GRAPHITE = HexColor("#1A1A2E")
DARK2 = HexColor("#222238")
GRAY = HexColor("#6B7280")
GRAY_LT = HexColor("#E5E2DD")
WHITE = HexColor("#FFFFFF")

PAGE_W, PAGE_H = A4
M = 2 * cm
W = PAGE_W - 2 * M


def _clean_eur(value: str) -> str:
    return str(value).replace("EUR", "").replace("€", "").strip()


def _extract_ig(ig: str) -> str:
    if not ig or ig in ("N/A", "Sem perfil Instagram", "Sem perfil", "Nao", "Não"):
        return "N/A"
    m = re.search(r'[\d.]+k?', str(ig), re.IGNORECASE)
    return m.group() if m else "N/A"


def _dark_bg(c, doc):
    c.saveState()
    c.setFillColor(GRAPHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(PURPLE)
    for x in range(0, int(PAGE_W), 18):
        for y in range(0, int(PAGE_H), 18):
            c.setFillAlpha(0.04)
            c.circle(x, y, 0.7, fill=1, stroke=0)
    c.setFillAlpha(1)
    c.setFont('Helvetica', 7)
    c.setFillColor(GRAY)
    c.drawString(M, 0.7*cm, "PercepTudo — Inteligencia Aplicada  |  Confidencial")
    c.drawRightString(PAGE_W - M, 0.7*cm, f"{doc.page}")
    c.restoreState()


def _light_bg(c, doc):
    c.saveState()
    c.setFillColor(CLOUD)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(PURPLE)
    c.rect(0, PAGE_H - 4, PAGE_W * 0.12, 4, fill=1, stroke=0)
    c.setFont('Helvetica', 7)
    c.setFillColor(GRAY)
    c.drawString(M, 0.7*cm, "PercepTudo — Inteligencia Aplicada  |  Confidencial")
    c.drawRightString(PAGE_W - M, 0.7*cm, f"{doc.page}")
    c.restoreState()


def _white_bg(c, doc):
    c.saveState()
    c.setFillColor(PURPLE)
    c.rect(0, PAGE_H - 4, PAGE_W * 0.12, 4, fill=1, stroke=0)
    c.setFont('Helvetica', 7)
    c.setFillColor(GRAY)
    c.drawString(M, 0.7*cm, "PercepTudo — Inteligencia Aplicada  |  Confidencial")
    c.drawRightString(PAGE_W - M, 0.7*cm, f"{doc.page}")
    c.restoreState()


def _cover_bg(c, doc):
    c.saveState()
    c.setFillColor(GRAPHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(PURPLE)
    c.setFillAlpha(0.12)
    c.circle(PAGE_W - 2.5*cm, PAGE_H - 3*cm, 5*cm, fill=1, stroke=0)
    c.setFillAlpha(0.06)
    c.circle(PAGE_W - 7*cm, 3.5*cm, 2.5*cm, fill=1, stroke=0)
    c.setFillAlpha(1)
    c.setStrokeColor(PURPLE)
    c.setLineWidth(3)
    c.line(M, PAGE_H * 0.35, M + 3*cm, PAGE_H * 0.35)
    c.restoreState()


def generate_pdf(data: dict, output_path: str) -> str:
    """Gera PDF de diagnostico com branding PercepTudo. Retorna path absoluto."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    D = data

    doc = BaseDocTemplate(output_path, pagesize=A4,
        leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=1.8*cm)

    doc.addPageTemplates([
        PageTemplate('cover', frames=Frame(M, M, W, PAGE_H-2*M, id='fc'), onPage=_cover_bg),
        PageTemplate('dark', frames=Frame(M, 1.8*cm, W, PAGE_H-3.5*cm, id='fd'), onPage=_dark_bg),
        PageTemplate('light', frames=Frame(M, 1.8*cm, W, PAGE_H-3.5*cm, id='fl'), onPage=_light_bg),
        PageTemplate('white', frames=Frame(M, 1.8*cm, W, PAGE_H-3.5*cm, id='fw'), onPage=_white_bg),
    ])

    story = []

    # ══════ P1: CAPA (dark) ══════
    story.append(Spacer(1, 5.5*cm))
    story.append(Paragraph(
        '<font name="Helvetica" color="#F5F2ED" size="24">percep</font>'
        '<font name="Helvetica-Bold" color="#7B2FF2" size="24">Tudo</font>',
        ParagraphStyle('logo', fontSize=24, leading=28, spaceAfter=2)))
    story.append(Paragraph("INTELIGENCIA APLICADA",
        ParagraphStyle('ia', fontName='Helvetica', fontSize=8, textColor=GRAY, spaceAfter=32)))
    story.append(Paragraph("Diagnostico de<br/>Inteligencia Aplicada",
        ParagraphStyle('ht', fontName='Helvetica-Bold', fontSize=28, textColor=WHITE, leading=34, spaceAfter=10)))
    story.append(Paragraph(D['nome'],
        ParagraphStyle('cn', fontName='Helvetica-Bold', fontSize=20, textColor=PURPLE, leading=24, spaceAfter=24)))
    story.append(Paragraph("Marco 2026  |  Confidencial",
        ParagraphStyle('dt', fontName='Helvetica', fontSize=10, textColor=GRAY)))
    story.append(NextPageTemplate('light'))

    # ══════ P2: QUEM SOMOS (light) ══════
    story.append(PageBreak())
    story.append(Paragraph("QUEM SOMOS", ParagraphStyle('sl', fontName='Helvetica-Bold', fontSize=8, textColor=PURPLE, spaceAfter=4)))
    story.append(Paragraph("IA que seu negocio entende.", ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=26, textColor=GRAPHITE, leading=32, spaceAfter=10)))
    story.append(Paragraph(
        "A PercepTudo traduz inteligencia artificial em resultado real para empresas. "
        "Sem jargao, sem teoria — um processo de cada vez, com resultado que voce mede em semanas.",
        ParagraphStyle('bd', fontName='Helvetica', fontSize=11, textColor=GRAY, leading=17, spaceAfter=16, alignment=TA_JUSTIFY)))

    for title, desc in [
        ("Resultado em Semanas", "Projetos piloto com impacto mensuravel em 30 dias."),
        ("Zero Jargao", "Falamos de faturamento e eficiencia, nao de algoritmos."),
        ("Processo que Roda", "Nao vendemos relatorio — entregamos processo funcionando."),
    ]:
        card = Table([[Paragraph(
            f"<font color='#7B2FF2' size='12'><b>{title}</b></font><br/>"
            f"<font color='#6B7280' size='9'>{desc}</font>",
            ParagraphStyle('vp', fontSize=10, leading=16, textColor=GRAPHITE))]], colWidths=[W])
        card.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), WHITE), ('LINEBEFORE', (0,0), (0,0), 4, PURPLE),
            ('TOPPADDING', (0,0), (-1,-1), 12), ('BOTTOMPADDING', (0,0), (-1,-1), 12),
            ('LEFTPADDING', (0,0), (-1,-1), 16), ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ]))
        story.append(card)
        story.append(Spacer(1, 6))
    story.append(NextPageTemplate('white'))

    # ══════ P3: ANALISE (white) ══════
    story.append(PageBreak())
    story.append(Paragraph("ANALISE", ParagraphStyle('sl2', fontName='Helvetica-Bold', fontSize=8, textColor=PURPLE, spaceAfter=4)))
    story.append(Paragraph("O que encontramos", ParagraphStyle('h1b', fontName='Helvetica-Bold', fontSize=26, textColor=GRAPHITE, leading=32, spaceAfter=14)))

    ig_val = _extract_ig(D.get('instagram', ''))
    met_cells = []
    for val, label, color, bg in [
        (str(D.get('rating', 'N/A')), "Rating Google", AMBER, HexColor("#FFF8E8")),
        (str(D.get('nReviews', D.get('n_reviews', 'N/A'))), "Avaliacoes", PURPLE, PURPLE_10),
        (ig_val, "Instagram", GREEN, GREEN_BG),
    ]:
        met_cells.append(Paragraph(
            f"<font size='32' color='{color.hexval()}'><b>{val}</b></font><br/><br/>"
            f"<font size='10' color='#6B7280'>{label}</font>",
            ParagraphStyle(f'm_{label}', fontSize=10, alignment=TA_CENTER, leading=18, spaceBefore=4, spaceAfter=4)))

    mt = Table([met_cells], colWidths=[W/3]*3)
    mt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), HexColor("#FFF8E8")), ('BACKGROUND', (1,0), (1,0), PURPLE_10),
        ('BACKGROUND', (2,0), (2,0), GREEN_BG), ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('TOPPADDING', (0,0), (-1,-1), 20),
        ('BOTTOMPADDING', (0,0), (-1,-1), 16), ('LINEBEFORE', (1,0), (1,0), 0.5, GRAY_LT),
        ('LINEBEFORE', (2,0), (2,0), 0.5, GRAY_LT),
    ]))
    story.append(mt)
    story.append(Spacer(1, 16))

    resumo = D.get('resumo', D.get('diagnostico', ''))
    sum_rows = [
        [Paragraph("<font color='#7B2FF2'><b>Resumo da Analise</b></font>", ParagraphStyle('rh', fontName='Helvetica-Bold', fontSize=13, textColor=PURPLE, leading=18))],
        [Paragraph(f"<font color='#D0D0D0'>{resumo}</font>", ParagraphStyle('rb', fontName='Helvetica', fontSize=10, textColor=HexColor("#D0D0D0"), leading=16))],
        [Paragraph(f"<font color='#00E5A0'>&#10003;</font> <font color='#D0D0D0'><b>Sector:</b> {D.get('sector','N/A')}</font>    "
                   f"<font color='#00E5A0'>&#10003;</font> <font color='#D0D0D0'><b>Localizacao:</b> {D.get('cidade','N/A')}</font>", ParagraphStyle('d1', fontSize=9, leading=14))],
        [Paragraph(f"<font color='#00E5A0'>&#10003;</font> <font color='#D0D0D0'><b>Website:</b> {D.get('website','N/A')}</font>    "
                   f"<font color='#00E5A0'>&#10003;</font> <font color='#D0D0D0'><b>Instagram:</b> {D.get('instagram','N/A')}</font>", ParagraphStyle('d2', fontSize=9, leading=14))],
    ]
    st = Table(sum_rows, colWidths=[W])
    st.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), GRAPHITE),
        ('TOPPADDING', (0,0), (0,0), 16), ('TOPPADDING', (0,1), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,-1), (0,-1), 16),
        ('LEFTPADDING', (0,0), (-1,-1), 20), ('RIGHTPADDING', (0,0), (-1,-1), 20),
    ]))
    story.append(st)
    story.append(NextPageTemplate('light'))

    # ══════ P4: OPORTUNIDADES (light) ══════
    story.append(PageBreak())
    story.append(Paragraph("OPORTUNIDADES", ParagraphStyle('sl3', fontName='Helvetica-Bold', fontSize=8, textColor=PURPLE, spaceAfter=4)))
    story.append(Paragraph("Onde a IA pode impulsionar", ParagraphStyle('h1c', fontName='Helvetica-Bold', fontSize=26, textColor=GRAPHITE, leading=32, spaceAfter=14)))

    for i, op in enumerate(D.get('oportunidades', [])[:4], 1):
        imp = op.get('impacto', 'MEDIO')
        imp_color = '#00E5A0' if imp == 'ALTO' else '#F2A900'
        imp_bg = GREEN_BG if imp == 'ALTO' else HexColor("#FFF8E8")
        titulo = op.get('titulo', '')
        desc = op.get('desc', op.get('descricao', ''))
        card = Table([
            [Paragraph(f"<font size='20' color='#7B2FF2'><b>0{i}</b></font>", ParagraphStyle(f'on{i}', fontSize=20, alignment=TA_CENTER)),
             Paragraph(f"<font size='12'><b>{titulo}</b></font>", ParagraphStyle(f'ot{i}', fontName='Helvetica-Bold', fontSize=12, textColor=GRAPHITE, leading=16)),
             Paragraph(f"<font size='9' color='{imp_color}'><b>{imp}</b></font>", ParagraphStyle(f'oi{i}', fontSize=9, alignment=TA_CENTER))],
            [Paragraph("", ParagraphStyle('e1', fontSize=1)),
             Paragraph(f"<font color='#6B7280' size='9'>{desc}</font>", ParagraphStyle(f'od{i}', fontSize=9, textColor=GRAY, leading=14)),
             Paragraph("", ParagraphStyle('e2', fontSize=1))],
        ], colWidths=[1.2*cm, W-3.4*cm, 2.2*cm])
        card.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), WHITE), ('BACKGROUND', (2,0), (2,0), imp_bg),
            ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,-1), (-1,-1), 12), ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10), ('LINEBEFORE', (0,0), (0,-1), 4, PURPLE),
            ('LINEBELOW', (0,0), (-1,0), 0.5, GRAY_LT), ('SPAN', (2,0), (2,1)),
        ]))
        story.append(KeepTogether([card, Spacer(1, 8)]))
    story.append(NextPageTemplate('white'))

    # ══════ P5: SOLUCOES (white) ══════
    story.append(PageBreak())
    story.append(Paragraph("SOLUCOES", ParagraphStyle('sl4', fontName='Helvetica-Bold', fontSize=8, textColor=PURPLE, spaceAfter=4)))
    story.append(Paragraph("O que implementamos", ParagraphStyle('h1d', fontName='Helvetica-Bold', fontSize=26, textColor=GRAPHITE, leading=32, spaceAfter=14)))

    for sol in D.get('solucoes', [])[:3]:
        titulo = sol.get('titulo', '')
        desc = sol.get('desc', sol.get('descricao', ''))
        prazo = sol.get('prazo', '')
        st2 = Table([
            [Paragraph(f"<font size='13'><b>{titulo}</b></font>", ParagraphStyle('stt', fontName='Helvetica-Bold', fontSize=13, textColor=GRAPHITE, leading=18)),
             Paragraph(f"<font color='#7B2FF2' size='11'><b>{prazo}</b></font>", ParagraphStyle('stp', fontName='Helvetica-Bold', fontSize=11, textColor=PURPLE, alignment=TA_RIGHT))],
            [Paragraph(f"<font color='#6B7280' size='10'>{desc}</font>", ParagraphStyle('std', fontSize=10, textColor=GRAY, leading=15)),
             Paragraph("", ParagraphStyle('e', fontSize=1))],
        ], colWidths=[W*0.72, W*0.28])
        st2.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), CLOUD), ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,0), 14), ('BOTTOMPADDING', (0,-1), (-1,-1), 14),
            ('LEFTPADDING', (0,0), (-1,-1), 16), ('RIGHTPADDING', (0,0), (-1,-1), 16),
            ('LINEBELOW', (0,0), (-1,0), 0.5, GRAY_LT),
        ]))
        story.append(KeepTogether([st2, Spacer(1, 8)]))

    story.append(Paragraph("<i>Prazos estimados apos validacao em reuniao de diagnostico.</i>",
        ParagraphStyle('fn', fontName='Helvetica', fontSize=8, textColor=GRAY)))
    story.append(NextPageTemplate('dark'))

    # ══════ P6: ROI (dark) ══════
    story.append(PageBreak())
    story.append(Paragraph("<font color='#00E5A0'>IMPACTO ESTIMADO</font>", ParagraphStyle('sl5', fontName='Helvetica-Bold', fontSize=8, spaceAfter=4)))
    story.append(Paragraph("<font color='#FFFFFF'>O que muda no seu negocio</font>", ParagraphStyle('h1e', fontName='Helvetica-Bold', fontSize=26, leading=32, spaceAfter=14)))

    roi = D.get('roi', {})
    pm = _clean_eur(roi.get('poupancaMensal', roi.get('poupanca_mensal', 'N/A')))
    pa = _clean_eur(roi.get('poupancaAnual', roi.get('poupanca_anual', 'N/A')))
    ch = _clean_eur(roi.get('custoHora', roi.get('custo_hora', 'N/A')))
    hs = str(roi.get('horasSemana', roi.get('horas_semana', 'N/A')))
    hp = str(roi.get('horasPoupadas', roi.get('horas_poupadas', 'N/A')))
    hd = roi.get('horasDesc', roi.get('horas_desc', ''))
    be = roi.get('beneficiosExtra', roi.get('beneficios_extra', []))

    ia_ben = "<br/>".join([f"<font color='#00E5A0'>&#10003;</font> <font color='#D0D0D0' size='9'>{b}</font>" for b in be])

    rt = Table([[
        Paragraph(f"<font color='#6B7280' size='9'><b>HOJE</b></font><br/><br/>"
                  f"<font color='#F2A900' size='34'><b>{hs}h</b></font><br/>"
                  f"<font color='#6B7280' size='10'>por semana</font><br/><br/>"
                  f"<font color='#999999' size='9'>{hd}</font><br/><br/>"
                  f"<font color='#999999' size='9'>{ch} EUR/hora</font>",
                  ParagraphStyle('rh2', fontSize=10, alignment=TA_CENTER, leading=16)),
        Paragraph(f"<font color='#00E5A0' size='9'><b>COM INTELIGENCIA APLICADA</b></font><br/><br/>"
                  f"<font color='#00E5A0' size='34'><b>{hp}h</b></font><br/>"
                  f"<font color='#D0D0D0' size='10'>poupadas/semana</font><br/><br/>"
                  f"{ia_ben}",
                  ParagraphStyle('ri2', fontSize=10, alignment=TA_LEFT, leading=16, leftIndent=16)),
    ]], colWidths=[W/2, W/2])
    rt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), DARK2), ('BACKGROUND', (1,0), (1,0), HexColor("#2A2A48")),
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('TOPPADDING', (0,0), (-1,-1), 20),
        ('BOTTOMPADDING', (0,0), (-1,-1), 20), ('LEFTPADDING', (0,0), (-1,-1), 14),
        ('RIGHTPADDING', (0,0), (-1,-1), 14),
    ]))
    story.append(rt)
    story.append(Spacer(1, 8))

    sv = Table([[Paragraph(
        f"<font color='#FFFFFF'><b>Poupanca estimada: {pm} EUR/mes  |  {pa} EUR/ano</b></font>",
        ParagraphStyle('sv', fontName='Helvetica-Bold', fontSize=13, alignment=TA_CENTER, textColor=WHITE))
    ]], colWidths=[W])
    sv.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), PURPLE), ('TOPPADDING', (0,0), (-1,-1), 14), ('BOTTOMPADDING', (0,0), (-1,-1), 14)]))
    story.append(sv)
    story.append(Spacer(1, 8))
    story.append(Paragraph("<font color='#6B7280'><i>* Estimativa baseada na analise publica. Valores reais definidos apos diagnostico.</i></font>", ParagraphStyle('disc', fontSize=8)))
    story.append(NextPageTemplate('light'))

    # ══════ P7: CTA (light) ══════
    story.append(PageBreak())
    story.append(Paragraph("PROXIMO PASSO", ParagraphStyle('sl6', fontName='Helvetica-Bold', fontSize=8, textColor=PURPLE, spaceAfter=4)))
    story.append(Paragraph("Vamos conversar?", ParagraphStyle('h1f', fontName='Helvetica-Bold', fontSize=26, textColor=GRAPHITE, leading=32, spaceAfter=10)))
    story.append(Paragraph(
        f"Esta analise e apenas o ponto de partida. Numa reuniao de 30 minutos, "
        f"podemos aprofundar o diagnostico e definir um plano concreto para o {D['nome']}.",
        ParagraphStyle('ctb', fontName='Helvetica', fontSize=11, textColor=GRAY, leading=17, spaceAfter=16)))

    for num, title, desc in [
        ("01", "Reuniao de Diagnostico", "30 min por videochamada para entender o negocio a fundo"),
        ("02", "Proposta Personalizada", "Plano detalhado com prazos, custos e resultados esperados"),
        ("03", "Implementacao Rapida", "Primeiro resultado visivel em 2-4 semanas"),
    ]:
        stp = Table([[
            Paragraph(f"<font size='22' color='#7B2FF2'><b>{num}</b></font>", ParagraphStyle(f'sn{num}', fontSize=22, alignment=TA_CENTER)),
            Paragraph(f"<font size='12'><b>{title}</b></font><br/><font size='9' color='#6B7280'>{desc}</font>",
                      ParagraphStyle(f'sd{num}', fontName='Helvetica', fontSize=12, textColor=GRAPHITE, leading=17)),
        ]], colWidths=[1.5*cm, W-1.5*cm])
        stp.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), WHITE), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 10), ('BOTTOMPADDING', (0,0), (-1,-1), 10), ('LEFTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(stp)
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="40%", thickness=3, color=PURPLE, spaceAfter=14))
    story.append(Paragraph(
        '<font name="Helvetica" size="20" color="#1A1A2E">percep</font>'
        '<font name="Helvetica-Bold" size="20" color="#7B2FF2">Tudo</font>'
        '   <font name="Helvetica" size="8" color="#6B7280">INTELIGENCIA APLICADA</font>',
        ParagraphStyle('lg', fontSize=20, leading=24, spaceAfter=8)))
    story.append(Paragraph("perceptudo@gmail.com  |  +351 910 104 835  |  perceptudo.vercel.app",
        ParagraphStyle('ct', fontName='Helvetica', fontSize=10, textColor=GRAY, spaceAfter=8)))

    cta = Table([[Paragraph(
        "<font color='#FFFFFF'><b>Agende sua reuniao:  cal.com/perceptudo/diagnostico</b></font>",
        ParagraphStyle('cta', fontName='Helvetica-Bold', fontSize=11, alignment=TA_CENTER, textColor=WHITE))
    ]], colWidths=[W])
    cta.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), PURPLE), ('TOPPADDING', (0,0), (-1,-1), 12), ('BOTTOMPADDING', (0,0), (-1,-1), 12)]))
    story.append(cta)
    story.append(Spacer(1, 12))
    story.append(Paragraph("<i>Enquanto outros explicam, a gente implementa.</i>",
        ParagraphStyle('tg', fontName='Helvetica-Oblique', fontSize=13, textColor=PURPLE, alignment=TA_CENTER)))

    doc.build(story)
    return str(Path(output_path).resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera PDF de diagnostico PercepTudo")
    parser.add_argument("--input", "-i", required=True, help="JSON com dados do lead")
    parser.add_argument("--output", "-o", required=True, help="Path para o PDF")
    args = parser.parse_args()
    with open(args.input, 'r') as f:
        data = json.load(f)
    print(f"PDF gerado: {generate_pdf(data, args.output)}")
