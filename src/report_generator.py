"""
src/report_generator.py
Gera relatório PDF de análise A/B e retorna (path, bytes).
"""

import io
import os
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

# ── CORES ─────────────────────────────────────────────────────────────────
C_ACCENT  = colors.HexColor("#378ADD")
C_GREEN   = colors.HexColor("#1D9E75")
C_RED     = colors.HexColor("#D85A30")
C_TEXT    = colors.HexColor("#E2E8F0")
C_MUTED   = colors.HexColor("#8BA7C7")
C_CARD    = colors.HexColor("#132236")
C_BORDER  = colors.HexColor("#1E3A5F")
C_BG      = colors.HexColor("#0B1929")
C_BG2     = colors.HexColor("#0F1E2E")
C_WINNER  = colors.HexColor("#0D2B1E")
C_DEC     = colors.HexColor("#0E1F35")

GROUP_COLORS = [
    colors.HexColor("#378ADD"),
    colors.HexColor("#1D9E75"),
    colors.HexColor("#D85A30"),
    colors.HexColor("#BA7517"),
    colors.HexColor("#534AB7"),
]

# ── FORMATTERS ────────────────────────────────────────────────────────────
def _brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(v)

def _pct(v):
    try:
        return f"{float(v)*100:.1f}%"
    except Exception:
        return str(v)

def _ratio(v):
    try:
        return f"{float(v):.2f}"
    except Exception:
        return str(v)

def _int(v):
    try:
        return f"{int(v):,}".replace(",", ".")
    except Exception:
        return str(v)

def _lift_str(v):
    try:
        v = float(v)
        sign = "+" if v >= 0 else ""
        return f"{sign}{v*100:.1f}%"
    except Exception:
        return "—"

# ── ESTILOS ───────────────────────────────────────────────────────────────
def _styles():
    return {
        "title":    ParagraphStyle("title",    fontSize=20, textColor=C_TEXT,  fontName="Helvetica-Bold",  spaceAfter=3,  leading=24),
        "subtitle": ParagraphStyle("subtitle", fontSize=10, textColor=C_MUTED, fontName="Helvetica",        spaceAfter=2),
        "section":  ParagraphStyle("section",  fontSize=12, textColor=C_ACCENT, fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=5),
        "body":     ParagraphStyle("body",     fontSize=9,  textColor=C_TEXT,  fontName="Helvetica",        leading=13,    spaceAfter=3),
        "small":    ParagraphStyle("small",    fontSize=8,  textColor=C_MUTED, fontName="Helvetica",        leading=11),
        "winner":   ParagraphStyle("winner",   fontSize=11, textColor=C_GREEN, fontName="Helvetica-Bold",   leading=15),
        "footer":   ParagraphStyle("footer",   fontSize=7,  textColor=C_MUTED, fontName="Helvetica",        alignment=TA_CENTER),
        "th":       ParagraphStyle("th",       fontSize=8,  textColor=C_MUTED, fontName="Helvetica-Bold",   alignment=TA_RIGHT),
        "td_left":  ParagraphStyle("td_left",  fontSize=9,  textColor=C_MUTED, fontName="Helvetica",        alignment=TA_LEFT),
        "td":       ParagraphStyle("td",       fontSize=9,  textColor=C_TEXT,  fontName="Helvetica-Bold",   alignment=TA_RIGHT),
        "lift_pos": ParagraphStyle("lift_pos", fontSize=9,  textColor=C_GREEN, fontName="Helvetica-Bold",   alignment=TA_RIGHT),
        "lift_neg": ParagraphStyle("lift_neg", fontSize=9,  textColor=C_RED,   fontName="Helvetica-Bold",   alignment=TA_RIGHT),
        "lift_neu": ParagraphStyle("lift_neu", fontSize=9,  textColor=C_MUTED, fontName="Helvetica",        alignment=TA_RIGHT),
        # estilos do glossário
        "glossary_title": ParagraphStyle("glossary_title", fontSize=9, textColor=C_TEXT, fontName="Helvetica-Bold", leading=13, spaceAfter=2),
        "glossary_body":  ParagraphStyle("glossary_body",  fontSize=8.5, textColor=C_MUTED, fontName="Helvetica", leading=12, spaceAfter=1),
    }

def _base_table_style():
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  C_BORDER),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_CARD, C_BG2]),
        ("GRID",          (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ])

# ── TABELA DE MÉTRICAS ────────────────────────────────────────────────────
METRIC_DEFS = [
    ("Compradores",        "buyers",               _int,   False),
    ("GMV",                "gmv",                  _brl,   False),
    ("Comissão",           "commission",            _brl,   False),
    ("Cashback (custo)",   "cashback",              _brl,   True),   # menor = melhor
    ("Receita líquida",    "net_revenue",           _brl,   False),
    ("ROI",                "roi",                   _ratio, False),
    ("Margem",             "margin",                _pct,   False),
    ("Ticket médio",       "avg_ticket",            _brl,   False),
    ("Cashback médio",     "avg_cashback",          _brl,   True),
    ("Comissão/comprador", "commission_per_buyer",  _brl,   False),
]

# ── GLOSSÁRIO DE MÉTRICAS ───────────────────────────────────────────────
# Cobre apenas as métricas que de fato aparecem na tabela hoje (as chaves
# que existem em compute_group_metrics: gmv, commission, cashback,
# net_revenue, roi, commission_per_buyer). "buyers", "margin", "avg_ticket"
# e "avg_cashback" não são produzidas com esses nomes pelo metrics.py e por
# isso não aparecem na tabela — não incluídas aqui para não descrever
# colunas que o leitor não vê no relatório.
METRIC_GLOSSARY = [
    (
        "GMV (Gross Merchandise Value)",
        "Soma do volume total de vendas geradas pelos usuários do grupo durante o período do teste.",
        "Indica o volume de negócios movimentado por cada grupo. Por si só não diz se o cashback "
        "está sendo eficiente — precisa ser olhado junto com Comissão e Cashback para entender se o "
        "volume maior também é mais rentável.",
    ),
    (
        "Comissão",
        "Soma do valor de comissão recebido pelo parceiro (Méliuz) sobre as vendas do grupo.",
        "É a receita bruta gerada pelas vendas, antes de descontar o custo do cashback pago aos "
        "usuários. Quanto maior, mais a operação do grupo está gerando de receita de origem.",
    ),
    (
        "Cashback (custo)",
        "Soma do valor de cashback pago aos usuários do grupo no período.",
        "Representa o custo do incentivo dado ao usuário. Aqui, menor é melhor — pesa o quanto o "
        "programa está \"gastando\" para gerar a Comissão e as vendas daquele grupo.",
    ),
    (
        "Receita líquida",
        "Comissão menos Cashback (commission − cashback).",
        "É o resultado financeiro real do grupo depois de pagar o cashback. É a métrica mais direta "
        "para saber se o grupo deu lucro ou prejuízo em termos absolutos (R$).",
    ),
    (
        "ROI (Retorno sobre o Investimento)",
        "Comissão dividida pelo Cashback pago (commission ÷ cashback). Quando não há cashback "
        "no grupo, o ROI é considerado 0.",
        "Mostra quanto de comissão é gerado para cada R$ 1,00 investido em cashback. Um ROI de 1,40, "
        "por exemplo, significa que cada real pago em cashback retornou R$ 1,40 em comissão. É a "
        "métrica chave para comparar a eficiência do investimento entre os grupos, independente do "
        "tamanho de cada grupo.",
    ),
    (
        "Comissão/comprador",
        "Comissão total dividida pelo número de compradores do grupo (ou pelo total de usuários, "
        "quando não há contagem de compradores disponível).",
        "Indica quanto de comissão, em média, cada comprador do grupo gerou. Ajuda a comparar a "
        "qualidade das vendas entre grupos de tamanhos diferentes, sem que o grupo maior pareça "
        "automaticamente \"melhor\" só por ter mais gente.",
    ),
]

def _metrics_table(metrics_df: pd.DataFrame, group_names: list, S: dict, W: float):
    header = [Paragraph("Métrica", S["th"])] + [
        Paragraph(f"<b>{n}</b>", ParagraphStyle(
            f"gh{i}", fontSize=8, textColor=GROUP_COLORS[i % len(GROUP_COLORS)],
            fontName="Helvetica-Bold", alignment=TA_RIGHT))
        for i, n in enumerate(group_names)
    ]
    rows = [header]

    mdf = metrics_df.set_index("group") if "group" in metrics_df.columns else metrics_df

    for label, key, fmt, lower_is_better in METRIC_DEFS:
        if key not in mdf.columns:
            continue
        vals = [mdf.at[n, key] if n in mdf.index else None for n in group_names]
        numeric = [v for v in vals if v is not None]
        if not numeric:
            continue
        best = min(numeric) if lower_is_better else max(numeric)

        row = [Paragraph(label, S["td_left"])]
        for i, (n, v) in enumerate(zip(group_names, vals)):
            if v is None:
                row.append(Paragraph("—", S["td"]))
                continue
            is_best = (v == best)
            style = ParagraphStyle(f"tv{i}", fontSize=9, fontName="Helvetica-Bold",
                alignment=TA_RIGHT,
                textColor=GROUP_COLORS[i % len(GROUP_COLORS)] if is_best else C_TEXT)
            row.append(Paragraph(fmt(v), style))
        rows.append(row)

    col_w = [4.5 * cm] + [(W - 4.5 * cm) / len(group_names)] * len(group_names)
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(_base_table_style())
    return t

# ── TABELA DE LIFTS ───────────────────────────────────────────────────────
LIFT_DEFS = [
    ("GMV",             "gmv",          False),
    ("Receita líquida", "net_revenue",  False),
    ("ROI",             "roi",          False),
    ("Margem",          "margin",       False),
    ("Ticket médio",    "avg_ticket",   False),
]

def _lifts_table(metrics_df: pd.DataFrame, group_names: list, control: str, S: dict, W: float):
    test_groups = [n for n in group_names if n != control]
    if not test_groups:
        return None

    mdf = metrics_df.set_index("group") if "group" in metrics_df.columns else metrics_df

    header = [Paragraph("Métrica", S["th"])] + [
        Paragraph(f"{g} vs {control}", S["th"]) for g in test_groups
    ]
    rows = [header]

    for label, key, invert in LIFT_DEFS:
        if key not in mdf.columns:
            continue
        ctrl_val = mdf.at[control, key] if control in mdf.index else None
        if ctrl_val is None or ctrl_val == 0:
            continue

        row = [Paragraph(label, S["td_left"])]
        for g in test_groups:
            test_val = mdf.at[g, key] if g in mdf.index else None
            if test_val is None:
                row.append(Paragraph("—", S["lift_neu"]))
                continue
            delta = (test_val - ctrl_val) / abs(ctrl_val)
            is_good = (delta >= 0) if not invert else (delta <= 0)
            st_key = "lift_pos" if is_good else "lift_neg"
            row.append(Paragraph(_lift_str(delta), S[st_key]))
        rows.append(row)

    col_w = [4.5 * cm] + [(W - 4.5 * cm) / len(test_groups)] * len(test_groups)
    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(_base_table_style())
    return t

# ── TABELA DO GLOSSÁRIO DE MÉTRICAS ───────────────────────────────────────
def _glossary_table(S: dict, W: float):
    rows = []
    for name, definition, usage in METRIC_GLOSSARY:
        cell = [
            Paragraph(name, S["glossary_title"]),
            Paragraph(f"<b>O que é:</b> {definition}", S["glossary_body"]),
            Paragraph(f"<b>Para que serve:</b> {usage}", S["glossary_body"]),
        ]
        rows.append([cell])

    t = Table(rows, colWidths=[W])
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_CARD, C_BG2]),
        ("GRID",           (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING",     (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 8),
        ("LEFTPADDING",    (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 10),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
    ]))
    return t

# ── GERADOR PRINCIPAL ─────────────────────────────────────────────────────
def generate_pdf_report(
    file_name: str,
    partner: str,
    period: str,
    metrics_df: pd.DataFrame,
    ranking: pd.DataFrame,
    ai_text: str,
) -> tuple[str, bytes]:
    """
    Gera o PDF em memória e salva em outputs/reports/.
    Retorna (caminho_do_arquivo, bytes_do_pdf).
    """
    out_dir = os.path.join("outputs", "reports")
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fname = f"relatorio_{ts}.pdf"
    path = os.path.join(out_dir, fname)

    # Monta em buffer de memória (para retornar bytes ao Streamlit)
    buf = io.BytesIO()
    _build_pdf(buf, file_name, partner, period, metrics_df, ranking, ai_text)
    pdf_bytes = buf.getvalue()

    # Salva em disco também
    with open(path, "wb") as f:
        f.write(pdf_bytes)

    return path, pdf_bytes


def _build_pdf(output, file_name, partner, period, metrics_df, ranking, ai_text):
    doc = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2.2*cm, bottomMargin=2*cm,
    )
    W = A4[0] - 4*cm
    S = _styles()

    # Grupos ordenados, controle primeiro
    group_names = sorted(metrics_df["group"].tolist() if "group" in metrics_df.columns else metrics_df.index.tolist())
    control = group_names[0] if group_names else "—"
    winner = ranking.iloc[0]["group"] if len(ranking) else control

    mdf = metrics_df.set_index("group") if "group" in metrics_df.columns else metrics_df
    winner_roi = _ratio(mdf.at[winner, "roi"]) if winner in mdf.index and "roi" in mdf.columns else "—"
    winner_net = _brl(mdf.at[winner, "net_revenue"]) if winner in mdf.index and "net_revenue" in mdf.columns else "—"
    days = int(mdf["days"].iloc[0]) if "days" in mdf.columns else "—"

    story = []

    # ── CABEÇALHO ─────────────────────────────────────────────────────────
    story.append(Paragraph("Relatório de Teste A/B — Cashback", S["title"]))
    story.append(Paragraph(
        f"Parceiro: <b>{partner}</b>  ·  Período: {period}  ·  "
        f"Grupos: {len(group_names)}  ·  Dias: {days}",
        S["subtitle"]
    ))
    story.append(HRFlowable(width=W, thickness=0.5, color=C_BORDER, spaceAfter=10))

    # ── BANNER DE RECOMENDAÇÃO ────────────────────────────────────────────
    rec_table = Table(
        [[Paragraph(f"Variante recomendada para escalar: <b>{winner}</b>  —  ROI {winner_roi}  |  Receita líquida {winner_net}", S["winner"])]],
        colWidths=[W]
    )
    rec_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), C_WINNER),
        ("BOX",          (0,0),(-1,-1), 0.8, C_GREEN),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING",  (0,0),(-1,-1), 14),
    ]))
    story.append(rec_table)
    story.append(Spacer(1, 14))

    # ── MÉTRICAS CONSOLIDADAS ─────────────────────────────────────────────
    story.append(Paragraph("Métricas consolidadas do período", S["section"]))
    story.append(_metrics_table(metrics_df, group_names, S, W))
    story.append(Spacer(1, 14))

    # ── LIFTS ─────────────────────────────────────────────────────────────
    lt = _lifts_table(metrics_df, group_names, control, S, W)
    if lt:
        story.append(Paragraph(f"Lifts vs grupo controle ({control})", S["section"]))
        story.append(lt)
        story.append(Spacer(1, 14))

    # ── RESUMO AI ─────────────────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=0.5, color=C_BORDER, spaceAfter=8))
    story.append(Paragraph("Resumo analítico", S["section"]))

    for line in ai_text.strip().split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 4))
            continue
        # Remove markdown bold/italic para não poluir o PDF
        line = line.replace("**", "").replace("__", "").replace("# ", "").replace("## ", "")
        prefix = "• " if line.startswith("-") or line.startswith("*") else ""
        clean = line.lstrip("-* ")
        story.append(Paragraph(f"{prefix}{clean}", S["body"]))

    story.append(Spacer(1, 10))

    # ── BOX DE DECISÃO ────────────────────────────────────────────────────
    decision_text = (
        f"<b>Decisão:</b> Escalar <b>{winner}</b> para 100% do tráfego. "
        f"ROI de {winner_roi} e receita líquida de {winner_net} no período analisado."
    )
    dec_table = Table([[Paragraph(decision_text, S["body"])]], colWidths=[W])
    dec_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), C_DEC),
        ("BOX",          (0,0),(-1,-1), 0.8, C_ACCENT),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING",  (0,0),(-1,-1), 14),
        ("RIGHTPADDING", (0,0),(-1,-1), 14),
    ]))
    story.append(dec_table)

    # ── GLOSSÁRIO DE MÉTRICAS (anexo, página nova) ────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Anexo — Glossário de Métricas", S["title"]))
    story.append(Paragraph(
        "O que significa e para que serve cada métrica calculada neste relatório.",
        S["subtitle"]
    ))
    story.append(HRFlowable(width=W, thickness=0.5, color=C_BORDER, spaceAfter=10))
    story.append(_glossary_table(S, W))

    # ── RODAPÉ ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width=W, thickness=0.3, color=C_BORDER, spaceAfter=4))
    story.append(Paragraph(
        f"Gerado automaticamente · Méliuz Growth · {partner} · {period}",
        S["footer"]
    ))

    doc.build(story)


# ── COMPATIBILIDADE: mantém generate_markdown_report apontando para PDF ──
def generate_markdown_report(file_name, partner, period, metrics_df, ranking, ai_text):
    """Alias para não quebrar imports existentes. Gera PDF e retorna o caminho."""
    path, _ = generate_pdf_report(file_name, partner, period, metrics_df, ranking, ai_text)
    return path